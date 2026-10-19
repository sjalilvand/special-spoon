"""فاز ۳۰ - B20 سند جامع: API استرداد وجه.

- درخواست: مالک سفارش یا کارکنان (مبلغ ≤ مجاز؛ سفارش باید پرداخت‌شده باشد).
- بررسی (approve/reject با یادداشت): مدیر سازمان/سامانه.
- اجرا: مدیر سازمان/سامانه — اتمیک؛ «اجرای تکراری ممنوع».
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.payment import Order
from app.models.refund import RefundRequest, RefundRequestStatus
from app.models.user import User
from app.services import refunds as refund_svc
from app.services.refunds import RefundError

router = APIRouter(tags=["refunds"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
VIEW_ROLES = (*MANAGE_ROLES, "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")


def _notify_refund(db: Session, user_id, title: str, body: str, severity: str = "info") -> None:
    from app.services.notifications import notify_user

    try:
        notify_user(db, recipient_user_id=user_id, event_code="refund.updated",
                    title=title, body=body, category="payment", severity=severity,
                    entity_type="refund_request")
    except Exception:
        db.rollback()


class RefundRequestCreate(BaseModel):
    order_id: uuid.UUID
    amount: int = Field(gt=0, le=1_000_000_000_000)
    reason: str = Field(min_length=5, max_length=500)


class ReviewPayload(BaseModel):
    action: str = Field(description="approve | reject")
    note: str | None = Field(default=None, max_length=500)


@router.post("/refund-requests", status_code=201)
def create_refund_request(
    payload: RefundRequestCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    order = db.get(Order, payload.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    is_staff = any(r.code in VIEW_ROLES for r in actor.roles)
    if not is_staff and order.owner_user_id != actor.id:
        raise HTTPException(status_code=403, detail="فقط مالک سفارش یا کارکنان مجازند")
    try:
        req = refund_svc.create_request(
            db, order, requested_by=actor, amount=payload.amount, reason=payload.reason
        )
    except RefundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _notify_refund(
        db, order.owner_user_id, "درخواست استرداد ثبت شد",
        f"درخواست استرداد {int(req.amount):,} ریال برای سفارش {order.order_number} ثبت و در انتظار بررسی است.",
    )
    return refund_svc.request_out(db, req)


@router.get("/refund-requests")
def list_refund_requests(
    status: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    q = select(RefundRequest).order_by(RefundRequest.created_at.desc()).limit(200)
    if status:
        if status not in RefundRequestStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        q = q.where(RefundRequest.status == status)
    is_staff = any(r.code in VIEW_ROLES for r in actor.roles)
    if not is_staff:
        q = q.join(Order, Order.id == RefundRequest.order_id).where(Order.owner_user_id == actor.id)
    items = db.scalars(q).all()
    return {"items": [refund_svc.request_out(db, r) for r in items]}


@router.post("/refund-requests/{request_id}/review")
def review_refund_request(
    request_id: uuid.UUID,
    payload: ReviewPayload,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    req = db.get(RefundRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    try:
        req = refund_svc.review_request(db, req, actor=actor, action=payload.action, note=payload.note)
    except RefundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    order = db.get(Order, req.order_id)
    _notify_refund(
        db, order.owner_user_id if order else req.requested_by,
        "نتیجه بررسی استرداد",
        f"درخواست استرداد {int(req.amount):,} ریال "
        f"{'تأیید شد و قابل اجراست' if req.status == RefundRequestStatus.APPROVED else 'رد شد'}."
        + (f" یادداشت: {req.decision_note}" if req.decision_note else ""),
        severity="info" if req.status == RefundRequestStatus.APPROVED else "warning",
    )
    return refund_svc.request_out(db, req)


@router.post("/refund-requests/{request_id}/execute")
def execute_refund_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    req = db.get(RefundRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    try:
        refund = refund_svc.execute_request(db, req, actor=actor)
    except RefundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    order = db.get(Order, req.order_id)
    _notify_refund(
        db, order.owner_user_id if order else req.requested_by, "استرداد اجرا شد",
        f"استرداد {int(refund.amount):,} ریال برای سفارش {order.order_number} اجرا شد؛ "
        + ("مبلغ به کیف پول شما بازگشت." if refund.channel == "wallet" else "بازگشت از مسیر درگاه انجام می‌شود."),
    )
    return refund_svc.request_out(db, req)
