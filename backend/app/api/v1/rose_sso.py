"""ورود یکپارچه (SSO) با رز هاب — Rose Hub

پروتکل نسخه پایه (BASIC) طبق «docs/sso-integration-fa.md» در مخزن رز هاب:
رز هاب کاربرِ احرازهویت‌شده را با ``?sso_token=<JWT HS256>`` به این سامانه
برمی‌گرداند. توکن با clientSecret اختصاصی سامانه (rose-psy-5c3f9b) امضا شده،
اعتبار ۵ دقیقه دارد و فقط یک‌بار باید مصرف شود. پس از اعتبارسنجی، حساب کاربر
پیدا یا ساخته شده و نشست عادی سامانه (AuthSession + refresh cookie) برقرار
می‌شود — یعنی کاربر با همان هویت رز هاب، بدون رمز جداگانه وارد Rosepsy می‌شود.

مسیرها:
- ``GET  /api/v1/auth/rose-sso?sso_token=...`` — جریان مرورگری؛ پس از ورود
  به ``/panel`` ریدایرکت می‌کند (پارامتر توکن از نشانی پاک می‌شود).
- ``POST /api/v1/auth/rose-sso`` با بدنه ``{"token": ...}`` — برای استفاده
  برنامه‌نویسی‌شده از سمت SPA.
"""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    is_https_request,
)
from app.db.session import get_db
from app.models.user import AuthSession, User, UserStatus
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["rose-sso"])
settings = get_settings()

REFRESH_COOKIE = "rosepsy_refresh"  # همان کوکی مسیر /api در auth.py


class RoseSSORequest(BaseModel):
    token: str


def _decode_rose_hub_token(raw: str) -> dict:
    """اعتبارسنجی توکن رز هاب — امضا، مخاطب (aud)، صادرکننده (iss) و انقضا."""
    try:
        return jwt.decode(
            raw,
            settings.rose_hub_client_secret,
            algorithms=["HS256"],
            audience=settings.rose_hub_client_id,
            issuer="rose-hub",
            leeway=60,
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="توکن ورود یکپارچه نامعتبر یا منقضی است؛ دوباره از رز هاب وارد شوید",
        )


def _find_or_create_user(db: Session, claims: dict) -> User:
    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=422, detail="توکن ورود یکپارچه فاقد ایمیل است")

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        # ساخت خودکار حساب بر اساس هویت تأییدشده رز هاب؛ گذرواژه تصادفی
        # غیرقابل حدس (ورود فقط از مسیر SSO/بازیابی رمز ممکن است)
        base = email.split("@")[0][:80].replace(" ", "") or "rosehub"
        username = base
        i = 1
        while db.scalar(select(User).where(User.username == username)) is not None:
            i += 1
            username = f"{base}{i}"
        user = User(
            username=username,
            display_name=(claims.get("name") or email)[:200],
            email=email,
            password_hash=hash_password(os.urandom(24).hex()),
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    if user.status == UserStatus.DISABLED:
        raise HTTPException(status_code=403, detail="حساب کاربری شما غیرفعال است")
    return user


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _open_session(db: Session, user: User, request: Request) -> str:
    """ساخت AuthSession و بازگرداندن refresh token (همان الگوی login)."""
    token, token_hash = generate_refresh_token()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
        ip=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:400],
    )
    db.add(session)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return token


def _set_refresh_cookie(response: Response, token: str, request: Request) -> None:
    # فیکس ورود یکپارچه روی HTTP ساده: کوکی Secure فقط روی HTTPS واقعی —
    # روی http://130.185.73.157 مرورگر کوکیِ Secure را دور می‌ریخت و کاربر
    # پس از تأیید توکن باز هم به صفحهٔ ورود برمی‌گشت (همان باگ رز هاب).
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        httponly=True,
        secure=is_https_request(request),
        samesite="lax",
        path="/api",
    )


def _issue_login(db: Session, raw_token: str, request: Request, response: Response):
    payload = _decode_rose_hub_token(raw_token)
    user = _find_or_create_user(db, payload)
    refresh = _open_session(db, user, request)
    record_audit(
        db,
        action="auth.rose_sso",
        actor_user_id=user.id,
        detail={"ip": _client_ip(request), "via": "rose-hub", "jti": payload.get("jti")},
    )
    _set_refresh_cookie(response, refresh, request)
    return user


@router.get("/rose-sso")
def rose_sso_redirect(
    request: Request,
    sso_token: str = "",
    db: Session = Depends(get_db),
):
    """جریان مرورگری: اعتبارسنجی توکن، برقراری نشست و ریدایرکت به برنامه."""
    if not sso_token:
        # ورود مستقیم → هدایت به رز هاب برای احراز هویت (جریان SP-initiated)
        return RedirectResponse(settings.rose_hub_launch_url)
    # مقصد: پنل سامانه — پس از برقراری نشست، اسپای پنل با کوکی refresh
    # به‌طور خودکار وارد می‌شود؛ پارامتر sso_token هم از نشانی پاک می‌شود.
    response = RedirectResponse("/panel", status_code=303)
    _issue_login(db, sso_token, request, response)
    return response


@router.post("/rose-sso")
def rose_sso_api(
    payload: RoseSSORequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = _issue_login(db, payload.token, request, response)
    return {
        "access_token": create_access_token(
            user_id=str(user.id), auth_version=user.auth_version
        ),
        "token_type": "bearer",
        "must_change_password": user.must_change_password,
    }
