"""تعریف فرم RS-PS-08-01 — فرم ارزیابی و مدیریت مورد حاد / پر خطر (نسخه ۲)

مطابق فرم پیوست (کد فرم: RS-PS-08-01 — نسخه کدگذاری‌شده فرم) و سند جامع v0.2 بخش ۰۴:
- سربرگ: تاریخ فرم
- اطلاعات فردی: نام و نام خانوادگی، سن، کد ملی، شماره تماس، استان، شهرستان، آدرس
- ارزیابی اولیه: کد مورد حاد، نوع خطر (چندگزینه‌ای)، شدت و فوریت (سه سطح)،
  افکار یا رفتار خطرناک فعلی، سابقه قبلی (اختلالات روانپزشکی، بستری، اقدام به خودکشی)،
  عوامل خطر/برنامه/قصد یا دسترسی به وسیله، عوامل محافظت‌کننده، اقدام فوری انجام‌شده
- اطلاعات ارجاع: مسئول اطلاع‌رسانی یا ارجاع، روز و ساعت ارجاع، مرجع ارجاع‌شده،
  نتیجه تماس و پذیرش مقصد، مسئول پیگیری، زمان پیگیری، وضعیت نهایی
- کارشناس نظارت حرفه‌ای: نام و نام خانوادگی

تغییرات نسخه ۲ (فاز ۲۴ — بدون تغییر معنای پاسخ‌های ثبت‌شده):
- افزودن فیلد «تاریخ فرم» مطابق سربرگ فرم پیوست
- افزودن سقف طول و قالب فیلدها (تماس، کد ملی با رقم کنترل، سن عددی) مطابق بخش ۰۴ سند
- اعتبارسنجی نهایی‌سازی نسخه‌آگاه بر اساس تعریف نسخه ذخیره‌شده همان ارزیابی (B14)

قواعد:
- «شدت و فوریت» سه سطح دارد: سطح ۱ (نیازمند پایش)، سطح ۲ (متوسط)، سطح ۳ (بالا).
- تشخیص خودکار و نمره خطر خودکار وجود ندارد؛ تنها قاعده ساختاری: با ثبت سطح ۳،
  تکمیل اطلاعات ارجاع برای نهایی‌سازی الزامی است.
- هشدار سطح ۳ به‌صورت خودکار در کارتابل مسئول فنی (فاز ۲۳) ظاهر می‌شود.
"""
from typing import Any

from app.core.form_common import canonicalize_answers, format_and_range_errors

FORM_CODE = "RS-PS-08-01"
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
    _sec("person_info", "اطلاعات فردی", [
        _f("full_name", "نام و نام خانوادگی", "text", True, max_length=150),
        _f("age", "سن", "text", False, format="integer", min=0, max=120, max_length=3),
        _f("national_id", "کد ملی", "text", False, format="national_id", max_length=10),
        _f("phone", "شماره تماس", "text", True, format="phone", max_length=11),
        _f("province", "استان", "text", True, max_length=50),
        _f("county", "شهرستان", "text", False, max_length=50),
        _f("address", "آدرس", "textarea", False, max_length=500),
    ]),
    _sec("initial_assessment", "ارزیابی اولیه", [
        _f("acute_code", "کد مورد حاد", max_length=50),
        _f("risk_types", "نوع خطر", "multiselect", True, [
            _o("suicidal_ideation", "افکار خودکشی یا آسیب به خود"),
            _o("suicide_attempt", "قصد یا اقدام به خودکشی"),
            _o("harm_to_others", "آسیب به دیگران"),
            _o("child_abuse", "کودک‌آزاری"),
            _o("violence", "خشونت"),
            _o("severe_crisis", "بحران شدید"),
            _o("other", "سایر"),
        ]),
        _f("risk_types_other", "شرح نوع خطر سایر", max_length=255),
        _f("severity", "شدت و فوریت", "select", True, [
            _o("level_1", "سطح ۱ (نیازمند پایش)"),
            _o("level_2", "سطح ۲ (متوسط)"),
            _o("level_3", "سطح ۳ (بالا)"),
        ]),
        _f("current_dangerous_thoughts", "افکار یا رفتار خطرناک فعلی", "textarea", True),
        _f("psych_history", "سابقه قبلی — اختلالات روانپزشکی", "textarea"),
        _f("hospitalization_history", "سابقه قبلی — بستری در بیمارستان روانپزشکی", "textarea"),
        _f("suicide_attempt_history", "سابقه قبلی — اقدام به خودکشی", "textarea"),
        _f("risk_factors_access", "عوامل خطر، برنامه، قصد یا دسترسی به وسیله (در صورت مرتبط بودن)", "textarea"),
        _f("protective_factors", "عوامل محافظت‌کننده و حمایت در دسترس", "textarea"),
        _f("immediate_action", "اقدام فوری انجام‌شده", "textarea", True),
    ]),
    _sec("referral_info", "اطلاعات ارجاع", [
        _f("referral_responsible", "مسئول اطلاع‌رسانی یا ارجاع", max_length=150),
        _f("referral_datetime", "روز و ساعت ارجاع", max_length=100),
        _f("referral_destination", "مرجع ارجاع‌شده", max_length=150),
        _f("referral_result", "نتیجه تماس و پذیرش مقصد", "textarea"),
        _f("followup_responsible", "مسئول پیگیری", max_length=150),
        _f("followup_time", "زمان پیگیری", max_length=100),
        _f("final_status", "وضعیت نهایی", "textarea"),
    ]),
    _sec("supervision", "نظارت حرفه‌ای", [
        _f("supervisor_name", "نام و نام خانوادگی کارشناس نظارت حرفه‌ای", max_length=150),
        _f("supervisor_note", "ملاحظات کارشناس نظارت حرفه‌ای", "textarea"),
    ]),
]

FORM_DEFINITION = {"code": FORM_CODE, "version": FORM_VERSION, "sections": FORM_SECTIONS}

REQUIRED_AT_FINALIZE: list[tuple[str, str]] = [
    ("person_info.full_name", "نام و نام خانوادگی"),
    ("person_info.phone", "شماره تماس"),
    ("initial_assessment.risk_types", "نوع خطر"),
    ("initial_assessment.severity", "شدت و فوریت"),
    ("initial_assessment.current_dangerous_thoughts", "افکار یا رفتار خطرناک فعلی"),
    ("initial_assessment.immediate_action", "اقدام فوری انجام‌شده"),
    ("referral_info.followup_responsible", "مسئول پیگیری"),
    ("referral_info.followup_time", "زمان پیگیری"),
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
    # نوع خطر «سایر» بدون شرح، معنادار نیست
    risk_types = answers.get("initial_assessment.risk_types") or []
    if isinstance(risk_types, list) and "other" in risk_types:
        other = answers.get("initial_assessment.risk_types_other")
        if other is None or (isinstance(other, str) and not other.strip()):
            errors.append({
                "field": "initial_assessment.risk_types_other",
                "label": "شرح نوع خطر سایر",
                "error": "با انتخاب نوع خطر «سایر»، شرح آن الزامی است",
            })
    # قاعده ساختاری سطح ۳: سند اقدام فوری باید کامل باشد (اطلاعات ارجاع)
    if answers.get("initial_assessment.severity") == "level_3":
        for path, label in (
            ("referral_info.referral_responsible", "مسئول اطلاع‌رسانی یا ارجاع"),
            ("referral_info.referral_destination", "مرجع ارجاع‌شده"),
            ("referral_info.referral_result", "نتیجه تماس و پذیرش مقصد"),
        ):
            v = answers.get(path)
            if v is None or (isinstance(v, str) and not v.strip()):
                errors.append({
                    "field": path, "label": label,
                    "error": "با ثبت سطح فوریت ۳ (بالا)، تکمیل اطلاعات ارجاع برای نهایی‌سازی الزامی است",
                })
    errors += format_and_range_errors(answers, definition or FORM_DEFINITION)
    return errors
