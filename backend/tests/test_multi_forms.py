"""فرم‌های چندگانه (RS-PS-01-01 / RS-PS-04-01 / RS-PS-08-01) — رجیستری و گردش ارزیابی"""
from conftest import API, bearer, login


def _list_forms(client, tok):
    return client.get(f"{API}/forms", headers=bearer(tok))


def test_forms_list_contains_three_registered_forms(client, env):
    tok = login(client, "t_counsa")
    r = _list_forms(client, tok)
    assert r.status_code == 200, r.text
    codes = {item["code"] for item in r.json()["items"]}
    assert codes == {"RS-PS-01-01", "RS-PS-04-01", "RS-PS-08-01"}
    for item in r.json()["items"]:
        assert item["title"] and item["version"] >= 1


def test_form_definition_by_code_and_unknown_404(client, env):
    tok = login(client, "t_counsa")
    r = client.get(f"{API}/forms/RS-PS-01-01", headers=bearer(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "RS-PS-01-01"
    assert body["definition"]["sections"], "تعریف فرم باید بخش داشته باشد"

    r2 = client.get(f"{API}/forms/RS-XX-99-99", headers=bearer(tok))
    assert r2.status_code == 404


def _new_case(db, env, case_number):
    """پرونده جدید برای مشاور الف تا نتیجه آزمون‌ها مستقل بماند."""
    from datetime import date
    from app.models.case import Case, CaseAssignment
    case = Case(case_number=case_number, applicant_id=env["applicant_a"].id,
                acceptance_date=date.today(), primary_counselor_id=env["counselor_a"].id,
                status="active", version=1)
    db.add(case)
    db.flush()
    db.add(CaseAssignment(case_id=case.id, counselor_id=env["counselor_a"].id, reason="تخصیص آزمون چندفرمی"))
    db.commit()
    return case


def _create(client, tok, case_id, form_code=None, answers=None):
    payload: dict = {"answers": answers or {}}
    if form_code:
        payload["form_code"] = form_code
    return client.post(f"{API}/cases/{case_id}/assessments", headers=bearer(tok), json=payload)


def test_telephone_intake_form_full_cycle(client, env):
    tok = login(client, "t_counsa")
    db = env["db"]
    case = _new_case(db, env, "RS-TEST-MF-0001")

    # ایجاد با فرم پذیرش تلفنی
    r = _create(client, tok, str(case.id), form_code="RS-PS-01-01")
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert r.json()["form_code"] == "RS-PS-01-01"

    # نهایی‌سازی ناقص → 422 با فهرست خطاها
    r = client.post(f"{API}/assessments/{aid}/finalize", headers=bearer(tok))
    assert r.status_code == 422, r.text
    fields = {e["field"] for e in r.json()["detail"]["errors"]}
    assert "initial_assessment.subject" in fields
    assert "routing.route" in fields

    # تکمیل و نهایی‌سازی موفق
    answers = {
        "caller_info.full_name": "زهرا محمدی",
        "caller_info.phone": "09121110000",
        "caller_info.province": "تهران",
        "initial_assessment.subject": ["family"],
        "initial_assessment.description": "تماس درباره تعارض خانوادگی؛ راهنمایی شد.",
        "contact_info.counselor_name": "سمیه کریمی",
        "contact_info.call_date": "1404/07/26",
        "routing.route": "inperson_intake",
    }
    r = client.patch(f"{API}/assessments/{aid}", headers=bearer(tok),
                     json={"answers": answers})
    assert r.status_code == 200
    r = client.post(f"{API}/assessments/{aid}/finalize", headers=bearer(tok))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_review"

    # تأیید مسئول فنی
    tok_sup = login(client, "t_super")
    r = client.post(f"{API}/assessments/{aid}/approve", headers=bearer(tok_sup), json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


def test_acute_case_form_level3_requires_referral_info(client, env):
    tok = login(client, "t_counsa")
    db = env["db"]
    case = _new_case(db, env, "RS-TEST-MF-0002")

    r = _create(client, tok, str(case.id), form_code="RS-PS-08-01")
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert r.json()["form_code"] == "RS-PS-08-01"

    base = {
        "person_info.full_name": "علی رضایی",
        "person_info.phone": "09351110000",
        "person_info.province": "اصفهان",
        "initial_assessment.risk_types": ["suicidal_ideation"],
        "initial_assessment.current_dangerous_thoughts": "افکار فعال بدون برنامه",
        "initial_assessment.immediate_action": "قرارداد ایمنی و آموزش",
        "referral_info.followup_responsible": "کارشناس پیگیری",
        "referral_info.followup_time": "فردا ۱۰",
    }
    client.patch(f"{API}/assessments/{aid}", headers=bearer(tok), json={"answers": base})

    # سطح ۳ بدون اطلاعات ارجاع → 422
    client.patch(f"{API}/assessments/{aid}", headers=bearer(tok),
                 json={"answers": {**base, "initial_assessment.severity": "level_3"}})
    r = client.post(f"{API}/assessments/{aid}/finalize", headers=bearer(tok))
    assert r.status_code == 422, r.text
    fields = {e["field"] for e in r.json()["detail"]["errors"]}
    assert "referral_info.referral_responsible" in fields
    assert "referral_info.referral_destination" in fields

    # تکمیل ارجاع → نهایی‌سازی موفق
    base.update({
        "initial_assessment.severity": "level_3",
        "referral_info.referral_responsible": "پذیرش",
        "referral_info.referral_destination": "اورژانس اجتماعی استان",
        "referral_info.referral_result": "پذیرش مقصد تأیید شد",
    })
    client.patch(f"{API}/assessments/{aid}", headers=bearer(tok), json={"answers": base})
    r = client.post(f"{API}/assessments/{aid}/finalize", headers=bearer(tok))
    assert r.status_code == 200, r.text


def test_default_form_code_is_rs_ps_04_01(client, env):
    """سازگاری با قبل: ارزیابی بدون form_code با فرم RS-PS-04-01 ساخته می‌شود."""
    tok = login(client, "t_counsa")
    db = env["db"]
    case = _new_case(db, env, "RS-TEST-MF-0003")
    r = _create(client, tok, str(case.id))
    assert r.status_code == 201, r.text
    assert r.json()["form_code"] == "RS-PS-04-01"


def test_assessments_list_includes_form_code(client, env):
    tok = login(client, "t_counsa")
    db = env["db"]
    case = _new_case(db, env, "RS-TEST-MF-0004")
    r = _create(client, tok, str(case.id), form_code="RS-PS-01-01")
    aid = r.json()["id"]
    r = client.get(f"{API}/cases/{case.id}/assessments", headers=bearer(tok))
    assert r.status_code == 200
    item = next(i for i in r.json()["items"] if i["id"] == aid)
    assert item["form_code"] == "RS-PS-01-01"
    assert item["form_title"]
