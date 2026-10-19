"""فاز ۳۹ - محافظ ورودی: رد درخواست‌های دارای نویسه NUL (0x00).

چرا: PostgreSQL در ستون‌های متنی بایت NUL را نمی‌پذیرد و psycopg با
«PostgreSQL text fields cannot contain NUL (0x00) bytes» خطا می‌دهد؛
این خطا در بعضی مسیرها به 500 نشت می‌کرد (کشف‌شده در آزمون قرارداد Schemathesis).
قرارداد درست: رد زودهنگام درخواست با 422 (validation_error در پاکت v2)،
پیش از رسیدن به لایه دیتابیس — روی هر دو نسخه v1 و v2.

نکته ظریف: NUL به سه شکل به سرور می‌رسد و هر سه باید رد شوند:
1. بایت خام 0x00 در بدنه (بدنه‌های باینری/form)؛
2. گریز JSON یعنی «\\u0000» — بعد از json.loads به NUL واقعی تبدیل می‌شود؛
3. انکودینگ درصد یعنی «%00» در کوئری‌استرینگ/بدنه form — پس از decode.
برای اطمینان از بدون مثبت‌کاذب بودن، بدنه JSON واقعاً parse و رشته‌های
دیکودشده بازرسی می‌شوند.
"""
from __future__ import annotations

import json
from urllib.parse import unquote

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

_NUL = "\x00"
_NUL_BYTES = b"\x00"
_JSON_TYPES = ("application/json", "application/x-www-form-urlencoded")
_DETAIL = {"detail": "درخواست شامل نویسه مجاز نیست (NUL/0x00)"}


def _parsed_contains_nul(payload: object) -> bool:
    """بازرسی بازگشتی رشته‌های دیکودشده (پس از JSON parse)."""
    if isinstance(payload, str):
        return _NUL in payload
    if isinstance(payload, dict):
        return any(_parsed_contains_nul(k) or _parsed_contains_nul(v) for k, v in payload.items())
    if isinstance(payload, (list, tuple)):
        return any(_parsed_contains_nul(x) for x in payload)
    return False


def _reject() -> JSONResponse:
    return JSONResponse(_DETAIL, status_code=422)


class NullByteGuardMiddleware:
    """میان‌افزار خالص ASGI — بدون سربار BaseHTTPMiddleware."""

    def __init__(self, app):  # type: ignore[no-untyped-def]
        self.app = app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # مسیر (starlette درصد-گشایی‌شده) و کوئری‌استرینگ (خام → دستی دیکود)
        path = scope.get("path") or ""
        query_raw = scope.get("query_string") or b""
        if _NUL in path or _NUL in unquote(query_raw.decode("latin-1", "ignore")):
            await _reject()(scope, receive, send)
            return

        headers = Headers(scope=scope)
        ctype = (headers.get("content-type") or "").lower()
        if not ctype.startswith(_JSON_TYPES):
            await self.app(scope, receive, send)
            return

        # خواندن کامل بدنه و بازپخش به پایین‌دست
        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                return
        body = b"".join(chunks)

        async def replay_receive():  # type: ignore[no-untyped-def]
            return {"type": "http.request", "body": body, "more_body": False}

        if _NUL_BYTES in body:
            await _reject()(scope, replay_receive, send)
            return

        if ctype.startswith("application/json"):
            # گریز «\u0000» فقط بعد از parse به NUL تبدیل می‌شود — دقیق بررسی می‌کنیم
            try:
                parsed = json.loads(body) if body else None
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed = None
            if parsed is not None and _parsed_contains_nul(parsed):
                await _reject()(scope, replay_receive, send)
                return
        else:
            # فرم urlencoded: «%00» پس از دیکود NUL است
            if _NUL in unquote(body.decode("latin-1", "ignore")):
                await _reject()(scope, replay_receive, send)
                return

        await self.app(scope, replay_receive, send)
