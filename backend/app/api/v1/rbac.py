"""فاز ۵۲ - API مدیریت نقش‌ها و ماتریس دسترسی (پشتیبان رابط گرافیکی پنل).

- ``GET  /rbac/permissions``           کاتالوگ دسترسی‌ها گروه‌بندی‌شده بر بخش
- ``GET  /rbac/roles``                  فهرست نقش‌ها با ماتریس و data_scope
- ``POST /rbac/roles``                  ساخت نقش سفارشی
- ``PUT  /rbac/roles/{code}``           ویرایش عنوان/scope/ماتریس دسترسی
- ``DELETE /rbac/roles/{code}``         حذف نقش سفارشی (بدون کاربر متصل)

همهٔ روت‌ها با ``require_perm("roles.manage")`` (یا users.view برای خواندن)
محافظت می‌شوند؛ SYSTEM_ADMIN به‌صورت ذاتی دسترسی کامل دارد.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_perm, user_permissions
from app.db.session import get_db
from app.models.rbac import DATA_SCOPES, DATA_SCOPE_TITLES, Permission, role_permissions_table
from app.models.user import SYSTEM_ROLE_CODES, Role, User, user_roles_table
from app.services.audit import record_audit

router = APIRouter(prefix="/rbac", tags=["rbac"])

_ROLE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,49}$")


class RoleUpsert(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    data_scope: str = "all"
    permissions: list[str] = []


def _role_out(db: Session, role: Role, member_count: int | None = None) -> dict:
    perms = sorted(p.code for p in role.permissions)
    out: dict = {
        "code": role.code,
        "title": role.title,
        "data_scope": role.data_scope,
        "data_scope_title": DATA_SCOPE_TITLES.get(role.data_scope, role.data_scope),
        "permissions": perms,
        "is_system": role.code in SYSTEM_ROLE_CODES,
    }
    if member_count is not None:
        out["member_count"] = member_count
    return out


def _get_role_or_404(db: Session, code: str) -> Role:
    role = db.get(Role, code)
    if role is None:
        raise HTTPException(status_code=404, detail="نقش یافت نشد")
    return role


def _validate_scope(scope: str) -> None:
    if scope not in DATA_SCOPES:
        raise HTTPException(
            status_code=422,
            detail=f"سطح داده نامعتبر است؛ مقادیر مجاز: {', '.join(DATA_SCOPES)}",
        )


def _validate_perm_codes(db: Session, codes: list[str]) -> None:
    known = set(db.scalars(select(Permission.code)).all())
    unknown = [c for c in codes if c not in known]
    if unknown:
        raise HTTPException(status_code=422, detail=f"دسترسی نامعتبر: {', '.join(unknown)}")


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_perm("roles.view", "users.view")),
) -> dict:
    """کاتالوگ دسترسی‌ها گروه‌بندی‌شده — ستون‌های ماتریس گرافیکی."""
    rows = db.scalars(select(Permission).order_by(Permission.section, Permission.sort, Permission.code)).all()
    sections: list[dict] = []
    order: list[str] = []
    by_section: dict[str, list[dict]] = {}
    for p in rows:
        if p.section not in by_section:
            by_section[p.section] = []
            order.append(p.section)
        by_section[p.section].append({"code": p.code, "title": p.title})
    for s in order:
        sections.append({"section": s, "permissions": by_section[s]})
    return {"sections": sections, "total": len(rows)}


@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_perm("roles.view", "users.view")),
) -> dict:
    roles = db.scalars(select(Role).order_by(Role.code)).all()
    counts = dict(
        db.execute(
            select(user_roles_table.c.role_code, func.count())
            .group_by(user_roles_table.c.role_code)
        ).all()
    )
    return {"items": [_role_out(db, r, counts.get(r.code, 0)) for r in roles]}


@router.get("/me/permissions")
def my_permissions(
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("*")),
) -> dict:
    """دسترسی‌های مؤثر کاربر جاری — برای گیت‌کردن منو و دکمه‌های پنل."""
    return {"permissions": sorted(user_permissions(db, actor))}


@router.put("/roles/{code}")
def update_role(
    code: str,
    payload: RoleUpsert,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("roles.manage")),
) -> dict:
    role = _get_role_or_404(db, code)
    _validate_scope(payload.data_scope)
    _validate_perm_codes(db, payload.permissions)

    role.title = payload.title.strip()
    role.data_scope = payload.data_scope
    rows = db.scalars(select(Permission).where(Permission.code.in_(payload.permissions))).all()
    role.permissions = list(rows)
    db.commit()
    record_audit(
        db, action="rbac.role_updated", actor_user_id=actor.id,
        entity_type="role", entity_id=code,
        detail={"permissions": sorted(p.code for p in rows), "data_scope": payload.data_scope},
    )
    return _role_out(db, role)


@router.post("/roles/{code}", status_code=201)
def create_role_with_code(
    code: str,
    payload: RoleUpsert,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("roles.manage")),
) -> dict:
    code = code.strip().upper()
    if not _ROLE_CODE_RE.match(code):
        raise HTTPException(
            status_code=422,
            detail="کد نقش باید حروف لاتین بزرگ/زیرخط، بین ۳ تا ۵۰ نویسه باشد (مثال: HR_MANAGER)",
        )
    if db.get(Role, code) is not None:
        raise HTTPException(status_code=409, detail="این کد نقش قبلاً ثبت شده است")
    _validate_scope(payload.data_scope)
    _validate_perm_codes(db, payload.permissions)

    role = Role(code=code, title=payload.title.strip(), data_scope=payload.data_scope)
    rows = db.scalars(select(Permission).where(Permission.code.in_(payload.permissions))).all()
    role.permissions = list(rows)
    db.add(role)
    db.commit()
    record_audit(
        db, action="rbac.role_created", actor_user_id=actor.id,
        entity_type="role", entity_id=code,
        detail={"permissions": sorted(p.code for p in rows)},
    )
    return _role_out(db, role)


@router.delete("/roles/{code}")
def delete_role(
    code: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("roles.manage")),
) -> dict:
    role = _get_role_or_404(db, code)
    if role.code in SYSTEM_ROLE_CODES:
        raise HTTPException(status_code=403, detail="نقش‌های سیستمی قابل حذف نیستند")
    members = db.scalar(
        select(func.count()).select_from(
            select(user_roles_table.c.user_id).where(user_roles_table.c.role_code == code).subquery()
        )
    ) or 0
    if members:
        raise HTTPException(
            status_code=409,
            detail=f"این نقش به {members} کاربر متصل است؛ ابتدا نقش کاربران را تغییر دهید",
        )
    db.delete(role)
    db.commit()
    record_audit(
        db, action="rbac.role_deleted", actor_user_id=actor.id,
        entity_type="role", entity_id=code,
    )
    return {"ok": True}
