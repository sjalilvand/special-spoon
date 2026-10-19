"""فاز ۲۹ - B10/B11 سند جامع: سفارش، پرداخت و فاکتور.

B10 قواعد سند:
- سفارش از snapshot قیمت نوبت/تعرفه ساخته می‌شود (B07: قیمت گذشته تغییر نکند)؛
- پرداخت فقط پس از «تأیید قطعی سمت سرور» موفق است؛ callback تکراری بی‌اثر؛
- شکست اعلان، پرداخت موفق را برنمی‌گرداند (B12).

B11 قواعد سند:
- پس از پرداخت موفق دقیقاً یک فاکتور با شماره یکتا؛ مبلغ فاکتور با
  snapshot سفارش منطبق است.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.appointment import Appointment
from app.models.catalog import Service
from app.models.payment import Invoice, InvoiceItem, Order, OrderStatus
from app.models.user import User
from app.services import payments as pay
from app.services.notifications import notify_user

router = APIRouter(tags=["payments"])

VIEW_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")
CREATE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION")


def _order_number(db: Session) -> str:
    from app.core.dates import gregorian_to_jalali
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    jy, _, _ = gregorian_to_jalali(now.year, now.month, now.day)
    from sqlalchemy import text

    for _ in range(30):
        count = db.execute(
            text("SELECT COUNT(*) FROM orders WHERE order_number LIKE :pfx"),
            {"pfx": f"ORD-{jy:04d}-%"},
        ).scalar() or 0
        candidate = f"ORD-{jy:04d}-{count + 1:06d}"
        taken = db.scalars(select(Order.id).where(Order.order_number == candidate)).first()
        if taken is None:
            return candidate
    raise HTTPException(status_code=500, detail="تولید شماره سفارش ناموفق بود")


def _order_out(db: Session, o: Order, with_invoice: bool = True) -> dict:
    data = {
        "id": str(o.id),
        "order_number": o.order_number,
        "owner_user_id": str(o.owner_user_id),
        "case_id": str(o.case_id) if o.case_id else None,
        "appointment_id": str(o.appointment_id) if o.appointment_id else None,
        "service_id": str(o.service_id) if o.service_id else None,
        "title": o.title,
        "amount": float(o.amount),
        "currency": o.currency,
        "discount_amount": float(o.discount_amount) if o.discount_amount is not None else None,
        "payable_amount": float(o.payable_amount),
        "status": o.status,
        "note": o.note,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }
    if with_invoice:
        inv = db.scalars(select(Invoice).where(Invoice.order_id == o.id)).first()
        data["invoice_id"] = str(inv.id) if inv else None
        data["invoice_number"] = inv.invoice_number if inv else None
    return data


def _can_view_order(actor: User, order: Order) -> bool:
    if any(r.code in VIEW_ROLES for r in actor.roles):
        return True
    return order.owner_user_id == actor.id


# ---------------------------------------------------------------- orders
class OrderCreate(BaseModel):
    appointment_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    discount_amount: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)
    owner_user_id: uuid.UUID | None = None


@router.get("/orders")
def list_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    q = select(Order).order_by(Order.created_at.desc()).limit(200)
    if status:
        if status not in OrderStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        q = q.where(Order.status == status)
    if not any(r.code in VIEW_ROLES for r in actor.roles):
        q = q.where(Order.owner_user_id == actor.id)
    orders = db.scalars(q).all()
    return {"items": [_order_out(db, o) for o in orders]}


@router.get("/orders/{order_id}")
def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    if not _can_view_order(actor, order):
        raise HTTPException(status_code=403, detail="دسترسی به این سفارش مجاز نیست")
    out = _order_out(db, order)
    pays = db.scalars(
        select(pay.Payment).where(pay.Payment.order_id == order.id).order_by(pay.Payment.created_at)
    ).all()
    out["payments"] = [
        {
            "id": str(p.id),
            "gateway": p.gateway,
            "amount": float(p.amount),
            "status": p.status,
            "authority": p.authority,
            "gateway_ref": p.gateway_ref,
            "fail_reason": p.fail_reason,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pays
    ]
    return out


@router.post("/orders", status_code=201)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*CREATE_ROLES)),
) -> dict:
    """ساخت سفارش با snapshot مبلغ از نوبت (اولویت) یا تعرفه جاری خدمت."""
    amount = None
    currency = "IRR"
    tariff_version_id = None
    service_id = payload.service_id
    title = (payload.title or "").strip()

    if payload.appointment_id is not None:
        appt = db.get(Appointment, payload.appointment_id)
        if appt is None:
            raise HTTPException(status_code=404, detail="نوبت یافت نشد")
        dup = db.scalars(select(Order.id).where(Order.appointment_id == appt.id)).first()
        if dup is not None:
            raise HTTPException(status_code=409, detail="برای این نوبت قبلاً سفارش ساخته شده است")
        if appt.price_amount is None:
            raise HTTPException(status_code=422, detail="نوبت فاقد قیمت snapshot است؛ ابتدا تعرفه را ثبت کنید")
        amount = int(appt.price_amount)
        currency = appt.price_currency or "IRR"
        tariff_version_id = appt.tariff_version_id
        service_id = appt.service_id or payload.service_id
        if not title:
            title = "خدمات مشاوره - نوبت"
    elif payload.service_id is not None:
        svc = db.get(Service, payload.service_id)
        if svc is None:
            raise HTTPException(status_code=404, detail="خدمت یافت نشد")
        from app.api.v1.catalog import current_tariff

        tariff = current_tariff(db, svc.id)
        if tariff is None:
            raise HTTPException(status_code=422, detail="برای این خدمت تعرفه معتبری وجود ندارد")
        amount = int(tariff.amount)
        currency = tariff.currency
        tariff_version_id = tariff.id
        if not title:
            title = svc.title
    else:
        raise HTTPException(status_code=422, detail="appointment_id یا service_id لازم است")

    discount = payload.discount_amount or 0
    if discount > amount:
        raise HTTPException(status_code=422, detail="تخفیف نمی‌تواند از مبلغ سفارش بیشتر باشد")

    owner = payload.owner_user_id or actor.id
    if db.get(User, owner) is None:
        raise HTTPException(status_code=404, detail="کاربر مالک سفارش یافت نشد")

    order = Order(
        order_number=_order_number(db),
        owner_user_id=owner,
        case_id=payload.case_id,
        appointment_id=payload.appointment_id,
        service_id=service_id,
        tariff_version_id=tariff_version_id,
        title=title[:300],
        amount=amount,
        currency=currency,
        discount_amount=discount if discount else None,
        payable_amount=amount - discount,
        status=OrderStatus.PENDING,
        note=payload.note,
        created_by=actor.id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


@router.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*CREATE_ROLES)),
) -> dict:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    if order.status == OrderStatus.PAID:
        raise HTTPException(status_code=409, detail="سفارش پرداخت‌شده قابل لغو نیست؛ از استرداد استفاده کنید (B20)")
    if order.status in (OrderStatus.CANCELLED, OrderStatus.FAILED):
        raise HTTPException(status_code=409, detail="سفارش قبلاً بسته شده است")
    order.status = OrderStatus.CANCELLED
    db.commit()
    return _order_out(db, order)


# ---------------------------------------------------------------- payments
class PaymentInit(BaseModel):
    gateway: str | None = Field(default=None, max_length=30)

@router.get("/payments/gateways")
def gateways(_actor: User = Depends(get_current_user)) -> dict:
    return {"items": pay.configured_gateways()}


@router.post("/orders/{order_id}/payments", status_code=201)
def start_payment(
    order_id: uuid.UUID,
    payload: PaymentInit,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*CREATE_ROLES)),
) -> dict:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    try:
        result = pay.initiate_payment(db, order, payload.gateway)
    except pay.GatewayError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "payment_id": str(result.payment.id),
        "authority": result.payment.authority,
        "gateway": result.payment.gateway,
        "amount": float(result.payment.amount),
        "redirect_url": result.redirect_url,
    }


@router.post("/payments/{authority}/verify")
def verify_payment(
    authority: str,
    approve: bool = True,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*CREATE_ROLES)),
) -> dict:
    """تأیید قطعی سمت سرور؛ callback تکراری بی‌اثر (idempotent)."""
    try:
        payment, result = pay.verify_payment(db, authority, approve=approve)
    except pay.GatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    order = db.get(Order, payment.order_id)
    if result.ok and order is not None:
        _notify_payment(db, payment, order)
    return {
        "payment_id": str(payment.id),
        "authority": payment.authority,
        "status": payment.status,
        "ok": result.ok,
        "reason": result.reason,
        "gateway_ref": payment.gateway_ref,
        "order_status": order.status if order else None,
        "idempotent": bool((result.payload or {}).get("idempotent")),
    }


@router.post("/payments/callback/{gateway}")
def gateway_callback(
    gateway: str,
    authority: str,
    approve: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    """callback درگاه - همان مسیر verify؛ تکرار آن بی‌اثر است."""
    try:
        payment, result = pay.verify_payment(db, authority, approve=approve)
    except pay.GatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    order = db.get(Order, payment.order_id)
    if result.ok and order is not None:
        _notify_payment(db, payment, order)
    return {
        "authority": payment.authority,
        "status": payment.status,
        "order_status": order.status if order else None,
    }


def _notify_payment(db: Session, payment: pay.Payment, order: Order) -> None:
    """اعلان B12 - شکست اعلان هرگز جریان پرداخت را برنمی‌گرداند."""
    try:
        info = pay.payment_notification(payment, order)
        notify_user(
            db,
            recipient_user_id=order.owner_user_id,
            event_code=info["event_code"],
            title=info["title"],
            body=info["body"],
            category=info["category"],
            severity=info["severity"],
            entity_type="order",
            entity_id=str(order.id),
        )
    except Exception:
        db.rollback()


# ---------------------------------------------------------------- invoices
def _invoice_out(db: Session, inv: Invoice) -> dict:
    order = db.get(Order, inv.order_id)
    items = db.scalars(
        select(InvoiceItem).where(InvoiceItem.invoice_id == inv.id).order_by(InvoiceItem.created_at)
    ).all()
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "order_id": str(inv.order_id),
        "order_number": order.order_number if order else None,
        "total_amount": float(inv.total_amount),
        "currency": inv.currency,
        "buyer_name": inv.buyer_name,
        "buyer_national_id": inv.buyer_national_id,
        "buyer_email": inv.buyer_email,
        "status": inv.status,
        "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
        "items": [
            {
                "id": str(i.id),
                "description": i.description,
                "quantity": i.quantity,
                "unit_amount": float(i.unit_amount),
                "line_total": float(i.line_total),
            }
            for i in items
        ],
    }


@router.get("/invoices")
def list_invoices(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    q = select(Invoice).order_by(Invoice.issued_at.desc()).limit(200)
    if not any(r.code in VIEW_ROLES for r in actor.roles):
        q = q.join(Order, Order.id == Invoice.order_id).where(Order.owner_user_id == actor.id)
    invoices = db.scalars(q).all()
    return {"items": [_invoice_out(db, i) for i in invoices]}


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="فاکتور یافت نشد")
    order = db.get(Order, inv.order_id)
    if not _can_view_order(actor, order):
        raise HTTPException(status_code=403, detail="دسترسی به این فاکتور مجاز نیست")
    return _invoice_out(db, inv)
