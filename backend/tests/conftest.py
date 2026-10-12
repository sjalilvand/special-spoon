"""فاز ۹ - بند ۱۷ سند: پایگاه داده ایزوله rosepsy_test + داده آزمایشی"""
import os
import time
from datetime import date, datetime, timedelta, timezone

_original_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://rosepsy:change_me@db:5432/rosepsy",
)
TEST_DB = "rosepsy_test"
TEST_URL = _original_url.rsplit("/", 1)[0] + "/" + TEST_DB

from sqlalchemy import create_engine, text  # noqa: E402

_admin = create_engine(_original_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
for _i in range(60):
    try:
        with _admin.connect() as _c:
            _c.execute(text("SELECT 1"))
        break
    except Exception:
        time.sleep(1)

with _admin.connect() as _c:
    _c.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
    _c.execute(text(f"CREATE DATABASE {TEST_DB}"))

os.environ["DATABASE_URL"] = TEST_URL

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

_cfg = Config(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini"))
_cfg.set_main_option("sqlalchemy.url", TEST_URL)
command.upgrade(_cfg, "head")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.appointment import Appointment  # noqa: E402
from app.models.case import Case, CaseAssignment  # noqa: E402
from app.models.people import Applicant, Counselor  # noqa: E402
from app.models.user import Role, User, UserStatus  # noqa: E402

PASSWORD = "TestPass!1234"


def _mk_user(db, username, roles, status=UserStatus.ACTIVE, password=PASSWORD):
    u = User(username=username, display_name=username, status=status, must_change_password=False)
    if password:
        u.password_hash = hash_password(password)
    for r in roles:
        u.roles.append(db.get(Role, r))
    db.add(u)
    db.flush()
    return u


@pytest.fixture(scope="session")
def env():
    db = SessionLocal()
    data = {}
    data["admin"] = _mk_user(db, "t_admin", ["SYSTEM_ADMIN"])
    data["manager"] = _mk_user(db, "t_manager", ["ORG_MANAGER"])
    data["reception"] = _mk_user(db, "t_reception", ["RECEPTION"])
    ua = _mk_user(db, "t_counsa", ["COUNSELOR"])
    ub = _mk_user(db, "t_counsb", ["COUNSELOR"])
    data["supervisor"] = _mk_user(db, "t_super", ["TECHNICAL_SUPERVISOR"])
    app_user = _mk_user(db, "t_appa", ["APPLICANT"])
    dis = _mk_user(db, "t_disabled", ["RECEPTION"])
    dis.status = UserStatus.DISABLED
    data["pending_user"] = _mk_user(db, "t_pending", ["RECEPTION"], status=UserStatus.PENDING, password=None)

    cA = Counselor(counselor_code="TC-A", first_name="آزمون", last_name="مشاورالف",
                   status="active", user_id=ua.id)
    cB = Counselor(counselor_code="TC-B", first_name="آزمون", last_name="مشاوریب",
                   status="active", user_id=ub.id)
    db.add_all([cA, cB])
    db.flush()

    aA = Applicant(external_id="T-EXT-A", employee_code="9001", national_id="0012345678",
                   first_name="متقاضی", last_name="آزمونالف", status="active",
                   record_source="manual", user_id=app_user.id)
    db.add(aA)
    db.flush()

    case = Case(case_number="RS-TEST-000001", applicant_id=aA.id, acceptance_date=date.today(),
                primary_counselor_id=cA.id, status="active", version=1)
    db.add(case)
    db.flush()
    db.add(CaseAssignment(case_id=case.id, counselor_id=cA.id, reason="تخصیص آزمون"))
    db.add(Appointment(case_id=case.id, counselor_id=cA.id,
                       scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
                       status="scheduled"))
    data["counselor_a"] = cA
    data["counselor_b"] = cB
    data["applicant_a"] = aA
    data["case"] = case
    db.commit()
    yield data
    db.close()


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def login(client, username, password=PASSWORD):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}
