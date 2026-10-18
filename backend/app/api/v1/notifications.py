"""B12/B38 سند جامع - API مرکز اعلان.

GET  /api/v1/notifications              لیست اعلان‌های من (فیلتر خوانده‌نشده + صفحه‌بندی)
GET  /api/v1/notifications/unread-count شمارنده زنگ اعلان
POST /api/v1/notifications/{id}/read    علامت‌گذاری خوانده‌شدن
POST /api/v1/notifications/read-all     خواندن همه
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.services.audit import record_audit

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _out(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "category": n.category,
        "event_code": n.event_code,
        "title": n.title,
        "body": n.body,
        "severity": n.severity,
        "entity_type": n.entity_type,
        "entity_id": n.entity_id,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    """فقط اعلان‌های خود کاربر - بند B38: کاربر غیرعضو اعلان دیگران را نمی‌بیند."""
    q = select(Notification).where(Notification.recipient_user_id == actor.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    rows = db.scalars(
        q.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    unread = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_user_id == actor.id,
            Notification.read_at.is_(None),
        )
    )
    return {"items": [_out(n) for n in rows], "unread": int(unread or 0)}


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    cnt = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_user_id == actor.id,
            Notification.read_at.is_(None),
        )
    )
    return {"count": int(cnt or 0)}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    n = db.get(Notification, notification_id)
    # 404 به‌جای 403 برای جلوگیری از افشای وجود اعلان متعلق به دیگری (IDOR)
    if n is None or n.recipient_user_id != actor.id:
        raise HTTPException(status_code=404, detail="اعلان یافت نشد")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        record_audit(
            db,
            action="notification.read",
            actor_user_id=actor.id,
            entity_type="notification",
            entity_id=str(n.id),
        )
    return _out(n)


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    now = datetime.now(timezone.utc)
    res = db.execute(
        update(Notification)
        .where(Notification.recipient_user_id == actor.id, Notification.read_at.is_(None))
        .values(read_at=now)
    )
    db.commit()
    return {"updated": res.rowcount or 0}
