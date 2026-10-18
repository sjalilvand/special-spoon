"""تعریف فرم RS-PS-01-01 — فرم پذیرش اولیه مراجعان تلفنی (نسخه ۲)

مطابق فرم پیوست (کد فرم: RS-PS-01-01) و سند جامع v0.2 بخش ۰۴ (فاز ۲۴):
- سربرگ: تاریخ فرم
- اطلاعات فردی مراجع: نام و نام خانوادگی، سن، کد ملی، شماره تماس، استان، شهرستان،
  نوع مراجع (مددجو آزاد/سایر)، جنسیت
- ارزیابی اولیه: موضوع مراجعه (خانواده/فردی/ازدواج/کودک و نوجوان/تحصیلی/بحران/سایر)
  و توضیحات (شرح مختصر مشکل و اقدامات انجام‌شده)
- اطلاعات تماس: نام مشاور و تاریخ تماس
- تعیین مسیر مراجع (سامانه‌ای): پذیرش حضوری / مورد حاد / اطلاع‌رسانی / تماس مجدد
- کارشناس نظارت حرفه‌ای: نام و نام خانوادگی

تغییرات نسخه ۲ نسبت به نسخه ۱ (بدون تغییر معنای پاسخ‌های ثبت‌شده):
- افزودن فیلد «تاریخ فرم» مطابق سربرگ فرم پیوست
- افزودن سقف طول و قالب فیلدها (موبایل، کد ملی با رقم کنترل، سن عددی) مطابق بخش ۰۴ سند
- اعتبارسنجی نهایی‌سازی نسخه‌آگاه شد: قواعد قالب بر اساس تعریف نسخه ذخیره‌شده
  همان ارزیابی اعمال می‌شود (B14 — پاسخ‌ها به تعریف نسخه خودشان متصل می‌مانند)

قواعد:
- این فرم مرحله نخست گردش کار است؛ خروجی آن تعیین مسیر مراجع است.
- تشخیص خودکار و نمره خطر خودکار وجود ندارد؛ موضوع «بحران» صرفاً ثبت‌شدنی است.
"""
from typing import Any

from app.core.form_common import canonicalize_answers, format_and_range_errors

FORM_CODE = "RS-PS-01-01"
FORM_VERSION = 2


def _o(value: str, label: str) -> dict:
    return {"value": value, "label": label}


def _f(key: str, label: str, ftype: str = "text", required: bool = False,
       options: list | None = None, **extra) -> dict:
    return {"key": key, "label": label, "type": ftype, "required": required, "options": options or [], **extra}


def _sec(key: str, title: str, fields: list) -> dict:
    return {"key": key, "title": title, "fields": fields}


FORM_SECTIONS: list[dict[str, Any]] = [
    _sec("form_header", "سربرگ فرم", [
        _f("form_date", "تاریخ فرم (شمسی)", "text", False, max_length=20),
    ]),
    _sec("caller_info", "اطلاعات فردی مراجع", [
        _f("full_name", "نام و نام خانوادگی", "text", True, max_length=150),
        _f("age", "سن", "text", False, format="integer", min=0, max=120, max_length=3),
        _f("national_id", "کد ملی", "text", False, format="national_id", max_length=10),
        _f("phone", "شماره تماس", "text", True, format="phone", max_length=11),
        _f("province", "استان", "text", True, max_length=50),
        _f("county", "شهرستان", "text", False, max_length=50),
        _f("applicant_type", "نوع مراجع", "select", False, [
            _o("free_applicant", "مددجو آزاد"),
            _o("other", "سایر"),
        ]),
        _f("applicant_type_note", "توضیح نوع مراجع (در صورت انتخاب سایر)", max_length=255),
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
        _f("subject_other", "شرح موضوع سایر", max_length=255),
        _f("description", "توضیحات (شرح مختصر مشکل و اقدامات انجام‌شده)", "textarea", True),
    ]),
    _sec("contact_info", "اطلاعات تماس", [
        _f("counselor_name", "نام مشاور", "text", True, max_length=150),
        _f("call_date", "تاریخ تماس (شمسی)", "text", True, max_length=20),
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
        _f("supervisor_name", "نام و نام خانوادگی کارشناس نظارت حرفه‌ای", max_length=150),
        _f("supervisor_note", "ملاحظات کارشناس نظارت حرفه‌ای", "textarea"),
    ]),
]

FORM_DEFINITION = {"code": FORM_CODE, "version": FORM_VERSION, "sections": FORM_SECTIONS}

REQUIRED_AT_FINALIZE: list[tuple[str, str]] = [
    ("caller_info.full_name", "نام و نام خانوادگی مراجع"),
    ("caller_info.phone", "شماره تماس"),
    ("caller_info.province", "استان"),
    ("initial_assessment.subject", "موضوع مراجعه"),
    ("initial_assessment.description", "شرح مختصر مشکل و اقدامات انجام‌شده"),
    ("contact_info.counselor_name", "نام مشاور"),
    ("contact_info.call_date", "تاریخ تماس"),
    ("routing.route", "تعیین مسیر مراجع"),
]


def normalize_answers(answers: dict, definition: dict | None = None) -> dict:
    """نرمال‌سازی پاسخ‌ها (ارقام فارسی، قالب تلفن/کد ملی، حذف فاصله‌های زائد)."""
    return canonicalize_answers(answers, definition or FORM_DEFINITION)


def validate_finalization(answers: dict, definition: dict | None = None) -> list[dict]:
    """اعتبارسنجی سمت سرور هنگام نهایی‌سازی — الزامات + قالب/سقف طول نسخه‌آگاه."""
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
    errors += format_and_range_errors(answers, definition or FORM_DEFINITION)
    return errors
