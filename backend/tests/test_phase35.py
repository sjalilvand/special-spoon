"""فاز ۳۵ - B23 + B37 + B25–B27 سند جامع.

- B23: نظرسنجی یک‌بارمصرف با امتیاز ۱..۵ (تکرار ۴۰۹؛ سقف/کف ۴۲۲) + گزارش
  میانگین/توزیع؛ شکایت با چرخه محافظت‌شده (بررسی فقط مدیر؛ وضعیت نامعتبر ۴۲۲؛
  بسته‌شده به جریان برنمی‌گردد)؛ تیکت با نخ پیام و چرخه open/answered/closed
  (تیکت دیگران ۴۰۳؛ تیکت بسته پیام قبول نمی‌کند)؛
- B37 (D08): «انتشار ابزار علمی فقط با تأیید ناظر علمی» — مدیر نمی‌تواند
  منتشر کند (۴۰۳)؛ ارسال بدون سؤال/بازه تفسیر ۴۲۲؛ تأیید/رد فقط
  TECHNICAL_SUPERVISOR؛ رد بدون یادداشت ۴۲۲؛ ویرایش ابزار منتشرشده →
  بازگشت به draft؛ برگزاری فقط منتشرشده؛ نمره‌دهی/تفسیر سمت سرور؛
  امتیاز گزینه‌ها در پرسش‌نامه عمومی نمی‌رود؛
- B25–B27 (D07): سرویس پلاگین‌پذیر — پیش‌فرض rule فعال بدون کلید؛ خروجی
  config بدون کلید؛ chat در دامنه + دیسکلیمر + سقف نرخ (۴۲۹) + لاگ؛
  پیشنهادگر قطعی هم‌دسته؛ ریسک عدم‌حضور قاعده‌محور فقط کارکنان (۴۰۳).
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import bearer, login


@pytest.fixture()
def manager_headers(client, env):
    return bearer(login(client, "t_manager"))


@pytest.fixture()
def supervisor_headers(client, env):
    return bearer(login(client, "t_super"))


@pytest.fixture()
def applicant_headers(client, env):
    return bearer(login(client, "t_appa"))


# ---------------- helpers ----------------

def _mk_psych_test(client, headers, slug=None) -> dict:
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/api/v1/psych-tests", headers=headers, json={
        "slug": slug or f"ptest-{suffix}",
        "title": f"ابزار ف۳۵ {suffix}",
        "description": "ابزار غربالگری آزمایشی",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _add_q(client, headers, test_id, scores=(0, 1, 2, 3)) -> dict:
    r = client.post(f"/api/v1/psych-tests/{test_id}/questions", headers=headers, json={
        "prompt": "چقدر خواب شما منظم است؟",
        "options": [{"label": f"گزینه {i}", "score": s} for i, s in enumerate(scores, 1)],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _add_range(client, headers, test_id, lo, hi, label) -> dict:
    r = client.post(f"/api/v1/psych-tests/{test_id}/interpretations", headers=headers, json={
        "score_min": lo, "score_max": hi, "label": label, "guidance": "توصیه آزمایشی",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _publish(client, manager, supervisor, test_id) -> dict:
    r = client.post(f"/api/v1/psych-tests/{test_id}/submit-review", headers=manager)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/psych-tests/{test_id}/review", headers=supervisor,
                    json={"approve": True, "note": "تأیید علمی"})
    assert r.status_code == 200, r.text
    return r.json()


# ================================================================ B23 نظرسنجی
def _mk_session_id(client, manager) -> str:
    """جلسه تازه — ثبت جلسه فقط با مشاور تخصیص‌یافته مجاز است
    (مشاور الف پرونده اول در conftest)."""
    case_id = client.get("/api/v1/cases?page_size=1", headers=manager).json()["items"][0]["id"]
    counselor = bearer(login(client, "t_counsa"))
    occurred = datetime.now(timezone.utc) - timedelta(days=3)
    r = client.post(f"/api/v1/cases/{case_id}/sessions", headers=counselor,
                    json={"occurred_at": occurred.isoformat()})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_b23_survey_submit_duplicate_bounds(client, env, manager_headers):
    session_id = _mk_session_id(client, manager_headers)
    r = client.post(f"/api/v1/sessions/{session_id}/survey", headers=manager_headers,
                    json={"score": 5, "comment": "عالی بود"})
    assert r.status_code == 201, r.text
    # تکراری ۴۰۹
    r = client.post(f"/api/v1/sessions/{session_id}/survey", headers=manager_headers,
                    json={"score": 4})
    assert r.status_code == 409
    # گزارش میانگین/توزیع
    r2 = client.get("/api/v1/reports/survey-summary", headers=manager_headers)
    assert r2.status_code == 200
    body = r2.json()
    assert body["total"] >= 1 and body["distribution"]["5"] >= 1
    assert 1 <= body["average"] <= 5
    # گزارش برای متقاضی ممنوع
    r = client.get("/api/v1/reports/survey-summary", headers=applicant_headers_r(client))
    assert r.status_code == 403


def applicant_headers_r(client):
    return bearer(login(client, "t_appa"))


def test_b23_survey_score_validation(client, env, manager_headers):
    # امتیاز باید 1..5 باشد — تست با pydantic validation مستقیم
    r = client.post("/api/v1/sessions/00000000-0000-0000-0000-000000000000/survey",
                    headers=manager_headers, json={"score": 0})
    assert r.status_code == 422
    r = client.post("/api/v1/sessions/00000000-0000-0000-0000-000000000000/survey",
                    headers=manager_headers, json={"score": 6})
    assert r.status_code == 422


# ================================================================ B23 شکایت
def test_b23_complaint_flow_and_permissions(client, env, manager_headers, applicant_headers):
    r = client.post("/api/v1/complaints", headers=applicant_headers, json={
        "subject": "تأخیر در پاسخ‌گویی", "body": "سه روز است پاسخی نگرفته‌ام و پیگیری می‌کنم.",
    })
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["status"] == "new"
    # متقاضی فهرست خودش را می‌بیند
    r = client.get("/api/v1/complaints", headers=applicant_headers)
    assert any(c["id"] == cid for c in r.json()["items"])
    # متقاضی اجازه بررسی ندارد (نقطه پایان review فقط برای مدیران تعریف شده —
    # 403 یا 404 بر اساس dependency ترتیب؛ require_roles ابتدا اجرا می‌شود → 403)
    r = client.patch(f"/api/v1/complaints/{cid}/review", headers=applicant_headers,
                     json={"status": "in_review"})
    assert r.status_code == 403
    # وضعیت نامعتبر ۴۲۲
    r = client.patch(f"/api/v1/complaints/{cid}/review", headers=manager_headers,
                     json={"status": "new"})
    assert r.status_code == 422
    # چرخه بررسی
    r = client.patch(f"/api/v1/complaints/{cid}/review", headers=manager_headers,
                     json={"status": "in_review"})
    assert r.status_code == 200 and r.json()["status"] == "in_review"
    r = client.patch(f"/api/v1/complaints/{cid}/review", headers=manager_headers,
                     json={"status": "resolved", "resolution_note": "پیگیری و حل شد"})
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    # شکایت بسته به جریان برنمی‌گردد
    r = client.patch(f"/api/v1/complaints/{cid}/review", headers=manager_headers,
                     json={"status": "in_review"})
    assert r.status_code == 409


# ================================================================ B23 تیکت
def _mk_extra_applicant(client) -> list:
    """کاربر عادی دوم (APPLICANT) برای تست دسترسی — با DB مستقیم."""
    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.user import Role, User as UserModel, UserStatus
    import conftest as _cf
    db = SessionLocal()
    try:
        u = UserModel(username=f"t_appx{uuid.uuid4().hex[:6]}", display_name="متقاضی دوم",
                      status=UserStatus.ACTIVE, must_change_password=False)
        u.password_hash = hash_password(_cf.PASSWORD)
        role = db.get(Role, "APPLICANT")
        if role:
            u.roles.append(role)
        db.add(u)
        db.commit()
        username = u.username
    finally:
        db.close()
    return bearer(login(client, username))


def test_b23_ticket_thread_flow(client, env, manager_headers, applicant_headers):
    r = client.post("/api/v1/tickets", headers=applicant_headers, json={
        "subject": "مشکل در پرداخت", "body": "پرداخت انجام شد اما سفارش پرداخت‌نشده است.",
        "priority": "high",
    })
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert r.json()["status"] == "open"
    # کاربر عادی دیگر به تیکت دسترسی ندارد (۴۰۳) — نه کارکنان
    other = _mk_extra_applicant(client)
    r = client.get(f"/api/v1/tickets/{tid}", headers=other)
    assert r.status_code == 403
    # پاسخ کارکنان → answered
    r = client.post(f"/api/v1/tickets/{tid}/messages", headers=manager_headers,
                    json={"body": "بررسی می‌کنیم؛ شماره سفارش را بفرستید."})
    assert r.status_code == 201 and r.json()["status"] == "answered"
    # پاسخ مالک → open
    r = client.post(f"/api/v1/tickets/{tid}/messages", headers=applicant_headers,
                    json={"body": "ORD-1404-000001"})
    assert r.status_code == 201 and r.json()["status"] == "open"
    # بستن توسط کارکنان؛ تکرار ۴۰۹؛ پیام جدید ۴۰۹
    r = client.post(f"/api/v1/tickets/{tid}/close", headers=manager_headers)
    assert r.status_code == 200 and r.json()["status"] == "closed"
    r = client.post(f"/api/v1/tickets/{tid}/close", headers=manager_headers)
    assert r.status_code == 409
    r = client.post(f"/api/v1/tickets/{tid}/messages", headers=applicant_headers,
                    json={"body": "دوباره باز شود"})
    assert r.status_code == 409
    # نخ پیام حفظ شده (اولیه + پاسخ کارکنان + پاسخ مالک)
    r = client.get(f"/api/v1/tickets/{tid}", headers=applicant_headers)
    assert len(r.json()["messages"]) == 3


# ================================================================ B37 (D08)
def test_b37_manager_cannot_publish_supervisor_gate(client, env, manager_headers, supervisor_headers):
    t = _mk_psych_test(client, manager_headers)
    _add_q(client, manager_headers, t["id"])
    _add_range(client, manager_headers, t["id"], 0, 4, "کم")
    _add_range(client, manager_headers, t["id"], 5, 12, "بالا")
    # ارسال برای بازبینی بدون سؤال/بازه امکان ندارد؛ ابزار دارد → 200
    r = client.post(f"/api/v1/psych-tests/{t['id']}/submit-review", headers=manager_headers)
    assert r.status_code == 200
    # «مدیر نمی‌تواند ابزار را منتشر کند» — نقش ناظر علمی لازم است
    r = client.post(f"/api/v1/psych-tests/{t['id']}/review", headers=manager_headers,
                    json={"approve": True})
    assert r.status_code == 403, "انتشار فقط با ناظر علمی (D08)"
    # ناظر علمی تأیید می‌کند
    r = client.post(f"/api/v1/psych-tests/{t['id']}/review", headers=supervisor_headers,
                    json={"approve": True, "note": "روایی کافی"})
    assert r.status_code == 200 and r.json()["status"] == "published"
    assert r.json()["reviewed_by"] is not None


def test_b37_submit_review_requires_questions_and_ranges(client, env, manager_headers):
    t = _mk_psych_test(client, manager_headers)
    r = client.post(f"/api/v1/psych-tests/{t['id']}/submit-review", headers=manager_headers)
    assert r.status_code == 422 and "سؤال" in r.json()["detail"]
    _add_q(client, manager_headers, t["id"])
    r = client.post(f"/api/v1/psych-tests/{t['id']}/submit-review", headers=manager_headers)
    assert r.status_code == 422 and "تفسیر" in r.json()["detail"]


def test_b37_reject_requires_note_and_resubmit(client, env, manager_headers, supervisor_headers):
    t = _mk_psych_test(client, manager_headers)
    _add_q(client, manager_headers, t["id"])
    _add_range(client, manager_headers, t["id"], 0, 10, "متوسط")
    client.post(f"/api/v1/psych-tests/{t['id']}/submit-review", headers=manager_headers)
    # رد بدون یادداشت ۴۲۲
    r = client.post(f"/api/v1/psych-tests/{t['id']}/review", headers=supervisor_headers,
                    json={"approve": False})
    assert r.status_code == 422
    r = client.post(f"/api/v1/psych-tests/{t['id']}/review", headers=supervisor_headers,
                    json={"approve": False, "note": "بازه‌ها باید بازبینی شود"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    # ابزار ردشده قابل ارسال مجدد است
    r = client.post(f"/api/v1/psych-tests/{t['id']}/submit-review", headers=manager_headers)
    assert r.status_code == 200 and r.json()["status"] == "pending_review"


def test_b37_published_edit_reverts_to_draft(client, env, manager_headers, supervisor_headers):
    t = _mk_psych_test(client, manager_headers)
    _add_q(client, manager_headers, t["id"])
    _add_range(client, manager_headers, t["id"], 0, 10, "متوسط")
    published = _publish(client, manager_headers, supervisor_headers, t["id"])
    assert published["status"] == "published"
    # ویرایش محتوای علمی منتشرشده → draft (باید دوباره تأیید شود)
    r = client.patch(f"/api/v1/psych-tests/{t['id']}", headers=manager_headers,
                     json={"description": "توضیح ویرایش‌شده"})
    assert r.status_code == 200 and r.json()["status"] == "draft"


def test_b37_take_test_scoring_interpretation_no_score_leak(client, env, manager_headers,
                                                            supervisor_headers, applicant_headers):
    t = _mk_psych_test(client, manager_headers)
    q1 = _add_q(client, manager_headers, t["id"], scores=(0, 1, 2, 3))
    _add_q(client, manager_headers, t["id"], scores=(0, 1))
    _add_range(client, manager_headers, t["id"], 0, 2, "سطح پایین")
    _add_range(client, manager_headers, t["id"], 3, 99, "سطح بالا")
    # پرسش‌نامه عمومی امتیاز گزینه‌ها را نمی‌فرستد
    r = client.get(f"/api/v1/public/psych-tests/{t['slug']}/paper")
    assert r.status_code == 404, "انتشارنشده عمومی نیست"
    _publish(client, manager_headers, supervisor_headers, t["id"])
    r = client.get(f"/api/v1/public/psych-tests/{t['slug']}/paper")
    assert r.status_code == 200
    for q in r.json()["questions"]:
        for opt in q["options"]:
            assert not isinstance(opt, dict), "امتیاز گزینه نباید در پرسش‌نامه عمومی باشد"
            assert opt is not None
    body = r.json()
    assert len(body["questions"]) == 2
    # اجرا: انتخاب گزینه ۴ از سؤال اول (امتیاز ۳) و گزینه ۲ از دوم (امتیاز ۱) → نمره ۴ → سطح بالا
    r = client.post(f"/api/v1/public/psych-tests/{t['slug']}/attempts", headers=applicant_headers,
                    json={"answers": [3, 1]})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["attempt"]["score"] == 4
    assert out["attempt"]["interpretation_label"] == "سطح بالا"
    assert "disclaimer" in out
    # فهرست عمومی فقط منتشرشده‌ها
    r = client.get("/api/v1/public/psych-tests")
    assert any(x["id"] == t["id"] for x in r.json()["items"])
    # نتایج کاربر
    r = client.get("/api/v1/my/psych-results", headers=applicant_headers)
    assert any(x["test_id"] == t["id"] and x["score"] == 4 for x in r.json()["items"])
    # فهرست تلاش‌ها برای کارکنان
    r = client.get(f"/api/v1/psych-tests/{t['id']}/attempts", headers=manager_headers)
    assert len(r.json()["items"]) == 1


# ================================================================ B25–B27 (D07)
def test_b27ai_config_default_rule_without_key_leak(client, env, applicant_headers):
    r = client.get("/api/v1/ai/config", headers=applicant_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["active_provider"] == "rule"
    assert body["configured_provider"] == "rule"
    assert body["fallback_applied"] is False
    assert body["rate_limit_per_minute"] >= 1
    # کلید در خروجی نیست (D07: شفافیت بدون افشا)
    assert not any("key" in k for k in body.keys())


def test_b27ai_chat_domain_answer_disclaimer_and_log(client, env, manager_headers, applicant_headers):
    r = client.post("/api/v1/ai/chat", headers=applicant_headers,
                    json={"message": "چطور نوبت رزرو کنم؟"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "rule"
    assert "رزرو" in body["response"]
    assert body["disclaimer"], "دیسکلیمر الزامی است"
    # پرسش خارج از دامنه → پاسخ fallback
    r = client.post("/api/v1/ai/chat", headers=applicant_headers,
                    json={"message": "قیمت بیت‌کوین چند است؟"})
    assert r.status_code == 200
    assert "خارج از دامنه" in r.json()["response"]
    # لاگ ثبت شده (کارکنان نگاه سروری می‌کنیم از طریق DB)
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.ai import AiChatLog
    db = SessionLocal()
    try:
        count = len(db.scalars(select(AiChatLog.id)).all())
    finally:
        db.close()
    assert count >= 2


def test_b27ai_rate_limit_429(client, env, applicant_headers):
    from app.services import ai_assistant
    user = client.get("/api/v1/auth/me", headers=applicant_headers).json()
    uid = uuid.UUID(user["id"])
    ai_assistant._rate_bucket.pop(uid, None)
    last = 200
    for _ in range(ai_assistant.RATE_LIMIT_PER_MINUTE + 1):
        r = client.post("/api/v1/ai/chat", headers=applicant_headers, json={"message": "سلام"})
        last = r.status_code
        if last == 429:
            break
    assert last == 429, "سقف نرخ باید فعال شود"


def test_b26_recommendations_same_topic_deterministic(client, env, manager_headers, applicant_headers):
    # بدون سفارش → خالی
    from app.services import ai_assistant
    user = client.get("/api/v1/auth/me", headers=applicant_headers).json()
    r = client.get("/api/v1/ai/recommendations", headers=applicant_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []
    # سفارش پرداخت‌شده با خدمتِ هم‌دسته → پیشنهاد قطعی
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/api/v1/specialties", headers=manager_headers, json={"name": f"تخصص B26 {suffix}"})
    sp = r.json()
    svcs = []
    for i in range(2):
        r = client.post("/api/v1/services", headers=manager_headers, json={
            "specialty_id": sp["id"], "title": f"خدمت B26 {suffix}-{i}", "duration_minutes": 45,
        })
        svcs.append(r.json())
    on = date.today() - timedelta(days=1)
    for svc in svcs:
        r = client.post("/api/v1/tariffs", headers=manager_headers, json={
            "service_id": svc["id"], "amount": 700000,
            "valid_from": str(on), "valid_to": str(on + timedelta(days=200)),
        })
        assert r.status_code == 201, r.text
    # دسته موضوعی مشترک + اتصال هر دو خدمت
    r = client.post("/api/v1/topics", headers=manager_headers, json={
        "name": f"دسته B26 {suffix}", "slug": f"b26-{suffix}",
    })
    topic = r.json()
    for svc in svcs:
        r = client.put(f"/api/v1/topics/{topic['id']}/services", headers=manager_headers,
                       json={"service_ids": [s["id"] for s in svcs]})
        assert r.status_code == 200, r.text
    case_id = client.get("/api/v1/cases?page_size=1", headers=manager_headers).json()["items"][0]["id"]
    sched = datetime.combine(date.today() + timedelta(days=15),
                             datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
    r = client.post("/api/v1/appointments", headers=manager_headers, json={
        "case_id": case_id, "service_id": svcs[0]["id"], "scheduled_at": sched.isoformat(),
    })
    appt = r.json()
    appa_id = client.get("/api/v1/auth/me", headers=applicant_headers).json()["id"]
    r = client.post("/api/v1/orders", headers=manager_headers,
                    json={"appointment_id": appt["id"], "owner_user_id": appa_id})
    order = r.json()
    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=manager_headers,
                    json={"gateway": "sandbox"})
    r = client.post(f"/api/v1/payments/{r.json()['authority']}/verify", headers=manager_headers)
    assert r.json()["ok"] is True
    # پیشنهاد باید خدمت دوم هم‌دسته باشد (قطعی)
    r = client.get("/api/v1/ai/recommendations", headers=applicant_headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["service_id"] == svcs[1]["id"]


def test_b27_no_show_risk_staff_only_and_shape(client, env, manager_headers, applicant_headers):
    r = client.get("/api/v1/ai/no-show-risk", headers=applicant_headers)
    assert r.status_code == 403, "ریسک عدم‌حضور فقط کارکنان"
    r = client.get("/api/v1/ai/no-show-risk", headers=manager_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_days"] == 7
    assert isinstance(body["items"], list)
    for it in body["items"]:
        assert 0 <= it["risk_score"] <= 95
        assert it["risk_level"] in ("کم", "متوسط", "بالا")
        assert isinstance(it["factors"], list)
