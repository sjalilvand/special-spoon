"""فاز ۳۶ - B28 سند جامع: صف خروجی پیامک (یکپارچه‌سازی‌های بیرونی).

- هر پیامک بیرونی (کپی اعلان‌ها) یک ردیف در صف پایگاه‌داده می‌سازد؛ ارسال
  واقعی بعداً توسط process انجام می‌شود (ADR-02: تا پیش از صف کار اختصاصی
  Celery/arq، صف در سطح DB نگه داشته می‌شود — همان الگوی email_outbox).
- آداپتور پلاگین‌پذیر همان الگوی D02/D03/D07:
  log = توسعه/آزمون بدون کلید (قطعی)؛ kavenegar/smsir فقط با کلید API؛
  کلید هرگز به کلاینت و به لاگ نمی‌رود.
- وضعیت disabled = سرویس پیامک پیکربندی نشده (شفافیت عملیاتی/DPO).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SmsOutboxStatus:
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DISABLED = "disabled"


class SmsOutbox(Base):
    __tablename__ = "sms_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','sent','failed','disabled')", name="ck_sms_outbox_status"
        ),
        CheckConstraint(
            "provider IN ('log','kavenegar','smsir')", name="ck_sms_outbox_provider"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient_mobile: Mapped[str] = mapped_column(String(20))
    purpose: Mapped[str] = mapped_column(String(30), default="notification")
    body: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(30), default="log")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
