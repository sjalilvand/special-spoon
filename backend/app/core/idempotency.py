"""فاز ۴۲ - ADR-05 گام ۳: میان‌افزار Idempotency-Key واقعی عملیات مالی.

قرارداد (طرح ۴ گام ADR-05): هر POST مالی می‌تواند هدر ``Idempotency-Key``
(UUID کلاینت) بفرستد؛ سرور کلید را با اثر عملیات در جدول ``idempotency_keys``
ذخیره می‌کند و تکرار همان کلید → همان پاسخ قبلی (بدون ایجاد ردیف دوم).
این قرارداد پیش‌نیاز اپ موبایل (B17) برای «دوبار-زدن دکمه پرداخت» روی
شبکه ناپایدار است.

محدوده اعمال (گام ۳ طرح — ابتدای مسیر، بسط بعدی در گام‌های آتی):
- ``POST /orders`` و ``POST /orders/{order_id}/payments`` — روی هر دو پیشوند
  نسخه (/api/v1 و /api/v2) چون همان روت‌ها دوبار سوار شده‌اند (ADR-03)؛
  مسیر نرمال‌شده (بدون پیشوند نسخه) ثبت می‌شود تا یک کلید بین دو نسخه هم
  بازپخش شود، اما استفاده همان کلید روی منبع دیگر تعارض ۴۰۹ است.
- بدون هدر → رفتار فعلی بدون تغییر (قرارداد opt-in؛ قیود یکتایی DB خط
  دفاعی دوم باقی می‌مانند).

جایگاه در پشته میان‌افزارها (add_middleware: بعدی = بیرونی‌تر):
- داخل‌تر از EnvelopeMiddleware تا پاسخ بازپخش‌شده روی v2 هم عیناً پاکت‌بندی
  شود (همان پاکت پاسخ اول)؛ بیرونی‌تر از NullByteGuard تا رد 422 آن هم
  رزرو را آزاد کند؛ V1DeprecationMiddleware (بیرونی‌ترین) هدرهای انقضای v1
  را روی پاسخ بازپخش‌شده v1 هم می‌گذارد.
"""
from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.envelope import API_V2_PREFIX
from app.db.session import SessionLocal
from app.services import idempotency as idem

HEADER_NAME = "Idempotency-Key"
REPLAYED_HEADER = "Idempotency-Replayed"
MAX_KEY_LEN = 128

# POST /orders و POST /orders/{order_id}/payments — پس از حذف پیشوند نسخه
FINANCIAL_PATH = re.compile(r"^/orders(?:/[^/]+/payments)?$")
FINANCIAL_ENDPOINTS_DOC = ("POST /orders", "POST /orders/{order_id}/payments")


def financial_core_path(path: str, api_prefix: str) -> str | None:
    """مسیر نرمال‌شده مالی (بدون پیشوند نسخه)؛ None یعنی خارج از محدوده قرارداد.

    هر دو پیشوند /api/v1 و /api/v2 پذیرفته می‌شود — همان روت‌ها دوبار سوار
    شده‌اند (ADR-03) و ثبت با مسیر نرمال‌شده یعنی یک کلید بین دو نسخه هم
    بازپخش می‌شود.
    """
    for prefix in (api_prefix, API_V2_PREFIX):
        if path == prefix or path.startswith(prefix + "/"):
            return "/" + path[len(prefix):].lstrip("/")
    return None


def normalize_key(raw: str | None) -> str:
    return (raw or "").strip()


def key_is_valid(key: str) -> bool:
    if not key or len(key) > MAX_KEY_LEN:
        return False
    return all(ch >= " " for ch in key)  # بدون کاراکتر کنترلی


def payload_fingerprint(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


class FinancialIdempotencyMiddleware(BaseHTTPMiddleware):
    """گام ۳ طرح ADR-05 — رزرو/بازپخش/آزادسازی کلید حول هندلر مالی."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method.upper() != "POST":
            return await call_next(request)

        s = get_settings()
        core = financial_core_path(request.url.path, s.api_prefix)
        if core is None or not FINANCIAL_PATH.match(core):
            return await call_next(request)

        key = normalize_key(request.headers.get(HEADER_NAME.lower()))
        if not key:
            return await call_next(request)
        if not key_is_valid(key):
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "کلید Idempotency نامعتبر است؛ رشته غیرخالی تا ۱۲۸ نویسه بدون کاراکتر کنترلی بفرستید."
                },
            )

        # بدنه پیش از عبور خوانده می‌شود؛ starlette آن را برای پایین‌دست کش می‌کند
        body_bytes = await request.body()
        payload_hash = payload_fingerprint(body_bytes)

        db: Session = SessionLocal()
        try:
            state, snapshot = idem.reserve(db, key, core, payload_hash)
        finally:
            db.close()

        if state == idem.REPLAY:
            return self._replayed_response(key, snapshot)
        if state == idem.INFLIGHT:
            return JSONResponse(
                status_code=409,
                headers={HEADER_NAME: key},
                content={
                    "detail": "درخواست دیگری با همین کلید Idempotency در جریان است؛ پس از دریافت پاسخ آن، همین درخواست را با همان کلید بفرستید."
                },
            )
        if state == idem.CONFLICT:
            return JSONResponse(
                status_code=409,
                headers={HEADER_NAME: key},
                content={
                    "detail": "این کلید Idempotency قبلاً برای درخواست متفاوتی استفاده شده است؛ برای درخواست جدید کلید تازه (UUID) بسازید."
                },
            )

        # OWNER — اجرای عادی + ثبت اثر یا آزادسازی رزرو
        try:
            response = await call_next(request)
        except Exception:
            self._release(key)
            raise

        ctype = (response.headers.get("content-type") or "").lower()
        if response.status_code >= 400 or not ctype.startswith("application/json"):
            # عملیات ماندگار انجام نشده (یا پاسخ قابل‌ثبت نیست) → رزرو آزاد
            self._release(key)
            return response

        body = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body += chunk
        try:
            payload = json.loads(body) if body else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        if payload is None:
            self._release(key)
            return Response(
                content=body,
                status_code=response.status_code,
                media_type="application/json",
            )

        db = SessionLocal()
        try:
            idem.store_snapshot(db, key, response.status_code, payload)
        finally:
            db.close()

        rebuilt = Response(
            content=body,
            status_code=response.status_code,
            media_type="application/json",
        )
        rebuilt.headers[HEADER_NAME] = key
        for k, v in response.headers.raw:
            lk = k.lower()
            if lk in (b"content-length", b"content-type", b"idempotency-key"):
                continue
            rebuilt.headers.append(k.decode("latin-1"), v.decode("latin-1"))
        return rebuilt

    def _replayed_response(self, key: str, snapshot: dict) -> Response:
        status = int(snapshot.get("status_code") or 200)
        body = snapshot.get("body")
        return JSONResponse(
            status_code=status,
            headers={HEADER_NAME: key, REPLAYED_HEADER: "true"},
            content=body,
        )

    def _release(self, key: str) -> None:
        db = SessionLocal()
        try:
            idem.release(db, key)
        except Exception:  # fail-soft — آزادسازی ناموفق با TTL رزرو جبران می‌شود
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()
