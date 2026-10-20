"""فاز ۴۳ - ADR-05 گام‌های ۱–۲: میان‌افزار سقف نرخ سراسری (لایه سرویس).

قرارداد سند (بند ۲ تصمیم ADR-05 + گام ۲ طرح):
- پنجره لغزان Redis به‌عنوان تک‌منبع حقیقت بین نمونه‌ها (گام ۱ طرح)؛
- کلید سقف: ``(route, user_id)`` برای احرازشده و ``(route, ip)`` برای
  ناشناس — route با فروریختن شناسه‌ها (:id) نرمال می‌شود تا مسیرهای
  پارامتری سطل واحد داشته باشند و حدس‌زدن شناسه‌های تازه سقف را دور نزند؛
- سقف پیش‌فرض: ۱۲۰/دقیقه برای ناشناس (عمومی) و ۶۰/دقیقه برای احرازشده +
  override per-route در Settings (بند گام ۲ طرح) + لیست بی‌سقف
  (توکن‌های سرویس/مشتریان اداری SLA-دار)؛
- پاسخ ۴۲۹ با هدر ``Retry-After`` و ``X-RateLimit-Limit/Remaining`` (برای
  مشتریان اداری SLA-دار — آستانهٔ بند ۴ سند)؛ بدنه قرارداد v1
  (``{"detail"}``) — روی v2 پاکت‌بندی می‌شود چون میان‌افزار داخل‌تر از
  EnvelopeMiddleware است؛
- ثبت ۴۲۹ در audit با نرخ نمونه‌برداری (بند گام ۲ طرح) — در حمله، فزونی
  رد شدن‌ها نباید خودش به سیل نوشتن DB تبدیل شود؛ شکست audit بی‌اثر است؛
- لایه قاعده (سقف‌های per-feature: تلاش ورود/OTP/نگهداشت/دستیار) عیناً
  برقرار می‌ماند — این لایه «محافظ اضافه» است نه جایگزین؛
- نبود Redis/خطای Redis → fail-open با هشدار (بند ۶ سند).

جایگاه در پشته (add_middleware: بعدی = بیرونی‌تر):
- داخل‌تر از EnvelopeMiddleware و V1DeprecationMiddleware → ۴۲۹ روی v2
  پاکت‌بندی می‌شود و ۴۲۹ روی v1 هدرهای انقضا می‌گیرد؛
- بیرونی‌تر از FinancialIdempotencyMiddleware و NullByteGuard → درخواستِ
  رد‌شده هرگز رزرو کلید idempotency نمی‌کند و هزینه هندلر مالی نمی‌پردازد.
"""
from __future__ import annotations

import json
import logging
import random
import re
import uuid as uuid_mod

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.envelope import API_V2_PREFIX
from app.core import redis_client
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.services.audit import record_audit
from app.services.rate_limit import sliding_window_hit

logger = logging.getLogger("rosepsy.rate_limit")

HEADER_LIMIT = "X-RateLimit-Limit"
HEADER_REMAINING = "X-RateLimit-Remaining"
WINDOW_SECONDS = 60  # پنجره سقف‌های پیش‌فرض و overrideها (per-minute)

# شناسه‌های مسیر (عدد، UUID یا هش طولانی) → :id تا سطل مسیر پارامتری واحد شود
_SEGMENT_ID = re.compile(
    r"^(?:\d+|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{20,})$"
)
# مسیرهای معاف (پس از حذف پیشوند نسخه): سلامت و اسناد API
_EXEMPT_CORE = ("/docs", "/redoc", "/openapi.json", "/health")

_429_DETAIL = "تعداد درخواست‌ها بیش از حد مجاز است؛ لطفاً پس از مدت اعلام‌شده در هدر Retry-After تلاش کنید."


def normalize_route(path: str) -> str:
    """نرمال‌سازی مسیر به قالب روت (شناسه‌ها → :id) برای سطل واحد."""
    return "/" + "/".join(":id" if _SEGMENT_ID.match(seg) else seg for seg in path.split("/") if seg)


def core_path(path: str, api_prefix: str) -> str | None:
    """مسیر بدون پیشوند نسخه (/api/v1 و /api/v2)؛ None یعنی خارج از دامنه."""
    for prefix in (api_prefix, API_V2_PREFIX):
        if path == prefix or path.startswith(prefix + "/"):
            return "/" + path[len(prefix):].lstrip("/")
    return None


def client_ip(request: Request) -> str:
    """همان الگوی auth.py/public.py — IP واقعی پشت Nginx."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _override_hit(overrides: dict, method: str, path: str) -> int | None:
    """تطبیق override: دقیق «METHOD مسیر» → «* مسیر» → پیشوندی با * پایانی."""
    exact = overrides.get(f"{method} {path}")
    if exact is None:
        exact = overrides.get(f"* {path}")
    if exact is not None:
        return exact
    for key, value in overrides.items():
        if not key.endswith("*"):
            continue
        method_part, _, path_part = key.partition(" ")
        if not path_part.startswith("/"):
            continue  # شکل نامعتبر — نادیده
        prefix = path_part[:-1] if path_part.endswith("*") else path_part
        if path.startswith(prefix) and method_part in ("*", method):
            return value
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """گام ۲ طرح ADR-05 — سقف نرخ سراسری Redis با پاسخ ۴۲۹ استاندارد."""

    def __init__(self, app):
        super().__init__(app)
        # کش پارس overrideها/whitelist به کلیدِ رشتهٔ خام Settings
        self._overrides_cache: tuple[str, dict] = ("", {})
        self._whitelist_cache: tuple[str, frozenset] = ("", frozenset())

    # ----------------------------- پیکربندی -----------------------------
    def _overrides(self, s) -> dict:
        raw = (s.rate_limit_overrides or "").strip()
        if self._overrides_cache[0] != raw:
            parsed: dict = {}
            if raw:
                try:
                    # فقط متد بزرگ‌نویسی می‌شود؛ مسیر حساس به حروف است
                    for k, v in dict(json.loads(raw)).items():
                        method, _, path = str(k).strip().partition(" ")
                        parsed[f"{method.upper()} {path.strip()}"] = int(v)
                except Exception:
                    logger.warning("RATE_LIMIT_OVERRIDES قابل تفسیر نیست؛ نادیده گرفته شد")
            self._overrides_cache = (raw, parsed)
        return self._overrides_cache[1]

    def _whitelist(self, s) -> frozenset:
        raw = (s.rate_limit_whitelist_user_ids or "").strip()
        if self._whitelist_cache[0] != raw:
            self._whitelist_cache = (raw, frozenset(x.strip() for x in raw.split(",") if x.strip()))
        return self._whitelist_cache[1]

    # ------------------------------ هویت -------------------------------
    @staticmethod
    def _user_sub(request: Request) -> str | None:
        """sub از توکن Bearer — بدون DB؛ توکن نامعتبر/ناموجود = ناشناس."""
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return None
        try:
            payload = decode_access_token(auth[7:])
            return str(payload.get("sub")) or None
        except Exception:
            return None

    # --------------------------- جریان اصلی ----------------------------
    async def dispatch(self, request: Request, call_next) -> Response:
        s = get_settings()
        if not s.rate_limit_enabled:
            return await call_next(request)

        core = core_path(request.url.path, s.api_prefix)
        if core is None or core in _EXEMPT_CORE or core.startswith("/health/"):
            return await call_next(request)

        # سطل با روت نرمال‌شده (شناسه‌ها → :id) — مسیرهای پارامتری سطل واحد دارند
        full = normalize_route(request.url.path)
        core = normalize_route(core)

        user_sub = self._user_sub(request)
        if user_sub and user_sub in self._whitelist(s):
            return await call_next(request)
        identity = f"u:{user_sub}" if user_sub else f"ip:{client_ip(request)}"

        limit = self._resolve_limit(request.method.upper(), core, full, user_sub, s)
        if limit <= 0:
            return await call_next(request)

        rc = redis_client.get_redis()  # مرجع ماژولی — برای جایگزینی در آزمون‌ها
        if rc is None:  # Redis تنظیم‌نشده/در دسترس نیست → fail-open
            return await call_next(request)

        route = f"{request.method.upper()} {core}"
        bucket = f"rl:{route}:{identity}"
        try:
            decision = sliding_window_hit(rc, bucket, limit=limit, window_seconds=WINDOW_SECONDS)
        except Exception as exc:
            logger.warning(
                "سقف نرخ: Redis در دسترس نیست (%s)؛ درخواست fail-open عبور کرد",
                exc.__class__.__name__,
            )
            return await call_next(request)

        if not decision.exceeded:
            return await call_next(request)

        self._audit_429(s, user_sub=user_sub, route=route, identity=identity, decision=decision)
        return JSONResponse(
            status_code=429,
            headers={
                "Retry-After": str(decision.retry_after or WINDOW_SECONDS),
                HEADER_LIMIT: str(decision.limit),
                HEADER_REMAINING: "0",
            },
            content={"detail": _429_DETAIL},
        )

    def _resolve_limit(self, method: str, core: str, full: str, user_sub: str | None, s) -> int:
        """سقف موثر: override per-route (مسیر هسته بدون نسخه → مسیر کامل) → پیش‌فرض."""
        ov = self._overrides(s)
        hit = _override_hit(ov, method, core)  # اول مسیر بدون نسخه — هر دو نسخه را می‌پوشاند
        if hit is None:
            hit = _override_hit(ov, method, full)  # سپس مسیر کامل با پیشوند نسخه
        if hit is not None:
            return hit
        return s.rate_limit_auth_per_minute if user_sub else s.rate_limit_public_per_minute

    # ----------------------------- audit -------------------------------
    def _audit_429(self, s, *, user_sub: str | None, route: str, identity: str, decision) -> None:
        """ثبت ۴۲۹ در audit با نرخ نمونه‌برداری (بند گام ۲ طرح) — بی‌ثبات به خطا."""
        rate = max(0.0, min(1.0, float(s.rate_limit_audit_sample_rate)))
        if random.random() >= rate:
            return
        db = None
        try:
            db = SessionLocal()
            record_audit(
                db,
                action="rate_limit.429",
                actor_user_id=uuid_mod.UUID(user_sub) if user_sub else None,
                entity_type="route",
                entity_id=route[:64],
                result="blocked",
                detail={
                    "identity": identity,
                    "limit": decision.limit,
                    "window_seconds": WINDOW_SECONDS,
                    "retry_after": decision.retry_after,
                    "mechanism": "global_redis_rate_limit",
                },
                ip=identity[3:] if identity.startswith("ip:") else None,
            )
        except Exception as exc:
            logger.warning("ثبت audit سقف نرخ ناموفق بود (%s)؛ بی‌اثر", exc.__class__.__name__)
        finally:
            if db is not None:
                db.close()
