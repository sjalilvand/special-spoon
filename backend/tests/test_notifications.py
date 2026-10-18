"""فاز ۲۵ — B12/B38 سند جامع: مرکز اعلان درون‌برنامه‌ای

پوشش:
- نهایی‌سازی فرم → اعلان به همه کاربران TECHNICAL_SUPERVISOR (category=assessment)
- فرم مورد حاد سطح ۳ → اعلان با severity=critical و event_code=assessment.level3
- تأیید فرم → اعلان به نویسنده
- برگشت فرم → اعلان به نویسنده با severity=warning
- unread-count و read و read-all فقط روی اعلان‌های خود کاربر (کاربر دیگر 404)
- بدون توکن = 401
"""
import uuid
from datetime import date

from conftest import bearer, login

API = "/api/v1"


def _h(client, who):
    """توکن Bearer بر اساس نام کاربری - الگوی سایر تست‌های مخزن."""
    return bearer(login(client, who))


TELEPHONE_ANSWERS = {
    "caller_info.full_name": "زهرا محمدی",
    "caller_info.phone": "09121110000",
    "caller_info.province": "تهران",
    "initial_assessment.subject": ["family"],
    "initial_assessment.description": "تماس درباره تعارض خانوادگی؛ راهنمایی شد.",
    "contact_info.counselor_name": "سمیه کریمی",
    "contact_info.call_date": "1404/07/26",
    "routing.route": "inperson_intake",
}

LEVEL3_ANSWERS = {
    "person_info.full_name": "مورد حاد اعلان",
    "person_info.phone": "09121234567",
    "person_info.province": "تهران",
    "initial_assessment.risk_types": ["suicidal_ideation"],
    "initial_assessment.current_dangerous_thoughts": "افکار فعال",
    "initial_assessment.immediate_action": "قرارداد ایمنی",
    "initial_assessment.severity": "level_3",
    "referral_info.followup_responsible": "کارشناس",
    "referral_info.followup_time": "امروز",
    "referral_info.referral_responsible": "پذیرش",
    "referral_info.referral_destination": "اورژانس اجتماعی",
    "referral_info.referral_result": "تأیید شد",
}


def _mk_case(client, env, suffix, form_code="RS-PS-01-01"):
    """پرونده مستقل + ارزیابی؛ خروجی (case_id, assessment_id)."""
    from app.models.case import Case, CaseAssignment
    from app.models.people import Applicant

    db = env["db"]
    app_row = Applicant(external_id=f"T-EXT-NTF-{suffix}", first_name="متقاضی",
                        last_name=f"اعلان{suffix}", status="active", record_source="manual", user_id=None)
    db.add(app_row)
    db.flush()
    case = Case(case_number=f"RS-NTF-{suffix}", applicant_id=app_row.id,
                acceptance_date=date.today(), primary_counselor_id=env["counselor_a"].id,
                status="active", version=1)
    db.add(case)
    db.flush()
    db.add(CaseAssignment(case_id=case.id, counselor_id=env["counselor_a"].id, reason="تست اعلان"))
    db.commit()
    r = client.post(f"{API}/cases/{case.id}/assessments",
                    json={"form_code": form_code}, headers=_h(client, "t_counsa"))
    assert r.status_code == 201, r.text
    return case.id, r.json()["id"]


def _finalize(client, env, assessment_id):
    """ثبت پاسخ معتبر + نهایی‌سازی."""
    from app.models.assessment import Assessment
    db = env["db"]
    a = db.get(Assessment, uuid.UUID(assessment_id))
    a.answers = dict(LEVEL3_ANSWERS if a.form_version_id and _form_code(db, a) == "RS-PS-08-01"
                     else TELEPHONE_ANSWERS)
    db.commit()
    r = client.post(f"{API}/assessments/{assessment_id}/finalize", headers=_h(client, "t_counsa"))
    assert r.status_code == 200, r.text


def _form_code(db, a):
    from app.models.assessment import FormVersion
    fv = db.get(FormVersion, a.form_version_id)
    return fv.form_code if fv else ""


def test_no_token_unauthorized(client):
    r = client.get(f"{API}/notifications")
    assert r.status_code == 401


def test_finalize_notifies_supervisors(client, env):
    case_id, aid = _mk_case(client, env, "F1")
    _finalize(client, env, aid)

    items = client.get(f"{API}/notifications", headers=_h(client, "t_super")).json()
    match = [x for x in items["items"] if x["event_code"] == "assessment.finalized" and x["entity_id"] == aid]
    assert match, "مسئول فنی باید اعلان نهایی‌سازی بگیرد"
    assert match[0]["category"] == "assessment"
    assert match[0]["read_at"] is None
    # پذیرش نباید این اعلان را ببیند (کاربر غیرعضو)
    rec = client.get(f"{API}/notifications", headers=_h(client, "t_reception")).json()
    assert not [x for x in rec["items"] if x["entity_id"] == aid]


def test_level3_notifies_critical(client, env):
    """فرم مورد حاد سطح ۳ → اعلان critical با event_code=assessment.level3."""
    case_id, aid = _mk_case(client, env, "F2", form_code="RS-PS-08-01")
    _finalize(client, env, aid)

    items = client.get(f"{API}/notifications", headers=_h(client, "t_super")).json()
    lvl3 = [x for x in items["items"] if x["event_code"] == "assessment.level3" and x["entity_id"] == aid]
    assert lvl3, "اعلان سطح ۳ باید ثبت شود"
    assert lvl3[0]["severity"] == "critical"


def test_approve_notifies_author(client, env):
    case_id, aid = _mk_case(client, env, "F3")
    _finalize(client, env, aid)
    r = client.post(f"{API}/assessments/{aid}/approve",
                    json={"comment": "تأیید شد"}, headers=_h(client, "t_super"))
    assert r.status_code == 200, r.text

    items = client.get(f"{API}/notifications", headers=_h(client, "t_counsa")).json()
    approved = [x for x in items["items"] if x["event_code"] == "assessment.approved" and x["entity_id"] == aid]
    assert approved, "نویسنده باید از تأیید مطلع شود"


def test_return_notifies_author_warning(client, env):
    case_id, aid = _mk_case(client, env, "F4")
    _finalize(client, env, aid)
    r = client.post(f"{API}/assessments/{aid}/return",
                    json={"comment": "بخش اطلاعات تماس ناقص است"}, headers=_h(client, "t_super"))
    assert r.status_code == 200, r.text

    items = client.get(f"{API}/notifications", headers=_h(client, "t_counsa")).json()
    returned = [x for x in items["items"] if x["event_code"] == "assessment.returned" and x["entity_id"] == aid]
    assert returned and returned[0]["severity"] == "warning"


def test_read_flow_and_isolation(client, env):
    """خواندن اعلان خودی OK؛ اعلان کاربر دیگر 404؛ read-all همه را می‌خواند."""
    case_id, aid = _mk_case(client, env, "F5")
    _finalize(client, env, aid)
    tok_headers = _h(client, "t_super")

    before = client.get(f"{API}/notifications/unread-count", headers=tok_headers).json()["count"]
    assert before > 0

    items = client.get(f"{API}/notifications?unread_only=true", headers=tok_headers).json()
    nid = items["items"][0]["id"]
    r = client.post(f"{API}/notifications/{nid}/read", headers=tok_headers)
    assert r.status_code == 200 and r.json()["read_at"] is not None

    after = client.get(f"{API}/notifications/unread-count", headers=tok_headers).json()["count"]
    assert after == before - 1

    # اعلان کاربر دیگری را نمی‌تواند بخواند (IDOR → 404)
    case_id2, aid2 = _mk_case(client, env, "F6")
    _finalize(client, env, aid2)
    items2 = client.get(f"{API}/notifications?unread_only=true", headers=tok_headers).json()
    target = [x for x in items2["items"] if x["entity_id"] == aid2][0]
    r2 = client.post(f"{API}/notifications/{target['id']}/read", headers=_h(client, "t_counsa"))
    assert r2.status_code == 404

    # read-all
    r3 = client.post(f"{API}/notifications/read-all", headers=tok_headers)
    assert r3.status_code == 200
    final = client.get(f"{API}/notifications/unread-count", headers=tok_headers).json()["count"]
    assert final == 0
