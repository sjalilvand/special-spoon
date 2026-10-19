"""فاز ۳۰ - B18 سند جامع: سرویس کیف پول.

- «مانده با جمع گردش‌ها سازگار» — هر تغییر مانده یک ردیف گردش با
  balance_after ثبت می‌کند؛ تابع verify_consistency این invariant را
  بازبینی می‌کند.
- «دوباره‌مصرفی ممنوع» — برداشت فقط با SELECT ... FOR UPDATE روی ردیف
  کیف پول و پس از کنترل مانده انجام می‌شود.
"""
import uuid
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.payment import Order
from app.models.user import User
from app.models.wallet import Wallet, WalletEntry, WalletEntryDirection, WalletEntryReason


class WalletError(Exception):
    """خطای قابل نمایش کاربر."""


def get_or_create_wallet(db: Session, user_id: uuid.UUID) -> Wallet:
    wallet = db.scalars(select(Wallet).where(Wallet.user_id == user_id)).first()
    if wallet is None:
        wallet = Wallet(user_id=user_id, balance=0, currency="IRR")
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet


def _locked_wallet(db: Session, user_id: uuid.UUID) -> Wallet:
    """قفل ردیفی کیف پول برای تراکنش امن (منع دوباره‌مصرفی)."""
    wallet = db.scalars(
        select(Wallet).where(Wallet.user_id == user_id).with_for_update()
    ).first()
    if wallet is None:
        wallet = Wallet(user_id=user_id, balance=0, currency="IRR")
        db.add(wallet)
        db.flush()
    return wallet


def _entry(
    db: Session,
    wallet: Wallet,
    direction: str,
    reason: str,
    amount: int,
    *,
    order_id=None,
    payment_id=None,
    refund_id=None,
    note: str | None = None,
    created_by=None,
) -> WalletEntry:
    new_balance = (Decimal(wallet.balance or 0) + (amount if direction == "credit" else -amount))
    entry = WalletEntry(
        wallet_id=wallet.id,
        direction=direction,
        reason=reason,
        amount=amount,
        balance_after=new_balance,
        currency=wallet.currency,
        order_id=order_id,
        payment_id=payment_id,
        refund_id=refund_id,
        note=note,
        created_by=created_by,
    )
    db.add(entry)
    db.flush()  # entry.id برای ساخت مراجع (مثل authority پرداخت کیفی)
    wallet.balance = new_balance
    return entry


def credit(
    db: Session, user_id: uuid.UUID, amount: int, reason: str, *, commit: bool = True, **refs
) -> WalletEntry:
    if amount <= 0:
        raise WalletError("مبلغ شارژ باید مثبت باشد")
    wallet = _locked_wallet(db, user_id)
    entry = _entry(db, wallet, WalletEntryDirection.CREDIT, reason, amount, **refs)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry


def debit(
    db: Session, user_id: uuid.UUID, amount: int, reason: str, *, commit: bool = True, **refs
) -> WalletEntry:
    """برداشت با قفل ردیفی؛ مانده ناکافی → خطا (بدون تغییر مانده)."""
    if amount <= 0:
        raise WalletError("مبلغ برداشت باید مثبت باشد")
    wallet = _locked_wallet(db, user_id)
    if Decimal(wallet.balance or 0) < amount:
        raise WalletError("مانده کیف پول کافی نیست")
    entry = _entry(db, wallet, WalletEntryDirection.DEBIT, reason, amount, **refs)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry


def entries_of(db: Session, user_id: uuid.UUID, limit: int = 100) -> list[WalletEntry]:
    wallet = db.scalars(select(Wallet).where(Wallet.user_id == user_id)).first()
    if wallet is None:
        return []
    return list(db.scalars(
        select(WalletEntry).where(WalletEntry.wallet_id == wallet.id)
        .order_by(WalletEntry.created_at.desc()).limit(limit)
    ).all())


def verify_consistency(db: Session, user_id: uuid.UUID) -> bool:
    """«مانده با جمع گردش‌ها سازگار» — بازبینی invariant (برای تست و ممیزی)."""
    wallet = db.scalars(select(Wallet).where(Wallet.user_id == user_id)).first()
    if wallet is None:
        return True
    res = db.execute(
        text(
            "SELECT COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE -amount END), 0) "
            "FROM wallet_entries WHERE wallet_id = :wid"
        ),
        {"wid": wallet.id},
    ).scalar() or Decimal(0)
    return Decimal(res) == Decimal(wallet.balance or 0)


def topup_order(db: Session, user_id: uuid.UUID, amount: int, created_by=None) -> Order:
    """سفارش شارژ کیف پول — از همان موتور پرداخت فاز ۲۹ عبور می‌کند."""
    if amount <= 0:
        raise WalletError("مبلغ شارژ باید مثبت باشد")
    from app.api.v1.payments import _order_number

    order = Order(
        order_number=_order_number(db),
        owner_user_id=user_id,
        title="شارژ کیف پول",
        amount=amount,
        currency="IRR",
        payable_amount=amount,
        status="pending",
        kind="topup",
        note="wallet_topup",
        created_by=created_by or user_id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def wallet_out(db: Session, user_id: uuid.UUID) -> dict:
    wallet = get_or_create_wallet(db, user_id)
    user = db.get(User, user_id)
    return {
        "id": str(wallet.id),
        "user_id": str(user_id),
        "user_name": user.display_name if user else None,
        "balance": float(wallet.balance or 0),
        "currency": wallet.currency,
        "is_active": wallet.is_active,
    }


def entry_out(e: WalletEntry) -> dict:
    return {
        "id": str(e.id),
        "direction": e.direction,
        "reason": e.reason,
        "amount": float(e.amount),
        "balance_after": float(e.balance_after),
        "currency": e.currency,
        "order_id": str(e.order_id) if e.order_id else None,
        "payment_id": str(e.payment_id) if e.payment_id else None,
        "refund_id": str(e.refund_id) if e.refund_id else None,
        "note": e.note,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
