"""تعریف فرم RS-PS-04-01 — نسخه ۲ (سند v1.00، اصلاحات روشن اعمال‌شده)

قواعد:
- نسخه ۱ حفظ شده است؛ ارزیابی‌های قدیمی به نسخه خودشان متصل‌اند و رندرشان
  با definition همان نسخه انجام می‌شود (تغییر گزینه‌ها معنای پاسخ قبلی را عوض نمی‌کند).
- «ارزیابی نشده» از «طبیعی» متمایز است؛ «اطلاعات کافی موجود نیست» قابل ثبت است.
- گزینه‌های علامت‌گذاری‌شده با (نیازمند تأیید تخصصی) پیش از استفاده بالینی نهایی می‌شوند.
- تشخیص خودکار و نمره خطر خودکار وجود ندارد.
"""
from typing import Any

FORM_CODE = "RS-PS-04-01"
FORM_VERSION = 2


def _o(value: str, label: str) -> dict:
    return {"value": value, "label": label}


NA = _o("not_assessed", "ارزیابی نشده")
INSUF = _o("insufficient_info", "اطلاعات کافی موجود نیست")
NORMAL = _o("normal", "طبیعی")


def _f(key: str, label: str, ftype: str = "text", required: bool = False, options: list | None = None) -> dict:
    return {"key": key, "label": label, "type": ftype, "required": required, "options": options or []}


def _sec(key: str, title: str, fields: list) -> dict:
    return {"key": key, "title": title, "fields": fields}


FORM_SECTIONS: list[dict[str, Any]] = [
    _sec("chief_complaint", "شکایت اصلی", [
        _f("description", "شرح شکایت اصلی", "textarea", True),
        _f("duration", "مدت مشکل"),
        _f("reason", "علت مراجعه", "textarea"),
    ]),
    _sec("current_history", "تاریخچه مشکل فعلی", [
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
    ]),
    _sec("psych_history", "سابقه روان‌پزشکی", [
        _f("prior_treatment", "مراجعه/درمان قبلی", "select", False, [
            _o("no", "خیر"), _o("yes", "بله"), INSUF,
        ]),
        _f("hospitalization", "بستری قبلی", "select", False, [
            _o("no", "خیر"), _o("yes", "بله"), INSUF,
        ]),
        _f("details", "شرح درمان و نتیجه قبلی", "textarea"),
    ]),
    _sec("medical_history", "سابقه پزشکی", [
        _f("conditions", "بیماری‌ها و شرایط مرتبط", "textarea"),
        _f("medical_visits", "سابقه مراجعات پزشکی (نام مراجع، تاریخ تقریبی، نتیجه)", "textarea"),
    ]),
    _sec("medication", "دارو و حساسیت", [
        _f("current", "داروهای جاری", "textarea"),
        _f("allergies", "حساسیت‌های گزارش‌شده", "textarea"),
    ]),
    _sec("personal_history", "تاریخچه شخصی", [
        _f("development", "رشد", "textarea"),
        _f("education_work", "تحصیل و کار", "textarea"),
        _f("relationships", "روابط", "textarea"),
        _f("supports", "منابع حمایت", "textarea"),
    ]),
    _sec("family_history", "تاریخچه خانوادگی", [
        _f("structure", "ساختار و روابط", "textarea"),
        _f("relevant", "سوابق مرتبط خانوادگی", "textarea"),
    ]),
    _sec("substance", "مصرف مواد", [
        _f("status", "وضعیت مصرف", "select", False, [_o("no", "خیر"), _o("yes", "بله"), NA]),
        _f("details", "شرح (فقط در صورت ضرورت بالینی)", "textarea"),
    ]),
    _sec("sources", "منابع و محدودیت‌ها", [
        _f("info_source", "منبع اطلاعات"),
        _f("limitations", "محدودیت ارزیابی", "textarea"),
        _f("insufficient_info", "اطلاعات کافی موجود نیست", "boolean"),
    ]),
    # ---------- MSE ----------
    _sec("mse_appearance", "MSE — الف) ظاهر", [
        _f("cover", "تظاهر پوشش", "select", False, [
            _o("appropriate", "مناسب"), _o("inappropriate", "نامناسب"), NA,
        ]),
        _f("grooming", "وضعیت آراستگی", "select", False, [
            NORMAL, _o("untidy", "نامرتب"), NA,
        ]),
        _f("jewelry", "آرایش و زیورآلات", "select", False, [
            NORMAL, _o("unusual", "غیرمعمول"), NA,
        ]),
        _f("apparent_age", "سن ظاهری (کمتر از سن واقعی / مطابق / بیشتر)"),
        _f("note", "توضیحات ظاهر", "textarea"),
    ]),
    _sec("mse_psychomotor", "MSE — ب) وضعیت روانی-حرکتی", [
        _f("state", "وضعیت", "select", False, [
            NORMAL, _o("trembling", "تردی"), _o("hyperactivity", "افزایش فعالیت"),
            _o("retardation", "کندی روانی-حرکتی"), _o("tremor", "لرزش"),
            _o("aimless", "فعالیت بی‌هدف"), _o("stereotypy", "حرکات با رفتارهای تکراری"),
            _o("echopraxia", "تقلید حرکات دیگران"), _o("abnormal_limbs", "وضعیت غیرمعمول اندام‌ها"),
            _o("other", "سایر"), NA,
        ]),
        _f("note", "توضیحات", "textarea"),
    ]),
    _sec("mse_speech", "MSE — ج) تکلم", [
        _f("speed", "سرعت", "select", False, [NORMAL, _o("fast", "سریع"), _o("slow", "هسته"), NA]),
        _f("amount", "میزان/جریان", "select", False, [
            NORMAL, _o("poverty", "کم‌حرفی"), _o("pressured", "پرگویی"),
            _o("blocking", "قطع‌شدگی/فقر تکلم"), NA,
        ]),
        _f("loudness", "بلندی صدا", "select", False, [NORMAL, _o("loud", "بلند"), _o("whisper", "هسته"), NA]),
        _f("tone", "آهنگ صدا", "select", False, [NORMAL, _o("monotone", "یک‌نواخت"), _o("pitchy", "نوسانی"), NA]),
        _f("fluency", "روانی تکلم", "select", False, [NORMAL, _o("dysfluent", "ناروان"), _o("stutter", "لکنت"), NA]),
        _f("other_speech", "سایر ویژگی‌های تکلم", "select", False, [
            _o("echolalia", "تقلید کلمات"), _o("neologism", "کلمات ساختگی"), _o("none", "سایر"), NA,
        ]),
        _f("note", "توضیحات"),
    ]),
    _sec("mse_thought_form", "MSE — د) تفکر (فرم و جریان)", [
        _f("form", "فرم فکر", "select", False, [
            NORMAL, _o("disorganized", "گسیختگی"), _o("flight", "پرش افکار"),
            _o("retarded", "کندی جریان"), NA,
        ]),
        _f("flow", "جریان فکر", "select", False, [
            NORMAL, _o("circumstantial", "درگیری کلامی مفرط"), _o("tangential", "دوری از موضوع"), NA,
        ]),
        _f("note", "توضیحات (محتوای فکر در بخش مستقل بعدی ثبت می‌شود)", "textarea"),
    ]),
    _sec("mse_thought_content", "MSE — ه) محتوای فکر", [
        _f("themes", "مضامین مشاهده‌شده (هر مورد لازم شد انتخاب شود)", "multiselect", False, [
            _o("grandiosity", "هذیان بزرگ‌منشی"), _o("reference", "هذیان انتشار"),
            _o("persecution", "هذیان گزند و آسیب"), _o("guilt", "هذیان گناه"),
            _o("poverty", "هذیان فقر"), _o("somatic", "هذیان جسمانی"),
            _o("control", "هذیان کنترل"), _o("thought_withdrawal", "ربایش فکر"),
            _o("thought_broadcasting", "پخش فکر"), _o("infidelity", "هذیان حسادت/بی‌وفایی"),
            _o("disorganized_ideas", "ایده‌های بی‌سازمان (هذیان بی‌سازمان)"),
            _o("hypochondriasis", "هذیان جسمانی (هذیان بیماری)"), _o("other", "سایر"),
        ]),
        _f("detail", "شرح بالینی مورد مشاهده‌شده", "textarea"),
        _f("timing", "زمان مشاهده"),
    ]),
    _sec("mse_mood", "MSE — و) خلق و عاطفه", [
        _f("mood", "خلق", "select", False, [
            NORMAL, _o("depressed", "افسرده"), _o("anxious", "مضطرب"),
            _o("irritable", "تحریک‌پذیر"), _o("angry", "خشمگین"),
            _o("elevated", "بالا (با سرخوشی)"), _o("subjective", "توصیف مراجع"), _o("other", "سایر"), NA,
        ]),
        _f("affect", "عاطفه (مشاهده‌گر)", "select", False, [
            NORMAL, _o("restricted", "محدود"), _o("slowed", "کند"), _o("flat", "تخت"),
            _o("blunted", "کاهش شدید بیان هیجانی"), _o("labile", "بی‌ثبات"),
            _o("incongruent", "ناهماهنگ با گفتار"), _o("other", "سایر"), NA,
        ]),
        _f("note", "توضیحات مشاهده‌گر", "textarea"),
    ]),
    _sec("mse_perception", "MSE — ز) ادراک", [
        _f("state", "وضعیت", "select", False, [
            _o("intact", "بدون اختلال گزارش‌شده یا مشاهده‌شده"), _o("illusion", "خطای حسی"),
            _o("hallucination", "توهم"), _o("other", "سایر تجربه‌های ادراکی"), NA,
        ]),
        _f("hallucination_type", "نوع توهم (فقط با تأیید مسئول فنی)", "select", False, [
            _o("auditory", "شنیداری"), _o("visual", "بینایی"), _o("olfactory", "بویایی"),
            _o("gustatory", "چشایی"), _o("tactile", "لمسی"), NA,
        ]),
        _f("hallucination_note", "توضیح توهم", "textarea"),
        _f("note", "توضیحات ادراک", "textarea"),
    ]),
    _sec("mse_cognition", "MSE — ح) وضعیت شناختی و هوشیاری", [
        _f("memory_immediate", "حافظه فوری", "select", False, [NORMAL, _o("impaired", "مختل"), NA]),
        _f("memory_recent", "حافظه نزدیک", "select", False, [NORMAL, _o("impaired", "مختل"), NA]),
        _f("memory_remote", "حافظه دور", "select", False, [NORMAL, _o("impaired", "مختل"), NA]),
        _f("orientation_time", "تلفظ به زمان", "select", False, [
            _o("intact", "درست"), _o("partial", "ناقص"), _o("impaired", "مختل"), NA,
        ]),
        _f("orientation_place", "تلفظ به مکان", "select", False, [
            _o("intact", "درست"), _o("partial", "ناقص"), _o("impaired", "مختل"), NA,
        ]),
        _f("orientation_person", "تلفظ به شخص", "select", False, [
            _o("intact", "درست"), _o("partial", "ناقص"), _o("impaired", "مختل"), NA,
        ]),
        _f("consciousness", "سطح هوشیاری", "select", False, [
            _o("alert", "هوشیار"), _o("drowsy", "خواب‌آلود"), _o("stupor", "نیمه‌هوشیار"),
            _o("coma", "بی‌هوش"), NA,
        ]),
        _f("attention", "توجه و تمرکز", "select", False, [NORMAL, _o("impaired", "مختل"), NA]),
        _f("cognition", "معلومات و توانایی شناختی", "select", False, [NORMAL, _o("impaired", "مختل"), NA]),
        _f("tool", "ابزار ارزیابی (نام آزمون و روش، در صورت استفاده)"),
        _f("note", "توضیحات شناخت", "textarea"),
    ]),
    _sec("mse_additional", "MSE — ط) تکمیل پیشنهادی ارزیابی", [
        _f("insight", "بینش", "select", False, [
            _o("good", "خوب"), _o("partial", "نسبی"), _o("absent", "فاقد"), NA,
        ]),
        _f("judgment", "قضاوت", "select", False, [
            _o("intact", "سالم"), _o("impaired", "مختل"), NA,
        ]),
        _f("functioning", "عملکرد روزمره، شغلی و اجتماعی", "textarea"),
        _f("supports", "عوامل حمایتی", "textarea"),
        _f("referral_needed", "نیاز به ارجاع یا اقدام تکمیلی", "select", False, [
            _o("no", "خیر"), _o("internal", "داخلی"), _o("external", "خارجی"),
        ]),
    ]),
    _sec("risk", "ارزیابی خطر و اقدام پیشنهادی", [
        _f("self_harm", "افکار یا رفتار مرتبط با آسیب به خود", "select", False, [
            _o("denied", "انکار"), _o("ideation", "افکار"), _o("history", "سابقه"), _o("current", "فعال"), NA,
        ]),
        _f("harm_to_others", "افکار یا رفتار مرتبط با آسیب به دیگران", "select", False, [
            _o("denied", "انکار"), _o("ideation", "افکار"), _o("history", "سابقه"), _o("current", "فعال"), NA,
        ]),
        _f("vulnerability", "نگرانی درباره خشونت، سوءاستفاده یا آسیب‌پذیری", "select", False, [
            _o("no", "خیر"), _o("suspected", "مشکوک"), _o("confirmed", "مستند"), NA,
        ]),
        _f("support_factors", "عوامل حمایتی", "textarea"),
        _f("findings", "یافته‌ها", "textarea"),
        _f("risk_summary", "جمع‌بندی حرفه‌ای خطر", "textarea", True),
        _f("risk_action", "اقدام انجام‌شده و پیگیری", "textarea", True),
    ]),
    _sec("summary", "جمع‌بندی", [
        _f("professional_summary", "توضیح حرفه‌ای", "textarea", True),
        _f("referral_note", "توضیح ارجاع"),
    ]),
    _sec("diagnosis", "تشخیص", [
        _f("status", "وضعیت", "select", True, [
            _o("confirmed", "قطعی"), _o("probable", "محتمل"),
            _o("under_review", "در حال بررسی"), _o("none", "ندارد"),
        ]),
        _f("title", "عنوان تشخیص (واژگان مصوب)"),
        _f("code", "کد (اختیاری)"),
        _f("comorbid", "تشخیص‌های افزایشی"),
        _f("note", "توضیح"),
    ]),
    _sec("treatment_plan", "طرح درمان", [
        _f("goals", "اهداف درمان", "textarea"),
        _f("approach", "رویکرد/پروتکل", "select", False, [
            _o("cbt", "شناختی-رفتاری"), _o("act", "پذیرش و تعهد"),
            _o("schema", "طرح‌واره"), _o("psychodynamic", "روان‌پویشی"),
            _o("family", "خانواده‌درمانی"), _o("medical", "دارودرمانی هماهنگ"),
            _o("other", "سایر"), NA,
        ]),
        _f("approach_note", "توضیح رویکرد"),
        _f("protocol_name", "نام و نسخه پروتکل"),
        _f("sessions_count", "تعداد جلسات پیشنهادی"),
        _f("session_interval", "فاصله جلسات (عدد و واحد)"),
        _f("interventions", "مداخلات برنامه‌ریزی‌شده", "textarea"),
        _f("external_referral", "ارجاع به مرکز دیگر (مقصد، علت، تاریخ)"),
        _f("review_date", "تاریخ بازبینی برنامه"),
        _f("remarks", "ملاحظات", "textarea"),
    ]),
    _sec("remarks", "ملاحظات تکمیلی", [
        _f("notes", "متن تکمیلی", "textarea"),
    ]),
]

FORM_DEFINITION = {"code": FORM_CODE, "version": FORM_VERSION, "sections": FORM_SECTIONS}

REQUIRED_AT_FINALIZE: list[tuple[str, str]] = [
    ("chief_complaint.description", "شرح شکایت اصلی"),
    ("risk.risk_summary", "جمع‌بندی حرفه‌ای خطر"),
    ("risk.risk_action", "اقدام و پیگیری خطر"),
    ("summary.professional_summary", "توضیح حرفه‌ای جمع‌بندی"),
    ("diagnosis.status", "وضعیت تشخیص"),
]


def validate_finalization(answers: dict) -> list[dict]:
    """اعتبارسنجی سمت سرور هنگام نهایی‌سازی."""
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
