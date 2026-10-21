"""فاز ۴۹ - B41/B42: فرایندهای سازمانی نسخه‌دار + مانیتورینگ وضعیت درخواست.

- تعریف فرایند (process_definitions): کد یکتا، عنوان، شرح.
- نسخه فرایند (process_versions): هر نسخه XML استاندارد BPMN 2.0 را نگه
  می‌دارد؛ انتشار نسخه جدید، نسخه منتشرشده قبلی را بایگانی می‌کند تا
  «ثبت نسخه قبلی» همیشه ممکن باشد و نمونه‌های در جریان به نسخه خودشان
  ارجاع دارند (نسخه‌داری مانند فرم‌ها).
- نمونه اجرا (process_instances): هر درخواست/پرونده/موضوع می‌تواند در
  یک فرایند منتشرشده جریان داشته باشد؛ گام فعلی و وضعیت کل نگه‌داری می‌شود.
- رخداد گام (process_instance_events): خط‌زمانی هر نمونه برای مانیتورینگ
  وضعیت درخواست در فرایند (کدام گام انجام شد، کدام گام فعال است).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessDefinition(Base):
    """B41 - فرایند سازمانی (مثل پذیرش تلفنی) با کد یکتا."""

    __tablename__ = "process_definitions"
    __table_args__ = (
        CheckConstraint("length(code) >= 2", name="ck_process_definitions_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcessVersion(Base):
    """B41 - نسخه فرایند: XML های BPMN 2.0 با شماره‌گذاری خودکار.

    وضعیت‌ها: draft → published (انتشار؛ نسخه منتشرشده قبلی بایگانی می‌شود)
    → archived (بایگانی دستی یا با انتشار نسخه جدید).
    """

    __tablename__ = "process_versions"
    __table_args__ = (
        UniqueConstraint("definition_id", "version_number", name="uq_process_version_number"),
        CheckConstraint(
            "status IN ('draft','published','archived')", name="ck_process_versions_status"
        ),
        Index("ix_process_versions_definition", "definition_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("process_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    bpmn_xml: Mapped[str] = mapped_column(Text, nullable=False)
    changelog: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessInstance(Base):
    """B42 - نمونه اجرای فرایند برای یک موضوع (درخواست/پرونده/متقاضی/دستی).

    subject_id شناسه موضوع است (UUID یا کد پیگیری) و FK نیست تا نمونه‌ها
    مستقل از جدول موضوع باقی بمانند؛ snapshot اطلاعات موضوع در
    subject_meta برای نمایش مانیتورینگ نگه‌داری می‌شود.
    """

    __tablename__ = "process_instances"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','suspended','completed','cancelled')",
            name="ck_process_instances_status",
        ),
        Index("ix_process_instances_subject", "subject_type", "subject_id"),
        Index("ix_process_instances_definition", "definition_id"),
        Index("ix_process_instances_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("process_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("process_versions.id", ondelete="RESTRICT"), nullable=False
    )
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subject_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    current_element_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_element_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessInstanceEvent(Base):
    """B42 - رخداد گام‌های نمونه فرایند (خط‌زمانی مانیتورینگ)."""

    __tablename__ = "process_instance_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('done','active','pending','skipped','failed')",
            name="ck_process_instance_events_status",
        ),
        Index("ix_process_instance_events_instance", "instance_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False
    )
    element_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    element_name: Mapped[str] = mapped_column(String(200), nullable=False)
    element_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="done")
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
