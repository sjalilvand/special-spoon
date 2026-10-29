"""فاز ۶۱ - فرم‌ساز و نظرسنجی + تماس تلفنی مدیریت‌شده.

طراحی:
- ``form_templates`` تعریف فرم توسط مدیر است؛ ``fields`` یک JSONB حاوی
  فهرست فیلدهاست (هر فیلد: id/type/label/required/options/help). انواع
  پشتیبانی‌شده در ``FIELD_TYPES`` — فرم‌ساز گرافیکی پنل همین ساختار را
  می‌سازد و ``FormRenderer`` سمت فرانت آن را رندر می‌کند.
- ``form_responses`` پاسخ‌های ثبت‌شدهٔ کاربران؛ ``answers`` نگاشت
  field_id → مقدار. پاسخ می‌تواند به یک تماس (``call_id``) گره بخورد
  (نظرسنجی پس از پایان تماس) یا مستقل ثبت شود.
- ``call_sessions`` تماس تلفنی مدیریت‌شده: مشاور/کاربر از گفتگو «تماس»
  می‌زند → زنگ‌خور (ringing) → پاسخ (ongoing) → پایان (ended) و بلافاصله
  نظرسنجیِ پیوندشده برای سمت «گیرنده» فعال می‌شود. وضعیت‌ها با
  CheckConstraint محدود شده‌اند.

نکته: این فایل عمداً جدول‌های چت را import نمی‌کند تا از وابستگی حلقوی
اجتناب شود؛ کلیدهای خارجی به ``conversations``/``users`` با نام جدول
ساخته می‌شوند.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# انواع فیلد مجاز در فرم‌ساز (متناسب با نیاز فرم‌های کاغذی مرکز)
FIELD_TYPES = (
    "text",       # متن کوتاه
    "textarea",   # متن بلند
    "number",     # عدد
    "date",       # تاریخ (تقویم شمسی)
    "select",     # فهرست بسته (یک انتخاب)
    "radio",      # چندگزینه‌ای (یک انتخاب، گزینه‌ها نمایان)
    "checkbox",   # چندانتخابی
    "rating",     # امتیاز ۱ تا ۵
    "yesno",      # بله / خیر
    "heading",    # سرصفحهٔ بخش (بدون مقدار)
)

# انواع فرم
FORM_KINDS = ("survey", "intake", "custom")

# وضعیت تماس
CALL_STATUSES = ("ringing", "ongoing", "ended", "declined", "cancelled")


class FormTemplate(Base):
    __tablename__ = "form_templates"
    __table_args__ = (
        CheckConstraint("kind IN ('survey','intake','custom')", name="ck_form_templates_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="custom")
    # فهرست فیلدها: [{id,type,label,required,options?,help?}]
    fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # نظرسنجی پیش‌فرضی که پس از پایان هر تماس به گیرنده تخصیص می‌یابد
    is_default_call_survey: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FormResponse(Base):
    __tablename__ = "form_responses"
    __table_args__ = (
        Index("ix_form_responses_template", "template_id"),
        Index("ix_form_responses_respondent", "respondent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_templates.id", ondelete="CASCADE")
    )
    respondent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # در نظرسنجی پس از تماس، پاسخ‌دهنده همان گیرندهٔ تماس است؛ این ستون برای
    # حالت‌های آینده (فرم دربارهٔ شخص دیگر) نگه داشته می‌شود.
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("call_sessions.id", ondelete="SET NULL"), nullable=True,
        index=True,
    )
    answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CallSession(Base):
    __tablename__ = "call_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ringing','ongoing','ended','declined','cancelled')",
            name="ck_call_sessions_status",
        ),
        Index("ix_call_sessions_callee_status", "callee_id", "status"),
        Index("ix_call_sessions_caller_status", "caller_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    caller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    callee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="ringing")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    # نظرسنجیِ پیشنهادی پس از پایان تماس (کپی از فرم پیش‌فرض هنگام پایان)
    survey_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_templates.id", ondelete="SET NULL"), nullable=True
    )
    end_note: Mapped[str | None] = mapped_column(Text, nullable=True)
