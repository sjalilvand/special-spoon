"""فاز ۴۲ - ADR-05 گام ۳: پایش و نگهداری کلیدهای Idempotency عملیات مالی.

GET  /api/v1/idempotency-keys           فهرست کلیدها + آمار (کل/در جریان/ثبت‌شده)
POST /api/v1/idempotency-keys/purge     پاک‌سازی ردیف‌های کهنه (>۲۴ ساعت پیش‌فرض)

دسترسی: SYSTEM_ADMIN — purge در audit ثبت می‌شود.
تا عملیاتی‌شدن beat صف کار (ADR-02)، همین روت جایگزین زمان‌بند است و
پاک‌سازی تنبل ساعتی داخل reserve هم فعال است.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.idempotency import IdempotencyKey
from app.services import idempotency as idem
from app.services.audit import record_audit

router = APIRouter(prefix="/idempotency-keys", tags=["idempotency"])

ADMIN_ROLES = ("SYSTEM_ADMIN",)


@router.get("")
def list_keys(
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    """فهرست کلیدهای اخیر + آمار شفافیت (بدون هیچ محتوای بالینی)."""
    total = int(idem.keys_summary(db)["total"])
    rows = db.scalars(
        select(IdempotencyKey)
        .order_by(IdempotencyKey.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [idem.key_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": idem.keys_summary(db),
    }


@router.post("/purge")
def purge_keys(
    before_hours: int | None = Query(default=None, ge=1, le=24 * 365),
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    """پاک‌سازی ردیف‌های کهنه — پیش‌فرض از تنظیمات (۲۴ ساعت طرح ADR-05)."""
    purged = idem.purge_expired(db, before_hours=before_hours)
    result = {"purged": purged, "before_hours": before_hours}
    record_audit(
        db,
        action="idempotency.keys_purged",
        actor_user_id=actor.id,
        entity_type="idempotency_keys",
        detail=result,
    )
    return result
