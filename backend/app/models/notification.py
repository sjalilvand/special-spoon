import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Notification(Base):
    """B12/B38 سند جامع - مرکز اعلان درون‌برنامه‌ای.

    اعلان برای کاربران داخلی سامانه است؛ محتوای حساس بالینی در متن
    اعلان نمی‌آید (فقط کد و ارجاع به موجودیت) - بند «عدم افشای محتوا».
    """

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','warning','critical')", name="ck_notifications_severity"
        ),
        CheckConstraint("read_at IS NULL OR read_at >= created_at", name="ck_notifications_read_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(30), default="system", index=True)
    event_code: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(String(500), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
