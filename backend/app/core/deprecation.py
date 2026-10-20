"""فاز ۴۱ - ADR-03 گام ۴: انقضای اعلام‌شده نسخه v1 با هدرهای استاندارد.

طرح ۴ گام سند ADR-03: «پس از منتقل‌شدن همه مصرف‌کنندگان، v1 به
"فقط-خواندنی با هدر Deprecation" و سپس حذف — حداقل یک چرخه انتشار فاصله.»

هر دو مصرف‌کننده شناخته‌شده (فرانت‌اند در فاز ۳۹ و اپ موبایل B17 در فاز ۴۰)
روی /api/v2 منتقل شده‌اند؛ این گام انقضا را «اعلام» می‌کند و حذف واقعی v1
به چرخه انتشار بعدی موکول می‌شود (فاصله الزامی سند):

- روی همه پاسخ‌های /api/v1 (موفق و خطا):
  * ``Deprecation: version="v1"`` — هدر انقضای پیش‌نویس IETF
    (draft-ietf-httpapi-deprecation-header)؛
  * ``Sunset: <HTTP-date>`` — RFC 8594؛ تاریخ پیشنهادی قطع از config
    (``v1_sunset_date`` به شکل YYYY-MM-DD)؛ مقدار نامعتبر/خالی → بدون Sunset؛
  * ``Warning: 299 - "..."`` — یادآوری برای پروکسی/مانیتورینگ.
- نسخه v2 و بقیه مسیرها (ریشه /، مستندات) بدون این هدرها می‌مانند.
- دو حالت عملیاتی (``v1_deprecation_mode``):
  * ``warn`` (پیش‌فرض): فقط هدر — سازگاری کامل، هیچ رفتاری عوض نمی‌شود؛
  * ``readonly``: کلید اضطراری چرخه حذف — متدهای نوشتاری v1 (POST/PUT/PATCH/
    DELETE) با 410 Gone و بدنه قرارداد v1 ({"detail": ...}) رد می‌شوند و
    خواندن (GET/HEAD/OPTIONS) برقرار می‌ماند. فعال‌سازی فقط پس از یک چرخه
    انتشار کامل با هدرهای انقضا (پایش لاگ/مانیتورینگ برای مصرف‌کننده جامانده).
- دانلود فایل B39 (GET) در هر دو حالت سر جایش است — هدرها صرفاً اطلاع‌رسانی‌اند.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

API_V1_PREFIX = "/api/v1"

# متدهای نوشتاری — در حالت readonly رد می‌شوند (خواندن برقرار می‌ماند)
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

DEPRECATION_VALUE = 'version="v1"'
WARNING_VALUE = '299 - "API version v1 is deprecated; migrate to /api/v2"'
READONLY_DETAIL = (
    "نسخه v1 منقضی شده و فقط-خواندنی است؛ درخواست‌های نوشتاری را با /api/v2 بفرستید."
)


def sunset_http_date(raw: str | None) -> str | None:
    """YYYY-MM-DD → HTTP-date استاندارد (RFC 8594)؛ خالی/نامعتبر → None.

    Sunset باید تاریخ آینده باشد؛ تاریخ گذشته هم پذیرفته می‌شود تا اپراتور
    آزاد باشد، اما هدر فقط وقتی ست می‌شود که مقدار قابل‌تحلیل باشد.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        day = datetime.strptime(raw, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
        )
    except ValueError:
        return None
    return format_datetime(day, usegmt=True)


def deprecation_headers(s=None) -> dict[str, str]:
    """هدرهای انقضای v1 — یک‌مکان برای میان‌افزار و آزمون‌ها."""
    s = s or get_settings()
    headers = {"Deprecation": DEPRECATION_VALUE, "Warning": WARNING_VALUE}
    sunset = sunset_http_date(getattr(s, "v1_sunset_date", "") or "")
    if sunset:
        headers["Sunset"] = sunset
    return headers


def deprecation_mode(s=None) -> str:
    """حالت انقضای v1 — warn (پیش‌فرض) | readonly؛ مقدار نامعتبر → warn."""
    s = s or get_settings()
    mode = (getattr(s, "v1_deprecation_mode", "warn") or "warn").strip().lower()
    return mode if mode in ("warn", "readonly") else "warn"


class V1DeprecationMiddleware(BaseHTTPMiddleware):
    """گام ۴ طرح ADR-03 — هدرهای انقضا فقط روی پیشوند /api/v1.

    در حالت readonly درخواست‌های نوشتاری پیش از مسیریابی با 410 رد می‌شوند
    (بدنه قرارداد v1: {"detail": ...})؛ هدرهای انقضا روی همه پاسخ‌ها — شامل
    همین 410 — ست می‌شوند تا کلاینت جامانده «چرا» را ببیند.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not (path == API_V1_PREFIX or path.startswith(API_V1_PREFIX + "/")):
            return await call_next(request)

        s = get_settings()
        if deprecation_mode(s) == "readonly" and request.method.upper() in WRITE_METHODS:
            response: Response = JSONResponse(status_code=410, content={"detail": READONLY_DETAIL})
        else:
            response = await call_next(request)

        for key, value in deprecation_headers(s).items():
            response.headers.setdefault(key, value)
        return response
