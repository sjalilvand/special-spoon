"""فاز ۲۷ — B39-plus (ClamAV واقعی + حذف متادیتا) + B12+ (ایمیل) + B41+ (گزارش DPO)

پوشش:
- قواعد پایه اسکنر: EICAR قرنطینه، فایل سالم تمیز
- پروتکل INSTREAM clamd با سرور جعلی TCP (مسیر واقعی اسکنر)
- آپلود EICAR از API → قرنطینه + مسدود شدن دانلود
- آپلود تصویر با EXIF → حذف فراداده (دانلود بدون EXIF)
- rescan با اسکنر جدید + endpoint وضعیت بسترهای اسکن
- اعلان دارای گیرنده ایمیل → ردیف صف؛ بدون SMTP → disabled
- ارسال موفق با SMTP جعلی → status sent + sent_at
- API صف ایمیل: دسترسی مدیر/دسترسی 403 متقاضی
- گزارش DPO: محتوا + دسترسی نقش‌ها (DPO مجاز، متقاضی 403)
"""
import io
import struct
import threading

from sqlalchemy import select

from conftest import PASSWORD, bearer, login
from app.core.security import hash_password

API = "/api/v1"

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def _h(client, who):
    return bearer(login(client, who))


def _mk_case(client, env, suffix):
    from datetime import date

    from app.models.case import Case, CaseAssignment
    from app.models.people import Applicant

    db = env["db"]
    app_row = Applicant(external_id=f"T-EXT-P27-{suffix}", first_name="متقاضی",
                        last_name=f"فاز۲۷{suffix}", status="active", record_source="manual", user_id=None)
    db.add(app_row)
    db.flush()
    case = Case(case_number=f"RS-P27-{suffix}", applicant_id=app_row.id,
                acceptance_date=date.today(),
                primary_counselor_id=env["counselor_a"].id, status="active", version=1)
    db.add(case)
    db.flush()
    db.add(CaseAssignment(case_id=case.id, counselor_id=env["counselor_a"].id, reason="تست فاز ۲۷"))
    db.commit()
    return case.id


# ---------- B39-plus: اسکنر ----------

def test_builtin_rules_eicar_and_clean():
    from app.services import av_scan

    ok = av_scan.scan_bytes("سلام.txt", "text/plain", "متن سالم".encode(), ["text/plain"])
    assert ok.status == "clean"
    bad = av_scan.scan_bytes("سلام.txt", "text/plain", EICAR, ["text/plain"])
    assert bad.status == "quarantined" and "EICAR" in bad.detail
    # امضای EICAR داخل محتوای بزرگ‌تر هم شناسایی شود
    hidden = av_scan.scan_bytes("a.txt", "text/plain", b"preamble" + EICAR + b"post", ["text/plain"])
    assert hidden.status == "quarantined"


def test_scanner_status_shape():
    from app.services import av_scan

    status = av_scan.scanner_status()
    assert set(status) >= {"clamd_configured", "clamd_reachable", "clamscan_available", "fallback"}
    assert status["fallback"] == "builtin-rules"


def test_clamd_instream_protocol(monkeypatch):
    """مسیر واقعی clamd: سرور جعلی INSTREAM که 'FOUND' برمی‌گرداند."""
    import socket as sock_mod

    from app.core.config import get_settings
    from app.services import av_scan

    received = bytearray()

    def serve(conn):
        try:
            # خواندن فرمان zINSTREAM\0 (۱۰ بایت شامل ته‌مقدار صفر) مطابق پروتکل clamd
            cmd = b""
            while len(cmd) < 10:
                part = conn.recv(10 - len(cmd))
                if not part:
                    return
                cmd += part
            if cmd != b"zINSTREAM\0":
                return
            while True:
                header = b""
                while len(header) < 4:
                    part = conn.recv(4 - len(header))
                    if not part:
                        return
                    header += part
                (n,) = struct.unpack("!L", header)
                if n == 0:
                    break
                data = b""
                while len(data) < n:
                    part = conn.recv(n - len(data))
                    if not part:
                        return
                    data += part
                received.extend(data)
            conn.sendall(b"stream: Rosepsy.Test-Virus FOUND\n")
        finally:
            conn.close()

    srv = sock_mod.socket()
    srv.setsockopt(sock_mod.SOL_SOCKET, sock_mod.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def accept():
        try:
            conn, _ = srv.accept()
            serve(conn)
        except OSError:
            pass

    t = threading.Thread(target=accept, daemon=True)
    t.start()

    settings = get_settings()
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "clamav_port", port)

    try:
        # محتوای غیر EICAR تا قواعد پایه راه نداده باشند و مسیر clamd اجرا شود
        result = av_scan.scan_bytes("doc.txt", "text/plain", b"payload-for-clamd", ["text/plain"])
        assert result.status == "quarantined"
        assert result.scanner == "clamav-clamd"
        assert "Rosepsy.Test-Virus" in result.detail
        assert bytes(received) == b"payload-for-clamd"
    finally:
        srv.close()


def test_upload_eicar_quarantined_and_download_blocked(client, env):
    case_id = _mk_case(client, env, "A1")
    r = client.post(f"{API}/files/upload",
                    files={"file": ("eicar.txt", EICAR, "text/plain")},
                    data={"case_id": str(case_id), "context": "case_document"},
                    headers=_h(client, "t_reception"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["scan_status"] == "quarantined"
    assert "EICAR" in body["scan_detail"]
    rt = client.post(f"{API}/files/{body['id']}/download-ticket", headers=_h(client, "t_reception"))
    assert rt.status_code == 403


def test_upload_clean_response_has_scanner_and_rescan(client, env):
    case_id = _mk_case(client, env, "A2")
    r = client.post(f"{API}/files/upload",
                    files={"file": ("یادداشت.txt", "محتوای سالم پرونده".encode(), "text/plain")},
                    data={"case_id": str(case_id), "context": "case_document"},
                    headers=_h(client, "t_reception"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["scan_status"] == "clean"
    assert body["scanner"] in ("clamav-clamd", "clamav-clamscan", "builtin-rules")
    # rescan مسئول فنی با اسکنر جدید
    rs = client.post(f"{API}/files/{body['id']}/rescan", headers=_h(client, "t_super"))
    assert rs.status_code == 200, rs.text
    assert rs.json()["scan_status"] == "clean"
    assert "scanner" in rs.json()


def test_scan_backend_status_endpoint(client, env):
    r = client.get(f"{API}/files/scan-status", headers=_h(client, "t_manager"))
    assert r.status_code == 200, r.text
    assert r.json()["fallback"] == "builtin-rules"
    # متقاضی مجاز نیست
    ra = client.get(f"{API}/files/scan-status", headers=_h(client, "t_appa"))
    assert ra.status_code == 403


def test_image_metadata_stripped_on_upload(client, env):
    from PIL import Image

    case_id = _mk_case(client, env, "A3")
    img = Image.new("RGB", (16, 12), (180, 40, 90))
    exif = img.getexif()
    exif[0x010F] = "ClinicTestCam"  # Make
    exif[0x0110] = "Model-X"        # Model
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    raw = buf.getvalue()

    r = client.post(f"{API}/files/upload",
                    files={"file": ("عکس.jpg", raw, "image/jpeg")},
                    data={"case_id": str(case_id), "context": "case_document"},
                    headers=_h(client, "t_reception"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert "فراداده" in (body["scan_detail"] or "")

    rt = client.post(f"{API}/files/{body['id']}/download-ticket", headers=_h(client, "t_reception"))
    assert rt.status_code == 200
    rd = client.get(f"{API}/files/{body['id']}/download", params={"ticket": rt.json()["ticket"]})
    assert rd.status_code == 200
    got = Image.open(io.BytesIO(rd.content))
    assert not got.getexif()  # EXIF حذف شده است


# ---------- B12+: صف ایمیل ----------

def _ensure_email(db, user, email):
    if user.email != email:
        user.email = email
        db.commit()


def test_notification_queues_email_then_disabled_without_smtp(client, env):
    from sqlalchemy import select

    from app.models.email_outbox import EmailOutbox
    from app.services.email_outbox import process_outbox
    from app.services.notifications import notify_user

    db = env["db"]
    _ensure_email(db, env["admin"], "admin-p27@test.local")
    n = notify_user(db, recipient_user_id=env["admin"].id,
                    event_code="test.email", title="تست خروجی ایمیل", body="متن آزمون اعلان")
    assert n is not None
    row = db.scalar(select(EmailOutbox).where(EmailOutbox.notification_id == n.id))
    assert row is not None
    assert row.recipient_email == "admin-p27@test.local"
    assert row.status == "pending"
    assert "Rosepsy" in row.body_text

    # بدون SMTP (پیش‌فرض تست): ردیف disabled می‌شود نه گم‌شدن
    result = process_outbox(db)
    db.refresh(row)
    assert row.status == "disabled"
    assert result["disabled"] >= 1


def test_notification_without_email_no_queue_row(client, env):
    from sqlalchemy import select

    from app.models.email_outbox import EmailOutbox
    from app.services.notifications import notify_user

    db = env["db"]
    _ensure_email(db, env["reception"], None)
    before = db.scalar(
        select(EmailOutbox.recipient_email).where(EmailOutbox.recipient_email == "none@test.local"))
    n = notify_user(db, recipient_user_id=env["reception"].id, event_code="test.noemail", title="بدون ایمیل")
    assert n is not None
    after = db.scalar(
        select(EmailOutbox.recipient_email).where(EmailOutbox.recipient_email == "none@test.local"))
    assert before is None and after is None


def test_email_sent_via_fake_smtp(client, env, monkeypatch):
    import app.services.email_outbox as eo
    from sqlalchemy import select

    from app.models.email_outbox import EmailOutbox
    from app.services.notifications import notify_user

    sent = []

    def fake_send(settings, to, subject, body):
        sent.append((to, subject, body))

    monkeypatch.setattr(eo, "_smtp_send", fake_send)
    settings = eo.get_settings()
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.test.local")

    db = env["db"]
    _ensure_email(db, env["manager"], "manager-p27@test.local")
    n = notify_user(db, recipient_user_id=env["manager"].id,
                    event_code="test.sent", title="اعلان ارسال‌شدنی")
    row = db.scalar(select(EmailOutbox).where(EmailOutbox.notification_id == n.id))
    assert row is not None and row.status == "pending"

    result = eo.process_outbox(db)
    db.refresh(row)
    assert row.status == "sent"
    assert row.sent_at is not None
    assert result["sent"] >= 1
    assert any(to == "manager-p27@test.local" and "اعلان ارسال‌شدنی" in subject for to, subject, _ in sent)


def test_email_outbox_api(client, env):
    r = client.get(f"{API}/email-outbox", headers=_h(client, "t_admin"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert {"items", "total", "summary"} <= set(data)
    assert "smtp_enabled" in data["summary"]
    # پردازش صف توسط مدیر سازمان
    rp = client.post(f"{API}/email-outbox/process", headers=_h(client, "t_manager"))
    assert rp.status_code == 200, rp.text
    assert set(rp.json()) >= {"queued", "sent", "failed", "disabled"}
    # متقاضی → 403
    ra = client.get(f"{API}/email-outbox", headers=_h(client, "t_appa"))
    assert ra.status_code == 403
    rb = client.post(f"{API}/email-outbox/process", headers=_h(client, "t_appa"))
    assert rb.status_code == 403


# ---------- B41+: گزارش DPO ----------

def _seed_consent(db, env):
    from datetime import date

    from app.models.case import Consent
    from app.models.consent import ConsentVersion

    cv = db.scalar(select(ConsentVersion).where(ConsentVersion.kind == "treatment"))
    if cv is None:
        cv = ConsentVersion(kind="treatment", version=1, title="رضایت درمان آزمون",
                            body="متن کامل رضایت‌نامه درمان برای آزمون فاز ۲۷")
        db.add(cv)
        db.flush()
    existing = db.scalar(select(Consent).where(Consent.case_id == env["case"].id, Consent.kind == "treatment"))
    if existing is None:
        db.add(Consent(case_id=env["case"].id, version=cv.version, status="granted",
                       consent_date=date.today(), kind="treatment", consent_version_id=cv.id,
                       recorded_by=env["admin"].id))
        db.commit()
    return cv


def test_dpo_report_content_and_access(client, env):
    from app.models.consent import ConsentVersion

    db = env["db"]
    _seed_consent(db, env)
    # نسخه رضایت حتماً ثبت شده باشد
    assert db.scalar(select(ConsentVersion).where(ConsentVersion.kind == "treatment")) is not None

    r = client.get(f"{API}/reports/dpo?days=30", headers=_h(client, "t_manager"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert {"generated_at", "consents", "access", "files", "email_outbox", "accounts"} <= set(data)
    assert data["consents"]["by_kind"].get("treatment", {}).get("granted_active", 0) >= 1
    assert "auth.login" in data["access"]["tracked_actions"]
    assert "scan_backends" in data["files"]

    # متقاضی → 403
    ra = client.get(f"{API}/reports/dpo", headers=_h(client, "t_appa"))
    assert ra.status_code == 403
    # مشاور → 403 (خارج از نقش‌های مجاز)
    rc = client.get(f"{API}/reports/dpo", headers=_h(client, "t_counsa"))
    assert rc.status_code == 403


def test_dpo_role_user_can_access(client, env):
    from sqlalchemy import select

    from app.models.user import Role, User

    db = env["db"]
    dpo = db.scalar(select(User).where(User.username == "t_dpo"))
    if dpo is None:
        dpo = User(username="t_dpo", display_name="حسابرس حفاظت داده", status="active",
                   must_change_password=False)
        dpo.password_hash = hash_password(PASSWORD)
        dpo.roles.append(db.get(Role, "DPO"))
        db.add(dpo)
        db.commit()
    r = client.get(f"{API}/reports/dpo", headers=_h(client, "t_dpo"))
    assert r.status_code == 200, r.text
    assert "consents" in r.json()
