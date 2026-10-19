"""فاز ۳۰ - B20 سند جامع: چرخه استرداد وجه.

قواعد سند:
- «استرداد از مبلغ مجاز بیشتر ممنوع» — مجاز = مبلغ پرداخت‌شده −
  استردادهای اجراشده؛ در درخواست و اجرا (اتمیک) کنترل می‌شود.
- «اجرای تکراری ممنوع» — درخواست فقط از وضعیت approved اجرا می‌شود و
  وضعیت اتمیک به executed تغییر می‌کند؛ جمع استردادها از پرداختی
  عبور نمی‌کند.
- مسیر بازگشت: wallet → شارژ کیف پول؛ sandbox → رسید شبیه‌ساز؛
  zarinpal → ثبت برای استرداد دستی از پنل درگاه.
"""
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Order, OrderStatus, Payment, PaymentStatus
from app.models.refund import Refund, RefundRequest, RefundRequestStatus
from app.models.user import User


class RefundError(Exception):
    """خطای قابل نمایش کاربر."""


def refundable_amount(db: Session, order: Order) -> int:
    paid = int(order.payable_amount) if order.status == OrderStatus.PAID else 0
    refunded = int(Decimal(order.refunded_amount or 0))
    return max(0, paid - refunded)


def _last_successful_payment(db: Session, order_id) -> Payment | None:
    return db.scalars(
        select(Payment).where(Payment.order_id == order_id, Payment.status == PaymentStatus.SUCCESS)
        .order_by(Payment.paid_at.desc())
    ).first()


def create_request(db: Session, order: Order, *, requested_by, amount: int, reason: str) -> RefundRequest:
    if order.status != OrderStatus.PAID:
        raise RefundError("استرداد فقط برای سفارش پرداخت‌شده امکان‌پذیر است")
    if amount <= 0:
        raise RefundError("مبلغ استرداد باید مثبت باشد")
    refundable = refundable_amount(db, order)
    if amount > refundable:
        raise RefundError(f"مبلغ استرداد از مبلغ مجاز بیشتر است (مجاز: {refundable:,})")
    req = RefundRequest(
        order_id=order.id,
        requested_by=requested_by.id,
        amount=amount,
        currency=order.currency,
        reason=reason.strip()[:500],
        status=RefundRequestStatus.PENDING,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def review_request(db: Session, req: RefundRequest, *, actor, action: str, note: str | None) -> RefundRequest:
    if req.status != RefundRequestStatus.PENDING:
        raise RefundError("این درخواست قبلاً بررسی شده است")
    if action not in ("approve", "reject"):
        raise RefundError("اقدام نامعتبر است")
    if action == "approve":
        order = db.get(Order, req.order_id)
        if order is None or refundable_amount(db, order) < int(req.amount):
            raise RefundError("مبلغ مجاز سفارش برای تأیید این درخواست کافی نیست")
        req.status = RefundRequestStatus.APPROVED
    else:
        req.status = RefundRequestStatus.REJECTED
    req.decided_by = actor.id
    req.decided_at = datetime.now(timezone.utc)
    req.decision_note = (note or "").strip()[:500] or None
    db.commit()
    db.refresh(req)
    return req


def execute_request(db: Session, req: RefundRequest, *, actor) -> Refund:
    """اجرای اتمیک استرداد: کنترل مجاز + ثبت ردیف + به‌روزرسانی سفارش/کیف پول."""
    if req.status == RefundRequestStatus.EXECUTED:
        raise RefundError("این درخواست قبلاً اجرا شده است (اجرای تکراری ممنوع)")
    if req.status != RefundRequestStatus.APPROVED:
        raise RefundError("فقط درخواست تأییدشده قابل اجراست")

    order = db.get(Order, req.order_id)
    if order is None:
        raise RefundError("سفارش یافت نشد")
    amount = int(req.amount)

    # کنترل اتمیک سقف مجاز با قفل ردیف سفارش
    locked_order = db.scalars(
        select(Order).where(Order.id == order.id).with_for_update()
    ).first()
    if refundable_amount(db, locked_order) < amount:
        db.rollback()
        raise RefundError("مبلغ مجاز سفارش برای این استرداد کافی نیست")

    payment = _last_successful_payment(db, order.id)
    channel = payment.gateway if payment and payment.gateway == "wallet" else "gateway"
    refund = Refund(
        refund_request_id=req.id,
        order_id=order.id,
        payment_id=payment.id if payment else None,
        amount=amount,
        currency=req.currency,
        channel=channel,
        gateway=payment.gateway if channel == "gateway" else None,
        gateway_ref=_gateway_ref_for(payment, channel),
        note="استرداد از پنل درگاه انجام می‌شود" if channel == "gateway" and payment and payment.gateway == "zarinpal" else None,
        executed_by=actor.id,
    )
    db.add(refund)
    db.flush()
    locked_order.refunded_amount = Decimal(locked_order.refunded_amount or 0) + amount
    req.status = RefundRequestStatus.EXECUTED

    if channel == "wallet":
        from app.services.wallet import credit, WalletEntryReason
        credit(
            db, order.owner_user_id, amount, WalletEntryReason.REFUND, commit=False,
            order_id=order.id, refund_id=refund.id,
            note=f"بازگشت وجه استرداد - سفارش {order.order_number}",
            created_by=actor.id,
        )
    # فاز ۳۱ - B22: سند خودکار استرداد در همان تراکنش (برگشت از فروش)
    from app.services.accounting import entry_for_refund
    entry_for_refund(db, refund, commit=False)
    db.commit()
    db.refresh(refund)
    return refund


def _gateway_ref_for(payment: Payment | None, channel: str) -> str | None:
    if channel == "wallet":
        return None
    if payment is None:
        return None
    if payment.gateway == "sandbox":
        return "SBXRF-" + secrets.token_hex(5).upper()
    return payment.gateway_ref  # زرین‌پال: رسید اصلی؛ استرداد از پنل


def request_out(db: Session, req: RefundRequest) -> dict:
    order = db.get(Order, req.order_id)
    refund = db.scalars(select(Refund).where(Refund.refund_request_id == req.id)).first()
    requester = db.get(User, req.requested_by)
    return {
        "id": str(req.id),
        "order_id": str(req.order_id),
        "order_number": order.order_number if order else None,
        "requested_by": str(req.requested_by),
        "requested_by_name": requester.display_name if requester else None,
        "amount": float(req.amount),
        "currency": req.currency,
        "reason": req.reason,
        "status": req.status,
        "decided_at": req.decided_at.isoformat() if req.decided_at else None,
        "decision_note": req.decision_note,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "refund": {
            "id": str(refund.id),
            "channel": refund.channel,
            "gateway": refund.gateway,
            "gateway_ref": refund.gateway_ref,
            "amount": float(refund.amount),
            "executed_at": refund.executed_at.isoformat() if refund.executed_at else None,
        } if refund else None,
    }
