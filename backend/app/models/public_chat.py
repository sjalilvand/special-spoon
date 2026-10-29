"""فاز ۵۴ - چت آنلاین عمومی سایت (Live Chat) — مدل‌ها.

- public_chat_sessions: یک نشست گفتگو برای هر بازدیدکننده؛ هویت لایه‌لایه:
  * کاربر لاگین‌شده → user_id (نمایش با نام کاربری)؛
  * بازدیدکنندهٔ ناشناس → token مرورر (localStorage) + IP سرور ثبت می‌شود؛
    نام اختیاری (visitor_name) هم اگر خودش معرفی کند ذخیره می‌شود؛
- public_chat_messages: پیام‌های user/assistant؛ پاسخ دستیار می‌تواند
  «کارت اقدام» (دکمهٔ انتقال به صفحهٔ مرتبط: رزرو/ورود/مشاوران/خدمات) و
  «پاسخ پیشنهادی» (quick replies) داشته باشد؛ امتیاز و نظر کاربر دربارهٔ
  خودِ گفتگو روی نشست ذخیره می‌شود (rating 1..5 + comment).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SESSION_TOKEN_MAX = 64
VISITOR_NAME_MAX = 100
RATING_COMMENT_MAX = 500
CONTENT_MAX_LEN = 1000


class PublicChatSession(Base):
    """فاز ۵۴ - نشست چت عمومی (هویت: کاربر لاگین / نام معرفی‌شده / IP)."""

    __tablename__ = "public_chat_sessions"
    __table_args__ = (
        Index("ix_public_chat_sessions_user", "user_id"),
        Index("ix_public_chat_sessions_ip", "ip"),
        Index("ix_public_chat_sessions_updated", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # توکن نشست سمت مرورگر (localStorage) — کلید تداوم گفتگو
    token: Mapped[str] = mapped_column(String(SESSION_TOKEN_MAX), unique=True, nullable=False)
    # در صورت لاگین بودن بازدیدکننده پر می‌شود (اختیاری)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # نامی که بازدیدکنندهٔ ناشناس خودش معرفی می‌کند (اختیاری)
    visitor_name: Mapped[str | None] = mapped_column(String(VISITOR_NAME_MAX), nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="unknown")
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    first_page: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="open")  # open / closed
    # نظر کاربر دربارهٔ خودِ گفتگو (فاز ۵۴ - بازخورد چت)
    rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    rating_comment: Mapped[str | None] = mapped_column(String(RATING_COMMENT_MAX), nullable=True)
    # فاز ۵۵ - پیگیری پذیرش/مدیر: یادداشت + آخرین همکارِ رسیدگی‌کننده
    staff_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PublicChatMessage(Base):
    """فاز ۵۴ - پیام‌های چت عمومی (append-only) + کارت اقدام."""

    __tablename__ = "public_chat_messages"
    __table_args__ = (
        Index("ix_public_chat_messages_session", "session_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public_chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(12))  # user / assistant
    content: Mapped[str] = mapped_column(Text, default="")
    # کارت‌های اقدام (دکمهٔ انتقال به صفحهٔ مرتبط) — فقط برای assistant
    actions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # پاسخ‌های پیشنهادی بعد از این پیام
    quick_replies: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
