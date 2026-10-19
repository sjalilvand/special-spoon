"""فاز ۳۸ - ADR-03 سند جامع: پاکت پاسخ استاندارد {data, meta, errors} روی /api/v2.

قرارداد نسخه v1 دست‌نخورده می‌ماند (سازگاری کامل فرانت و اپ موبایل فعلی)؛
نسخه v2 همان روت‌های v1 را با پاکت استاندارد سند عرضه می‌کند:

- موفقیت: ``{"data": <payload>, "meta": {...}, "errors": null}``
- خطا:    ``{"data": null, "meta": {...}, "errors": [{"code", "message", "details"?}]}``
- پاسخ غیر JSON (دانلود فایل/بلیت B39، 204 بدون بدنه) بدون تغییر عبور می‌کند.

قواعد پاکت:
- ``meta`` همیشه شامل ``request_id`` (uuid تصادفی)، ``timestamp`` (ISO-8601 UTC)،
  ``version="v2"`` و ``duration_ms`` است؛
- اگر کلاینت هدر ``Idempotency-Key`` بفرستد، همان کلید در ``meta`` اکو می‌شود
  (زمینه‌سازی قرارداد ADR-05 برای عملیات مالی؛ ذخیره اثر واقعی سرور = گام ۳ ADR-05)؛
- برای پاسخ‌های صفحه‌بندی‌شده ``{items, ...}``: ``items`` به ``data`` می‌رود و
  بقیه کلیدها (total/page/page_size/unread/...) داخل ``meta.pagination`` قرار
  می‌گیرند تا قرارداد آتی v2 فهرست‌محور شود؛
- خطاها از بدنه ``{"detail": ...}`` FastAPI نگاشت می‌شوند: رشته → یک خطای
  ``{"code", "message"}``؛ فهرست خطاهای اعتبارسنجی 422 → نگاشت loc/msg/type؛
  هر شکل دیگری → ``{"code": "http_<status>", "message": <پیام پیش‌فرض>, "details": <بدنه>}``.
- استثناهای مدیریت‌نشده 500 با بدنه متنی، بدون تغییر عبور می‌کنند (لاگ استاندارد
  سرور حفظ می‌شود) — نگاشت کامل خطاها به‌تدریج در v2 کامل می‌شود.
"""
from __future__ import annotations

import json
import time
import uuid as uuid_mod

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

API_V2_PREFIX = "/api/v2"

# نگاشت وضعیت HTTP به کد پایدار پاکت (قرارداد v2 — کدها هرگز تغییر نمی‌کنند)
_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    423: "locked",
    429: "rate_limited",
    500: "internal_error",
    502: "bad_gateway",
    503: "service_unavailable",
}

_STATUS_MESSAGES = {
    400: "درخواست نامعتبر است",
    401: "احراز هویت لازم است",
    403: "دسترسی مجاز نیست",
    404: "منبع یافت نشد",
    405: "متد مجاز نیست",
    409: "تعارض در وضعیت منبع",
    413: "حجم درخواست بیش از حد مجاز است",
    422: "اعتبارسنجی درخواست ناموفق بود",
    423: "منبع قفل است",
    429: "سقف نرخ درخواست پر شده است",
    500: "خطای داخلی سرور",
    503: "سرویس در دسترس نیست",
}


def code_for_status(status: int) -> str:
    return _STATUS_CODES.get(status, f"http_{status}")


def default_message(status: int) -> str:
    return _STATUS_MESSAGES.get(status, "خطا در پردازش درخواست")


def split_items(payload: object) -> tuple[object, dict]:
    """پاسخ‌های صفحه‌بندی‌شده {items, ...} → (items, {"pagination": {...}})."""
    if isinstance(payload, dict) and "items" in payload:
        rest = {k: v for k, v in payload.items() if k != "items"}
        return payload["items"], ({"pagination": rest} if rest else {})
    return payload, {}


def errors_from(payload: object, status: int) -> list[dict]:
    """نگاشت بدنه خطای FastAPI به فهرست استاندارد errors پاکت."""
    detail = payload.get("detail") if isinstance(payload, dict) else None
    errors: list[dict] = []
    if isinstance(detail, str):
        errors.append({"code": code_for_status(status), "message": detail})
    elif isinstance(detail, list):
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(x) for x in item.get("loc", []))
                msg = item.get("msg") or default_message(status)
                entry: dict = {"code": str(item.get("type") or "validation_error"),
                               "message": f"{loc}: {msg}" if loc else msg}
                if item.get("loc") is not None:
                    entry["details"] = {"loc": item.get("loc"), "type": item.get("type")}
                errors.append(entry)
            else:
                errors.append({"code": "validation_error", "message": str(item)})
    else:
        entry = {"code": code_for_status(status), "message": default_message(status)}
        if payload:
            entry["details"] = payload
        errors.append(entry)
    return errors


def build_meta(request: Request, request_id: str, duration_ms: int) -> dict:
    meta: dict = {
        "request_id": request_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": "v2",
        "duration_ms": duration_ms,
    }
    # زمینه‌سازی Idempotency-Key (ADR-05) — فقط اکو؛ اثر سرور در گام ۳ ADR-05
    idem = (request.headers.get("idempotency-key") or "").strip()
    if idem:
        meta["idempotency_key"] = idem[:200]
    return meta


class EnvelopeMiddleware(BaseHTTPMiddleware):
    """پاکت‌بندی پاسخ‌های JSON فقط روی پیشوند /api/v2 — v1 دست‌نخورده."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not (path == API_V2_PREFIX or path.startswith(API_V2_PREFIX + "/")):
            return await call_next(request)

        request_id = uuid_mod.uuid4().hex
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)

        ctype = (response.headers.get("content-type") or "").lower()
        if not ctype.startswith("application/json"):
            # دانلود فایل (B39)، 204 بدون بدنه، پاسخ‌های متنی — بدون پاکت
            return response

        body = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body += chunk
        try:
            payload = json.loads(body) if body else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None

        meta = build_meta(request, request_id, duration_ms)
        if response.status_code < 400:
            data, extra_meta = split_items(payload)
            meta.update(extra_meta)
            envelope = {"data": data, "meta": meta, "errors": None}
        else:
            envelope = {"data": None, "meta": meta,
                        "errors": errors_from(payload, response.status_code)}

        content = json.dumps(envelope, ensure_ascii=False, default=str).encode("utf-8")
        wrapped = Response(
            content=content,
            status_code=response.status_code,
            media_type="application/json",
        )
        # حفظ هدرهای معنادار (set-cookie، retry-after، www-authenticate و ...)
        for k, v in response.headers.raw:
            lk = k.lower()
            if lk in (b"content-length", b"content-type"):
                continue
            wrapped.headers.append(k.decode("latin-1"), v.decode("latin-1"))
        return wrapped
