"""B12+ فاز ۲۷ - مدیریت صف خروجی ایمیل اعلان‌ها.

GET  /api/v1/email-outbox           فهرست ردیف‌های صف (فیلتر وضعیت + صفحه‌بندی)
POST /api/v1/email-outbox/process   اجرای ارسال ردیف‌های pending (محدود)

دسترسی: SYSTEM_ADMIN / ORG_MANAGER - هر دو عملیات در audit ثبت می‌شوند.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.email_outbox import EmailOutbox
from app.services.audit import record_audit
from app.services.email_outbox import outbox_summary, process_outbox

router = APIRouter(prefix="/email-outbox", tags=["email-outbox"])

ADMIN_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")

_STATUS_META = ("pending", "sent", "failed", "disabled")


def _out(row: EmailOutbox) -> dict:
    return {
        "id": str(row.id),
        "notification_id": str(row.notification_id) if row.notification_id else None,
        "recipient_email": row.recipient_email,
        "subject": row.subject,
        "status": row.status,
        "attempts": row.attempts,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
    }


@router.get("")
def list_outbox(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    q = select(EmailOutbox)
    if status:
        if status not in _STATUS_META:
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        q = q.where(EmailOutbox.status == status)
    total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = db.scalars(
        q.order_by(EmailOutbox.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": outbox_summary(db),
    }


@router.post("/process")
def process_queue(
    limit: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    """ارسال ردیف‌های صف؛ در حالت بدون SMTP، ردیف‌ها disabled می‌شوند (شفافیت DPO)."""
    result = process_outbox(db, limit=limit)
    record_audit(
        db,
        action="email.outbox_processed",
        actor_user_id=actor.id,
        entity_type="email_outbox",
        detail=result,
    )
    db.commit()
    return result
