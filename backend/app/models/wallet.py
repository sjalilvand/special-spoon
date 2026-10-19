"""فاز ۳۰ - B18 سند جامع: کیف پول، مانده، گردش و پرداخت از اعتبار.

قواعد سند:
- «مانده با جمع گردش‌ها سازگار و دوباره‌مصرفی ممنوع» — مانده همیشه
  برابر جمع بدهکار/بستانکار دفتر است؛ هر ردیف گردش «مانده پس از
  تراکنش» را ثبت می‌کند و تغییر مانده فقط با قفل ردیف کیف پول
  (SELECT ... FOR UPDATE) انجام می‌شود تا برداشت هم‌زمان مضاعف رخ ندهد.
- شارژ کیف پول از مسیر پرداخت فاز ۲۹ (سفارش kind='topup') انجام
  می‌شود؛ پرداخت سفارش از اعتبار با gateway='wallet' ثبت می‌گردد.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WalletEntryDirection:
    CREDIT = "credit"
    DEBIT = "debit"
    ALL = (CREDIT, DEBIT)


class WalletEntryReason:
    TOPUP = "topup"                      # شارژ از درگاه (سفارش topup)
    PAYMENT = "payment"                  # پرداخت سفارش از اعتبار
    REFUND = "refund"                    # بازگشت وجه استرداد به کیف پول
    ADJUSTMENT = "adjustment"            # تعدیل دستی مدیر
    ALL = (TOPUP, PAYMENT, REFUND, ADJUSTMENT)


class Wallet(Base):
    """B18 - کیف پول کاربر؛ یک کیف به‌ازای هر کاربر."""

    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallets_balance_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    balance: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WalletEntry(Base):
    """B18 - گردش کیف پول با مانده پس از تراکنش (دفتر تأییدپذیر)."""

    __tablename__ = "wallet_entries"
    __table_args__ = (
        CheckConstraint("direction IN ('credit','debit')", name="ck_wallet_entries_direction"),
        CheckConstraint("reason IN ('topup','payment','refund','adjustment')", name="ck_wallet_entries_reason"),
        CheckConstraint("amount > 0", name="ck_wallet_entries_amount_positive"),
        Index("ix_wallet_entries_wallet", "wallet_id"),
        Index("ix_wallet_entries_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(String(20))
    amount: Mapped[int] = mapped_column(Numeric(16, 2))
    balance_after: Mapped[int] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    # مرجع تراکنش: سفارش/پرداخت/استرداد مرتبط
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    refund_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("refunds.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


