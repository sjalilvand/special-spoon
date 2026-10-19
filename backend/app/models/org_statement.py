"""فاز ۳۴ - B21-plus سند جامع: صورتحساب دوره‌ای سازمان و تسویه مطالبات.

- صورتحساب از سفارش‌های «پرداخت‌شده دارای سهم سازمان» در یک بازه
  snapshot می‌شود (مبالغ از snapshot سفارش — فاز ۳۳)؛ هر سفارش
  حداکثر یک‌بار در صورتحساب می‌آید (uq روی order_id)؛
- صدور صورتحساب سند جدیدی نمی‌زند (مطالبه در لحظه پرداخت با ۱۱۰۴
  شناسایی شده است)؛ «تسویه مطالبات» سند می‌زند:
      Dr 1101 بانک  |  Cr 1104 دریافتنی از سازمان‌ها
  سند متوازن، idempotent با (source_type='org_statement', source_id)؛
- تسویه فقط برای صورتحساب issued؛ تسویه مجدد ۴۰۹.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
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


class OrgStatementStatus:
    ISSUED = "issued"
    SETTLED = "settled"
    ALL = (ISSUED, SETTLED)


class OrgStatement(Base):
    """B21-plus - صورتحساب دوره‌ای سازمان (خروجی مطالبات بازه مشخص)."""

    __tablename__ = "org_statements"
    __table_args__ = (
        CheckConstraint("status IN ('issued','settled')", name="ck_org_statements_status"),
        CheckConstraint("period_to >= period_from", name="ck_org_statements_period"),
        CheckConstraint("total_amount >= 0 AND org_share_total >= 0", name="ck_org_statements_amounts"),
        Index("ix_org_statements_org", "organization_id"),
        Index("ix_org_statements_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_no: Mapped[str] = mapped_column(String(40), unique=True)  # ORG-<سال شمسی>-<ترتیب>
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    period_from: Mapped[date] = mapped_column(Date)
    period_to: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=OrgStatementStatus.ISSUED)
    orders_count: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    total_amount: Mapped[int] = mapped_column(Numeric(16, 2), default=0)        # ناخالص سفارش‌ها
    org_share_total: Mapped[int] = mapped_column(Numeric(16, 2), default=0)     # مبلغ صورتحساب (سهم سازمان)
    applicant_share_total: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    settled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["OrgStatementItem"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan", lazy="selectin"
    )


class OrgStatementItem(Base):
    """B21-plus - ردیف صورتحساب؛ هر سفارش حداکثر یک‌بار در کل صورتحساب‌ها."""

    __tablename__ = "org_statement_items"
    __table_args__ = (
        Index("ix_org_statement_items_statement", "statement_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_statements.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    order_number: Mapped[str] = mapped_column(String(40))  # snapshot
    amount: Mapped[int] = mapped_column(Numeric(16, 2))                  # ناخالص سفارش
    org_share_amount: Mapped[int] = mapped_column(Numeric(16, 2))        # سهم سازمان
    applicant_share_amount: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    coverage_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    statement: Mapped[OrgStatement] = relationship(back_populates="items")
