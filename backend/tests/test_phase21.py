"""فاز ۲۱ - تست رزرو آنلاین اسلات از سایت عمومی"""
from datetime import datetime, timedelta, timezone

from app.core.booking import CLOSED_WEEKDAYS, bookable_range, free_slots
from app.models.consultation import ConsultationRequest

from conftest import login


def test_bookable_range_starts_tomorrow(env):
    f, t = bookable_range()
    today = datetime.now(timezone.utc).date()
    assert f == today + timedelta(days=1)
    assert (t - f).days <= 30


def test_friday_has_no_slots(env):
    f, t = bookable_range()
    d = f
    found = False
    while d <= t:
        if d.weekday() in CLOSED_WEEKDAYS:
            found = True
            assert free_slots(env["db"], env["counselor_a"].id, d, d) == []
            break
        d += timedelta(days=1)
    assert found, "در ۳۰ روز آینده جمعه‌ای یافت نشد"


def test_thursday_half_day(env):
    f, t = bookable_range()
    d = f
    found = False
    while d <= t:
        if d.weekday() == 3:
            found = True
            days = free_slots(env["db"], env["counselor_a"].id, d, d)
            if days:
                assert len(days[0]["slots"]) <= 4
            break
        d += timedelta(days=1)
    assert found


def test_double_booking_conflict_409(env, client):
    login(client, "t_reception")
    f, t = bookable_range()
    days = free_slots(env["db"], env["counselor_b"].id, f, t)
    assert days, "اسلات آزاد یافت نشد"
    slot = days[0]["slots"][0]
    payload = {
        "full_name": "مراجع رزرو تست",
        "mobile": "09121110000",
        "topic": "مشاوره فردی",
        "counselor_id": str(env["counselor_b"].id),
        "start_at": slot["start_at"],
    }
    r1 = client.post("/api/v1/public/consultation-requests", json=payload)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/v1/public/consultation-requests", json=payload)
    assert r2.status_code == 409, r2.text


def test_booked_slot_removed_from_free_list(env, client):
    login(client, "t_reception")
    f, t = bookable_range()
    days = free_slots(env["db"], env["counselor_b"].id, f, t)
    day = days[0]
    slot = day["slots"][1]
    payload = {
        "full_name": "مراجع دوم",
        "mobile": "09121110001",
        "topic": "مشاوره فردی",
        "counselor_id": str(env["counselor_b"].id),
        "start_at": slot["start_at"],
    }
    r = client.post("/api/v1/public/consultation-requests", json=payload)
    assert r.status_code == 201, r.text
    after = free_slots(env["db"], env["counselor_b"].id, day["date"], day["date"])
    for d2 in after:
        assert all(s2["start_at"] != slot["start_at"] for s2 in d2["slots"])


def test_invalid_slot_rejected_409(env, client):
    login(client, "t_reception")
    payload = {
        "full_name": "مراجع سوم",
        "mobile": "09121110002",
        "topic": "مشاوره فردی",
        "counselor_id": str(env["counselor_b"].id),
        "start_at": "2024-01-01T03:00:00+00:00",
    }
    r = client.post("/api/v1/public/consultation-requests", json=payload)
    assert r.status_code == 409, r.text


def test_booking_row_has_counselor_and_time(env):
    rows = (
        env["db"]
        .query(ConsultationRequest)
        .filter(ConsultationRequest.preferred_start_at.isnot(None))
        .all()
    )
    assert len(rows) >= 2
    for row in rows:
        assert row.preferred_counselor_id is not None
        assert row.preferred_slot