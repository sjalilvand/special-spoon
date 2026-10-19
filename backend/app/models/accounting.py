"""فاز ۳۱ - B22 سند جامع: کدینگ، سند حسابداری، تسویه و مغایرت.

قواعد سند:
- «سند متوازن» — جمع بدهکار هر سند با جمع بستانکار آن برابر است؛ هر
  ردیف فقط یک سمت دارد (بدهکار یا بستانکار) و مبالغ مثبت‌اند. این
  قاعده در لایه سرویس، در CHECKهای پایگاه و در گزارش تراز بازبینی می‌شود.
- «قابل ردیابی به رویداد مالی» — هر سند خودکار دارای source_type و
  source_id رویداد مالی مبدأ (پرداخت/استرداد/تعدیل کیف پول/تسویه)
  است؛ قید یکتایی (source_type, source_id) تکرار سند برای یک رویداد
  را ناممکن می‌کند (idempotent — سازگار با callback تکراری فاز ۲۹).
- اسناد ثبت‌شده تغییرناپذیرند؛ ابطال فقط با «سند برگشتی» آینه‌ای
  انجام می‌شود (رویه استاندارد حسابداری).
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
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AccountType:
    ASSET = "asset"              # دارایی
    LIABILITY = "liability"      # بدهی
    EQUITY = "equity"            # حقوق مالکانه
    REVENUE = "revenue"          # درآمد
    EXPENSE = "expense"          # هزینه
    ALL = (ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE)


class JournalSource:
    """رویدادهای مالی مبدأ سند — قابل ردیابی بودن به رویداد."""
    PAYMENT = "payment"                        # پرداخت موفق (درگاه یا کیف پول)
    REFUND = "refund"                          # استرداد اجراشده
    WALLET_ADJUSTMENT = "wallet_adjustment"    # تعدیل دستی مدیر (فقط reason=adjustment)
    SETTLEMENT = "settlement"                  # تسویه دوره درگاه
    ORG_STATEMENT = "org_statement"            # فاز ۳۴ - B21-plus: تسویه صورتحساب سازمان
    MANUAL = "manual"                          # سند دستی
    REVERSAL = "reversal"                      # سند برگشتی


class SettlementStatus:
    DRAFT = "draft"
    SETTLED = "settled"
    ALL = (DRAFT, SETTLED)


class Account(Base):
    """B22 - سرفصل حساب (کدینگ) درخت‌واره با کد یکتا."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "type IN ('asset','liability','equity','revenue','expense')",
            name="ck_accounts_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # سرفصل سیستمی: حذف/تغییر کد ممنوع
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JournalEntry(Base):
    """B22 - سند حسابداری دوطرفه؛ متوازن و قابل ردیابی به رویداد مالی."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_journal_source_event"),
        CheckConstraint("source_type IN ('payment','refund','wallet_adjustment','settlement','org_statement','manual','reversal')",
                        name="ck_journal_source_type"),
        Index("ix_journal_entries_date", "entry_date"),
        Index("ix_journal_entries_source", "source_type", "source_id"),
        Index("ix_journal_entries_kind", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_no: Mapped[str] = mapped_column(String(40), unique=True)  # JE-<سال شمسی>-<ترتیب>
    entry_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(40))  # payment_gateway/payment_wallet/refund_wallet/...
    source_type: Mapped[str] = mapped_column(String(30))
    # سند دستی و برگشتی رویداد خارجی ندارند (NULL)؛ قید یکتا فقط برای رویدادهای سیستمی
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True
    )
    is_reversal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin"
    )


class JournalLine(Base):
    """B22 - ردیف سند؛ فقط یک سمت (بدهکار XOR بستانکار) و مبلغ مثبت."""

    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_lines_nonneg"),
        CheckConstraint("(debit > 0) <> (credit > 0)", name="ck_journal_lines_one_side"),
        Index("ix_journal_lines_entry", "entry_id"),
        Index("ix_journal_lines_account", "account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    debit: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    credit: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")


class Settlement(Base):
    """B22 - تسویه دوره‌ای دریافت‌های درگاه (جزو B22؛ درگاه wallet تسویه بیرونی ندارد)."""

    __tablename__ = "settlements"
    __table_args__ = (
        CheckConstraint("status IN ('draft','settled')", name="ck_settlements_status"),
        CheckConstraint("gross_amount >= 0", name="ck_settlements_gross_nonneg"),
        CheckConstraint("fee_amount IS NULL OR fee_amount >= 0", name="ck_settlements_fee_nonneg"),
        CheckConstraint("period_start IS NULL OR period_end IS NULL OR period_end >= period_start",
                        name="ck_settlements_period"),
        Index("ix_settlements_gateway", "gateway"),
        Index("ix_settlements_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    settlement_no: Mapped[str] = mapped_column(String(40), unique=True)  # SET-<سال شمسی>-<ترتیب>
    gateway: Mapped[str] = mapped_column(String(30))
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    payments_count: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    gross_amount: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    fee_amount: Mapped[int | None] = mapped_column(Numeric(16, 2), nullable=True)
    net_amount: Mapped[int | None] = mapped_column(Numeric(16, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    status: Mapped[str] = mapped_column(String(20), default=SettlementStatus.DRAFT)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    settled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SettlementItem(Base):
    """B22 - پرداخت‌های شامل تسویه؛ هر پرداخت حداکثر یک‌بار تسویه می‌شود."""

    __tablename__ = "settlement_items"
    __table_args__ = (
        Index("ix_settlement_items_settlement", "settlement_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    amount: Mapped[int] = mapped_column(Numeric(16, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
