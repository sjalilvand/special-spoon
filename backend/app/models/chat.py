"""فاز ۵۲ - چت آنلاین داخلی: گفتگوی دو نفره و مشاورهٔ گروهی.

طراحی:
- ``conversations`` اتاق گفتگو است؛ kind=dm گفتگوی دو نفره و kind=group
  اتاق مشاوره (دعوت نفر سوم+) است.
- ``conversation_members`` عضویت در اتاق + نشانگر آخرین پیام خوانده‌شده برای
  محاسبهٔ شمارندهٔ نخوانده‌ها.
- ``messages`` پیام‌ها؛ kind=text متن ساده و kind=voice پیام صوتی (بایت‌های
  ogg/webm صوتی در ``media_data`` از نوع LargeBinary نگهداری می‌شود تا
  «نگهداری و ذخیرهٔ پیام و صوت‌ها» مطابق نیازمندی ماندگار باشد؛ سقف ۵ مگابایت
  در لایهٔ API کنترل می‌شود). kind=system رخدادهای داخلی اتاق (دعوت/ترک) است.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# سقف حجم فایل صوتی هر پیام (۵ مگابایت)
VOICE_MAX_BYTES = 5 * 1024 * 1024
# سقف طول متن پیام
TEXT_MAX_LEN = 5000


class ConversationKind:
    DM = "dm"
    GROUP = "group"


class MessageKind:
    TEXT = "text"
    VOICE = "voice"
    SYSTEM = "system"


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("kind IN ('dm','group')", name="ck_conversations_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(10), default=ConversationKind.DM)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", lazy="selectin"
    )


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # آخرین پیامی که این عضو خوانده است - مبنای شمارندهٔ نخوانده
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    conversation: Mapped[Conversation] = relationship(back_populates="members")
    # نام نمایشی اعضا بدون relationship به User (جلوگیری از مپ دوبارهٔ جدول)
    # در لایهٔ API با یک کوئری دسته‌ای (IN) پر می‌شود.


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("kind IN ('text','voice','system')", name="ck_messages_kind"),
        Index("ix_messages_conv_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(10), default=MessageKind.TEXT)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # پیام صوتی: بایت‌های فایل + نوع mime + مدت (میلی‌ثانیه)
    media_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    media_mime: Mapped[str | None] = mapped_column(String(80), nullable=True)
    media_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    media_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
