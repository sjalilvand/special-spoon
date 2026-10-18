"""ابزارهای مشترک قواعد فرم‌ها — فاز ۲۴ (بازنویسی مطابق سند جامع v0.2، بخش ۰۴)

الزامات سند که این ماژول پوشش می‌دهد:
- «هر فیلد ضروری، سقف طول، قالب، یکتایی و پیام خطای مشخص داشته باشد»
  → سقف طول پیش‌فرض برای text/textarea + اعتبارسنجی قالب موبایل/تلفن/کد ملی/عدد صحیح.
- «شماره موبایل به قالب نرمال واحد تبدیل و برای موارد لازم یکتا شود»
  → تبدیل ارقام فارسی/عربی به لاتین و حذف جداکننده‌ها در فیلدهای قالب‌دار.
- «ویرایش موجودیت منتشرشده، داده تاریخی را بی‌اعتبار نکند» (B14)
  → اعتبارسنجی همیشه بر اساس تعریف نسخه ذخیره‌شده‌ی همان ارزیابی انجام می‌شود؛
    کلیدهای ناشناخته در نسخه جاری، خطا نمی‌سازند تا ارزیابی نسخه‌های قدین broken نشود.
"""
import re
from typing import Any

# ارقام فارسی (۰-۹) و عربی-هندی (٠-٩) → لاتین
_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_TABLE = str.maketrans(_FA_DIGITS + _AR_DIGITS, "01234567890123456789")

MOBILE_RE = re.compile(r"^09\d{9}$")          # موبایل ایران: ۱۱ رقم و شروع با ۰۹
PHONE_RE = re.compile(r"^0\d{9,10}$")          # تلفن تماس (موبایل یا ثابت با کد شهر)
NATIONAL_ID_RE = re.compile(r"^\d{10}$")       # کد ملی: دقیقاً ۱۰ رقم

DEFAULT_MAX_TEXT = 255        # سقف طول پیش‌فرض فیلدهای متنی کوتاه
DEFAULT_MAX_TEXTAREA = 5000   # سقف طول پیش‌فرض متن‌های بلند

FORMAT_MESSAGES = {
    "mobile": "قالب شماره موبایل نادرست است (مثال درست: 09121234567)",
    "phone": "قالب شماره تماس نادرست است (مثال درست: 09121234567 یا 02112345678)",
    "national_id": "کد ملی باید ۱۰ رقم معتبر باشد",
    "integer": "این فیلد باید عدد صحیح باشد",
}


def fa_to_en_digits(value: str) -> str:
    """تبدیل ارقام فارسی/عربی به لاتین."""
    return (value or "").translate(_DIGIT_TABLE)


def norm_text(value: str) -> str:
    """نرمال‌سازی متنی عمومی: تبدیل ارقام + حذف فاصله‌های ابتدا/انتها."""
    return fa_to_en_digits(value).strip()


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", fa_to_en_digits(value or ""))


def is_valid_national_id(value: str) -> bool:
    """رقم کنترل کد ملی ایران (الگوریتم استاندارد ضرب وزنی mod 11)."""
    if not NATIONAL_ID_RE.match(value):
        return False
    if value == value[0] * 10:  # همه ارقام یکسان نامعتبر است
        return False
    s = sum(int(value[i]) * (10 - i) for i in range(9))
    r = s % 11
    check = int(value[9])
    return check == r if r < 2 else check == 11 - r


def build_field_index(definition: dict | None) -> dict[str, dict]:
    """نمایه «مسیر فیلد → تعریف فیلد» از تعریف نسخه فرم (کلیدهای تخت نقطه‌دار)."""
    index: dict[str, dict] = {}
    if not definition:
        return index
    for section in definition.get("sections", []):
        for f in section.get("fields", []):
            index[f"{section['key']}.{f['key']}"] = f
    return index


def canonicalize_answers(answers: dict, definition: dict | None) -> dict:
    """نرمال‌سازی مقادیر بر اساس قالب فیلدهای نسخه فرم.

    - همه رشته‌ها: تبدیل ارقام فارسی/عربی + strip
    - فیلدهای قالب‌دار (mobile/phone/national_id/integer): فقط رقم می‌ماند؛
      مقدار خالی به None تبدیل می‌شود تا بررسی «الزامی» یکدست باشد.
    - لیست‌ها (multiselect): هر آیتم رشته‌ای نرمال می‌شود.
    کلیدهای خارج از تعریف دست‌نخورده عبور می‌کنند (سازگاری نسخه‌های قدیمی).
    """
    if not isinstance(answers, dict):
        return answers or {}
    index = build_field_index(definition)
    out: dict[str, Any] = {}
    for key, value in answers.items():
        if isinstance(value, str):
            value = norm_text(value) or None
        elif isinstance(value, list):
            value = [(norm_text(v) if isinstance(v, str) else v) for v in value]
            value = value or None
        f = index.get(key)
        if f and isinstance(value, str) and f.get("format") in ("mobile", "phone", "national_id", "integer"):
            value = _only_digits(value) or None
        out[key] = value
    return out


def _check_one_value(f: dict, path: str, value: Any, errors: list[dict]) -> None:
    label = f.get("label") or path
    fmt = f.get("format")
    ftype = f.get("type", "text")

    if value is None:
        return  # خالی بودن را قاعده «الزامی بودن» همان فرم بررسی می‌کند

    if ftype == "boolean":
        if not isinstance(value, bool):
            errors.append({"field": path, "label": label, "error": "مقدار این فیلد باید بله/خیر باشد"})
        return

    if ftype == "select":
        opts = {o["value"] for o in (f.get("options") or [])}
        if opts and value not in opts:
            errors.append({"field": path, "label": label, "error": "مقدار انتخاب‌شده در فهرست گزینه‌های مجاز نیست"})
        return

    if ftype == "multiselect":
        opts = {o["value"] for o in (f.get("options") or [])}
        if not isinstance(value, list):
            errors.append({"field": path, "label": label, "error": "مقدار این فیلد باید فهرست انتخاب‌ها باشد"})
            return
        if opts and any(v not in opts for v in value):
            errors.append({"field": path, "label": label, "error": "یک یا چند گزینه انتخابی مجاز نیست"})
        return

    # ----- فیلدهای متنی / عددی -----
    if fmt == "integer":
        try:
            n = int(value)
        except (TypeError, ValueError):
            errors.append({"field": path, "label": label, "error": FORMAT_MESSAGES["integer"]})
            return
        lo = f.get("min", 0)
        hi = f.get("max", 1000000)
        if not (lo <= n <= hi):
            errors.append({"field": path, "label": label,
                           "error": f"مقدار باید عددی بین {lo} و {hi} باشد"})
        return

    if not isinstance(value, str):
        return

    if fmt == "mobile" and not MOBILE_RE.match(value):
        errors.append({"field": path, "label": label, "error": FORMAT_MESSAGES["mobile"]})
        return
    if fmt == "phone" and not PHONE_RE.match(value):
        errors.append({"field": path, "label": label, "error": FORMAT_MESSAGES["phone"]})
        return
    if fmt == "national_id" and not is_valid_national_id(value):
        errors.append({"field": path, "label": label, "error": FORMAT_MESSAGES["national_id"]})
        return

    max_len = f.get("max_length") or (DEFAULT_MAX_TEXTAREA if ftype == "textarea" else DEFAULT_MAX_TEXT)
    if len(value) > max_len:
        errors.append({"field": path, "label": label,
                       "error": f"حداکثر طول مجاز این فیلد {max_len} نویسه است"})


def format_and_range_errors(answers: dict, definition: dict | None) -> list[dict]:
    """اعتبارسنجی قالب/سقف طول/گزینه‌های مجاز بر اساس تعریف نسخه همان ارزیابی.

    فقط کلیدهای شناخته‌شده در تعریف بررسی می‌شوند؛ کلیدهای ناشناخته عبور
    می‌کنند تا ارزیابی‌های نسخه‌های قدیمی فرم قابل نهایی‌سازی بمانند (B14).
    """
    errors: list[dict] = []
    if not isinstance(answers, dict):
        return errors
    index = build_field_index(definition)
    for path, f in index.items():
        if path in answers:
            _check_one_value(f, path, answers[path], errors)
    return errors
