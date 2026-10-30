import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_password_hasher = PasswordHasher()
settings = get_settings()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(
    *, user_id: str, auth_version: int, expires_minutes: int | None = None
) -> str:
    """توکن دسترسی — به‌طور پیش‌فرض با انقضای استاندارد settings؛
    فاز ۶۰: impersonation با ``expires_minutes`` طولانی‌تر صادر می‌شود."""
    now = datetime.now(timezone.utc)
    minutes = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    payload = {
        "sub": user_id,
        "ver": auth_version,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "typ": "access",
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.auth_secret_key, algorithms=["HS256"])
    if payload.get("typ") != "access":
        raise ValueError("invalid token type")
    return payload


def generate_refresh_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    return token, hash_token(token)


def generate_activation_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_random_password(length: int = 16) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def is_https_request(request) -> bool:
    """تشخیص HTTPS واقعی — از هدر X-Forwarded-Proto (پشت پراکسی مثل Caddy)
    یا اسکیم خود درخواست.

    چرا مهم است: کوکی با فلگ Secure روی HTTP ساده توسط مرورگر دور ریخته می‌شود
    و کاربر در صفحهٔ ورود گیر می‌کند (همان باگ شناخته‌شدهٔ رز هاب روی
    http://130.185.73.157). تشخیص از اسکیم واقعی یعنی روی HTTPS همچنان Secure
    می‌ماند و روی HTTP ساده هم ورود کار می‌کند.
    """
    try:
        forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
        if forwarded:
            return forwarded == "https"
        scheme = getattr(getattr(request, "url", None), "scheme", "") or ""
        return scheme == "https"
    except Exception:
        return False
