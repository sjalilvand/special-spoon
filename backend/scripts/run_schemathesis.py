"""فاز ۳۹ - آزمون قرارداد API با Schemathesis (ADR: پایداری قرارداد v1/v2).

اجرای خودکفا:
    DATABASE_URL=postgresql+psycopg://rosepsy:change_me@127.0.0.1:5432/rosepsy \
        python scripts/run_schemathesis.py

چه می‌کند:
- پایگاه قربانی «rosepsy_contract» را می‌سازد و مهاجرت‌های alembic را اعمال می‌کند؛
- یک مدیر آزمون می‌سازد (رمز تصادفی، فقط یک‌بار چاپ می‌شود)؛
- سرور FastAPI را روی 127.0.0.1:8100 بالا می‌آورد؛
- schemathesis CLI را با چک «not_a_server_error» علیه OpenAPI v1 اجرا می‌کند
  (نسخه v2 عمداً بیرون از OpenAPI است — ADR-03)؛
- گزارش junit در backend/schemathesis-report.xml + خلاصه در stdout؛
- در پایان سرور را متوقف و پایگاه قربانی را حذف می‌کند.

خروج: کد خروج schemathesis (صفر = قرارداد سالم).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time

CONTRACT_DB = "rosepsy_contract"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8100
BASE = f"http://{SERVER_HOST}:{SERVER_PORT}"

_MAX_EXAMPLES = os.environ.get("SCHEMATHESIS_MAX_EXAMPLES", "15")
_CONCURRENCY = os.environ.get("SCHEMATHESIS_CONCURRENCY", "4")


def _log(msg: str) -> None:
    print(f"[contract] {msg}", flush=True)


def main() -> int:
    from sqlalchemy import create_engine, text

    admin_url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://rosepsy:change_me@127.0.0.1:5432/rosepsy"
    )
    if not admin_url.startswith("postgresql"):
        # محیط ناسازگار (مثلاً متغیر DATABASE_URL ناآشنای پوسته) — پیش‌فرض محلی
        _log(f"DATABASE_URL نامعتبر ({admin_url[:40]}...) — استفاده از پیش‌فرض محلی")
        admin_url = "postgresql+psycopg://rosepsy:change_me@127.0.0.1:5432/rosepsy"
    base_admin = admin_url.rsplit("/", 1)[0]
    contract_url = f"{base_admin}/{CONTRACT_DB}"

    admin = create_engine(base_admin + "/postgres", isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {CONTRACT_DB} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {CONTRACT_DB}"))
    admin.dispose()
    _log(f"پایگاه قربانی ساخته شد: {CONTRACT_DB}")

    os.environ["DATABASE_URL"] = contract_url
    os.environ["ENVIRONMENT"] = "development"

    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, backend_root)

    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(backend_root, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", contract_url)
    command.upgrade(cfg, "head")
    _log("مهاجرت‌ها اعمال شد")

    # --- مدیر آزمون (الگوی create_admin.py) ---
    from app.core.security import generate_random_password, hash_password
    from app.db.session import SessionLocal
    from app.models.user import Role, User, UserStatus

    admin_password = generate_random_password()
    db = SessionLocal()
    u = User(
        username="contract_admin",
        display_name="مدیر آزمون قرارداد",
        status=UserStatus.ACTIVE,
        must_change_password=False,
    )
    u.password_hash = hash_password(admin_password)
    u.roles.append(db.get(Role, "SYSTEM_ADMIN"))
    db.add(u)
    db.commit()
    db.close()
    _log(f"مدیر آزمون ساخته شد — username=contract_admin password={admin_password}")

    # --- سرور ---
    import uvicorn

    from app.main import app

    server = uvicorn.Server(
        uvicorn.Config(app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning")
    )
    th = threading.Thread(target=server.run, daemon=True)
    th.start()

    deadline = time.time() + 30
    import httpx

    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/api/v1/health", timeout=2).status_code == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        _log("سرور بالا نیامد")
        return 2
    _log(f"سرور روی {BASE} آماده است")

    # --- توکن ---
    r = httpx.post(
        f"{BASE}/api/v2/auth/login",
        json={"username": "contract_admin", "password": admin_password},
        timeout=10,
    )
    token = r.json()["data"]["access_token"]
    _log("ورود v2 موفق — پاکت سالم است")

    # --- schemathesis CLI ---
    exe = shutil.which("schemathesis") or shutil.which("schemathesis3")
    if exe is None:
        exe = sys.executable
        cmd = [exe, "-m", "schemathesis.cli"]
    else:
        cmd = [exe]

    report_path = os.path.join(backend_root, "schemathesis-report.xml")
    cmd += [
        "run",
        f"{BASE}/api/v1/openapi.json",
        # FastAPI 0.115 OpenAPI 3.1 تولید می‌کند — پشتیبانی آزمایشی schemathesis 3.x
        "--experimental=openapi-3.1",
        "--checks",
        "not_a_server_error",
        "--hypothesis-max-examples",
        _MAX_EXAMPLES,
        "--workers",
        _CONCURRENCY,
        "--header",
        f"Authorization: Bearer {token}",
        "--request-timeout",
        "20000",
        "--junit-xml",
        report_path,
        "--hypothesis-suppress-health-check=too_slow,filter_too_much",
    ]
    _log("اجرای schemathesis: " + " ".join(cmd[1:]))
    try:
        proc = subprocess.run(cmd, check=False)
        rc = proc.returncode
    finally:
        server.should_exit = True
        th.join(timeout=10)
        eng = create_engine(base_admin + "/postgres", isolation_level="AUTOCOMMIT")
        with eng.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {CONTRACT_DB} WITH (FORCE)"))
        eng.dispose()
        _log("سرور متوقف و پایگاه قربانی حذف شد")

    _log(f"کد خروج schemathesis = {rc} (گزارش: {report_path})")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
