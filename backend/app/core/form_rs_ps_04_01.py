"""تعریف نسخه اول فرم RS-PS-04-01 (بند ۶.۲ سند)

- ساختار ثابت اما نسخه‌دار؛ نسخه در پایگاه داده ثبت می‌شود.
- گزینه «ارزیابی نشده» از «طبیعی» متمایز است.
- «اطلاعات کافی موجود نیست» قابل ثبت است.
- تشخیص و نمره خطر خودکار وجود ندارد؛ فیلدهای خطر ورودی حرفه‌ای متن هستند.
- اطلاعات هویتی در JSON فرم تکرار نمی‌شود.
"""

FORM_CODE = "RS-PS-04-01"
FORM_VERSION = 1


def _o(value: str, label: str) -> dict:
    return {"value": value, "label": label}


NA = _o("not_assessed", "ارزیابی نشده")
INSUF = _o("insufficient_info", "اطلاعات کافی موجود نیست")
NORMAL = _o("normal", "طبیعی")


def _f(key: str, label: str, ftype: str = "text", required: bool = False, options: list | None = None) -> dict:
    return {"key": key, "label": label, "type": ftype, "required": required, "options": options or []}


FORM_SECTIONS: list[dict] = [
    {"key": "chief_complaint", "title": "شکایت اصلی", "fields": [
        _f("description", "شرح شکایت اصلی", "textarea", True),
        _f("duration", "مدت مشکل"),
        _f("reason", "علت مراجعه", "textarea"),
    ]},
    {"key": "current_history", "title": "تاریخچه مشکل فعلی", "fields": [
        _f("onset", "شروع"),
        _f("course", "سیر", "select", False, [
            _o("improving", "بهبود"), _o("stable", "ثابت"), _o("worsening", "تشدید"),
            _o("fluctuating", "نوسانی"), NA, INSUF,
        ]),
        _f("severity", "شدت", "select", False, [
            _o("mild", "خفیف"), _o("moderate", "متوسط"), _o("severe", "شدید"), NA,
        ]),
        _f("factors", "عوامل مؤثر", "textarea"),
        _f("impact", "اثر بر عملکرد", "textarea"),
    ]},
    {"key": "psych_history", "title": "سابقه روان‌پزشکی", "fields": [
        _f("prior_treatment", "مراجعه/درمان قبلی", "select", False, [
            _o("no", "خیر"), _o("yes", "بله"), INSUF,
        ]),
        _f("details", "شرح بستری/درمان و نتیجه قبلی", "textarea"),
    ]},
    {"key": "medical_history", "title": "سابقه پزشکی", "fields": [
        _f("conditions", "بیماری‌ها و شرایط مرتبط", "textarea"),
        _f("treatment", "درمان جاری پزشکی", "textarea"),
    ]},
    {"key": "medication", "title": "دارو و حساسیت", "fields": [
        _f("current", "داروهای جاری", "textarea"),
        _f("allergies", "حساسیت‌های گزارش‌شده", "textarea"),
    ]},
    {"key": "personal_history", "title": "تاریخچه شخصی", "fields": [
        _f("development", "رشد", "textarea"),
        _f("education_work", "تحصیل و کار", "textarea"),
        _f("relationships", "روابط", "textarea"),
        _f("supports", "منابع حمایت", "textarea"),
    ]},
    {"key": "family_history", "title": "تاریخچه خانوادگی", "fields": [
        _f("structure", "ساختار و روابط", "textarea"),
        _f("relevant", "سوابق مرتبط خانوادگی", "textarea"),
    ]},
    {"key": "substance", "title": "مصرف مواد", "fields": [
        _f("status", "وضعیت مصرف", "select", False, [_o("no", "خیر"), _o("yes", "بله"), NA]),
        _f("details", "شرح (فقط در صورت ضرورت بالینی)", "textarea"),
    ]},
    {"key": "sources", "title": "منابع و محدودیت‌ها", "fields": [
        _f("info_source", "منبع اطلاعات"),
        _f("limitations", "محدودیت ارزیابی", "textarea"),
        _f("insufficient_info", "اطلاعات کافی موجود نیست", "boolean"),
    ]},
    {"key": "mse", "title": "معاینه وضعیت روانی (MSE)", "fields": [
        _f("appearance_cover", "پوشش", "select", False, [
            _o("appropriate", "مناسب"), _o("inappropriate", "نامناسب"), NA,
        ]),
        _f("appearance_grooming", "آراستگی", "select", False, [
            _o("tidy", "مرتب"), _o("untidy", "نامرتب"), NA,
        ]),
        _f("appearance_note", "توضیح ظاهر و سن ظاهری"),
        _f("psychomotor", "روانی-حرکتی", "select", False, [
            NORMAL, _o("hyper", "افزایش فعالیت"), _o("hypo", "کاهش فعالیت"),
            _o("tremor", "لرزش"), _o("stereotypy", "حرکات تکراری"), _o("other", "سایر"), NA,
        ]),
        _f("psychomotor_note", "توضیح روانی-حرکتی"),
        _f("speech", "تکلم", "select", False, [
            NORMAL, _o("pressure", "افزایش سرعت"), _o("slowed", "کاهش سرعت"),
            _o("poverty", "کم‌حرفی"), _o("elaborate", "پرحرفی"),
            _o("dysfluency", "اختلال روانی تکلم"), NA,
        ]),
        _f("speech_note", "توضیح تکلم"),
        _f("thought_form", "فرم فکر", "select", False, [
            NORMAL, _o("disorganized", "گسیختگی"), _o("flight", "پرش افکار"),
            _o("retarded", "کندی جریان"), NA,
        ]),
        _f("thought_content", "محتوای فکر", "select", False, [
            NORMAL, _o("delusion", "هذیان"), _o("obsession", "وسواس"),
            _o("anxious", "اضطراب غالب"), _o("self_harm_ideas", "افکار خودآسیبی"),
            _o("harm_ideas", "افکار آسیب به دیگران"), _o("other", "سایر"), NA,
        ]),
        _f("thought_note", "توضیح تفکر"),
        _f("mood", "خلق و عاطفه", "select", False, [
            _o("depressed", "افسرده"), _o("anxious", "اضطرابی"), _o("elevated", "بالا"),
            _o("irritable", "تحریک‌پذیر"), _o("flat", "تخت"), NA,
        ]),
        _f("mood_note", "توضیح خلق"),
        _f("perception", "ادراک", "select", False, [
            _o("intact", "بدون اختلال مشاهده‌شده/گزارش‌شده"), _o("hallucination", "توهم"),
            _o("illusion", "خطای حسی"), _o("other", "سایر"), NA,
        ]),
        _f("perception_note", "توضیح ادراک"),
        _f("memory_immediate", "حافظه فوری", "select", False, [NORMAL, _o("impaired", "مختل"), NA]),
        _f("memory_recent", "حافظه نزدیک", "select", False, [NORMAL, _o("impaired", "مختل"), NA]),
        _f("memory_remote", "حافظه دور", "select", False, [NORMAL, _o("impaired", "مختل"), NA]),
        _f("orientation", "جهت‌یابی", "select", False, [
            _o("intact", "کامل"), _o("partial", "ناقص"), _o("disoriented", "مختل"), NA,
        ]),
        _f("attention", "توجه", "select", False, [NORMAL, _o("impaired", "مختل"), NA]),
        _f("consciousness", "هوشیاری", "select", False, [
            _o("alert", "هوشیار"), _o("reduced", "کاهش‌یافته"), NA,
        ]),
        _f("insight", "بینش", "select", False, [
            _o("good", "خوب"), _o("partial", "نسبی"), _o("absent", "فاقد"), NA,
        ]),
        _f("judgment", "قضاوت", "select", False, [
            _o("intact", "سالم"), _o("impaired", "مختل"), NA,
        ]),
        _f("functioning", "عملکرد", "textarea"),
        _f("cognition_note", "توضیح شناخت"),
    ]},
    {"key": "risk", "title": "ارزیابی خطر", "fields": [
        _f("self_harm", "خطر خودآسیبی/خودکشی", "select", False, [
            _o("denied", "انکار"), _o("history", "سابقه"), _o("current", "فعال"), NA,
        ]),
        _f("harm_to_others", "خطر آسیب به دیگران", "select", False, [
            _o("denied", "انکار"), _o("history", "سابقه"), _o("current", "فعال"), NA,
        ]),
        _f("findings", "یافته‌ها", "textarea"),
        _f("risk_summary", "جمع‌بندی حرفه‌ای خطر", "textarea", True),
        _f("risk_action", "اقدام و پیگیری", "textarea", True),
    ]},
    {"key": "summary", "title": "جمع‌بندی", "fields": [
        _f("professional_summary", "توضیح حرفه‌ای", "textarea", True),
        _f("referral_needed", "نیاز به ارجاع", "select", False, [
            _o("no", "خیر"), _o("internal", "داخلی"), _o("external", "خارجی"),
        ]),
        _f("referral_note", "توضیح ارجاع"),
    ]},
    {"key": "diagnosis", "title": "تشخیص", "fields": [
        _f("status", "وضعیت", "select", True, [
            _o("confirmed", "قطعی"), _o("probable", "محتمل"),
            _o("under_review", "در حال بررسی"), _o("none", "ندارد"),
        ]),
        _f("title", "عنوان تشخیص"),
        _f("code", "کد (اختیاری)"),
        _f("note", "توضیح"),
    ]},
    {"key": "treatment_plan", "title": "طرح درمان", "fields": [
        _f("goals", "اهداف", "textarea"),
        _f("approach", "رویکرد"),
        _f("sessions", "جلسات پیشنهادی"),
        _f("review", "بازبینی"),
    ]},
    {"key": "remarks", "title": "ملاحظات", "fields": [
        _f("notes", "متن تکمیلی", "textarea"),
    ]},
]

FORM_DEFINITION = {"code": FORM_CODE, "version": FORM_VERSION, "sections": FORM_SECTIONS}

# فیلدهای لازم هنگام نهایی‌سازی (بند ۶.۲: هنگام نهایی‌سازی، فیلدهای لازم کنترل می‌شوند)
REQUIRED_AT_FINALIZE: list[tuple[str, str]] = [
    ("chief_complaint.description", "شرح شکایت اصلی"),
    ("risk.risk_summary", "جمع‌بندی حرفه‌ای خطر"),
    ("risk.risk_action", "اقدام و پیگیری خطر"),
    ("summary.professional_summary", "توضیح حرفه‌ای جمع‌بندی"),
    ("diagnosis.status", "وضعیت تشخیص"),
]


def validate_finalization(answers: dict) -> list[dict]:
    """اعتبارسنجی سمت سرور هنگام نهایی‌سازی - فهرست خطا با برچسب فارسی."""
    errors: list[dict] = []
    for path, label in REQUIRED_AT_FINALIZE:
        v = answers.get(path)
        if v is None or (isinstance(v, str) and not v.strip()) or v == "not_assessed":
            errors.append({"field": path, "label": label, "error": "تکمیل این فیلد برای نهایی‌سازی الزامی است"})
    ds = answers.get("diagnosis.status")
    if ds and ds != "none":
        t = answers.get("diagnosis.title")
        if t is None or (isinstance(t, str) and not t.strip()):
            errors.append({"field": "diagnosis.title", "label": "عنوان تشخیص",
                           "error": "با انتخاب وضعیت تشخیص، عنوان تشخیص الزامی است"})
    return errors
