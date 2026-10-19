"""فاز ۳۶ - B28 سند جامع: یکپارچه‌سازی‌های بیرونی.

GET  /api/v1/integrations/config   وضعیت همه یکپارچه‌سازی‌های بیرونی — بدون هیچ کلیدی
GET  /api/v1/sms-outbox            فهرست ردیف‌های صف پیامک (فیلتر وضعیت + صفحه‌بندی)
POST /api/v1/sms-outbox/process    اجرای ارسال ردیف‌های pending (محدود)

دسترسی: SYSTEM_ADMIN / ORG_MANAGER — کلید هرگز در خروجی نمی‌آید و عملیات
در audit ثبت می‌شود.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.integration import SmsOutbox
from app.services.audit import record_audit
from app.services.integrations import integrations_config_out, process_sms_outbox, sms_outbox_summary

router = APIRouter(tags=["integrations"])

ADMIN_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")

_STATUS_META = ("pending", "sent", "failed", "disabled")


def _out(row: SmsOutbox) -> dict:
    return {
        "id": str(row.id),
        "notification_id": str(row.notification_id) if row.notification_id else None,
        "recipient_mobile": row.recipient_mobile,
        "purpose": row.purpose,
        "body": row.body,
        "provider": row.provider,
        "status": row.status,
        "attempts": row.attempts,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
    }


@router.get("/integrations/config")
def integrations_config(_actor=Depends(require_roles(*ADMIN_ROLES))) -> dict:
    """شفافیت B28 — وضعیت همه یکپارچه‌سازی‌های بیرونی بدون هیچ کلیدی."""
    return {"integrations": integrations_config_out()}


@router.get("/sms-outbox")
def list_sms_outbox(
    status: str | None = Query(default=None),
    purpose: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    q = select(SmsOutbox)
    if status:
        if status not in _STATUS_META:
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        q = q.where(SmsOutbox.status == status)
    if purpose:
        q = q.where(SmsOutbox.purpose == purpose.strip()[:30])
    total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = db.scalars(
        q.order_by(SmsOutbox.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": sms_outbox_summary(db),
    }


@router.post("/sms-outbox/process")
def process_queue(
    limit: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    """ارسال ردیف‌های صف پیامک؛ در حالت بدون سرویس، ردیف‌ها disabled می‌شوند."""
    result = process_sms_outbox(db, limit=limit)
    record_audit(
        db,
        action="integrations.sms_outbox_processed",
        actor_user_id=actor.id,
        entity_type="sms_outbox",
        detail={k: v for k, v in result.items()},
    )
    db.commit()
    return result


@router.post("/sms-outbox/{row_id}/retry")
def retry_row(
    row_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*ADMIN_ROLES)),
) -> dict:
    """بازگذاری ردیف failed در صف — retry دستی توسط مدیر."""
    row = db.get(SmsOutbox, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ردیف یافت نشد")
    if row.status != "failed":
        raise HTTPException(status_code=409, detail="فقط ردیف failed قابل تلاش مجدد است")
    row.status = "pending"
    row.attempts = 0
    row.last_error = None
    record_audit(
        db,
        action="integrations.sms_outbox_retried",
        actor_user_id=actor.id,
        entity_type="sms_outbox",
        entity_id=str(row.id),
    )
    db.commit()
    return _out(row)
