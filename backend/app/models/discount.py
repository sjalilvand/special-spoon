"""فاز ۳۰ - B19 سند جامع: کد تخفیف.

قواعد سند:
- «مصرف هم‌زمان بیش از سقف پذیرفته نشود» — سقف کل (max_uses) و سقف هر
  کاربر (max_uses_per_user) هنگام اعمال کد با قفل ردیف تخفیف کنترل
  می‌شود؛ شمارش فقط سفارش‌های مؤثر (pending/paid) است تا لغو سفارش
  سهمیه را آزاد کند.
- نوع تخفیف: مبلغ ثابت (amount) یا درصد (percent ≤ 100)؛ مقدار تخفیف
  هرگز از مبلغ سفارش بیشتر نمی‌شود.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DiscountKind:
    AMOUNT = "amount"
    PERCENT = "percent"
    ALL = (AMOUNT, PERCENT)


class Discount(Base):
    """B19 - کد تخفیف با سقف، اعتبار و حداقل مبلغ سفارش."""

    __tablename__ = "discounts"
    __table_args__ = (
        CheckConstraint("kind IN ('amount','percent')", name="ck_discounts_kind"),
        CheckConstraint("value > 0", name="ck_discounts_value_positive"),
        CheckConstraint("kind != 'percent' OR value <= 100", name="ck_discounts_percent_max"),
        CheckConstraint(
            "expires_at IS NULL OR starts_at IS NULL OR expires_at >= starts_at",
            name="ck_discounts_range",
        ),
        CheckConstraint("min_order_amount IS NULL OR min_order_amount >= 0", name="ck_discounts_min_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default=DiscountKind.AMOUNT)
    value: Mapped[int] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_uses_per_user: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    min_order_amount: Mapped[int | None] = mapped_column(Numeric(16, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DiscountRedemption(Base):
    """B19 - مصرف کد روی سفارش؛ یک مصرف به‌ازای هر سفارش (یکتا)."""

    __tablename__ = "discount_redemptions"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_discount_redemption_order"),
        Index("ix_discount_redemptions_discount", "discount_id"),
        Index("ix_discount_redemptions_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    discount_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discounts.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    amount_applied: Mapped[int] = mapped_column(Numeric(16, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
