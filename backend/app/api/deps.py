import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserStatus


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="احراز هویت لازم است")
    try:
        payload = decode_access_token(auth[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="نشست نامعتبر است؛ دوباره وارد شوید")

    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="حساب فعال نیست")
    if payload.get("ver") != user.auth_version:
        # بند ۴.۲: تغییر حساس باعث ابطال نشست‌های قبلی می‌شود
        raise HTTPException(status_code=401, detail="نشست منقضی شده است؛ دوباره وارد شوید")
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def require_roles(*role_codes: str):
    """کنترل مجوز سمت سرور - بند ۳.۲ سند"""

    def checker(user: User = Depends(get_current_user)) -> User:
        user_role_codes = {r.code for r in user.roles}
        if not user_role_codes.intersection(set(role_codes)):
            raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")
        return user

    return checker


# ---------------------------------------------------------------------------
# فاز ۵۲ - کنترل دسترسی ریزدانه بر اساس ماتریس نقش ↔ دسترسی
# - نقش SYSTEM_ADMIN همیشه دسترسی کامل دارد (bypass) تا مدیر خودش را قفل نکند؛
# - اثربخشی کاربر = اجتماع دسترسی‌های همهٔ نقش‌های او (role_permissions)؛
# - ``require_perm`` مکمل ``require_roles`` است؛ روت‌های موجود با require_roles
#   دست‌نخورده می‌مانند و روت‌های جدید (rbac/chat/...) از require_perm استفاده
#   می‌کنند تا ماتریس گرافیکی پنل واقعاً اثر عملیاتی داشته باشد.
# ---------------------------------------------------------------------------
def user_permissions(db: Session, user: User) -> set[str]:
    """مجموعهٔ کدهای دسترسی مؤثر کاربر؛ ``*`` یعنی همه."""
    from app.models.rbac import effective_permissions

    return effective_permissions(user.roles)


def require_perm(*perm_codes: str):
    """سازندهٔ دیپندنسی: کاربر باید حداقل یکی از دسترسی‌های داده‌شده را داشته باشد."""

    def checker(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> User:
        perms = user_permissions(db, user)
        if "*" in perms:
            return user
        if not perms.intersection(set(perm_codes)):
            raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")
        return user

    return checker
