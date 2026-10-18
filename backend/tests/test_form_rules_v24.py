"""فاز ۲۴ — قواعد جدید اعتبارسنجی و نرمال‌سازی فرم‌ها (سند جامع v0.2 بخش ۰۴ و B14)

پوشش:
- نرمال‌سازی ارقام فارسی در تلفن و متن‌ها
- قالب تلفن، کد ملی با رقم کنترل، بازه سن
- گزینه‌های غیرمجاز در select/multiselect
- سقف طول فیلدها
- کلیدهای ناشناخته (نسخه‌های قدیمی) مانع نهایی‌سازی نمی‌شوند
- نسخه‌های جدید فرم‌ها: تاریخ فرم، بخش اطلاعات فردی فرم ۰۴، گزینه‌های افزوده
"""
from conftest import bearer, login

API = "/api/v1"

# کد ملی معتبر بر اساس الگوریتم رقم کنترل (جمع وزنی mod 11)
VALID_NID = "0012345679"
INVALID_NID = "0012345678"


def _acute_case(client, env, case_number):
    from datetime import date
    from app.models.case import Case, CaseAssignment
    from app.models.people import Applicant
    db = env["db"]
    app_row = Applicant(external_id=f"T-EXT-V24-{case_number}", first_name="متقاضی",
                        last_name="قواعد۲۴", status="active", record_source="manual", user_id=None)
    db.add(app_row)
    db.flush()
    case = Case(case_number=case_number, applicant_id=app_row.id, acceptance_date=date.today(),
                primary_counselor_id=env["counselor_a"].id, status="active", version=1)
    db.add(case)
    db.flush()
    db.add(CaseAssignment(case_id=case.id, counselor_id=env["counselor_a"].id, reason="تست فاز ۲۴"))
    db.commit()
    tok = login(client, "t_counsa")
    return tok, str(case.id)


def _create(client, tok, case_id, form_code, answers):
    r = client.post(f"{API}/cases/{case_id}/assessments", headers=bearer(tok),
                    json={"answers": answers, "form_code": form_code})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _patch(client, tok, aid, answers):
    r = client.patch(f"{API}/assessments/{aid}", headers=bearer(tok), json={"answers": answers})
    assert r.status_code == 200, r.text
    return r.json()


def _finalize(client, tok, aid):
    return client.post(f"{API}/assessments/{aid}/finalize", headers=bearer(tok))


def _valid_acute_answers(**overrides):
    base = {
        "person_info.full_name": "زهرا احمدی",
        "person_info.phone": "09121110000",
        "person_info.province": "تهران",
        "initial_assessment.risk_types": ["suicidal_ideation"],
        "initial_assessment.current_dangerous_thoughts": "افکار فعال",
        "initial_assessment.immediate_action": "قرارداد ایمنی",
        "initial_assessment.severity": "level_1",
        "referral_info.followup_responsible": "پیگیر",
        "referral_info.followup_time": "فردا",
    }
    base.update(overrides)
    return base


def test_persian_digits_are_normalized_on_create_and_patch(client, env):
    tok, case_id = _acute_case(client, env, "RS-TEST-V24-01")
    answers = _valid_acute_answers(**{
        "person_info.phone": "۰۹۱۲۱۱۱۰۰۰۰",       # ارقام فارسی
        "person_info.full_name": "  زهرا احمدی ",   # فاصله اضافه
    })
    aid = _create(client, tok, case_id, "RS-PS-08-01", answers)
    detail = _patch(client, tok, aid, answers)
    assert detail["answers"]["person_info.phone"] == "09121110000"
    assert detail["answers"]["person_info.full_name"] == "زهرا احمدی"


def test_invalid_phone_rejected_at_finalize(client, env):
    tok, case_id = _acute_case(client, env, "RS-TEST-V24-02")
    aid = _create(client, tok, case_id, "RS-PS-08-01", _valid_acute_answers())
    _patch(client, tok, aid, _valid_acute_answers(**{"person_info.phone": "12345"}))
    r = _finalize(client, tok, aid)
    assert r.status_code == 422, r.text
    fields = {e["field"] for e in r.json()["detail"]["errors"]}
    assert "person_info.phone" in fields


def test_invalid_national_id_check_digit_rejected(client, env):
    tok, case_id = _acute_case(client, env, "RS-TEST-V24-03")
    aid = _create(client, tok, case_id, "RS-PS-08-01", _valid_acute_answers())
    _patch(client, tok, aid, _valid_acute_answers(**{"person_info.national_id": INVALID_NID}))
    r = _finalize(client, tok, aid)
    assert r.status_code == 422, r.text
    fields = {e["field"] for e in r.json()["detail"]["errors"]}
    assert "person_info.national_id" in fields

    # کد ملی معتبر مانع نهایی‌سازی نیست
    _patch(client, tok, aid, _valid_acute_answers(**{"person_info.national_id": VALID_NID}))
    assert _finalize(client, tok, aid).status_code == 200


def test_age_out_of_range_rejected(client, env):
    tok, case_id = _acute_case(client, env, "RS-TEST-V24-04")
    aid = _create(client, tok, case_id, "RS-PS-08-01", _valid_acute_answers())
    _patch(client, tok, aid, _valid_acute_answers(**{"person_info.age": "250"}))
    r = _finalize(client, tok, aid)
    assert r.status_code == 422, r.text
    fields = {e["field"]: e["error"] for e in r.json()["detail"]["errors"]}
    assert "person_info.age" in fields and "بین 0 و 120" in fields["person_info.age"]


def test_invalid_select_and_multiselect_options_rejected(client, env):
    tok, case_id = _acute_case(client, env, "RS-TEST-V24-05")
    aid = _create(client, tok, case_id, "RS-PS-08-01", _valid_acute_answers())
    _patch(client, tok, aid, _valid_acute_answers(**{
        "initial_assessment.severity": "level_9",                      # گزینه ناموجود
        "initial_assessment.risk_types": ["suicidal_ideation", "hack"],  # گزینه ناموجود
    }))
    r = _finalize(client, tok, aid)
    assert r.status_code == 422, r.text
    fields = {e["field"] for e in r.json()["detail"]["errors"]}
    assert "initial_assessment.severity" in fields
    assert "initial_assessment.risk_types" in fields


def test_max_length_rejected_at_finalize(client, env):
    tok, case_id = _acute_case(client, env, "RS-TEST-V24-06")
    aid = _create(client, tok, case_id, "RS-PS-08-01", _valid_acute_answers())
    _patch(client, tok, aid, _valid_acute_answers(**{"person_info.province": "الف" * 60}))
    r = _finalize(client, tok, aid)
    assert r.status_code == 422, r.text
    fields = {e["field"]: e["error"] for e in r.json()["detail"]["errors"]}
    assert "person_info.province" in fields and "حداکثر طول مجاز" in fields["person_info.province"]


def test_unknown_keys_do_not_block_finalization(client, env):
    """سازگاری نسخه‌ها (B14): کلید خارج از تعریف نسخه، خطا نمی‌سازد."""
    tok, case_id = _acute_case(client, env, "RS-TEST-V24-07")
    answers = _valid_acute_answers(**{"legacy_field_from_old_version": "قابل عبور"})
    aid = _create(client, tok, case_id, "RS-PS-08-01", answers)
    r = _finalize(client, tok, aid)
    assert r.status_code == 200, r.text


def test_new_form_versions_and_fields_present(client, env):
    tok = login(client, "t_counsa")
    # فرم تلفنی v2 — تاریخ فرم
    r = client.get(f"{API}/forms/RS-PS-01-01", headers=bearer(tok))
    assert r.json()["version"] == 2
    sec_keys = {s["key"] for s in r.json()["definition"]["sections"]}
    assert "form_header" in sec_keys

    # فرم پرونده v4 — اطلاعات فردی و اجتماعی + گزینه‌های افزوده MSE
    r = client.get(f"{API}/forms/RS-PS-04-01", headers=bearer(tok))
    assert r.json()["version"] == 4
    sections = {s["key"]: s for s in r.json()["definition"]["sections"]}
    assert "person_snapshot" in sections
    snap_fields = {f["key"] for f in sections["person_snapshot"]["fields"]}
    assert {"marital_status", "education", "job", "referral_source", "residence_contact"} <= snap_fields
    thought = next(s for k, s in sections.items() if k == "mse_thought_content")
    theme_values = {o["value"] for o in thought["fields"][0]["options"]}
    assert {"thought_insertion", "nihilistic", "erotomanic", "deprivation", "fear"} <= theme_values

    # فرم مورد حاد v2 — تاریخ فرم + فهرست فرم‌ها نسخه جدید را می‌دهد
    r = client.get(f"{API}/forms/RS-PS-08-01", headers=bearer(tok))
    assert r.json()["version"] == 2
