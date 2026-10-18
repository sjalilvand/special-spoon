"""B12+ فاز ۲۷ - صف خروجی ایمیل اعلان‌ها (تصمیم D04: SMTP).

- هر اعلان درون‌برنامه‌ای برای گیرنده دارای ایمیل، یک ردیف در صف می‌سازد.
- محتوای ایمیل همان محتوای اعلان است؛ سیاست «عدم افشای محتوای بالینی» برقرار است.
- ارسال بعداً توسط process_outbox انجام می‌شود (ADR-02: صف کار)؛ شکست SMTP
  هرگز جریان اصلی را متوقف نمی‌کند.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmailOutboxStatus:
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DISABLED = "disabled"


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','sent','failed','disabled')", name="ck_email_outbox_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(200))
    body_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
