"""فاز ۳۴ - B33/B34/B35/B36 سند جامع: محتوا، دوره، آزمون و گواهی.

همه روی دسته‌بندی موضوعی B32 (فاز ۳۳) سوار می‌شوند — topic_id اختیاری
برای دسته‌بندی؛ «دسته غیرفعال در صفحات عمومی نشان داده نشود» در
خروجی‌های عمومی نیز رعایت می‌شود (محتوای منتشرشده زیر دسته غیرفعال
عمومی نیست).

B33 محتوا: slug یکتا؛ وضعیت draft/published؛ انتشار فقط دستی.
B34 دوره: دوره رایگان (price=0) ثبت‌نام فوری فعال دارد؛ دوره پولی سفارش
  kind='course' می‌سازد و پس از پرداخت موفق (B10) ثبت‌نام فعال می‌شود
  (snapshot قیمت — قیمت گذشته تغییر نمی‌کند)؛ ظرفیت محدود قابل اعمال است.
B35 آزمون: سؤال‌ها با گزینه‌های JSONB و پاسخ صحیح فقط سمت سرور؛
  «پاسخ صحیح هرگز به کلاینت نمی‌رود»؛ نمره‌دهی سمت سرور؛ تلاش بیش از
  سقف ممنوع؛ آزمون دوره‌ای نیازمند ثبت‌نام فعال؛ آزمون پولی نیازمند
  سفارش پرداخت‌شده kind='exam'.
B36 گواهی: پس از قبولی آزمون خودکار صادر می‌شود (idempotent)؛ پس از
  «تکمیل دوره» با اقدام مدیر؛ شماره یکتای جلالی؛ verify عمومی؛ ابطال
  فقط با پرچم revoked (سابقه حفظ می‌شود).
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PublishStatus:
    DRAFT = "draft"
    PUBLISHED = "published"
    ALL = (DRAFT, PUBLISHED)


class EnrollmentStatus:
    PENDING = "pending"      # منتظر پرداخت
    ACTIVE = "active"        # فعال (رایگان: از لحظه ثبت‌نام؛ پولی: پس از پرداخت)
    COMPLETED = "completed"  # تکمیل‌شده → گواهی دوره
    CANCELLED = "cancelled"
    ALL = (PENDING, ACTIVE, COMPLETED, CANCELLED)


class AttemptStatus:
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    ALL = (IN_PROGRESS, PASSED, FAILED)


# ---------------------------------------------------------------- B33
class Content(Base):
    """B33 - محتوا (مقاله/صفحه) متصل به دسته موضوعی B32."""

    __tablename__ = "contents"
    __table_args__ = (
        CheckConstraint("status IN ('draft','published')", name="ck_contents_status"),
        Index("ix_contents_topic", "topic_id"),
        Index("ix_contents_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default=PublishStatus.DRAFT)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------- B34
class Course(Base):
    """B34 - دوره آموزشی روی دسته B32؛ رایگان یا پولی (سفارش kind='course')."""

    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint("status IN ('draft','published')", name="ck_courses_status"),
        CheckConstraint("price_amount >= 0", name="ck_courses_price_nonneg"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_courses_capacity_positive"),
        Index("ix_courses_topic", "topic_id"),
        Index("ix_courses_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default=PublishStatus.DRAFT)
    price_amount: Mapped[int] = mapped_column(Numeric(16, 2), default=0)  # 0 = رایگان
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = بی‌نهایت
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CourseSession(Base):
    """B34 - جلسات برنامه‌ریزی‌شده دوره."""

    __tablename__ = "course_sessions"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="ck_course_sessions_duration"),
        CheckConstraint("sort_order >= 0", name="ck_course_sessions_sort_nonneg"),
        Index("ix_course_sessions_course", "course_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300))
    session_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=90)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CourseEnrollment(Base):
    """B34 - ثبت‌نام کاربر در دوره؛ یکتا per (course, user)؛ pending → active
    با پرداخت سفارش kind='course' (اثر جانبی verify) یا اقدام مدیر."""

    __tablename__ = "course_enrollments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','active','completed','cancelled')",
            name="ck_course_enrollments_status",
        ),
        UniqueConstraint("course_id", "user_id", name="uq_course_enrollment"),
        Index("ix_course_enrollments_course", "course_id"),
        Index("ix_course_enrollments_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=EnrollmentStatus.PENDING)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=True, unique=True,
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- B35
class Exam(Base):
    """B35 - آزمون روی دسته B32؛ پیوند اختیاری به دوره (نیازمند ثبت‌نام فعال)
    یا آزمون مستقل رایگان/پولی (سفارش kind='exam')."""

    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint("status IN ('draft','published')", name="ck_exams_status"),
        CheckConstraint("duration_minutes > 0", name="ck_exams_duration_positive"),
        CheckConstraint("pass_percent >= 0 AND pass_percent <= 100", name="ck_exams_pass_range"),
        CheckConstraint("price_amount >= 0", name="ck_exams_price_nonneg"),
        CheckConstraint("max_attempts > 0", name="ck_exams_attempts_positive"),
        Index("ix_exams_topic", "topic_id"),
        Index("ix_exams_course", "course_id"),
        Index("ix_exams_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default=PublishStatus.DRAFT)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    pass_percent: Mapped[int] = mapped_column(Integer, default=60)
    price_amount: Mapped[int] = mapped_column(Numeric(16, 2), default=0)  # 0 = رایگان
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ExamQuestion(Base):
    """B35 - سؤال آزمون؛ correct_index فقط سمت سرور می‌ماند."""

    __tablename__ = "exam_questions"
    __table_args__ = (
        CheckConstraint("points > 0", name="ck_exam_questions_points_positive"),
        CheckConstraint("sort_order >= 0", name="ck_exam_questions_sort_nonneg"),
        Index("ix_exam_questions_exam", "exam_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exams.id", ondelete="RESTRICT"), nullable=False
    )
    prompt: Mapped[str] = mapped_column(String(1000))
    options: Mapped[list] = mapped_column(JSONB, default=list)  # ۲ تا ۶ گزینه
    correct_index: Mapped[int] = mapped_column(Integer)         # 0..len(options)-1
    points: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExamAttempt(Base):
    """B35 - تلاش کاربر در آزمون؛ پاسخ‌ها JSONB (فهرست اندیس گزینه)؛
    نمره‌دهی سمت سرور در submit انجام می‌شود."""

    __tablename__ = "exam_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('in_progress','passed','failed')", name="ck_exam_attempts_status"),
        CheckConstraint("score_percent IS NULL OR (score_percent >= 0 AND score_percent <= 100)",
                        name="ck_exam_attempts_score_range"),
        Index("ix_exam_attempts_exam", "exam_id"),
        Index("ix_exam_attempts_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exams.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=AttemptStatus.IN_PROGRESS)
    score_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    answers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------- B36
class Certificate(Base):
    """B36 - گواهی با شماره یکتای جلالی؛ پس از قبولی آزمون خودکار و پس از
    تکمیل دوره با اقدام مدیر؛ ابطال با پرچم revoked (سابقه حفظ می‌شود)."""

    __tablename__ = "certificates"
    __table_args__ = (
        Index("ix_certificates_user", "user_id"),
        Index("ix_certificates_course", "course_id"),
        Index("ix_certificates_exam", "exam_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certificate_number: Mapped[str] = mapped_column(String(40), unique=True)  # CERT-<سال شمسی>-<ترتیب>
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )
    exam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exams.id", ondelete="SET NULL"), nullable=True
    )
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exam_attempts.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300))
    holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)  # snapshot نام دارنده
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
