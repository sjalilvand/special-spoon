"""فاز ۸۸ — ابزارهای اعتبارسنجی فراخوان همکاری (پورت فرم مرجع farakhan).

توابع خالص و بدون وابستگی:
- ``is_valid_national_code``: الگوریتم رسمی کد ملی (ارقام فارسی هم نرمال می‌شود)
- ``normalize_phone`` / ``is_valid_mobile`` / ``is_valid_landline``
- ``is_valid_postal_code_format``: ۱۰ رقم + بلوک دوریقم در بازه‌های رسمی پست
- ``clean_text``: فشرده‌سازی فاصله‌ها و خالی→None

همهٔ پیام‌های خطا فارسی هستند تا مستقیم در 422 نشان داده شوند.
"""
from __future__ import annotations

import re

from app.core.dates import normalize_digits

_SEPARATORS_RE = re.compile(r"[\s\-().]")
_WHITESPACE_RE = re.compile(r"\s+")
_MOBILE_RE = re.compile(r"^09\d{9}$")
# ثابت: ۰ + کد شهر (رقم ۱..۸) + شماره مشترک = ۱۱ رقم؛ موبایل (09...) حذف می‌شود
_LANDLINE_RE = re.compile(r"^0[1-8]\d{9}$")

# ── کدپستی ایران: بازه‌های رسمی بلوک دوریقم بر اساس رقم اول ──
POSTAL_GROUP_RANGES: dict[int, list[tuple[int, int]]] = {
    1: [(11, 19)],   # تهران
    3: [(31, 39)],   # البرز، قزوین، قم، مرکزی، سمنان
    4: [(43, 49)],   # گیلان، مازندران، گلستان، زنجان
    5: [(51, 59)],   # آذربایجان شرقی/غربی، اردبیل
    6: [(63, 69)],   # خوزستان، ایلام، کرمانشاه، کردستان، همدان، لرستان
    7: [(71, 79)],   # فارس، بوشهر، هرمزگان، کرمان، کهگیلویه و بویراحمد
    8: [(81, 89)],   # اصفهان، یزد، چهارمحال و بختیاری
    9: [(91, 99)],   # خراسان‌ها، سیستان و بلوچستان
}


def clean_text(value: str | None) -> str | None:
    """فاصله‌های اضافی حذف/فشرده و رشتهٔ خالی → None."""
    if value is None:
        return None
    cleaned = _WHITESPACE_RE.sub(" ", str(value)).strip()
    return cleaned or None


def normalize_phone(value: str | None) -> str | None:
    """ارقام فارسی→انگلیسی، حذف جداکننده‌ها، +98/0098/98→۰، بازگرداندن صفر ابتدای موبایل."""
    if value is None:
        return None
    cleaned = _SEPARATORS_RE.sub("", normalize_digits(str(value))).strip()
    if not cleaned:
        return None
    if cleaned.startswith("+98"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("0098"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("98") and len(cleaned) == 12:
        cleaned = "0" + cleaned[2:]
    if len(cleaned) == 10 and cleaned.startswith("9"):
        cleaned = "0" + cleaned
    return cleaned


def is_valid_mobile(value: str | None) -> bool:
    value = normalize_phone(value)
    return bool(value and _MOBILE_RE.match(value))


def is_valid_landline(value: str | None) -> bool:
    value = normalize_phone(value)
    return bool(value and _LANDLINE_RE.match(value))


def is_valid_national_code(code: str | None) -> bool:
    """الگوریتم رسمی کد ملی؛ رشتهٔ ۱۰ رقمی (صفرهای ابتدایی حفظ می‌شود)."""
    code = normalize_digits(code or "").strip()
    if not code or not code.isdigit() or len(code) != 10:
        return False
    if code == code[0] * 10:  # 0000000000، 1111111111 و … نامعتبرند
        return False
    weighted = sum(int(d) * (10 - i) for i, d in enumerate(code[:9]))
    remainder = weighted % 11
    control = int(code[9])
    if remainder < 2:
        return control == remainder
    return control == 11 - remainder


def normalize_postal_code(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = normalize_digits(str(value)).strip().replace("-", "").replace(" ", "")
    return cleaned or None


def is_valid_postal_code_format(code: str | None) -> bool:
    """۱۰ رقم + بلوک دوریقم در بازه‌های رسمی (رقم اول یکی از ۱،۳..۹)."""
    code = normalize_postal_code(code)
    if not code or len(code) != 10 or not code.isdigit():
        return False
    first, block = int(code[0]), int(code[:2])
    ranges = POSTAL_GROUP_RANGES.get(first)
    if not ranges:
        return False
    return any(lo <= block <= hi for lo, hi in ranges)
