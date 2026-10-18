"""فاز ۲۶ - B24: داشبورد مدیر - دسترسی، KPI، روند روزانه، میانگین زمان بررسی"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.appointment import Appointment
from app.models.assessment import Assessment, AssessmentStatus, ReviewAction, FormVersion
from app.models.case import Case

from conftest import bearer, login


def test_admin_dashboard_access_matrix(env, client):
    # مدیر سازمان و مدیر سامانه مجاز
    for u in ("t_manager", "t_admin"):
        tok = login(client, u)
        r = client.get("/api/v1/reports/admin-dashboard", headers=bearer(tok))
        assert r.status_code == 200, (u, r.text)
    # سایر نقش‌ها ممنوع
    for u in ("t_counsa", "t_reception", "t_super", "t_appa"):
        tok = login(client, u)
        r = client.get("/api/v1/reports/admin-dashboard", headers=bearer(tok))
        assert r.status_code == 403, u
    # بدون توکن
    r = client.get("/api/v1/reports/admin-dashboard")
    assert r.status_code == 401


def test_admin_dashboard_shape(env, client):
    tok = login(client, "t_manager")
    r = client.get("/api/v1/reports/admin-dashboard", headers=bearer(tok))
    body = r.json()
    assert body["days"] == 30
    k = body["kpis"]
    assert k["cases_total"] >= 1  # پرونده تست conftest
    assert k["counselors_active"] >= 2
    assert "no_show_rate" in k and "avg_review_hours" in k
    assert len(body["trends"]["cases"]) == 30
    assert len(body["trends"]["bookings"]) == 30
    assert all("date" in row and "count" in row for row in body["trends"]["cases"])
    assert len(body["counselor_workload"]) >= 2


def test_admin_dashboard_days_param(env, client):
    tok = login(client, "t_manager")
    r = client.get("/api/v1/reports/admin-dashboard?days=7", headers=bearer(tok))
    body = r.json()
    assert body["days"] == 7
    assert len(body["trends"]["cases"]) == 7
    r2 = client.get("/api/v1/reports/admin-dashboard?days=0", headers=bearer(tok))
    assert r2.status_code == 422


def test_admin_dashboard_avg_review_hours(env, client):
    """KPI میانگین زمان بررسی: نهایی‌سازی ← اولین داوری."""
    db = env["db"]
    case: Case = env["case"]
    fv = db.query(FormVersion).filter(FormVersion.form_code == "RS-PS-04-01").first()
    if fv is None:
        pytest.skip("FormVersion RS-PS-04-01 ثبت نشده است")
    now = datetime.now(timezone.utc)
    a = Assessment(
        case_id=case.id, form_version_id=fv.id, status=AssessmentStatus.APPROVED,
        answers={}, finalized_at=now - timedelta(hours=3), finalized_by=env["admin"].id,
    )
    db.add(a)
    db.flush()
    db.add(ReviewAction(
        assessment_id=a.id, decision="approved", reviewer_user_id=env["supervisor"].id,
        created_at=now - timedelta(hours=1),
    ))
    db.commit()

    tok = login(client, "t_manager")
    r = client.get("/api/v1/reports/admin-dashboard", headers=bearer(tok))
    hours = r.json()["kpis"]["avg_review_hours"]
    assert hours is not None
    assert 1.5 <= hours <= 2.5, f"میانگین انتظار ≈۲ ساعت، دریافت {hours}"


def test_admin_dashboard_booking_kpis(env, client):
    tok = login(client, "t_manager")
    before = client.get("/api/v1/reports/admin-dashboard", headers=bearer(tok)).json()
    login(client, "t_reception")
    r = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "درخواست داشبورد",
        "mobile": "09121700000",
        "topic": "مشاوره فردی",
    })
    assert r.status_code == 201, r.text
    after = client.get("/api/v1/reports/admin-dashboard", headers=bearer(tok)).json()
    assert after["kpis"]["consultations_total"] == before["kpis"]["consultations_total"] + 1
    assert after["kpis"]["consultations_by_status"].get("new", 0) >= 1
