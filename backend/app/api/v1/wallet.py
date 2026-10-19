"""فاز ۳۰ - B18 سند جامع: API کیف پول.

- کاربر: مشاهده کیف پول و گردش‌ها، شارژ از درگاه (سفارش topup + موتور
  پرداخت فاز ۲۹)، پرداخت سفارش خود از اعتبار.
- مدیر سازمان/سامانه: فهرست کیف پول‌ها، گردش هر کاربر، تعدیل دستی با
  یادداشت (ردیف adjustment).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.payment import Order, OrderStatus
from app.models.user import User
from app.services import payments as pay
from app.services import wallet as wallet_svc
from app.services.notifications import notify_user

router = APIRouter(tags=["wallet"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")


def _notify_wallet(db: Session, user_id, title: str, body: str, severity: str = "info") -> None:
    try:
        notify_user(
            db, recipient_user_id=user_id, event_code="wallet.updated",
            title=title, body=body, category="payment", severity=severity,
            entity_type="wallet",
        )
    except Exception:
        db.rollback()


@router.get("/wallet")
def my_wallet(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    return wallet_svc.wallet_out(db, actor.id)


@router.get("/wallet/entries")
def my_wallet_entries(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    return {"items": [wallet_svc.entry_out(e) for e in wallet_svc.entries_of(db, actor.id)]}


class TopupCreate(BaseModel):
    amount: int = Field(gt=0, le=1_000_000_000_000, description="مبلغ شارژ (ریال) — سقف برای جلوگیری از سرریز Numeric(16,2)")
    gateway: str | None = Field(default=None, max_length=30)


@router.post("/wallet/topup", status_code=201)
def topup(
    payload: TopupCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """شارژ کیف پول از درگاه: سفارش topup + آغاز پرداخت (فاز ۲۹)."""
    order = wallet_svc.topup_order(db, actor.id, payload.amount, created_by=actor.id)
    try:
        result = pay.initiate_payment(db, order, payload.gateway)
    except pay.GatewayError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "order_id": str(order.id),
        "order_number": order.order_number,
        "payment_id": str(result.payment.id),
        "authority": result.payment.authority,
        "redirect_url": result.redirect_url,
    }


@router.post("/orders/{order_id}/pay-from-wallet")
def pay_from_wallet(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """B18 - پرداخت سفارش از اعتبار کیف پول (مالک یا کارکنان مجاز)."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    view_roles = (*MANAGE_ROLES, "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")
    has_view = any(r.code in view_roles for r in actor.roles)
    if not has_view and order.owner_user_id != actor.id:
        raise HTTPException(status_code=403, detail="فقط مالک سفارش می‌تواند از کیف پول خود پرداخت کند")
    try:
        payment = pay.pay_order_from_wallet(db, order, actor)
    except pay.GatewayError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _notify_wallet(
        db, order.owner_user_id, "پرداخت از کیف پول",
        f"پرداخت سفارش {order.order_number} به مبلغ {int(payment.amount):,} ریال از کیف پول انجام شد.",
    )
    return {
        "payment_id": str(payment.id),
        "gateway": payment.gateway,
        "amount": float(payment.amount),
        "order_status": order.status,
    }


@router.get("/wallets")
def list_wallets(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    wallets = db.scalars(
        select(wallet_svc.Wallet).order_by(wallet_svc.Wallet.updated_at.desc()).limit(200)
    ).all()
    items = []
    for w in wallets:
        u = db.get(User, w.user_id)
        items.append({
            "id": str(w.id),
            "user_id": str(w.user_id),
            "user_name": u.display_name if u else None,
            "username": u.username if u else None,
            "balance": float(w.balance or 0),
            "currency": w.currency,
        })
    return {"items": items}


@router.get("/wallets/{user_id}/entries")
def user_wallet_entries(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    return {"items": [wallet_svc.entry_out(e) for e in wallet_svc.entries_of(db, user_id)]}


class AdjustCreate(BaseModel):
    amount: int = Field(ge=-1_000_000_000_000, le=1_000_000_000_000, description="مثبت = شارژ، منفی = کسر (ریال)")
    note: str = Field(min_length=3, max_length=300)


@router.post("/wallets/{user_id}/adjust")
def adjust_wallet(
    user_id: uuid.UUID,
    payload: AdjustCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    try:
        # فاز ۳۱ - B22: تعدیل و سند حسابداری آن در یک تراکنش اتمیک
        entry = None
        if payload.amount > 0:
            entry = wallet_svc.credit(db, user_id, payload.amount, wallet_svc.WalletEntryReason.ADJUSTMENT,
                                      commit=False, note=payload.note, created_by=actor.id)
        elif payload.amount < 0:
            entry = wallet_svc.debit(db, user_id, -payload.amount, wallet_svc.WalletEntryReason.ADJUSTMENT,
                                     commit=False, note=payload.note, created_by=actor.id)
        else:
            raise HTTPException(status_code=422, detail="مبلغ باید غیرصفر باشد")
        if entry is not None:
            from app.services.accounting import entry_for_wallet_adjustment
            entry_for_wallet_adjustment(db, entry, commit=False)
        db.commit()
    except wallet_svc.WalletError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _notify_wallet(db, user_id, "تعدیل کیف پول",
                   f"کیف پول شما به مبلغ {abs(payload.amount):,} ریال "
                   f"{'شارژ' if payload.amount > 0 else 'کسر'} شد: {payload.note}",
                   severity="info" if payload.amount > 0 else "warning")
    return wallet_svc.wallet_out(db, user_id)
