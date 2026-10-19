"""فاز ۳۳ - B32 سند جامع: دسته‌بندی موضوعی.

- دسته‌بندی سلسله‌مراتبی (parent_id اختیاری) با slug یکتا؛
- اتصال چند‌به‌چند به خدمات (service_topics) — محتوا/دوره/آزمون (B33–B36)
  بعداً بر همین دسته‌ها سوار می‌شوند؛
- قواعد پذیرش: slug یکتا؛ والد باید فعال و غیرخودی باشد (چرخه ممنوع)؛
  دسته دارای خدمت یا فرزند حذف نمی‌شود (409)؛ دسته غیرفعال در صفحات
  عمومی و انتخاب‌گرها ظاهر نمی‌شود.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Topic(Base):
    """B32 - دسته موضوعی: ریشه یا فرزند؛ پایه دسته‌بندی محتوا/دوره."""

    __tablename__ = "topics"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="ck_topics_sort_nonneg"),
        Index("ix_topics_parent", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="RESTRICT"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ServiceTopic(Base):
    """B32 - اتصال خدمت به دسته؛ تکرار بی‌معناست (uq)."""

    __tablename__ = "service_topics"
    __table_args__ = (
        UniqueConstraint("service_id", "topic_id", name="uq_service_topic"),
        Index("ix_service_topics_service", "service_id"),
        Index("ix_service_topics_topic", "topic_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
