"""فاز ۳۴ - B33-B36 + B21-plus سند جامع: محتوا/دوره/آزمون/گواهی + صورتحساب سازمان.

- B33: محتوای draft عمومی نیست؛ محتوای زیر دسته غیرفعال عمومی نیست؛ slug یکتا.
- B34: ثبت‌نام رایگان فوری فعال؛ ثبت‌نام تکراری ۴۰۹؛ ظرفیت تکمیل ۴۰۹؛
  دوره پولی → سفارش kind='course' → پس از پرداخت sandbox ثبت‌نام فعال می‌شود.
- B35: «پاسخ صحیح هرگز به کلاینت نمی‌رود»؛ نمره‌دهی سمت سرور دقیق؛
  سقف تلاش ۴۰۹؛ آزمون دوره‌ای بدون ثبت‌نام ۴۰۳؛ آزمون پولی بدون پرداخت ۴۰۳؛
  خرید آزمون (kind='exam') پس از پرداخت دسترسی می‌دهد؛ خرید تکراری ۴۰۹.
- B36: قبولی → گواهی خودکار شماره‌دار؛ تکراری صادر نمی‌شود؛ تکمیل دوره →
  گواهی دوره؛ verify عمومی؛ ابطال → verify نامعتبر.
- B21-plus: صورتحساب دوره‌ای (snapshot بازه، سفارش تکراری حذف)؛ تسویه با
  سند متوازن Dr 1101/Cr 1104؛ تسویه مجدد ۴۰۹؛ گزارش مطالبات outstanding.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import bearer, login


@pytest.fixture()
def manager_headers(client, env):
    return bearer(login(client, "t_manager"))


@pytest.fixture()
def applicant_headers(client, env):
    return bearer(login(client, "t_appa"))


# ---------------- helpers ----------------

def _mk_topic(client, headers, name=None, slug=None, **kw) -> dict:
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/api/v1/topics", headers=headers, json={
        "name": name or f"دسته ف۳۴ {suffix}", "slug": slug or f"topic-{suffix}", **kw,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _mk_content(client, headers, topic_id=None, slug=None, status=None) -> dict:
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/api/v1/contents", headers=headers, json={
        "slug": slug or f"content-{suffix}",
        "title": f"محتوای فاز ۳۴ {suffix}",
        "summary": "خلاصه محتوای آزمون",
        "body": "متن کامل محتوای آزمون فاز ۳۴",
        "topic_id": topic_id,
    })
    assert r.status_code == 201, r.text
    content = r.json()
    if status:
        r = client.patch(f"/api/v1/contents/{content['id']}", headers=headers,
                         json={"status": status})
        assert r.status_code == 200, r.text
        content = r.json()
    return content


def _mk_course(client, headers, topic_id=None, price=0, capacity=None, status=None) -> dict:
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/api/v1/courses", headers=headers, json={
        "slug": f"course-{suffix}",
        "title": f"دوره فاز ۳۴ {suffix}",
        "summary": "دوره آزمایشی",
        "topic_id": topic_id,
        "price_amount": price,
        "capacity": capacity,
    })
    assert r.status_code == 201, r.text
    course = r.json()
    if status:
        r = client.patch(f"/api/v1/courses/{course['id']}", headers=headers,
                         json={"status": status})
        assert r.status_code == 200, r.text
        course = r.json()
    return course


def _mk_exam(client, headers, topic_id=None, course_id=None, price=0,
             max_attempts=1, pass_percent=60, status=None) -> dict:
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/api/v1/exams", headers=headers, json={
        "slug": f"exam-{suffix}",
        "title": f"آزمون فاز ۳۴ {suffix}",
        "topic_id": topic_id,
        "course_id": course_id,
        "price_amount": price,
        "max_attempts": max_attempts,
        "pass_percent": pass_percent,
    })
    assert r.status_code == 201, r.text
    exam = r.json()
    if status:
        r = client.patch(f"/api/v1/exams/{exam['id']}", headers=headers,
                         json={"status": status})
        assert r.status_code == 200, r.text
        exam = r.json()
    return exam


def _add_question(client, headers, exam_id, correct=1, points=1) -> dict:
    r = client.post(f"/api/v1/exams/{exam_id}/questions", headers=headers, json={
        "prompt": "پایتخت ایران کدام است؟",
        "options": ["اصفهان", "تهران", "شیراز", "تبریز"],
        "correct_index": correct,
        "points": points,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _mk_org_contract_applicant_order(client, manager, amount=1_000_000, percent=40) -> tuple[dict, dict, dict]:
    """سازمان + قرارداد فعال + متقاضی منتسب + سفارش/نوبت پرداخت‌شده با سهم سازمان."""
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/api/v1/organizations", headers=manager, json={
        "name": f"سازمان ف۳۴ {suffix}", "slug": f"org34-{suffix}",
    })
    assert r.status_code == 201, r.text
    org = r.json()
    r = client.post(f"/api/v1/organizations/{org['id']}/contracts", headers=manager, json={
        "title": "قرارداد ف۳۴", "coverage_percent": percent,
        "valid_from": str(date.today() - timedelta(days=1)),
        "valid_to": str(date.today() + timedelta(days=60)),
        "service_ids": [],
    })
    assert r.status_code == 201, r.text
    contract = r.json()
    r = client.patch(f"/api/v1/contracts/{contract['id']}", headers=manager,
                     json={"status": "active"})
    assert r.status_code == 200, r.text

    applicant_id = client.get("/api/v1/applicants?page_size=1", headers=manager).json()["items"][0]["id"]
    r = client.patch(f"/api/v1/applicants/{applicant_id}", headers=manager,
                     json={"organization_id": org["id"]})
    assert r.status_code == 200, r.text

    r = client.post("/api/v1/specialties", headers=manager, json={"name": f"تخصص ف۳۴ {suffix}"})
    sp = r.json()
    r = client.post("/api/v1/services", headers=manager, json={
        "specialty_id": sp["id"], "title": f"خدمت ف۳۴ {suffix}", "duration_minutes": 45,
    })
    svc = r.json()
    on = date.today() - timedelta(days=1)
    r = client.post("/api/v1/tariffs", headers=manager, json={
        "service_id": svc["id"], "amount": amount,
        "valid_from": str(on), "valid_to": str(on + timedelta(days=200)),
    })
    assert r.status_code == 201, r.text

    case_id = client.get("/api/v1/cases?page_size=1", headers=manager).json()["items"][0]["id"]
    sched = datetime.combine(date.today() + timedelta(days=20),
                             datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
    r = client.post("/api/v1/appointments", headers=manager, json={
        "case_id": case_id, "service_id": svc["id"], "scheduled_at": sched.isoformat(),
    })
    assert r.status_code == 201, r.text
    appt = r.json()
    r = client.post("/api/v1/orders", headers=manager, json={"appointment_id": appt["id"]})
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["org_share_amount"] is not None, "سهم سازمان باید snapshot شود"
    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=manager,
                    json={"gateway": "sandbox"})
    assert r.status_code == 201, r.text
    pay_start = r.json()
    r = client.post(f"/api/v1/payments/{pay_start['authority']}/verify", headers=manager)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    return org, contract, order


# ================================================================ B33
def test_b33_content_draft_hidden_public(client, env, manager_headers):
    c = _mk_content(client, manager_headers)  # draft
    r = client.get("/api/v1/public/contents")
    assert r.status_code == 200
    assert all(item["id"] != c["id"] for item in r.json()["items"])
    r = client.get(f"/api/v1/public/contents/{c['slug']}")
    assert r.status_code == 404


def test_b33_content_published_visible_and_topic_gate(client, env, manager_headers):
    topic = _mk_topic(client, manager_headers)
    c = _mk_content(client, manager_headers, topic_id=topic["id"], status="published")
    r = client.get("/api/v1/public/contents")
    items = [i for i in r.json()["items"] if i["id"] == c["id"]]
    assert len(items) == 1 and items[0]["topic_name"] == topic["name"]
    # دسته غیرفعال → محتوا عمومی نیست («دسته غیرفعال در صفحات عمومی نشان داده نشود»)
    r = client.patch(f"/api/v1/topics/{topic['id']}", headers=manager_headers,
                     json={"is_active": False})
    assert r.status_code == 200
    r = client.get("/api/v1/public/contents")
    assert all(item["id"] != c["id"] for item in r.json()["items"])
    r = client.get(f"/api/v1/public/contents/{c['slug']}")
    assert r.status_code == 404


def test_b33_content_slug_dup_409(client, env, manager_headers):
    c = _mk_content(client, manager_headers)
    r = client.post("/api/v1/contents", headers=manager_headers, json={
        "slug": c["slug"], "title": "تکراری",
    })
    assert r.status_code == 409


# ================================================================ B34
def test_b34_free_course_enroll_immediate_active(client, env, manager_headers, applicant_headers):
    course = _mk_course(client, manager_headers, status="published")
    r = client.post(f"/api/v1/public/courses/{course['slug']}/enroll", headers=applicant_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enrollment"]["status"] == "active"
    assert body["order"] is None
    # تکراری ۴۰۹
    r = client.post(f"/api/v1/public/courses/{course['slug']}/enroll", headers=applicant_headers)
    assert r.status_code == 409


def test_b34_capacity_full_409(client, env, manager_headers, applicant_headers):
    course = _mk_course(client, manager_headers, capacity=1, status="published")
    other = bearer(login(client, "t_reception"))
    r = client.post(f"/api/v1/public/courses/{course['slug']}/enroll", headers=other)
    assert r.status_code == 200
    r = client.post(f"/api/v1/public/courses/{course['slug']}/enroll", headers=applicant_headers)
    assert r.status_code == 409
    assert "ظرفیت" in r.json()["detail"]


def test_b34_paid_course_flow_order_then_activation(client, env, manager_headers, applicant_headers):
    course = _mk_course(client, manager_headers, price=800000, status="published")
    r = client.post(f"/api/v1/public/courses/{course['slug']}/enroll", headers=applicant_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enrollment"]["status"] == "pending"
    order = body["order"]
    assert order["kind"] == "course" and order["amount"] == 800000
    # ثبت‌نام فعال نیست تا پیش از پرداخت
    r = client.post("/api/v1/exams", headers=manager_headers, json={
        "slug": f"gate-{uuid.uuid4().hex[:8]}", "title": "کنترل",
    })
    # پرداخت sandbox
    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=manager_headers,
                    json={"gateway": "sandbox"})
    assert r.status_code == 201, r.text
    authority = r.json()["authority"]
    r = client.post(f"/api/v1/payments/{authority}/verify", headers=manager_headers)
    assert r.status_code == 200 and r.json()["ok"] is True
    # ثبت‌نام باید فعال شده باشد (اثر جانبی verify)
    r = client.get(f"/api/v1/courses/{course['id']}/enrollments", headers=manager_headers)
    assert r.status_code == 200
    enr = [e for e in r.json()["items"] if e["order_id"] == order["id"]]
    assert len(enr) == 1 and enr[0]["status"] == "active"


def test_b34_sessions_and_course_delete_guard(client, env, manager_headers):
    course = _mk_course(client, manager_headers)
    when = datetime.now(timezone.utc) + timedelta(days=7)
    r = client.post(f"/api/v1/courses/{course['id']}/sessions", headers=manager_headers, json={
        "title": "جلسه اول", "session_date": when.isoformat(), "duration_minutes": 90,
    })
    assert r.status_code == 201, r.text
    # دوره دارای جلسه حذف نمی‌شود (409)
    r = client.delete(f"/api/v1/courses/{course['id']}", headers=manager_headers)
    assert r.status_code == 409
    # پس از حذف جلسه، حذف دوره آزاد است
    r = client.get("/api/v1/courses", headers=manager_headers,
                   params={"include_unpublished": "true"})
    sessions = [c for c in r.json()["items"] if c["id"] == course["id"]][0]["sessions"]
    r = client.delete(f"/api/v1/courses/{course['id']}/sessions/{sessions[0]['id']}",
                      headers=manager_headers)
    assert r.status_code == 204
    r = client.delete(f"/api/v1/courses/{course['id']}", headers=manager_headers)
    assert r.status_code == 204


# ================================================================ B35
def test_b35_public_questions_never_leak_correct_index(client, env, manager_headers, applicant_headers):
    exam = _mk_exam(client, manager_headers, status="published")
    _add_question(client, manager_headers, exam["id"], correct=1)
    r = client.post(f"/api/v1/exams/{exam['id']}/attempts", headers=applicant_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["resumed"] is False
    for q in body["questions"]:
        assert "correct_index" not in q, "پاسخ صحیح نباید به کلاینت برود"
    # فهرست کارکنان پاسخ صحیح دارد
    r = client.get(f"/api/v1/exams/{exam['id']}/questions", headers=manager_headers)
    assert all("correct_index" in q for q in r.json()["items"])


def test_b35_grading_exact_math_and_certificate(client, env, manager_headers, applicant_headers):
    exam = _mk_exam(client, manager_headers, pass_percent=60, status="published")
    _add_question(client, manager_headers, exam["id"], correct=0, points=2)
    _add_question(client, manager_headers, exam["id"], correct=1, points=1)
    _add_question(client, manager_headers, exam["id"], correct=2, points=1)
    r = client.post(f"/api/v1/exams/{exam['id']}/attempts", headers=applicant_headers)
    body = r.json()
    attempt_id = body["attempt"]["id"]
    # ۲ از ۴ امتیاز = ۵۰٪ → مردود (سقف ۶۰)
    r = client.post(f"/api/v1/exams/attempts/{attempt_id}/submit", headers=applicant_headers,
                    json={"answers": [0, 0, 0]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["passed"] is False and out["score_percent"] == 50.0
    assert "certificate" not in out
    # سقف تلاش = ۱ → تلاش دوم ۴۰۹
    r = client.post(f"/api/v1/exams/{exam['id']}/attempts", headers=applicant_headers)
    assert r.status_code == 409
    assert "سقف" in r.json()["detail"]


def test_b35_pass_issues_certificate_once_and_verify(client, env, manager_headers, applicant_headers):
    exam = _mk_exam(client, manager_headers, status="published")
    _add_question(client, manager_headers, exam["id"], correct=1)
    r = client.post(f"/api/v1/exams/{exam['id']}/attempts", headers=applicant_headers)
    attempt_id = r.json()["attempt"]["id"]
    r = client.post(f"/api/v1/exams/attempts/{attempt_id}/submit", headers=applicant_headers,
                    json={"answers": [1]})
    out = r.json()
    assert out["passed"] is True and out["score_percent"] == 100.0
    cert = out["certificate"]
    assert cert["certificate_number"].startswith("CERT-")
    # گواهی تکراری برای همان (کاربر، آزمون) وجود ندارد
    r = client.get("/api/v1/certificates", headers=manager_headers)
    mine = [c for c in r.json()["items"] if c["exam_id"] == exam["id"]]
    assert len(mine) == 1
    # verify عمومی
    r = client.get("/api/v1/public/certificates/verify", params={"number": cert["certificate_number"]})
    assert r.status_code == 200 and r.json()["valid"] is True
    # ابطال → verify نامعتبر + تکرار ابطال ۴۰۹
    r = client.post(f"/api/v1/certificates/{cert['id']}/revoke", headers=manager_headers,
                    json={"reason": "تست ابطال"})
    assert r.status_code == 200 and r.json()["revoked"] is True
    r = client.post(f"/api/v1/certificates/{cert['id']}/revoke", headers=manager_headers, json={})
    assert r.status_code == 409
    r = client.get("/api/v1/public/certificates/verify", params={"number": cert["certificate_number"]})
    assert r.status_code == 200 and r.json()["valid"] is False and r.json()["revoked"] is True
    # شماره ناشناس ۴۰۴
    r = client.get("/api/v1/public/certificates/verify", params={"number": "CERT-0000-999999"})
    assert r.status_code == 404


def test_b35_course_exam_requires_active_enrollment(client, env, manager_headers, applicant_headers):
    course = _mk_course(client, manager_headers, status="published")
    exam = _mk_exam(client, manager_headers, course_id=course["id"], status="published")
    _add_question(client, manager_headers, exam["id"])
    r = client.post(f"/api/v1/exams/{exam['id']}/attempts", headers=applicant_headers)
    assert r.status_code == 403, "بدون ثبت‌نام فعال باید ۴۰۳ بدهد"
    client.post(f"/api/v1/public/courses/{course['slug']}/enroll", headers=applicant_headers)
    r = client.post(f"/api/v1/exams/{exam['id']}/attempts", headers=applicant_headers)
    assert r.status_code == 201, r.text


def test_b35_paid_exam_requires_purchase(client, env, manager_headers, applicant_headers):
    exam = _mk_exam(client, manager_headers, price=500000, status="published")
    _add_question(client, manager_headers, exam["id"])
    r = client.post(f"/api/v1/exams/{exam['id']}/attempts", headers=applicant_headers)
    assert r.status_code == 403, "آزمون پولی بدون پرداخت باید ۴۰۳ بدهد"
    # خرید → سفارش kind='exam'
    r = client.post(f"/api/v1/public/exams/{exam['slug']}/purchase", headers=applicant_headers)
    assert r.status_code == 200, r.text
    order = r.json()["order"]
    assert order["kind"] == "exam" and order["amount"] == 500000
    # خرید تکراری قبل از پرداخت مجاز است؟ دسترسی نه — سفارش دوم ممنوع نیست ولی
    # پس از پرداخت باید ۴۰۹ بدهد؛ حالا پرداخت می‌کنیم:
    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=manager_headers,
                    json={"gateway": "sandbox"})
    authority = r.json()["authority"]
    r = client.post(f"/api/v1/payments/{authority}/verify", headers=manager_headers)
    assert r.json()["ok"] is True
    r = client.post(f"/api/v1/public/exams/{exam['slug']}/purchase", headers=applicant_headers)
    assert r.status_code == 409
    # حالا تلاش مجاز است
    r = client.post(f"/api/v1/exams/{exam['id']}/attempts", headers=applicant_headers)
    assert r.status_code == 201, r.text


def test_b35_unpublished_exam_hidden(client, env, manager_headers, applicant_headers):
    exam = _mk_exam(client, manager_headers)  # draft
    _add_question(client, manager_headers, exam["id"])
    r = client.post(f"/api/v1/exams/{exam['id']}/attempts", headers=applicant_headers)
    assert r.status_code == 404


# ================================================================ B36
def test_b36_course_completion_issues_certificate(client, env, manager_headers, applicant_headers):
    course = _mk_course(client, manager_headers, status="published")
    r = client.post(f"/api/v1/public/courses/{course['slug']}/enroll", headers=applicant_headers)
    enr_id = r.json()["enrollment"]["id"]
    r = client.patch(f"/api/v1/enrollments/{enr_id}", headers=manager_headers,
                     json={"status": "completed"})
    assert r.status_code == 200, r.text
    certs = r.json()["certificates"]
    assert len(certs) == 1 and certs[0]["course_id"] == course["id"]
    assert certs[0]["certificate_number"].startswith("CERT-")
    # گواهی تکراری صادر نمی‌شود (idempotent) — ثبت‌نام دوباره completed
    r = client.get("/api/v1/certificates", headers=manager_headers,
                   params={"user_id": r.json()["user_id"]})
    course_certs = [c for c in r.json()["items"] if c["course_id"] == course["id"]]
    assert len(course_certs) == 1


def test_b36_manual_issue_idempotent_and_my_certificates(client, env, manager_headers, applicant_headers):
    course = _mk_course(client, manager_headers)
    user = client.get("/api/v1/auth/me", headers=applicant_headers).json()
    payload = {"user_id": user["id"], "title": "گواهی افتخار", "course_id": course["id"]}
    r = client.post("/api/v1/certificates/issue", headers=manager_headers, json=payload)
    assert r.status_code == 201 and r.json()["already_existed"] is False
    first = r.json()["certificate"]
    r = client.post("/api/v1/certificates/issue", headers=manager_headers, json=payload)
    assert r.status_code == 201 and r.json()["already_existed"] is True
    assert r.json()["certificate"]["id"] == first["id"]
    r = client.get("/api/v1/my/certificates", headers=applicant_headers)
    assert any(c["id"] == first["id"] for c in r.json()["items"])


# ================================================================ B21-plus
def test_b21plus_statement_generate_and_no_double_include(client, env, manager_headers):
    org, contract, order = _mk_org_contract_applicant_order(client, manager_headers)
    period_from = date.today() - timedelta(days=10)
    period_to = date.today() + timedelta(days=1)
    r = client.post(f"/api/v1/organizations/{org['id']}/statements", headers=manager_headers,
                    json={"period_from": str(period_from), "period_to": str(period_to)})
    assert r.status_code == 201, r.text
    st = r.json()
    assert st["status"] == "issued"
    assert st["orders_count"] == 1
    assert st["statement_no"].startswith("ORG-")
    assert st["org_share_total"] == order["org_share_amount"]
    assert len(st["items"]) == 1
    # سفارش همان، دوباره در صورتحساب نمی‌آید → بازه خالی ۴۲۲
    r = client.post(f"/api/v1/organizations/{org['id']}/statements", headers=manager_headers,
                    json={"period_from": str(period_from), "period_to": str(period_to)})
    assert r.status_code == 422
    # بازه نامعتبر ۴۲۲
    r = client.post(f"/api/v1/organizations/{org['id']}/statements", headers=manager_headers,
                    json={"period_from": str(period_to), "period_to": str(period_from)})
    assert r.status_code == 422


def test_b21plus_settle_posts_balanced_1104_entry_once(client, env, manager_headers):
    org, contract, order = _mk_org_contract_applicant_order(client, manager_headers)
    r = client.post(f"/api/v1/organizations/{org['id']}/statements", headers=manager_headers,
                    json={"period_from": str(date.today() - timedelta(days=5)),
                          "period_to": str(date.today() + timedelta(days=1))})
    st = r.json()
    r = client.post(f"/api/v1/statements/{st['id']}/settle", headers=manager_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "settled"
    assert body["journal_entry"]["source_type"] == "org_statement"
    # سند متوازن: ۱۱۰۱ بدهکار = ۱۱۰۴ بستانکار = سهم سازمان
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.models.accounting import JournalEntry, JournalLine
    db = SessionLocal()
    try:
        entry = db.scalars(
            select(JournalEntry).where(JournalEntry.id == uuid.UUID(body["journal_entry"]["id"]))
        ).first()
        assert entry is not None
        debits = sum(int(ln.debit) for ln in entry.lines)
        credits = sum(int(ln.credit) for ln in entry.lines)
        assert debits == credits == int(st["org_share_total"])
        codes = set()
        for ln in entry.lines:
            from app.models.accounting import Account
            acc = db.get(Account, ln.account_id)
            codes.add(acc.code)
        assert codes == {"1101", "1104"}
    finally:
        db.close()
    # تسویه مجدد ۴۰۹
    r = client.post(f"/api/v1/statements/{st['id']}/settle", headers=manager_headers)
    assert r.status_code == 409


def test_b21plus_receivables_report_outstanding(client, env, manager_headers):
    org, contract, order = _mk_org_contract_applicant_order(client, manager_headers)
    r = client.get(f"/api/v1/organizations/{org['id']}/receivables", headers=manager_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["org_share_total"] == order["org_share_amount"]
    assert body["settled_total"] == 0
    assert body["outstanding_total"] == order["org_share_amount"]
    # صدور و تسویه → outstanding صفر
    r = client.post(f"/api/v1/organizations/{org['id']}/statements", headers=manager_headers,
                    json={"period_from": str(date.today() - timedelta(days=5)),
                          "period_to": str(date.today() + timedelta(days=1))})
    st = r.json()
    r = client.post(f"/api/v1/statements/{st['id']}/settle", headers=manager_headers)
    assert r.status_code == 200
    r = client.get(f"/api/v1/organizations/{org['id']}/receivables", headers=manager_headers)
    body = r.json()
    assert body["settled_total"] == order["org_share_amount"]
    assert body["outstanding_total"] == 0
    assert len(body["statements"]) == 1


def test_b34_reconciliation_includes_course_and_exam(client, env, manager_headers, applicant_headers):
    """تطبیق فروش گزارش با دفتر پس از سفارش دوره/آزمون هم برقرار می‌ماند (فاز ۳۴)."""
    course = _mk_course(client, manager_headers, price=300000, status="published")
    client.post(f"/api/v1/public/courses/{course['slug']}/enroll", headers=applicant_headers)
    r = client.get(f"/api/v1/courses/{course['id']}/enrollments", headers=manager_headers)
    order_id = r.json()["items"][0]["order_id"]
    r = client.post(f"/api/v1/orders/{order_id}/payments", headers=manager_headers,
                    json={"gateway": "sandbox"})
    client.post(f"/api/v1/payments/{r.json()['authority']}/verify", headers=manager_headers)
    r = client.get("/api/v1/reports/financial-reconciliation", headers=manager_headers)
    assert r.status_code == 200, r.text
    assert r.json()["sales_reconciliation"]["reconciled"] is True, r.json()["sales_reconciliation"]
