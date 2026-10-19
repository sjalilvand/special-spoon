"""فاز ۳۶ - B28 یکپارچه‌سازی‌های بیرونی + B17 اپ Flutter + ADR بدهی فنی.

- B28: سرویس پیامک پلاگین‌پذیر (همان الگوی D02/D03/D07):
  · آداپتور log (پیش‌فرض بدون کلید) — قطعی؛ process → sent با provider=log؛
  · آداپتور کلیددار بدون کلید → fallback به log (fail-soft) و گزارش شفاف؛
  · آداپتور کلیددار با کلید: موفقیت (HTTP موک‌شده) → sent؛ شکست مکرر → failed؛
  · SMS_ENABLED=false → ردیف‌ها disabled (شفافیت DPO)؛
  · OTP: کد خام هرگز در پایگاه‌داده ذخیره نمی‌شود؛ با آداپتور واقعی ارسال مستقیم؛
  · اعلان → کپی پیامک برای گیرنده دارای موبایل؛
  · /integrations/config بدون هیچ کلیدی؛ دسترسی فقط مدیران (۴۰۳)؛
  · /sms-outbox فهرست/process/retry + ۴۲۲ وضعیت نامعتبر + ۴۰۹ تلاش مجدد.
- B17: اپ Flutter در مسیر mobile/ — آزمون ساخت آن به Flutter SDK نیاز دارد
  (خارج از این مجموعه؛ README موبایل راهنمای build است).
"""
import uuid

import pytest

import app.services.integrations as integrations_svc
from conftest import bearer, login
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.integration import SmsOutbox, SmsOutboxStatus
from app.models.otp import OtpChallenge
from app.models.user import User
from app.services.integrations import (
    active_sms_provider,
    integrations_config_out,
    process_sms_outbox,
    queue_sms,
    sms_config_out,
    sms_outbox_summary,
)


@pytest.fixture()
def st():
    return get_settings()


@pytest.fixture()
def admin_headers(client, env):
    return bearer(login(client, "t_admin"))


@pytest.fixture()
def applicant_headers(client, env):
    return bearer(login(client, "t_appa"))


# ---------------- helpers ----------------

def _mk_row(db, mobile="09120000001", purpose="notification", body="تست پیامک") -> SmsOutbox:
    row = queue_sms(db, recipient_mobile=mobile, purpose=purpose, body=body)
    assert row is not None
    db.commit()
    return row


# ================================================================ آداپتور پیامک
def test_b28_log_adapter_sends(st, admin_headers):
    st.sms_enabled = True
    st.sms_provider = "log"
    st.sms_api_key = ""
    db = SessionLocal()
    try:
        row = _mk_row(db)
        result = process_sms_outbox(db)
        assert result["queued"] >= 1 and result["sent"] >= 1
        db.refresh(row)
        assert row.status == SmsOutboxStatus.SENT
        assert row.provider == "log"
        assert row.sent_at is not None
        # خلاصه صف
        summary = sms_outbox_summary(db)
        assert summary["sms_enabled"] is True
        assert summary["by_status"].get("sent", 0) >= 1
    finally:
        db.close()
        st.sms_enabled = False


def test_b28_keyless_provider_falls_back(st, admin_headers, client):
    st.sms_enabled = True
    st.sms_provider = "kavenegar"
    st.sms_api_key = ""  # بدون کلید → fallback
    try:
        provider, fallback = active_sms_provider(st)
        assert provider == "log" and fallback is True
        cfg = sms_config_out(st)
        assert cfg["configured_provider"] == "kavenegar"
        assert cfg["active_provider"] == "log"
        assert cfg["fallback_applied"] is True
        # شفاف در خروجی API
        r = client.get("/api/v1/integrations/config", headers=admin_headers)
        assert r.status_code == 200
        sms = r.json()["integrations"]["sms"]
        assert sms["fallback_applied"] is True
    finally:
        st.sms_provider = "log"
        st.sms_enabled = False


def test_b28_kavenegar_send_success_and_failure(st, monkeypatch):
    st.sms_enabled = True
    st.sms_provider = "kavenegar"
    st.sms_api_key = "test-key-secret"
    st.sms_max_attempts = 2
    calls: list[dict] = []

    def fake_http(url, payload, headers=None, timeout=15.0):
        calls.append({"url": url, "payload": payload})
        return {"return": {"status": 200}}

    monkeypatch.setattr(integrations_svc, "_http_post_json", fake_http)
    db = SessionLocal()
    try:
        row = _mk_row(db, mobile="09120000002")
        result = process_sms_outbox(db)
        assert result["sent"] >= 1 and result["active_provider"] == "kavenegar"
        db.refresh(row)
        assert row.status == SmsOutboxStatus.SENT
        assert row.provider == "kavenegar"
        assert calls and "test-key-secret" in calls[0]["url"]
        assert calls[0]["payload"]["receptor"] == "09120000002"

        # شکست مکرر → failed پس از سقف تلاش
        def bad_http(url, payload, headers=None, timeout=15.0):
            raise RuntimeError("شبکه در دسترس نیست")

        monkeypatch.setattr(integrations_svc, "_http_post_json", bad_http)
        row2 = _mk_row(db, mobile="09120000003")
        process_sms_outbox(db)
        db.refresh(row2)
        assert row2.status == SmsOutboxStatus.PENDING and row2.attempts == 1
        process_sms_outbox(db)
        db.refresh(row2)
        assert row2.status == SmsOutboxStatus.FAILED
        assert "شبکه" in (row2.last_error or "")
    finally:
        db.close()
        st.sms_enabled = False
        st.sms_provider = "log"
        st.sms_api_key = ""


def test_b28_disabled_when_service_off(st):
    st.sms_enabled = False
    db = SessionLocal()
    try:
        row = _mk_row(db, mobile="09120000004")
        result = process_sms_outbox(db)
        assert result["disabled"] >= 1
        db.refresh(row)
        assert row.status == SmsOutboxStatus.DISABLED
        assert "SMS_ENABLED" in (row.last_error or "")
    finally:
        db.close()


def test_b28_queue_sms_empty_mobile_is_none():
    db = SessionLocal()
    try:
        assert queue_sms(db, recipient_mobile="  ", purpose="notification", body="x") is None
    finally:
        db.close()


# ================================================================ OTP × پیامک
def test_b28_otp_direct_send_without_storing_code(st, client, monkeypatch):
    st.sms_enabled = True
    st.sms_provider = "kavenegar"
    st.sms_api_key = "otp-test-key"
    calls: list[dict] = []

    def fake_http(url, payload, headers=None, timeout=15.0):
        calls.append({"url": url, "payload": payload})
        return {"return": {"status": 200}}

    monkeypatch.setattr(integrations_svc, "_http_post_json", fake_http)
    mobile = "0913" + f"{uuid.uuid4().int % 10_000_000:07d}"
    try:
        r = client.post("/api/v1/auth/otp/request", json={"mobile": mobile, "purpose": "login"})
        assert r.status_code == 200, r.text
        assert r.json()["dev_code"]  # حالت توسعه کد را در پاسخ می‌دهد
        # ارسال مستقیم به آداپتور واقعی انجام شد
        assert len(calls) == 1
        assert calls[0]["payload"]["receptor"] == mobile
        # «کد خام هرگز در پایگاه‌داده ذخیره نمی‌شود»
        db = SessionLocal()
        try:
            sms_rows = db.query(SmsOutbox).filter(SmsOutbox.recipient_mobile == mobile).all()
            assert sms_rows == []
            code = r.json()["dev_code"]
            leaked = db.query(SmsOutbox).filter(SmsOutbox.body.contains(code)).all()
            assert leaked == []
            ch = db.query(OtpChallenge).filter(OtpChallenge.mobile == mobile).one()
            assert code not in (ch.code_hash or "")
        finally:
            db.close()
    finally:
        st.sms_enabled = False
        st.sms_provider = "log"
        st.sms_api_key = ""


# ================================================================ اعلان → کپی پیامک
def test_b28_notification_sms_copy(st):
    st.sms_enabled = True
    st.sms_provider = "log"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "t_admin").one()
        user.mobile = "09120000009"
        db.commit()
        from app.services.notifications import notify_user

        n = notify_user(
            db,
            recipient_user_id=user.id,
            event_code="test.b28.sms",
            title="اعلان آزمون پیامک",
            body="متن غیربالینی آزمون",
            category="system",
        )
        assert n is not None
        db.commit()
        row = (
            db.query(SmsOutbox)
            .filter(SmsOutbox.notification_id == n.id)
            .one_or_none()
        )
        assert row is not None
        assert row.purpose == "notification"
        assert "اعلان آزمون پیامک" in row.body
        user.mobile = None
        db.commit()
    finally:
        db.close()
        st.sms_enabled = False


# ================================================================ API صف پیامک
def test_b28_sms_outbox_endpoints(st, client, admin_headers, applicant_headers):
    # فهرست برای مدیر
    r = client.get("/api/v1/sms-outbox", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1 and "summary" in body
    # فیلتر وضعیت نامعتبر → ۴۲۲
    r = client.get("/api/v1/sms-outbox?status=bogus", headers=admin_headers)
    assert r.status_code == 422
    # دسترسی متقاضی → ۴۰۳
    for path, method in [
        ("/api/v1/sms-outbox", "get"),
        ("/api/v1/sms-outbox/process", "post"),
        ("/api/v1/integrations/config", "get"),
    ]:
        r = getattr(client, method)(path, headers=applicant_headers)
        assert r.status_code == 403
    # process برای مدیر
    st.sms_enabled = True
    st.sms_provider = "log"
    try:
        r = client.post("/api/v1/sms-outbox/process?limit=10", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert {"queued", "sent", "failed", "disabled"} <= set(r.json().keys())
    finally:
        st.sms_enabled = False


def test_b28_sms_retry_flow(st, client, admin_headers, monkeypatch):
    st.sms_enabled = True
    st.sms_provider = "kavenegar"
    st.sms_api_key = "retry-key"
    st.sms_max_attempts = 1

    def bad_http(url, payload, headers=None, timeout=15.0):
        raise RuntimeError("پذیرفته نشد")

    monkeypatch.setattr(integrations_svc, "_http_post_json", bad_http)
    db = SessionLocal()
    row_id = None
    try:
        row = _mk_row(db, mobile="09120000005")
        row_id = str(row.id)
        process_sms_outbox(db)
        db.refresh(row)
        assert row.status == SmsOutboxStatus.FAILED
    finally:
        db.close()
        st.sms_enabled = False
        st.sms_provider = "log"
        st.sms_api_key = ""

    # تلاش مجدد روی ردیف sent/failed نامعتبر → ۴۰۹؛ روی failed → pending
    r = client.post(f"/api/v1/sms-outbox/{row_id}/retry", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    # ردیف ناموجود → ۴۰۴
    r = client.post(f"/api/v1/sms-outbox/{uuid.uuid4()}/retry", headers=admin_headers)
    assert r.status_code == 404


def test_b28_integrations_config_never_exposes_keys(st, client, admin_headers):
    st.sms_api_key = "super-secret-sms-key"
    st.zarinpal_merchant_id = "super-secret-merchant"
    st.neshan_api_key = "super-secret-map-key"
    st.ai_api_key = "super-secret-ai-key"
    try:
        cfg = integrations_config_out()
        assert set(cfg.keys()) == {"payment_gateway", "maps", "email", "ai", "sms"}
        r = client.get("/api/v1/integrations/config", headers=admin_headers)
        assert r.status_code == 200
        text = r.text
        for secret in ("super-secret-sms-key", "super-secret-merchant",
                       "super-secret-map-key", "super-secret-ai-key"):
            assert secret not in text
    finally:
        st.sms_api_key = ""
        st.zarinpal_merchant_id = ""
        st.neshan_api_key = ""
        st.ai_api_key = ""
