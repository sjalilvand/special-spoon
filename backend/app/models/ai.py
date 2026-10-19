"""فاز ۳۵ - B25 سند جامع: لاگ تعامل دستیار هوشمند (تصمیم D07).

- هر گفتگو با دستیار (پیام/پاسخ/سرویس‌دهنده) برای ردیابی و ممیزی
  ذخیره می‌شود؛ «کلید سرویس AI هرگز در لاگ یا پاسخ نمی‌رود»؛
- محتوای حساس پرونده/بالینی به دستیار ارسال یا در لاگ ذخیره نمی‌شود
  (دستیار فقط دامنه عمومی سامانه را پاسخ می‌دهد).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiChatLog(Base):
    """B25 - لاگ تعامل دستیار؛ بدون کلید سرویس و بدون محتوای بالینی."""

    __tablename__ = "ai_chat_logs"
    __table_args__ = (
        Index("ix_ai_chat_logs_user", "user_id"),
        Index("ix_ai_chat_logs_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(30))  # rule / llm (پیش‌فرض rule — D07)
    message: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
