"""فاز ۳۰ - B19 سند جامع: اعتبارسنجی و اعمال کد تخفیف.

قواعد سند:
- «مصرف هم‌زمان بیش از سقف پذیرفته نشود» — کنترل سقف داخل تراکنش با
  قفل ردیف تخفیف (FOR UPDATE) انجام می‌شود؛ شمارش مصرف فقط سفارش‌های
  مؤثر (pending/paid) است؛ سفارش لغو/ناموفق سهمیه را آزاد می‌کند.
- مقدار تخفیف هرگز از مبلغ سفارش بیشتر نمی‌شود (درصد گرد به پایین).
"""
import math
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.discount import Discount, DiscountKind, DiscountRedemption
from app.models.payment import Order, OrderStatus


class DiscountError(Exception):
    """رد کد تخفیف با دلیل قابل نمایش."""


def _effective_uses(db: Session, discount_id) -> int:
    """شمار مصرف‌های مؤثر (سفارش pending/paid) — لغو/ناموفق آزاد می‌کند."""
    return int(db.scalar(
        select(func.count()).select_from(DiscountRedemption)
        .join(Order, Order.id == DiscountRedemption.order_id)
        .where(
            DiscountRedemption.discount_id == discount_id,
            Order.status.in_([OrderStatus.PENDING, OrderStatus.PAID]),
        )
    ) or 0)


def _user_uses(db: Session, discount_id, user_id) -> int:
    return int(db.scalar(
        select(func.count()).select_from(DiscountRedemption)
        .join(Order, Order.id == DiscountRedemption.order_id)
        .where(
            DiscountRedemption.discount_id == discount_id,
            DiscountRedemption.user_id == user_id,
            Order.status.in_([OrderStatus.PENDING, OrderStatus.PAID]),
        )
    ) or 0)


def _locked_discount(db: Session, code: str) -> Discount:
    disc = db.scalars(
        select(Discount).where(Discount.code == code.strip().upper()).with_for_update()
    ).first()
    if disc is None:
        raise DiscountError("کد تخفیف یافت نشد")
    return disc


def compute_discount_amount(disc: Discount, amount: int) -> int:
    if disc.kind == DiscountKind.PERCENT:
        return int(math.floor(Decimal(amount) * Decimal(disc.value) / Decimal(100)))
    return min(int(Decimal(disc.value)), amount)


def validate(db: Session, code: str, amount: int, user_id) -> tuple[Discount, int]:
    """اعتبارسنجی کامل کد برای مبلغ سفارش؛ (کد، مبلغ تخفیف) برمی‌گرداند."""
    disc = _locked_discount(db, code)
    today = date.today()
    if not disc.is_active:
        raise DiscountError("کد تخفیف غیرفعال است")
    if disc.starts_at and today < disc.starts_at:
        raise DiscountError("کد تخفیف هنوز فعال نشده است")
    if disc.expires_at and today > disc.expires_at:
        raise DiscountError("کد تخفیف منقضی شده است")
    if disc.min_order_amount and amount < int(Decimal(disc.min_order_amount)):
        raise DiscountError("مبلغ سفارش کمتر از حداقل مجاز این کد است")
    if disc.max_uses is not None and _effective_uses(db, disc.id) >= disc.max_uses:
        raise DiscountError("سقف استفاده از این کد تکمیل شده است")
    if disc.max_uses_per_user is not None and _user_uses(db, disc.id, user_id) >= disc.max_uses_per_user:
        raise DiscountError("سقف استفاده هر کاربر از این کد تکمیل شده است")
    return disc, compute_discount_amount(disc, amount)


def apply_to_order(db: Session, order: Order, code: str, user_id) -> int:
    """اعمال کد روی سفارش تازه‌ساخته: ثبت مصرف + به‌روزرسانی مبالغ."""
    disc, discount_amount = validate(db, code, int(order.amount), user_id)
    redemption = DiscountRedemption(
        discount_id=disc.id,
        order_id=order.id,
        user_id=user_id,
        amount_applied=discount_amount,
    )
    db.add(redemption)
    order.discount_id = disc.id
    order.discount_amount = discount_amount
    order.payable_amount = int(order.amount) - discount_amount
    db.commit()
    return discount_amount


def discount_out(db: Session, d: Discount, with_usage: bool = True) -> dict:
    out = {
        "id": str(d.id),
        "code": d.code,
        "kind": d.kind,
        "value": float(d.value),
        "currency": d.currency,
        "max_uses": d.max_uses,
        "max_uses_per_user": d.max_uses_per_user,
        "starts_at": d.starts_at.isoformat() if d.starts_at else None,
        "expires_at": d.expires_at.isoformat() if d.expires_at else None,
        "min_order_amount": float(d.min_order_amount) if d.min_order_amount is not None else None,
        "is_active": d.is_active,
        "note": d.note,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }
    if with_usage:
        out["effective_uses"] = _effective_uses(db, d.id)
    return out
