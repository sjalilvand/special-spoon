"""فاز ۳۰ - B20 سند جامع: درخواست، بررسی و اجرای استرداد وجه.

قواعد سند:
- «استرداد از مبلغ مجاز بیشتر ممنوع» — مبلغ مجاز = مبلغ پرداخت‌شده
  سفارش منهای استردادهای اجراشده؛ در درخواست و اجرا دوباره کنترل
  می‌شود (در همان تراکنش).
- «اجرای تکراری ممنوع» — هر درخواست فقط یک‌بار اجرا می‌شود (بررسی
  وضعیت + به‌روزرسانی اتمیک) و جمع استردادها هرگز از مبلغ پرداختی
  عبور نمی‌کند.
- مسیر بازگشت: پرداختِ از کیف پول → شارژ مجدد کیف پول؛ پرداختِ درگاه
  (sandbox/zarinpal) → ثبت رسید استرداد (زرین‌پال: استرداد از پنل).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
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


class RefundRequestStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    ALL = (PENDING, APPROVED, REJECTED, EXECUTED)


class RefundRequest(Base):
    """B20 - درخواست استرداد با چرخه pending → approved/rejected → executed."""

    __tablename__ = "refund_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','executed')",
            name="ck_refund_requests_status",
        ),
        CheckConstraint("amount > 0", name="ck_refund_requests_amount_positive"),
        Index("ix_refund_requests_order", "order_id"),
        Index("ix_refund_requests_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default=RefundRequestStatus.PENDING)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Refund(Base):
    """B20 - استرداد اجراشده؛ مرجع بازگشت وجه (کیف پول یا درگاه)."""

    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_refunds_amount_positive"),
        Index("ix_refunds_order", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    refund_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("refund_requests.id", ondelete="RESTRICT"),
        nullable=False, unique=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[int] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    channel: Mapped[str] = mapped_column(String(20))  # wallet / gateway
    gateway: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gateway_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    executed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
