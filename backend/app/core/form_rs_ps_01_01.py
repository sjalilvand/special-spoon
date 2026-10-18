"""تعریف فرم RS-PS-01-01 — فرم پذیرش اولیه مراجعان تلفنی (نسخه ۱)

مطابق سند فرم پیوست (کد فرم: RS-PS-01-01):
- اطلاعات فردی مراجع: نام و نام خانوادگی، سن، کد ملی، شماره تماس،
  استان، شهرستان، نوع مراجع، جنسیت
- ارزیابی اولیه: موضوع مراجعه (خانواده/فردی/ازدواج/کودک و نوجوان/تحصیلی/بحران/سایر)
  و توضیحات (شرح مختصر مشکل و اقدامات انجام‌شده)
- اطلاعات تماس: نام مشاور و تاریخ تماس
- کارشناس نظارت حرفه‌ای: نام و نام خانوادگی

قواعد:
- این فرم مرحله نخست گردش کار است؛ خروجی آن تعیین مسیر مراجع:
  پذیرش حضوری (RS-PS-04-01) یا فعال‌سازی فرایند مورد حاد/پرخطر (RS-PS-08-01).
- تشخیص خودکار و نمره خطر خودکار وجود ندارد؛ موضوع «بحران» صرفاً ثبت‌شدنی است و
  تصمیم مسیریابی با کارشناس/نظارت حرفه‌ای است.
- نسخه‌داری: پاسخ‌های ثبت‌شده به تعریف نسخه خودشان متصل می‌مانند.
"""
from typing import Any

FORM_CODE = "RS-PS-01-01"
FORM_VERSION = 1


def _o(value: str, label: str) -> dict:
    return {"value": value, "label": label}


def _f(key: str, label: str, ftype: str = "text", required: bool = False, options: list | None = None) -> dict:
    return {"key": key, "label": label, "type": ftype, "required": required, "options": options or []}


def _sec(key: str, title: str, fields: list) -> dict:
    return {"key": key, "title": title, "fields": fields}


FORM_SECTIONS: list[dict[str, Any]] = [
    _sec("caller_info", "اطلاعات فردی مراجع", [
        _f("full_name", "نام و نام خانوادگی", "text", True),
        _f("age", "سن"),
        _f("national_id", "کد ملی"),
        _f("phone", "شماره تماس", "text", True),
        _f("province", "استان", "text", True),
        _f("county", "شهرستان"),
        _f("applicant_type", "نوع مراجع", "select", False, [
            _o("free_applicant", "مددجو آزاد"),
            _o("other", "سایر"),
        ]),
        _f("applicant_type_note", "توضیح نوع مراجع (در صورت انتخاب سایر)"),
        _f("gender", "جنسیت", "select", False, [
            _o("female", "زن"),
            _o("male", "مرد"),
        ]),
    ]),
    _sec("initial_assessment", "ارزیابی اولیه", [
        _f("subject", "موضوع مراجعه", "multiselect", True, [
            _o("family", "خانواده"),
            _o("individual", "فردی"),
            _o("marriage", "ازدواج"),
            _o("child_teen", "کودک و نوجوان"),
            _o("education", "تحصیلی"),
            _o("crisis", "بحران"),
            _o("other", "سایر"),
        ]),
        _f("subject_other", "شرح موضوع سایر"),
        _f("description", "توضیحات (شرح مختصر مشکل و اقدامات انجام‌شده)", "textarea", True),
    ]),
    _sec("contact_info", "اطلاعات تماس", [
        _f("counselor_name", "نام مشاور", "text", True),
        _f("call_date", "تاریخ تماس", "text", True),
        _f("call_summary", "خلاصه تماس و مسیر پیشنهادی", "textarea"),
    ]),
    _sec("routing", "تعیین مسیر مراجع", [
        _f("route", "مسیر پیشنهادی پس از تماس", "select", True, [
            _o("inperson_intake", "پذیرش حضوری و تشکیل پرونده (RS-PS-04-01)"),
            _o("acute_case", "مورد حاد/پرخطر — فعال‌سازی فرایند مدیریت مورد حاد (RS-PS-08-01)"),
            _o("info_only", "فقط اطلاعات‌رسانی — نیاز به پذیرش ندارد"),
            _o("followup_call", "نیاز به تماس پیگیری مجدد"),
        ]),
        _f("routing_note", "توضیح تعیین مسیر", "textarea"),
    ]),
    _sec("supervision", "نظارت حرفه‌ای", [
        _f("supervisor_name", "نام و نام خانوادگی کارشناس نظارت حرفه‌ای"),
        _f("supervisor_note", "ملاحظات کارشناس نظارت حرفه‌ای", "textarea"),
    ]),
]

FORM_DEFINITION = {"code": FORM_CODE, "version": FORM_VERSION, "sections": FORM_SECTIONS}

REQUIRED_AT_FINALIZE: list[tuple[str, str]] = [
    ("caller_info.full_name", "نام و نام خانوادگی مراجع"),
    ("caller_info.phone", "شماره تماس"),
    ("initial_assessment.subject", "موضوع مراجعه"),
    ("initial_assessment.description", "شرح مختصر مشکل و اقدامات انجام‌شده"),
    ("contact_info.counselor_name", "نام مشاور"),
    ("contact_info.call_date", "تاریخ تماس"),
    ("routing.route", "تعیین مسیر مراجع"),
]


def validate_finalization(answers: dict) -> list[dict]:
    """اعتبارسنجی سمت سرور هنگام نهایی‌سازی."""
    errors: list[dict] = []
    for path, label in REQUIRED_AT_FINALIZE:
        v = answers.get(path)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
            errors.append({"field": path, "label": label, "error": "تکمیل این فیلد برای نهایی‌سازی الزامی است"})
    # موضوع «سایر» بدون شرح، معنادار نیست
    subjects = answers.get("initial_assessment.subject") or []
    if isinstance(subjects, list) and "other" in subjects:
        other = answers.get("initial_assessment.subject_other")
        if other is None or (isinstance(other, str) and not other.strip()):
            errors.append({
                "field": "initial_assessment.subject_other",
                "label": "شرح موضوع سایر",
                "error": "با انتخاب موضوع «سایر»، شرح آن الزامی است",
            })
    return errors
