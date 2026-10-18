"""کارتابل هشدار سطح ۳ مسئول فنی (فاز ۲۳) — RS-PS-08-01 با فوریت بالا

پوشش:
- دسترسی فقط نقش TECHNICAL_SUPERVISOR (بند ۹.۱)
- ظهور فرم نهایی‌شده سطح ۳ با جزئیات فوری (نوع خطر، اقدام فوری، ارجاع)
- عدم ظهور سطح‌های ۱ و ۲، پیش‌نویس‌ها و موارد تأییدشده در آیتم‌ها
- ترتیب قدیمی‌ترین هشدار اول و شمارش کل total_level3
"""
import time
from datetime import date

from conftest import bearer, login

API = "/api/v1"


def _acute_answers(severity="level_3", with_referral=True):
    """پاسخ‌های معتبر فرم مورد حاد مطابق الزامات نهایی‌سازی RS-PS-08-01."""
    base = {
        "person_info.full_name": "مریم کریمی",
        "person_info.phone": "09121234567",
        "person_info.province": "تهران",
        "initial_assessment.risk_types": ["suicidal_ideation", "severe_crisis"],
        "initial_assessment.current_dangerous_thoughts": "افکار فعال با برنامه نامشخص",
        "initial_assessment.immediate_action": "اقدام فوری — قرارداد ایمنی و اطلاع‌رسانی خانواده",
        "initial_assessment.severity": severity,
        "referral_info.followup_responsible": "کارشناس پیگیری",
        "referral_info.followup_time": "امروز ۱۸:۰۰",
    }
    if with_referral and severity == "level_3":
        base.update({
            "referral_info.referral_responsible": "پذیرش",
            "referral_info.referral_destination": "اورژانس اجتماعی",
            "referral_info.referral_result": "پذیرش مقصد تأیید شد",
        })
    return base


def _new_acute_case(client, env, case_number, answers, finalize=True):
    """پرونده مستقل + ارزیابی فرم مورد حاد؛ خروجی: (assessment_id, case_id)."""
    from app.models.case import Case, CaseAssignment
    from app.models.people import Applicant

    db = env["db"]
    app_row = Applicant(external_id=f"T-EXT-L3-{case_number}", first_name="متقاضی",
                        last_name="سطح‌سه", status="active", record_source="manual", user_id=None)
    db.add(app_row)
    db.flush()
    case = Case(case_number=case_number, applicant_id=app_row.id, acceptance_date=date.today(),
                primary_counselor_id=env["counselor_a"].id, status="active", version=1)
    db.add(case)
    db.flush()
    db.add(CaseAssignment(case_id=case.id, counselor_id=env["counselor_a"].id, reason="تست کارتابل سطح ۳"))
    db.commit()

    tok = login(client, "t_counsa")
    r = client.post(f"{API}/cases/{case.id}/assessments", headers=bearer(tok),
                    json={"answers": answers, "form_code": "RS-PS-08-01"})
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    if finalize:
        r = client.post(f"{API}/assessments/{aid}/finalize", headers=bearer(tok))
        assert r.status_code == 200, r.text
    return aid, str(case.id)


def _cartable(client):
    tok = login(client, "t_super")
    r = client.get(f"{API}/worklists/level3", headers=bearer(tok))
    assert r.status_code == 200, r.text
    return r.json()


def test_level3_cartable_requires_technical_supervisor(client, env):
    tok_rec = login(client, "t_reception")
    assert client.get(f"{API}/worklists/level3", headers=bearer(tok_rec)).status_code == 403
    tok_c = login(client, "t_counsa")
    assert client.get(f"{API}/worklists/level3", headers=bearer(tok_c)).status_code == 403
    assert client.get(f"{API}/worklists/level3").status_code == 401


def test_level3_pending_appears_with_acute_details(client, env):
    aid, case_id = _new_acute_case(client, env, "RS-TEST-L3-0001", _acute_answers())
    data = _cartable(client)
    row = next((i for i in data["items"] if i["id"] == aid), None)
    assert row is not None, "هشدار سطح ۳ در انتظار بررسی باید در کارتابل باشد"
    assert row["case_id"] == case_id
    assert row["status"] == "pending_review"
    assert row["form_code"] == "RS-PS-08-01"
    assert row["applicant_name"] == "متقاضی سطح‌سه"
    assert row["person_name"] == "مریم کریمی"
    assert row["person_phone"] == "09121234567"
    assert row["severity_label"] and "سطح ۳" in row["severity_label"]
    assert "افکار خودکشی یا آسیب به خود" in row["risk_types"]
    assert "بحران شدید" in row["risk_types"]
    assert row["immediate_action"] and "قرارداد ایمنی" in row["immediate_action"]
    assert row["referral_destination"] == "اورژانس اجتماعی"
    assert row["referral_result"] == "پذیرش مقصد تأیید شد"
    assert data["total_level3"] >= 1


def test_lower_severity_and_draft_are_not_listed(client, env):
    aid1, _ = _new_acute_case(client, env, "RS-TEST-L3-0002", _acute_answers(severity="level_1"))
    aid_draft, _ = _new_acute_case(client, env, "RS-TEST-L3-0003", _acute_answers(), finalize=False)
    data = _cartable(client)
    ids = {i["id"] for i in data["items"]}
    assert aid1 not in ids, "سطح ۱ نباید در کارتابل هشدار سطح ۳ باشد"
    assert aid_draft not in ids, "پیش‌نویس نهایی‌نشده نباید هشدار بسازد"


def test_oldest_alert_first_ordering(client, env):
    aid_a, _ = _new_acute_case(client, env, "RS-TEST-L3-0004", _acute_answers())
    time.sleep(0.02)  # تضمین اختلاف finalized_at
    aid_b, _ = _new_acute_case(client, env, "RS-TEST-L3-0005", _acute_answers())
    data = _cartable(client)
    ours = [i["id"] for i in data["items"] if i["id"] in (aid_a, aid_b)]
    assert ours == [aid_a, aid_b], "قدیمی‌ترین هشدار سطح ۳ باید اول دیده شود"


def test_approved_alert_leaves_queue_but_counts_in_total(client, env):
    aid, _ = _new_acute_case(client, env, "RS-TEST-L3-0006", _acute_answers())
    tok_sup = login(client, "t_super")
    r = client.post(f"{API}/assessments/{aid}/approve", headers=bearer(tok_sup), json={})
    assert r.status_code == 200, r.text
    data = _cartable(client)
    assert all(i["id"] != aid for i in data["items"]), "هشدار تأییدشده از صف بررسی خارج می‌شود"
    assert data["total_level3"] >= 1, "شمارش کل شامل هشدارهای تأییدشده هم هست"
