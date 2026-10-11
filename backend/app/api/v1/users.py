import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import get_settings
from app.core.security import generate_activation_token
from app.db.session import get_db
from app.models.user import ROLE_CODES, ActivationToken, AuthSession, Role, User, UserStatus
from app.schemas.user import ActivationTokenOut, RolesUpdate, UserCreate, UserUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/users", tags=["users"])
settings = get_settings()


def _user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "mobile": user.mobile,
        "status": user.status,
        "must_change_password": user.must_change_password,
        "roles": sorted(r.code for r in user.roles),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _validate_role_codes(codes: list[str]) -> None:
    unknown = [c for c in codes if c not in ROLE_CODES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"نقش نامعتبر: {', '.join(unknown)}")


def _revoke_all_sessions(db: Session, user_id) -> None:
    now = datetime.now(timezone.utc)
    sessions = db.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    ).all()
    for s in sessions:
        s.revoked_at = now


@router.get("")
def list_users(
    search: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles("SYSTEM_ADMIN")),
) -> dict:
    q = select(User)
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(User.username.ilike(like), User.display_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [_user_out(u) for u in items], "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSTEM_ADMIN")),
) -> dict:
    username = payload.username.strip().lower()
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="این نام کاربری قبلاً ثبت شده است")
    _validate_role_codes(payload.roles)

    user = User(
        username=username,
        display_name=payload.display_name.strip(),
        email=(payload.email or None),
        mobile=(payload.mobile or None),
        status=UserStatus.PENDING,
        must_change_password=True,
    )
    if payload.roles:
        roles = db.scalars(select(Role).where(Role.code.in_(payload.roles))).all()
        user.roles = list(roles)
    db.add(user)
    db.commit()
    record_audit(
        db,
        action="user.created",
        actor_user_id=actor.id,
        entity_type="user",
        entity_id=str(user.id),
        detail={"username": username, "roles": payload.roles},
    )
    return _user_out(user)


@router.patch("/{user_id}")
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSTEM_ADMIN")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")

    changed: list[str] = []
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
        changed.append("display_name")
    if payload.email is not None:
        user.email = payload.email or None
        changed.append("email")
    if payload.mobile is not None:
        user.mobile = payload.mobile or None
        changed.append("mobile")
    if payload.status is not None:
        if payload.status not in (UserStatus.ACTIVE, UserStatus.DISABLED, UserStatus.PENDING):
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        if payload.status != user.status:
            user.status = payload.status
            user.auth_version += 1  # ابطال نشست‌ها - بند ۴.۲ سند
            _revoke_all_sessions(db, user.id)
            changed.append("status")

    db.commit()
    record_audit(
        db, action="user.updated", actor_user_id=actor.id,
        entity_type="user", entity_id=str(user.id), detail={"changed": changed},
    )
    return _user_out(user)


@router.put("/{user_id}/roles")
def set_roles(
    user_id: uuid.UUID,
    payload: RolesUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSTEM_ADMIN")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    _validate_role_codes(payload.roles)

    roles = db.scalars(select(Role).where(Role.code.in_(payload.roles))).all()
    user.roles = list(roles)
    user.auth_version += 1  # تغییر حساس نقش → ابطال نشست‌ها
    _revoke_all_sessions(db, user.id)
    db.commit()
    record_audit(
        db, action="user.roles_changed", actor_user_id=actor.id,
        entity_type="user", entity_id=str(user.id), detail={"roles": payload.roles},
    )
    return _user_out(user)


@router.post("/{user_id}/activation-token", response_model=ActivationTokenOut)
def create_activation(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSTEM_ADMIN")),
) -> ActivationTokenOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")

    raw, token_hash = generate_activation_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.activation_token_expire_hours)
    db.add(ActivationToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()
    record_audit(
        db, action="user.activation_token_created", actor_user_id=actor.id,
        entity_type="user", entity_id=str(user.id),
    )
    return ActivationTokenOut(token=raw, expires_at=expires_at)
