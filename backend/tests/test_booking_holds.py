"""فاز ۲۶ - B09: نگهداشت موقت اسلات (booking hold) - انقضا، تعارض، تأیید"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

import pytest

from app.api.v1 import public as public_mod
from app.core.booking import bookable_range, free_slots
from app.models.booking import SlotClaim, SlotClaimStatus
from app.models.consultation import ConsultationRequest
from app.services import booking_hold

from conftest import login


@pytest.fixture(autouse=True)
def _clear_rate_limiters():
    public_mod._req_ip.clear()
    public_mod._hold_ip.clear()
    yield
    public_mod._req_ip.clear()
    public_mod._hold_ip.clear()


def _first_free_slot(env, counselor):
    f, t = bookable_range()
    days = free_slots(env["db"], counselor.id, f, t)
    assert days, "اسلات آزاد یافت نشد"
    return days[0]["date"], days[0]["slots"][0]


def _create_hold(client, env, counselor=None):
    counselor = counselor or env["counselor_b"]
    _day, slot = _first_free_slot(env, counselor)
    r = client.post("/api/v1/public/booking-holds", json={
        "counselor_id": str(counselor.id),
        "start_at": slot["start_at"],
    })
    assert r.status_code == 201, r.text
    return r.json(), slot


def test_hold_created_and_slot_hidden(env, client):
    login(client, "t_reception")
    counselor = env["counselor_b"]
    data, slot = _create_hold(client, env, counselor)

    assert data["hold_token"]
    assert data["remaining_seconds"] > 0
    assert data["counselor"]["name"]

    # اسلات نگه‌داشته‌شده از فهرست آزاد حذف شود
    day = data["start_at"][:10]
    from datetime import date as date_type
    after = free_slots(env["db"], counselor.id, date_type.fromisoformat(day), date_type.fromisoformat(day))
    for d in after:
        assert all(s["start_at"] != slot["start_at"] for s in d["slots"])

    # GET وضعیت hold
    r = client.get(f"/api/v1/public/booking-holds/{data['hold_token']}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert body["remaining_seconds"] > 0


def test_second_hold_same_slot_conflict_409(env, client):
    login(client, "t_reception")
    counselor = env["counselor_b"]
    _day, slot = _first_free_slot(env, counselor)
    r1 = client.post("/api/v1/public/booking-holds", json={
        "counselor_id": str(counselor.id), "start_at": slot["start_at"]})
    assert r1.status_code == 201
    r2 = client.post("/api/v1/public/booking-holds", json={
        "counselor_id": str(counselor.id), "start_at": slot["start_at"]})
    assert r2.status_code == 409, r2.text


def test_hold_expires_and_slot_freed(env, client):
    """الزام B09: hold منقضی آزاد شود و اسلات در دسترس برگردد."""
    login(client, "t_reception")
    counselor = env["counselor_b"]
    data, slot = _create_hold(client, env, counselor)
    hold_id = data["hold_id"]
    # انقضای دستی hold
    env["db"].execute(
        update(SlotClaim)
        .where(SlotClaim.id == hold_id)
        .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    env["db"].commit()

    r = client.get(f"/api/v1/public/booking-holds/{data['hold_token']}")
    assert r.status_code == 200
    assert r.json()["status"] == "expired"
    assert r.json()["remaining_seconds"] == 0

    # اسلات دوباره آزاد است و hold جدید روی همان اسلات ممکن است
    from datetime import date as date_type
    day = data["start_at"][:10]
    after = free_slots(env["db"], counselor.id, date_type.fromisoformat(day), date_type.fromisoformat(day))
    found = any(
        s["start_at"] == slot["start_at"] for d in after for s in d["slots"]
    )
    assert found, "اسلات پس از انقضای hold باید آزاد می‌شد"
    r2 = client.post("/api/v1/public/booking-holds", json={
        "counselor_id": str(counselor.id), "start_at": slot["start_at"]})
    assert r2.status_code == 201, r2.text


def test_release_hold_frees_slot(env, client):
    login(client, "t_reception")
    counselor = env["counselor_b"]
    data, slot = _create_hold(client, env, counselor)
    r = client.delete(f"/api/v1/public/booking-holds/{data['hold_token']}")
    assert r.status_code == 204
    r2 = client.delete(f"/api/v1/public/booking-holds/{data['hold_token']}")
    assert r2.status_code == 204  # idempotent
    body = client.get(f"/api/v1/public/booking-holds/{data['hold_token']}").json()
    assert body["status"] == "released"
    # اسلات آزاد شد → hold جدید ممکن
    r3 = client.post("/api/v1/public/booking-holds", json={
        "counselor_id": str(counselor.id), "start_at": slot["start_at"]})
    assert r3.status_code == 201, r3.text


def test_confirm_booking_via_hold(env, client):
    """ثبت درخواست با hold_token موفق است و hold تأیید می‌شود."""
    login(client, "t_reception")
    counselor = env["counselor_b"]
    data, slot = _create_hold(client, env, counselor)
    payload = {
        "full_name": "مراجع نگهداشت",
        "mobile": "09121120000",
        "topic": "مشاوره فردی",
        "counselor_id": str(counselor.id),
        "start_at": slot["start_at"],
        "hold_token": data["hold_token"],
    }
    r = client.post("/api/v1/public/consultation-requests", json=payload)
    assert r.status_code == 201, r.text

    body = client.get(f"/api/v1/public/booking-holds/{data['hold_token']}").json()
    assert body["status"] == SlotClaimStatus.CONFIRMED

    # رزرو دوم بدون token روی همان اسلات: منع تعارض
    r2 = client.post("/api/v1/public/consultation-requests", json={**payload, "hold_token": None})
    assert r2.status_code == 409, r2.text


def test_booking_with_expired_hold_409(env, client):
    login(client, "t_reception")
    counselor = env["counselor_b"]
    data, slot = _create_hold(client, env, counselor)
    env["db"].execute(
        update(SlotClaim)
        .where(SlotClaim.id == data["hold_id"])
        .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    env["db"].commit()
    r = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "مراجع دیر",
        "mobile": "09121120001",
        "topic": "مشاوره فردی",
        "counselor_id": str(counselor.id),
        "hold_token": data["hold_token"],
    })
    assert r.status_code == 409, r.text


def test_hold_counselor_mismatch_409(env, client):
    login(client, "t_reception")
    data, slot = _create_hold(client, env, env["counselor_b"])
    r = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "مراجع ناسازگار",
        "mobile": "09121120002",
        "topic": "مشاوره فردی",
        "counselor_id": str(env["counselor_a"].id),  # مشاور دیگری
        "hold_token": data["hold_token"],
    })
    assert r.status_code == 409, r.text


def test_hold_unknown_token_404(env, client):
    r = client.get("/api/v1/public/booking-holds/does-not-exist")
    assert r.status_code == 404
