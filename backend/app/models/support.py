"""فاز ۳۵ - B23 سند جامع: نظرسنجی، شکایت و تیکت پشتیبانی.

قواعد پذیرش:
- نظرسنجی پس از جلسه: هر جلسه حداکثر یک نظرسنجی (uq روی session_id)؛
  امتیاز ۱..۵ (CHECK)؛ گزارش میانگین/توزیع برای مدیران؛
- شکایت: ثبت توسط کاربر احراز‌هویت (یا کارکنان به‌نام وی)؛ چرخه
  new → in_review → resolved/rejected؛ فقط مدیران بررسی می‌کنند؛
  متقاضی فقط شکایت خودش را می‌بیند؛ یادداشت بررسی الزامی نیست ولی
  خروجی آن را نشان می‌دهد؛
- تیکت پشتیبانی: نخ گفتگو (ticket_messages)؛ چرخه open → answered →
  closed؛ پاسخ کارکنان وضعیت را answered می‌کند؛ پاسخ کاربر دوباره open؛
  بستن توسط مالک یا کارکنان؛ «تیکت دیگران برای کاربر عادی دیده نمی‌شود».
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ComplaintStatus:
    NEW = "new"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    ALL = (NEW, IN_REVIEW, RESOLVED, REJECTED)


class TicketStatus:
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"
    ALL = (OPEN, ANSWERED, CLOSED)


class SessionSurvey(Base):
    """B23 - نظرسنجی رضایت پس از جلسه؛ هر جلسه حداکثر یک‌بار (uq)."""

    __tablename__ = "session_surveys"
    __table_args__ = (
        CheckConstraint("score >= 1 AND score <= 5", name="ck_session_surveys_score"),
        UniqueConstraint("session_id", name="uq_session_survey"),
        Index("ix_session_surveys_session", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    respondent_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer)  # 1..5
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Complaint(Base):
    """B23 - شکایت؛ بررسی فقط توسط مدیران (چرخه وضعیت محافظت‌شده)."""

    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','in_review','resolved','rejected')", name="ck_complaints_status"
        ),
        Index("ix_complaints_status", "status"),
        Index("ix_complaints_user", "complainant_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complainant_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=ComplaintStatus.NEW)
    resolution_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    """B23 - تیکت پشتیبانی با نخ پیام؛ مالک فقط تیکت خودش را می‌بیند."""

    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("status IN ('open','answered','closed')", name="ck_tickets_status"),
        CheckConstraint("priority IN ('normal','high')", name="ck_tickets_priority"),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default=TicketStatus.OPEN)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TicketMessage(Base):
    """B23 - پیام نخ تیکت؛ is_staff تفکیک پاسخ پشتیبانی از کاربر."""

    __tablename__ = "ticket_messages"
    __table_args__ = (
        Index("ix_ticket_messages_ticket", "ticket_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text)
    is_staff: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
