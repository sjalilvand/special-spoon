"""فاز ۸۸ — فراخوان همکاری: پورت کامل فرم مرجع Samaneh-IT-rose/farakhan در سامانه.

مسیرهای عمومی (بدون ورود — برای لینک مستقیم در گروه‌ها و سامانه‌های دیگر):
- ``GET  /farakhan/meta``                     گزینه‌های ثابت فرم + قواعد اعتبارسنجی
- ``GET  /farakhan/captcha``                  کپچای محاسبهٔ دو عدد (SVG تک‌مصرف)
- ``GET  /farakhan/provinces``                استان‌ها
- ``GET  /farakhan/provinces/{id}/counties``  شهرستان‌های استان
- ``POST /farakhan/submissions``              ثبت نهایی فرم (multipart: payload + فایل‌ها)

مسیرهای پنل (گیت ماتریس منو + نقش):
- ``GET /farakhan/admin/submissions``           فهرست (صفحه‌بندی + جست‌وجو)
- ``GET /farakhan/admin/submissions/{id}``      جزئیات + فایل‌ها
- ``PUT /farakhan/admin/submissions/{id}/status`` تغییر وضعیت بررسی
- ``GET /farakhan/admin/export``               خروجی اکسل

قواعد کلیدی (هم‌ارز فرم مرجع):
- کپچای محاسبهٔ دو عدد پیش از ذخیره — تک‌مصرف، TTL ۱۰ دقیقه، سقف حافظه.
- اعتبارسنجی کامل سمت سرور: کد ملی، تاریخ تولد شمسی، موبایل/ثابت، کدپستی،
  فیلدهای شرطی (سربازی برای آقایان، شماره پروانه برای «معتبر»).
- فایل‌ها فقط PDF/JPG/PNG، سقف ۵ مگابایت هر فایل، تشخیص نوع واقعی با magic bytes،
  حذف فرادادهٔ تصاویر + اسکن ClamAV + ذخیره در زیرساخت امن فایل سامانه (بند B39)؛
  دانلود فقط با بلیت امضاشده از مسیر /files.
- فیلدهای فایل اجباری: کارت ملی + مدرک تحصیلی + پروانهٔ مرکز فعالیت
  (پیش‌فرض فرم مرجع).
"""

from __future__ import annotations

import io
import logging
import secrets
import time
import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import get_settings
from app.core.dates import jalali_to_gregorian, normalize_digits
from app.db.session import get_db
from app.models.farakhan import FARAKHAN_STATUSES, FarakhanFile, FarakhanLocation, FarakhanSubmission
from app.models.file import FileScan, StoredFile
from app.services import av_scan
from app.services import object_storage as objstore
from app.services.farakhan_validation import (
    clean_text,
    is_valid_landline,
    is_valid_mobile,
    is_valid_national_code,
    is_valid_postal_code_format,
    normalize_phone,
    normalize_postal_code,
)
from app.services.image_sanitizer import strip_image_metadata

router = APIRouter(prefix="/farakhan", tags=["farakhan"])

# فاز ۹۱ — لاگر اختصاصی؛ هر خطای غیرمنتظرهٔ ثبت با ردیابی کامل در لاگ می‌افتد
logger = logging.getLogger("farakhan")

# ---------------------------------------------------------------- گزینه‌های فرم
GENDER_OPTIONS = {"male": "مرد", "female": "زن"}
MILITARY_STATUS_OPTIONS = {
    "served": "پایان خدمت",
    "permanent_exemption": "معافیت دائم",
    "medical_exemption": "معافیت پزشکی",
    "temporary_exemption": "معافیت موقت / کسر خدمت",
}
EDUCATION_DEGREE_OPTIONS = {"bachelor": "کارشناسی", "master": "کارشناسی ارشد", "phd": "دکترا"}
LICENSE_STATUS_OPTIONS = {"valid": "دارای پروانه معتبر", "in_progress": "در حال دریافت پروانه", "none": "فاقد پروانه"}
CENTER_OWNERSHIP_OPTIONS = {"owned": "ملکی", "rented": "استیجاری", "other": "سایر"}

# کلید فیلد فایل → برچسب (برچسب فایل‌های اجباری با «تصویر» شروع می‌شود تا پیام
# خطا دقیقاً نام همان فایل را بگوید — الگوی فرم مرجع)
FILE_FIELD_KEYS = {
    "military_card": "کارت پایان خدمت / معافیت",
    "national_id_card": "تصویر کارت ملی",
    "degree_document": "تصویر مدرک تحصیلی",
    "professional_license": "پروانه فعالیت / عضویت نظام",
    "center_activity_license": "پروانه مرکز فعالیت",
    "center_permit": "پروانه تأسیس مرکز",
    "property_documents": "اسناد مالکیت / اجاره‌نامه",
}
REQUIRED_FILE_FIELDS = ("national_id_card", "degree_document", "center_activity_license")
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
MAX_FILES = 7
MAGIC_BYTES = {
    "application/pdf": b"%PDF-",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}

STATUS_TITLES = {"new": "جدید", "reviewed": "بررسی‌شده", "accepted": "پذیرفته‌شده", "rejected": "ردشده"}

# برچسب فارسی فیلدها برای پیام‌های خطای اعتبارسنجی
FIELD_LABELS = {
    "first_name": "نام", "last_name": "نام خانوادگی", "national_code": "کد ملی",
    "gender": "جنسیت", "birth_date": "تاریخ تولد", "military_status": "وضعیت سربازی",
    "education_degree": "مدرک تحصیلی", "education_field": "رشته تحصیلی",
    "license_status": "وضعیت پروانه", "license_number": "شماره پروانه",
    "license_description": "توضیحات پروانه", "center_ownership": "مالکیت مرکز",
    "province_name": "استان", "county_name": "شهرستان", "phone": "تلفن ثابت",
    "mobile_number": "شماره همراه", "postal_code": "کدپستی", "address": "نشانی",
    "individual_rooms": "اتاق انفرادی", "group_rooms": "اتاق گروهی",
    "child_rooms": "اتاق کودک", "counselors_count": "تعداد مشاوران",
    "terms_accepted": "پذیرش قوانین", "captcha_id": "کپچا", "captcha_answer": "کپچا",
    "session_id": "نشست فرم", "session_ttl_seconds": "مهلت فرم",
    "payload": "دادهٔ فرم",
}

# ---------------------------------------------------------------- کپچای محاسبه‌ای
_CAPTCHA_TTL = 600.0  # ۱۰ دقیقه
_CAPTCHA_MAX_STORE = 2000
_captcha_store: dict[str, dict] = {}

# فاز ۸۹ - نشست یک‌ساعتهٔ فرم: از لحظهٔ ورود به صفحه، کاربر یک ساعت فرصت تکمیل
# و ذخیره دارد؛ پس از آن سرور ثبت را رد می‌کند (به‌همراه شمارش معکوس سمت مرورگر).
_FORM_SESSION_TTL = 3600.0  # یک ساعت
_FORM_SESSION_MAX = 5000
_form_sessions: dict[str, float] = {}

# محدودسازی نرخ ثبت فرم از هر IP (کپچا + این سقف، هم‌پوشان یکدیگرند)
_submit_ip_hits: dict[str, list[float]] = {}
_SUBMIT_RATE = 20
_SUBMIT_WINDOW = 3600.0

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_TEXT_COLORS = ["#1f2a44", "#0f4c81", "#5b3a8e", "#1a6b52", "#8a2d2d"]
_NOISE_COLORS = ["#9aa7bd", "#7f93ad", "#b3bed2"]


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _submit_rate_ok(ip: str) -> bool:
    now = time.monotonic()
    lst = [t for t in _submit_ip_hits.get(ip, []) if now - t < _SUBMIT_WINDOW]
    if len(lst) >= _SUBMIT_RATE:
        _submit_ip_hits[ip] = lst
        return False
    lst.append(now)
    _submit_ip_hits[ip] = lst
    return True


def _purge_captcha() -> None:
    now = time.monotonic()
    for key in [k for k, v in _captcha_store.items() if v["exp"] <= now]:
        _captcha_store.pop(key, None)


def _render_math_svg(a: int, b: int) -> str:
    """تصویر SVG «۴۵ + ۳۲ = ؟» با نویز — جلوگیری از خواندن ماشینی ساده."""
    rng = secrets.SystemRandom()
    width, height = 190, 54
    question = f"{a} + {b} = ؟".translate(_FA_DIGITS)
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="کپچای محاسبهٔ دو عدد">',
        f'<rect width="{width}" height="{height}" fill="#f4f6fb" rx="6"/>',
    ]
    for _ in range(4):
        parts.append(
            f'<line x1="{rng.randint(0, width)}" y1="{rng.randint(4, height - 4)}" '
            f'x2="{rng.randint(0, width)}" y2="{rng.randint(4, height - 4)}" '
            f'stroke="{rng.choice(_NOISE_COLORS)}" stroke-width="{rng.randint(1, 2)}" opacity="0.55"/>'
        )
    for _ in range(22):
        parts.append(
            f'<circle cx="{rng.randint(2, width - 2)}" cy="{rng.randint(2, height - 2)}" '
            f'r="{rng.uniform(0.8, 1.6):.1f}" fill="{rng.choice(_NOISE_COLORS)}" opacity="0.5"/>'
        )
    # سؤال یک‌جا با چرخش کم — نویز کافی است و خوانایی برای انسان حفظ می‌شود
    y = rng.randint(33, 39)
    x = width // 2
    parts.append(
        f'<text x="{x}" y="{y}" font-size="23" '
        f'font-family="Vazirmatn, Tahoma, sans-serif" font-weight="700" '
        f'fill="{rng.choice(_TEXT_COLORS)}" text-anchor="middle" '
        f'transform="rotate({rng.randint(-5, 5)} {x} {y})">{question}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _new_math_captcha() -> dict:
    """کپچای محاسبهٔ دو عدد؛ خروجی (captcha_id، svg). تک‌مصرف در verify."""
    _purge_captcha()
    if len(_captcha_store) >= _CAPTCHA_MAX_STORE:
        _captcha_store.clear()
    a = secrets.randbelow(80) + 11  # ۱۱..۹۰
    b = secrets.randbelow(80) + 11
    captcha_id = secrets.token_urlsafe(16)
    _captcha_store[captcha_id] = {"answer": a + b, "exp": time.monotonic() + _CAPTCHA_TTL}
    return {"captcha_id": captcha_id, "svg": _render_math_svg(a, b), "ttl_seconds": int(_CAPTCHA_TTL)}


def _verify_math_captcha(captcha_id: str | None, answer: str | None) -> bool:
    """تک‌مصرف: هر تلاش (درست یا غلط) کپچا را مصرف می‌کند — ضد replay."""
    entry = _captcha_store.pop(captcha_id or "", None)
    if not entry or entry["exp"] <= time.monotonic():
        return False
    given = normalize_digits((answer or "").strip())
    return given.isdigit() and int(given) == entry["answer"]


def _purge_form_sessions() -> None:
    now = time.monotonic()
    for key in [k for k, exp in _form_sessions.items() if exp <= now]:
        _form_sessions.pop(key, None)


def _new_form_session() -> dict:
    """نشست تازهٔ فرم — از لحظهٔ بازکردن صفحه تا یک ساعت معتبر است."""
    _purge_form_sessions()
    if len(_form_sessions) >= _FORM_SESSION_MAX:
        for key, _exp in sorted(_form_sessions.items(), key=lambda kv: kv[1])[: _FORM_SESSION_MAX // 5]:
            _form_sessions.pop(key, None)
    session_id = secrets.token_urlsafe(16)
    _form_sessions[session_id] = time.monotonic() + _FORM_SESSION_TTL
    return {"session_id": session_id, "session_ttl_seconds": int(_FORM_SESSION_TTL)}


def _form_session_ok(session_id: str | None) -> bool:
    """نشست باید موجود و منقضی‌نشده باشد (چند بار تلاش در همان ساعت مجاز است)."""
    exp = _form_sessions.get(session_id or "")
    return bool(exp and exp > time.monotonic())


def _errors_422(errors: dict[str, str]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"message": "اعتبارسنجی اطلاعات ناموفق بود.", "errors": errors},
    )


# فاز ۹۱ — ترجمهٔ پیام‌های فنی pydantic به فارسی روان با ذکر محدودیت فیلد
_PYDANTIC_TYPE_FA: dict[str, str] = {
    "missing": "این فیلد الزامی است.",
    "int_parsing": "باید عدد باشد.",
    "int_type": "باید عدد باشد.",
    "bool_parsing": "باید صحیح/نادرست باشد.",
    "bool_type": "مقدار بله/خیر نامعتبر است.",
    "string_type": "متن وارد کنید.",
    "json_invalid": "قالب دادهٔ ارسالی خراب است.",
}


def _translate_validation_error(exc: ValidationError) -> dict[str, str]:
    """خطاهای pydantic → نقشهٔ «برچسب فیلد → پیام فارسی»؛ پیام انگلیسی باقی نمی‌ماند."""
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ["payload"]))
        etype = str(err.get("type") or "")
        msg = str(err.get("msg") or "مقدار نامعتبر است.")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        elif msg.startswith("Assertion failed, "):
            msg = msg[len("Assertion failed, "):]
        # فاز ۹۱ — پیام‌های فنی انگلیسی pydantic جایگزین فارسی می‌شوند
        if etype in _PYDANTIC_TYPE_FA:
            msg = _PYDANTIC_TYPE_FA[etype]
        elif etype == "string_too_long":
            limit = (err.get("ctx") or {}).get("max_length") or (err.get("ctx") or {}).get("limit")
            msg = f"حداکثر {limit} نویسه مجاز است." if limit else "متن بیش از حد مجاز است."
        elif etype == "string_too_short":
            limit = (err.get("ctx") or {}).get("min_length") or (err.get("ctx") or {}).get("limit")
            msg = f"حداقل {limit} نویسه لازم است." if limit else "متن بیش از حد کوتاه است."
        elif etype == "greater_than_equal":
            minimum = (err.get("ctx") or {}).get("ge")
            msg = f"کمترین مقدار مجاز {minimum} است."
        elif etype == "less_than_equal":
            maximum = (err.get("ctx") or {}).get("le")
            msg = f"بیشترین مقدار مجاز {maximum} است."
        label = FIELD_LABELS.get(loc, loc) or "فرم"
        if label not in errors:  # اولین خطای هر فیلد نگه داشته می‌شود
            errors[label] = msg
    return errors or {"payload": "قالب JSON بخش payload نامعتبر است."}


# ---------------------------------------------------------------- اسکیما
class FarakhanCreate(BaseModel):
    """بار JSON فرم — نرمال‌سازی و اعتبارسنجی هم‌ارز فرم مرجع."""

    model_config = ConfigDict(str_strip_whitespace=True)

    # مشخصات فردی
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    national_code: str = Field(min_length=1, max_length=20)
    gender: str
    birth_date: str = Field(min_length=8, max_length=10)

    # سربازی (شرطی)
    military_status: str | None = None

    # تحصیلات
    education_degree: str
    education_field: str | None = Field(default=None, max_length=120)

    # پروانه
    license_status: str
    license_number: str | None = Field(default=None, max_length=50)
    license_description: str | None = Field(default=None, max_length=1000)

    # مرکز
    center_ownership: str
    province_name: str = Field(min_length=1, max_length=80)
    county_name: str = Field(min_length=1, max_length=80)

    # تماس و نشانی
    phone: str = Field(max_length=20)
    mobile_number: str | None = Field(default=None, max_length=20)
    postal_code: str | None = Field(default=None, max_length=15)
    address: str | None = Field(default=None, max_length=500)

    # ظرفیت
    individual_rooms: int = Field(ge=0, le=999)
    group_rooms: int = Field(ge=0, le=999)
    child_rooms: int = Field(ge=0, le=999)
    counselors_count: int = Field(ge=0, le=999)

    # امکانات
    has_waiting_space: bool
    accepts_company_pattern: bool
    has_accessibility: bool

    # قوانین
    terms_accepted: bool

    # کپچا
    captcha_id: str = Field(min_length=1, max_length=64)
    captcha_answer: str = Field(min_length=1, max_length=12)

    # فاز ۸۹ - نشست یک‌ساعتهٔ فرم (از GET /farakhan/meta صادر می‌شود)
    session_id: str = Field(min_length=1, max_length=64)

    # ---------- نرمال‌سازها ----------
    @field_validator("first_name", "last_name", "education_field", "license_number",
                     "license_description", "address", mode="before")
    @classmethod
    def _clean(cls, value):
        return clean_text(value) if value is not None else None

    @field_validator("national_code", "birth_date", "postal_code", "phone", "mobile_number", mode="before")
    @classmethod
    def _digits(cls, value):
        if value is None:
            return None
        return normalize_digits(str(value)).strip()

    # فاز ۹۱ — فیلدهای عددی: ارقام فارسی/فاصله هم پذیرفته می‌شود («۳»، " 2 ")
    @field_validator("individual_rooms", "group_rooms", "child_rooms", "counselors_count", mode="before")
    @classmethod
    def _int_fa(cls, value):
        if value is None or value == "":
            return 0
        if isinstance(value, bool):
            raise ValueError("باید عدد باشد.")
        if isinstance(value, int):
            return value
        normalized = normalize_digits(str(value)).strip()
        try:
            return int(float(normalized))
        except (TypeError, ValueError):
            raise ValueError("باید عدد باشد.")

    # ---------- قواعد هر فیلد ----------
    @field_validator("gender")
    @classmethod
    def _gender(cls, value: str) -> str:
        if value not in GENDER_OPTIONS:
            raise ValueError("جنسیت را انتخاب کنید.")
        return value

    @field_validator("military_status")
    @classmethod
    def _military(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        if value not in MILITARY_STATUS_OPTIONS:
            raise ValueError("وضعیت سربازی نامعتبر است.")
        return value

    @field_validator("education_degree", mode="before")
    @classmethod
    def _degree_required(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError("مدرک تحصیلی را انتخاب کنید.")
        return value

    @field_validator("education_degree")
    @classmethod
    def _degree_valid(cls, value: str) -> str:
        if value not in EDUCATION_DEGREE_OPTIONS:
            raise ValueError("مدرک تحصیلی نامعتبر است.")
        return value

    @field_validator("education_field")
    @classmethod
    def _field_required(cls, value: str | None) -> str:
        if not (value or "").strip():
            raise ValueError("رشته تحصیلی را وارد کنید.")
        return value

    @field_validator("national_code")
    @classmethod
    def _national_code(cls, value: str) -> str:
        if len(value) != 10 or not value.isdigit():
            raise ValueError("کد ملی باید ۱۰ رقم باشد.")
        if not is_valid_national_code(value):
            raise ValueError("کد ملی واردشده معتبر نیست.")
        return value

    @field_validator("birth_date")
    @classmethod
    def _birth_date(cls, value: str) -> str:
        parts = value.replace("-", "/").split("/")
        if len(parts) != 3:
            raise ValueError("تاریخ تولد باید تاریخ شمسی معتبر به قالب YYYY/MM/DD باشد.")
        try:
            year, month, day = (int(p) for p in parts)
        except ValueError:
            raise ValueError("تاریخ تولد باید تاریخ شمسی معتبر به قالب YYYY/MM/DD باشد.")
        if not (1250 <= year <= 1500):
            raise ValueError("تاریخ تولد واردشده معقول نیست.")
        try:
            gregorian = jalali_to_gregorian(year, month, day)
        except ValueError:
            raise ValueError("تاریخ تولد باید تاریخ شمسی معتبر به قالب YYYY/MM/DD باشد.")
        today = datetime.now(timezone.utc).date()
        if gregorian > today:
            raise ValueError("تاریخ تولد نمی‌تواند در آینده باشد.")
        return value

    @field_validator("license_status")
    @classmethod
    def _license_status(cls, value: str) -> str:
        if value not in LICENSE_STATUS_OPTIONS:
            raise ValueError("وضعیت پروانه را انتخاب کنید.")
        return value

    @field_validator("license_number")
    @classmethod
    def _license_number(cls, value: str | None, info) -> str | None:
        # شماره پروانه فقط وقتی وضعیت «دارای پروانه معتبر» است الزامی می‌شود
        status = info.data.get("license_status")
        if status == "valid" and not (value or "").strip():
            raise ValueError("شماره پروانه الزامی است.")
        return value

    @field_validator("center_ownership")
    @classmethod
    def _ownership(cls, value: str) -> str:
        if value not in CENTER_OWNERSHIP_OPTIONS:
            raise ValueError("مالکیت مرکز را انتخاب کنید.")
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def _phone_required(cls, value):
        # تلفن ثابت اجباری است (خواستهٔ فرم مرجع)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError("شماره تلفن ثابت الزامی است.")
        return value

    @field_validator("phone")
    @classmethod
    def _phone_valid(cls, value: str) -> str:
        normalized = normalize_phone(value)
        if not normalized or not is_valid_landline(normalized):
            raise ValueError("شماره تلفن ثابت معتبر نیست. نمونه صحیح: 02112345678")
        return normalized

    @field_validator("mobile_number")
    @classmethod
    def _mobile_optional(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        normalized = normalize_phone(value)
        if not normalized or not is_valid_mobile(normalized):
            raise ValueError("شماره همراه معتبر نیست. نمونه صحیح: 09123456789")
        return normalized

    @field_validator("postal_code")
    @classmethod
    def _postal(cls, value: str | None) -> str | None:
        value = normalize_postal_code(value)
        if value is None:
            return None
        if not is_valid_postal_code_format(value):
            raise ValueError("کدپستی باید ۱۰ رقم و مطابق الگوی کدپستی ایران باشد.")
        return value

    @field_validator("terms_accepted")
    @classmethod
    def _terms(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("پذیرش قوانین و شرایط برای ثبت نهایی الزامی است.")
        return value

    # ---------- قواعد بین‌فیلدی ----------
    @model_validator(mode="after")
    def _conditional(self) -> "FarakhanCreate":
        # فاز ۸۹ - نشست یک‌ساعته: پیش از مصرف کپچا چک می‌شود تا کپچا بی‌سبب مصرف نشود
        if not _form_session_ok(self.session_id):
            raise ValueError("مهلت یک‌ساعتهٔ تکمیل فرم منقضی شده است؛ لطفاً صفحه را دوباره باز کنید.")
        # سربازی فقط برای آقایان معنا دارد؛ برای خانم‌ها بی‌صدا حذف می‌شود
        # (رفتار مستند فرم مرجع — open decision #1)
        if self.gender == "female":
            self.military_status = None
        elif self.gender == "male" and not self.military_status:
            raise ValueError("وضعیت سربازی برای متقاضی مرد الزامی است.")
        # سازگاری پروانه
        if self.license_status == "none":
            self.license_number = None
            self.license_description = None
        # کپچا — تک‌مصرف؛ هر تلاش مصرف می‌شود
        if not _verify_math_captcha(self.captcha_id, self.captcha_answer):
            raise ValueError("کپچا نامعتبر است؛ لطفاً پاسخ محاسبهٔ دو عدد را درست وارد کنید یا کپچای تازه بگیرید.")
        return self


# ---------------------------------------------------------------- خروجی‌ها
def _submission_out(s: FarakhanSubmission, file_count: int = 0) -> dict:
    return {
        "id": str(s.id),
        "tracking_code": s.tracking_code,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "national_code": s.national_code,
        "gender": s.gender,
        "gender_label": GENDER_OPTIONS.get(s.gender, s.gender),
        "birth_date_jalali": s.birth_date_jalali,
        "military_status": s.military_status,
        "military_status_label": MILITARY_STATUS_OPTIONS.get(s.military_status or "", None),
        "education_degree": s.education_degree,
        "education_degree_label": EDUCATION_DEGREE_OPTIONS.get(s.education_degree, s.education_degree),
        "education_field": s.education_field,
        "license_status": s.license_status,
        "license_status_label": LICENSE_STATUS_OPTIONS.get(s.license_status, s.license_status),
        "license_number": s.license_number,
        "license_description": s.license_description,
        "center_ownership": s.center_ownership,
        "center_ownership_label": CENTER_OWNERSHIP_OPTIONS.get(s.center_ownership, s.center_ownership),
        "province_name": s.province_name,
        "county_name": s.county_name,
        "phone": s.phone,
        "mobile_number": s.mobile_number,
        "postal_code": s.postal_code,
        "address": s.address,
        "individual_rooms": s.individual_rooms,
        "group_rooms": s.group_rooms,
        "child_rooms": s.child_rooms,
        "counselors_count": s.counselors_count,
        "has_waiting_space": s.has_waiting_space,
        "accepts_company_pattern": s.accepts_company_pattern,
        "has_accessibility": s.has_accessibility,
        "status": s.status,
        "status_label": STATUS_TITLES.get(s.status, s.status),
        "review_note": s.review_note,
        "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
        "submit_ip": s.submit_ip,
        "file_count": file_count,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ---------------------------------------------------------------- مسیرهای عمومی
@router.get("/meta")
def get_farakhan_meta() -> dict:
    return {
        "genders": [{"value": k, "label": v} for k, v in GENDER_OPTIONS.items()],
        "military_status_options": [{"value": k, "label": v} for k, v in MILITARY_STATUS_OPTIONS.items()],
        "education_degrees": [{"value": k, "label": v} for k, v in EDUCATION_DEGREE_OPTIONS.items()],
        "license_status_options": [{"value": k, "label": v} for k, v in LICENSE_STATUS_OPTIONS.items()],
        "center_ownership_options": [{"value": k, "label": v} for k, v in CENTER_OWNERSHIP_OPTIONS.items()],
        "file_fields": [{"key": k, "label": v, "required": k in REQUIRED_FILE_FIELDS} for k, v in FILE_FIELD_KEYS.items()],
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "max_file_size_bytes": MAX_FILE_SIZE_BYTES,
        "max_files": MAX_FILES,
        "rules": {"require_military_status_for_male": True, "phone_required": True},
        # فاز ۸۹ - نشست یک‌ساعتهٔ فرم: شناسه + طول مهلت برای شمارش معکوس مرورگر
        **_new_form_session(),
    }


@router.get("/captcha")
def get_farakhan_captcha() -> dict:
    return _new_math_captcha()


@router.get("/provinces")
def get_farakhan_provinces(db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(
        select(FarakhanLocation)
        .where(FarakhanLocation.county_name.is_(None), FarakhanLocation.is_active.is_(True))
        .order_by(FarakhanLocation.id)
    ).all()
    return {"items": [{"id": r.id, "name": r.province_name} for r in rows]}


@router.get("/provinces/{province_id}/counties")
def get_farakhan_counties(province_id: int, db: Session = Depends(get_db)) -> dict:
    province = db.get(FarakhanLocation, province_id)
    if province is None or province.county_name is not None:
        raise HTTPException(status_code=404, detail="استان مورد نظر یافت نشد.")
    rows = db.scalars(
        select(FarakhanLocation)
        .where(
            FarakhanLocation.province_name == province.province_name,
            FarakhanLocation.county_name.is_not(None),
            FarakhanLocation.is_active.is_(True),
        )
        .order_by(FarakhanLocation.county_name)
    ).all()
    return {"items": [{"id": r.id, "name": r.county_name} for r in rows]}


def _validate_upload(upload: UploadFile, field_key: str) -> tuple[bytes, str]:
    """اعتبارسنجی یک فایل: پسوند + حجم + magic bytes؛ خروجی (بایت‌ها، mime)."""
    raw_name = upload.filename or ""
    extension = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise _errors_422({f"files.{field_key}": "تنها فایل‌های PDF و تصویری (JPG، JPEG، PNG) پذیرفته می‌شود."})
    data = upload.file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(data) == 0:
        raise _errors_422({f"files.{field_key}": "فایل خالی است."})
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise _errors_422({f"files.{field_key}": "حجم هر فایل حداکثر ۵ مگابایت است."})
    mime = None
    for candidate, signature in MAGIC_BYTES.items():
        if data.startswith(signature):
            mime = candidate
            break
    if mime is None:
        raise _errors_422({f"files.{field_key}": "محتوای فایل با پسوند اعلام‌شده همخوان نیست."})
    return data, mime


@router.post("/submissions", status_code=201)
async def submit_farakhan(request: Request, db: Session = Depends(get_db)) -> dict:
    """ثبت نهایی فراخوان همکاری — فرم + فایل‌ها در یک تراکنش."""
    ip = _client_ip(request)
    if not _submit_rate_ok(ip):
        raise HTTPException(status_code=429, detail="تعداد ثبت‌نام‌ها بیش از حد مجاز است؛ کمی بعد تلاش کنید.")

    try:
        form = await request.form()
    except Exception:
        raise HTTPException(status_code=400, detail="قالب درخواست multipart نامعتبر است.")

    payload_part = form.get("payload")
    if payload_part is None:
        raise _errors_422({"payload": "بخش payload الزامی است."})
    if not isinstance(payload_part, str):
        payload_part = (await payload_part.read()).decode("utf-8", errors="replace")

    try:
        data = FarakhanCreate.model_validate_json(payload_part)
    except ValidationError as exc:
        # فاز ۹۱ — پیام‌ها همیشه فارسی و روی برچسب فیلد نقشه می‌شوند
        raise _errors_422(_translate_validation_error(exc))

    # فایل‌ها: فقط کلیدهای مجاز فرم
    uploads: list[tuple[str, UploadFile]] = []
    seen_fields: set[str] = set()
    for key, value in form.multi_items():
        if key == "payload" or not hasattr(value, "read"):
            continue
        if key not in FILE_FIELD_KEYS:
            raise _errors_422({f"files.{key}": "کلید فایل نامعتبر است."})
        if key in seen_fields:
            raise _errors_422({f"files.{key}": "هر فیلد فقط یک فایل می‌پذیرد."})
        seen_fields.add(key)
        uploads.append((key, value))

    if len(uploads) > MAX_FILES:
        raise _errors_422({"files": f"حداکثر {MAX_FILES} فایل قابل آپلود است."})
    for required in REQUIRED_FILE_FIELDS:
        if required not in seen_fields:
            label = FILE_FIELD_KEYS[required]
            raise _errors_422({f"files.{required}": f"آپلود «{label}» الزامی است."})

    # استان/شهرستان باید واقعاً در دادهٔ پایه باشد (الگوی فرم مرجع با FK)
    province_row = db.scalar(
        select(FarakhanLocation).where(
            FarakhanLocation.province_name == data.province_name,
            FarakhanLocation.county_name.is_(None),
        )
    )
    if province_row is None:
        raise _errors_422({"استان": "استان انتخاب‌شده معتبر نیست."})
    county_row = db.scalar(
        select(FarakhanLocation).where(
            FarakhanLocation.province_name == data.province_name,
            FarakhanLocation.county_name == data.county_name,
        )
    )
    if county_row is None:
        raise _errors_422({"شهرستان": "شهرستان انتخاب‌شده با استان همخوان نیست."})

    settings = get_settings()
    # فاز ۹۱ — سپر خطای غیرمنتظره: هیچ خطای پایگاه‌داده/فایل دیگر «۵۰۰ بی‌پیام»
    # نمی‌سازد؛ ردیابی کامل در لاگ می‌افتد و پاسخ JSON ساختاریافته با پیام فارسی
    # برمی‌گردد تا فرم می‌تواند آن را نشان دهد و کاربر داده‌اش را از دست ندهد.
    try:
        submission = FarakhanSubmission(
            tracking_code=f"FRK-{secrets.token_hex(6).upper()}",
            first_name=data.first_name,
            last_name=data.last_name,
            national_code=data.national_code,
            gender=data.gender,
            birth_date_jalali=data.birth_date.replace("-", "/"),
            military_status=data.military_status,
            education_degree=data.education_degree,
            education_field=(data.education_field or "").strip(),
            license_status=data.license_status,
            license_number=data.license_number,
            license_description=data.license_description,
            center_ownership=data.center_ownership,
            province_name=data.province_name,
            county_name=data.county_name,
            phone=data.phone,
            mobile_number=data.mobile_number,
            postal_code=data.postal_code,
            address=data.address,
            individual_rooms=data.individual_rooms,
            group_rooms=data.group_rooms,
            child_rooms=data.child_rooms,
            counselors_count=data.counselors_count,
            has_waiting_space=data.has_waiting_space,
            accepts_company_pattern=data.accepts_company_pattern,
            has_accessibility=data.has_accessibility,
            terms_accepted_at=datetime.now(timezone.utc),
            submit_ip=ip,
            status="new",
        )
        db.add(submission)
        db.flush()

        for field_key, upload in uploads:
            raw, mime = _validate_upload(upload, field_key)
            raw, metadata_stripped = strip_image_metadata(raw, mime)
            scan = av_scan.scan_bytes(upload.filename or "file", mime, raw, settings.allowed_mime_list)
            provider, storage_key, sha, st_fallback = objstore.store(raw, settings)
            detail = scan.detail
            if metadata_stripped:
                detail = f"{detail} - فراداده تصویر حذف شد"
            if st_fallback:
                detail = f"{detail} - ذخیره‌سازی به محلی بازگشت (S3 فعال/در دسترس نبود)"
            stored = StoredFile(
                case_id=None,
                uploaded_by=None,
                context="farakhan",
                original_name=(upload.filename or "file")[:255],
                mime=mime,
                size_bytes=len(raw),
                sha256=sha,
                storage_key=storage_key,
                storage=provider,
                sensitivity="confidential",
                scan_status=scan.status,
            )
            db.add(stored)
            db.flush()
            db.add(FileScan(file_id=stored.id, status=scan.status, detail=detail, scanner=scan.scanner))
            db.add(FarakhanFile(
                submission_id=submission.id,
                file_id=stored.id,
                field_key=field_key,
                original_name=stored.original_name,
                size_bytes=len(raw),
            ))

        db.commit()
    except IntegrityError:
        db.rollback()
        logger.exception("farakhan submit: تداخل داده در ذخیره (کد ملی/کد پیگیری)")
        raise _errors_422({"داده": "ثبت با این اطلاعات از قبل وجود دارد یا با دادهٔ سامانه تداخل دارد؛ اطلاعات را بازبینی کنید."})
    except OperationalError as exc:
        db.rollback()
        logger.exception("farakhan submit: خطای اتصال پایگاه‌داده")
        raise HTTPException(status_code=503, detail={
            "message": "در حال حاضر امکان ذخیره نیست (خدمت پایگاه‌داده در دسترس نیست). چند لحظه بعد دوباره تلاش کنید.",
            "errors": {},
            "kind": "database",
        }) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("farakhan submit: خطای غیرمنتظره در ذخیرهٔ فرم")
        raise HTTPException(status_code=500, detail={
            "message": "در ذخیره‌سازی فرم خطای غیرمنتظرهٔ سرور رخ داد؛ اطلاعات شما ذخیره نشد. لطفاً دوباره تلاش کنید؛ اگر تکرار شد با پشتیبانی تماس بگیرید.",
            "errors": {},
            "kind": "server",
        }) from exc
    return {
        "success": True,
        "tracking_code": submission.tracking_code,
        "message": "اطلاعات با موفقیت ثبت شد. کد پیگیری شما:" ,
    }


# ---------------------------------------------------------------- مسیرهای پنل
FARAKHAN_ADMIN_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION")


@router.get("/admin/submissions")
def list_farakhan_submissions(
    q: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*FARAKHAN_ADMIN_ROLES)),
) -> dict:
    stmt = select(FarakhanSubmission)
    count_stmt = select(func.count(FarakhanSubmission.id))
    if q.strip():
        like = f"%{q.strip()}%"
        cond = (
            FarakhanSubmission.first_name.ilike(like)
            | FarakhanSubmission.last_name.ilike(like)
            | FarakhanSubmission.national_code.ilike(like)
            | FarakhanSubmission.tracking_code.ilike(like)
            | FarakhanSubmission.phone.ilike(like)
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    if status in FARAKHAN_STATUSES:
        stmt = stmt.where(FarakhanSubmission.status == status)
        count_stmt = count_stmt.where(FarakhanSubmission.status == status)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(FarakhanSubmission.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    counts = dict(db.execute(
        select(FarakhanFile.submission_id, func.count(FarakhanFile.id))
        .where(FarakhanFile.submission_id.in_([r.id for r in rows] or [uuid_mod.uuid4()]))
        .group_by(FarakhanFile.submission_id)
    ).all())

    items = [_submission_out(r, counts.get(r.id, 0)) for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/admin/submissions/{submission_id}")
def get_farakhan_submission(
    submission_id: uuid_mod.UUID,
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*FARAKHAN_ADMIN_ROLES)),
) -> dict:
    submission = db.get(FarakhanSubmission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="ثبت‌نام فراخوان یافت نشد.")
    files = db.scalars(select(FarakhanFile).where(FarakhanFile.submission_id == submission.id)).all()
    out = _submission_out(submission, len(files))
    out["files"] = [
        {
            "id": str(f.id),
            "file_id": str(f.file_id),
            "field_key": f.field_key,
            "field_label": FILE_FIELD_KEYS.get(f.field_key, f.field_key),
            "original_name": f.original_name,
            "size_bytes": f.size_bytes,
        }
        for f in files
    ]
    return out


@router.put("/admin/submissions/{submission_id}/status")
def set_farakhan_submission_status(
    submission_id: uuid_mod.UUID,
    payload: dict,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*FARAKHAN_ADMIN_ROLES)),
) -> dict:
    submission = db.get(FarakhanSubmission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="ثبت‌نام فراخوان یافت نشد.")
    status = str(payload.get("status") or "")
    if status not in FARAKHAN_STATUSES:
        raise HTTPException(status_code=422, detail="وضعیت نامعتبر است.")
    note = clean_text(str(payload.get("note") or "")) or None
    if note and len(note) > 500:
        raise HTTPException(status_code=422, detail="یادداشت بررسی حداکثر ۵۰۰ نویسه است.")
    submission.status = status
    submission.review_note = note
    submission.reviewed_by = actor.id
    submission.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return _submission_out(submission)


@router.post("/admin/files/{file_id}/download-ticket")
def farakhan_file_download_ticket(
    file_id: uuid_mod.UUID,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*FARAKHAN_ADMIN_ROLES)),
) -> dict:
    """بلیت دانلود کوتاه‌مدت برای فایل‌های فراخوان (همان الگوی B39 مسیر /files)."""
    from app.services import file_storage as fs

    stored = db.get(StoredFile, file_id)
    # فقط فایل‌های متعلق به فراخوان (context=farakhan) — نه فایل‌های پرونده‌ها
    link = db.scalar(select(FarakhanFile).where(FarakhanFile.file_id == file_id))
    if stored is None or stored.context != "farakhan" or link is None:
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    if stored.scan_status == "quarantined":
        raise HTTPException(status_code=403, detail="فایل در قرنطینه است و قابل دانلود نیست")
    settings = get_settings()
    token, expires = fs.make_download_ticket(
        settings.auth_secret_key, str(stored.id), str(actor.id), settings.download_ticket_seconds
    )
    from app.services.audit import record_audit

    record_audit(
        db,
        action="file.download_ticket",
        actor_user_id=actor.id,
        entity_type="file",
        entity_id=str(stored.id),
        detail={"context": "farakhan"},
    )
    db.commit()
    return {"ticket": token, "expires_at": expires}


@router.get("/admin/files/{file_id}/download")
def farakhan_file_download(
    file_id: uuid_mod.UUID,
    ticket: str = Query(default=""),
    db: Session = Depends(get_db),
) -> Response:
    """دانلود با بلیت امضاشده؛ محتوا از پروایدر ردیف فایل (local یا s3)."""
    from fastapi.responses import FileResponse
    from urllib.parse import quote as url_quote
    from app.services import file_storage as fs

    settings = get_settings()
    if not ticket:
        raise HTTPException(status_code=401, detail="بلیت دانلود الزامی است")
    verified = fs.verify_download_ticket(settings.auth_secret_key, ticket)
    if verified is None:
        raise HTTPException(status_code=401, detail="بلیت دانلود نامعتبر یا منقضی است")
    tid, _uid = verified
    if str(file_id) != tid:
        raise HTTPException(status_code=401, detail="بلیت متعلق به این فایل نیست")
    stored = db.get(StoredFile, file_id)
    link = db.scalar(select(FarakhanFile).where(FarakhanFile.file_id == file_id))
    if stored is None or stored.context != "farakhan" or link is None:
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    if stored.scan_status == "quarantined":
        raise HTTPException(status_code=403, detail="فایل در قرنطینه است")
    try:
        if stored.storage == "s3":
            data = objstore.open_bytes(settings.upload_dir, "s3", stored.storage_key, settings)
            return Response(
                content=data,
                media_type=stored.mime,
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{url_quote(stored.original_name)}",
                },
            )
        path = fs.storage_path(settings.upload_dir, stored.storage_key)
        return FileResponse(path, media_type=stored.mime, filename=stored.original_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="محتوای فایل در فضای ذخیره‌سازی یافت نشد")
    except Exception:
        raise HTTPException(status_code=502, detail="خواندن از سرویس ذخیره‌سازی ممکن نشد")


@router.get("/admin/export")
def export_farakhan_submissions(
    status: str = Query(default=""),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*FARAKHAN_ADMIN_ROLES)),
) -> StreamingResponse:
    """خروجی اکسل ثبت‌نام‌های فراخوان (فیلتر وضعیت اختیاری)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from urllib.parse import quote as url_quote

    stmt = select(FarakhanSubmission).order_by(FarakhanSubmission.created_at.desc())
    if status in FARAKHAN_STATUSES:
        stmt = stmt.where(FarakhanSubmission.status == status)
    rows = db.scalars(stmt).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "فراخوان همکاری"
    headers = [
        "کد پیگیری", "نام", "نام خانوادگی", "کد ملی", "جنسیت", "تاریخ تولد",
        "وضعیت سربازی", "مدرک", "رشته", "وضعیت پروانه", "شماره پروانه",
        "مالکیت مرکز", "استان", "شهرستان", "تلفن ثابت", "همراه", "کدپستی",
        "اتاق انفرادی", "اتاق گروهی", "اتاق کودک", "تعداد مشاور",
        "فضای انتظار", "الگوی شرکت", "دسترسی‌پذیری", "وضعیت بررسی",
        "یادداشت بررسی", "تاریخ ثبت",
    ]
    ws.append(headers)
    fill = PatternFill(start_color="F3DCE2", end_color="F3DCE2", fill_type="solid")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = fill
    for s in rows:
        ws.append([
            s.tracking_code, s.first_name, s.last_name, s.national_code,
            GENDER_OPTIONS.get(s.gender, s.gender), s.birth_date_jalali,
            MILITARY_STATUS_OPTIONS.get(s.military_status or "", "") or "",
            EDUCATION_DEGREE_OPTIONS.get(s.education_degree, s.education_degree),
            s.education_field,
            LICENSE_STATUS_OPTIONS.get(s.license_status, s.license_status),
            s.license_number or "",
            CENTER_OWNERSHIP_OPTIONS.get(s.center_ownership, s.center_ownership),
            s.province_name, s.county_name, s.phone, s.mobile_number or "",
            s.postal_code or "", s.individual_rooms, s.group_rooms, s.child_rooms,
            s.counselors_count,
            "بله" if s.has_waiting_space else "خیر",
            "بله" if s.accepts_company_pattern else "خیر",
            "بله" if s.has_accessibility else "خیر",
            STATUS_TITLES.get(s.status, s.status),
            s.review_note or "",
            s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "",
        ])
    for column, width in (("A", 16), ("B", 14), ("C", 18), ("D", 13), ("Q", 13)):
        ws.column_dimensions[column].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = url_quote("farakhan-submissions.xlsx")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
