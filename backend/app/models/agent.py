"""فاز ۵۳ - مدل‌های نشست عامل هوشمند (Session Log — الگوی dsh).

- agent_sessions: یک نشست گفتگو برای هر موضوع؛ عنوان خودکار از اولین پیام؛
- agent_messages: لاگ append-only؛ نقش‌ها user/assistant/tool؛ برای پیام‌های
  tool، نام/آرگومان/خلاصهٔ نتیجهٔ ابزار ذخیره می‌شود (بدون کلید و بدون دادهٔ
  بالینی — همان مرز فاز ۳۵)؛ بازپخش تاریخچه برای UI و ممیزی.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentSession(Base):
    """فاز ۵۳ - نشست گفتگو با عامل هوشمند."""

    __tablename__ = "agent_sessions"
    __table_args__ = (
        Index("ix_agent_sessions_user", "user_id"),
        Index("ix_agent_sessions_updated", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), default="گفتگوی جدید")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentMessage(Base):
    """فاز ۵۳ - پیام‌های نشست (append-only)."""

    __tablename__ = "agent_messages"
    __table_args__ = (
        Index("ix_agent_messages_session", "session_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(12))  # user / assistant / tool
    content: Mapped[str] = mapped_column(Text, default="")
    # رد فراخوانی ابزار (فقط برای role=tool)
    tool_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    tool_args: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
