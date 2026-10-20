"""فاز ۳۵ - B37 سند جامع: تست روان‌شناسی و تفسیر — با تصمیم D08 (ناظر علمی).

قواعد پذیرش:
- ابزار تست (PsychTest) با سؤال‌ها (هر گزینه امتیاز دارد) و «بازه‌های
  تفسیر» تعریف می‌شود و روی دسته‌بندی موضوعی B32 سوار است (topic_id)؛
- تصمیم D08: «انتشار ابزار علمی فقط با تأیید ناظر علمی» — چرخه
  draft → pending_review → published | rejected؛ نقش
  TECHNICAL_SUPERVISOR تنها مجاز به approve/reject است (مدیر سازمان/
  سامانه فقط ارسال برای بازبینی دارد)؛ بازرسی با یادداشت ثبت می‌شود؛
- تأیید ابزار بدون حداقل یک بازه تفسیر ممنوع (۴۲۲)؛
- برگزاری فقط برای ابزار منتشرشده؛ نمره = جمع امتیاز گزینه‌های انتخابی؛
  تفسیر از بازه‌های تأییدشده (اولین بازه شامل نمره)؛ نتیجه برای کاربر
  خودش و کارکنان/مشاور دیدنی است.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PsychStatus:
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ALL = (DRAFT, PENDING_REVIEW, PUBLISHED, REJECTED)


class PsychTest(Base):
    """B37 - ابزار تست روان‌شناسی؛ انتشار فقط با تأیید ناظر علمی (D08)."""

    __tablename__ = "psych_tests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','pending_review','published','rejected')",
            name="ck_psych_tests_status",
        ),
        Index("ix_psych_tests_topic", "topic_id"),
        Index("ix_psych_tests_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default=PsychStatus.DRAFT)
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PsychQuestion(Base):
    """B37 - سؤال ابزار؛ گزینه‌ها JSONB [{label, score}] — امتیاز هر گزینه ≥ ۰.

    فاز ۴۷: subscale اختیاری — نام زیرمقیاس (مثلاً «اضطراب» در DASS-21) برای
    نمایش ریز‌نمره‌ها در نتیجه؛ نمره کل همچنان جمع همه سؤال‌هاست.
    """

    __tablename__ = "psych_questions"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="ck_psych_questions_sort_nonneg"),
        Index("ix_psych_questions_test", "test_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("psych_tests.id", ondelete="RESTRICT"), nullable=False
    )
    prompt: Mapped[str] = mapped_column(String(1000))
    options: Mapped[list] = mapped_column(JSONB, default=list)  # [{"label": "...", "score": 0}]
    subscale: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PsychInterpretation(Base):
    """B37 - بازه تفسیر نمره؛ «تفسیر فقط از بازه‌های ثبت‌شده ابزار»."""

    __tablename__ = "psych_interpretations"
    __table_args__ = (
        CheckConstraint("score_min <= score_max", name="ck_psych_interp_range"),
        Index("ix_psych_interp_test", "test_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("psych_tests.id", ondelete="RESTRICT"), nullable=False
    )
    score_min: Mapped[int] = mapped_column(Integer)
    score_max: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(200))
    guidance: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PsychAttempt(Base):
    """B37 - اجرای تست توسط کاربر؛ نمره/تفسیر سمت سرور محاسبه و snapshot می‌شود."""

    __tablename__ = "psych_attempts"
    __table_args__ = (
        CheckConstraint("score >= 0", name="ck_psych_attempts_score_nonneg"),
        Index("ix_psych_attempts_test", "test_id"),
        Index("ix_psych_attempts_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("psych_tests.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    score: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    interpretation_label: Mapped[str] = mapped_column(String(200))
    interpretation_guidance: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    answers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # فاز ۴۷ - ریزنمره زیرمقیاس‌ها snapshot می‌شود: {"اضطراب": 9, "فشار": 12}
    subscale_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
