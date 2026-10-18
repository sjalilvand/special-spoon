"""فاز ۲۶ - B02-lite: کد یک‌بارمصرف (OTP) - انقضا، سقف تلاش، مصرف یک‌باره"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.models.otp import OtpChallenge

from conftest import login

settings = get_settings()

MOBILE = "09121300000"


@pytest.fixture(autouse=True)
def _raise_rate(monkeypatch):
    """سقف درخواست OTP برای تست‌ها بالا می‌رود؛ تست مخصوص rate-limit آن را پایین می‌آورد."""
    monkeypatch.setattr(settings, "otp_request_max", 50)
    yield


def _request(client: TestClient, mobile: str = MOBILE, purpose: str = "booking") -> dict:
    r = client.post("/api/v1/auth/otp/request", json={"mobile": mobile, "purpose": purpose})
    assert r.status_code == 200, r.text
    return r.json()


def _get_challenge(env, mobile: str = MOBILE) -> OtpChallenge:
    env["db"].expire_all()
    ch = (
        env["db"].query(OtpChallenge)
        .filter(OtpChallenge.mobile == mobile)
        .order_by(OtpChallenge.created_at.desc())
        .first()
    )
    assert ch is not None
    return ch


def test_otp_request_returns_dev_code_in_dev_mode(client):
    out = _request(client)
    assert out["status"] == "sent"
    assert out["expires_in"] == settings.otp_code_ttl_seconds
    assert len(out["dev_code"]) == 6 and out["dev_code"].isdigit()
    assert "dev_notice" in out


def test_otp_verify_wrong_then_right(client, env):
    _request(client)
    code = _get_challenge(env).code_hash  # فقط برای اطمینان از ثبت چالش
    r = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": "000000"})
    assert r.status_code == 400, r.text
    out = _request(client)
    code = out["dev_code"]
    r2 = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": code})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["status"] == "verified"
    assert body["verify_token"]


def test_otp_code_consumed_cannot_be_reused(client, env):
    """الزام B02: کد مصرف‌شده دوباره پذیرفته نشود."""
    code = _request(client)["dev_code"]
    r = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": code})
    assert r.status_code == 200
    r2 = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": code})
    assert r2.status_code == 400, r2.text


def test_otp_locked_after_max_attempts(client, env):
    code = _request(client)["dev_code"]
    wrong = "111111" if code != "111111" else "222222"
    for _ in range(settings.otp_max_attempts):
        r = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": wrong})
        assert r.status_code == 400
    # تلاش بعدی حتی با کد درست هم قفل است
    r = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": code})
    assert r.status_code == 429, r.text
    ch = _get_challenge(env)
    assert ch.consumed_at is not None


def test_otp_expired_code_rejected(client, env):
    code = _request(client)["dev_code"]
    ch = _get_challenge(env)
    ch.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    env["db"].commit()
    r = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": code})
    assert r.status_code == 400, r.text


def test_otp_request_rate_limit_429(client, env):
    monkey_free = None
    m = "09121400000"
    monkey_settings = settings
    saved = monkey_settings.otp_request_max
    try:
        monkey_settings.otp_request_max = 2
        _request(client, mobile=m)
        _request(client, mobile=m)
        r = client.post("/api/v1/auth/otp/request", json={"mobile": m, "purpose": "booking"})
        assert r.status_code == 429, r.text
    finally:
        monkey_settings.otp_request_max = saved


def test_new_request_invalidates_previous_code(client, env):
    c1 = _request(client)["dev_code"]
    _request(client)
    r = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": c1})
    assert r.status_code == 400, r.text


def test_booking_with_otp_token_single_use(client, env):
    """توکن اثبات تأیید موبایل یک‌بارمصرف است - B02/B02-lite."""
    from app.services.otp import consume_verify_token

    login(client, "t_reception")
    code = _request(client)["dev_code"]
    r = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": code})
    token = r.json()["verify_token"]

    payload = {
        "full_name": "مراجع OTP",
        "mobile": MOBILE,
        "topic": "مشاوره فردی",
    }
    r1 = client.post("/api/v1/public/consultation-requests", json={**payload, "otp_token": token})
    assert r1.status_code == 201, r1.text
    # استفاده دوباره از همان توکن → ۴۰۳
    r2 = client.post("/api/v1/public/consultation-requests", json={**payload, "otp_token": token})
    assert r2.status_code == 403, r2.text


def test_booking_otp_token_mobile_mismatch_403(client, env):
    code = _request(client)["dev_code"]
    r = client.post("/api/v1/auth/otp/verify", json={"mobile": MOBILE, "code": code})
    token = r.json()["verify_token"]
    r2 = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "مراجع ناهمخوان",
        "mobile": "09121500000",  # موبایل متفاوت
        "topic": "مشاوره فردی",
        "otp_token": token,
    })
    assert r2.status_code == 403, r2.text


def test_booking_without_otp_allowed_by_default(client, env):
    """پیش‌فرض BOOKING_REQUIRE_OTP=false است (تصمیم نهایی با D04)."""
    login(client, "t_reception")
    r = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "مراجع بدون OTP",
        "mobile": "09121600000",
        "topic": "مشاوره فردی",
    })
    assert r.status_code == 201, r.text


def test_otp_invalid_mobile_422(client):
    r = client.post("/api/v1/auth/otp/request", json={"mobile": "12345", "purpose": "booking"})
    assert r.status_code == 422
