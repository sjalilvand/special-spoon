"""فاز ۲۹ - B31 سند جامع: مراکز مشاوره و شعب.

- مرکز (clinic): نام، slug یکتا، شرح، لوگو، تلفن، وب‌سایت.
- شعبه (branch): استان/شهر/نشانی/کدپستی، ساعات کاری، مختصات و وضعیت.
  قواعد سند: slug یکتا؛ عرض جغرافیایی بین −۹۰ و ۹۰؛ طول بین −۱۸۰ و ۱۸۰؛
  شعبه منتشرنشده عمومی نیست.
- خدمت شعبه (branch_service_offerings): خدمت ناموجود برای شعبه
  در صفحات عمومی نشان داده نمی‌شود.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BranchStatus:
    DRAFT = "draft"
    PUBLISHED = "published"
    ALL = (DRAFT, PUBLISHED)


class Clinic(Base):
    """B31 - مرکز مشاوره (کلینیک) با شناسه عمومی یکتا."""

    __tablename__ = "clinics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Branch(Base):
    """B31 - شعبه مرکز: نشانی، ساعات و مختصات با کنترل انتشار."""

    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint("status IN ('draft','published')", name="ck_branches_status"),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_branches_lat_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_branches_lon_range",
        ),
        Index("ix_branches_clinic", "clinic_id"),
        Index("ix_branches_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200))
    province: Mapped[str | None] = mapped_column(String(80), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    working_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=BranchStatus.DRAFT)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    clinic: Mapped["Clinic"] = relationship(lazy="joined", foreign_keys=[clinic_id])


class BranchServiceOffering(Base):
    """B31 - خدمات ارائه‌شده در هر شعبه؛ پذیرش سند: «خدمت ناموجود برای
    شعبه نشان داده نشود»."""

    __tablename__ = "branch_service_offerings"
    __table_args__ = (
        UniqueConstraint("branch_id", "service_id", name="uq_branch_service"),
        Index("ix_branch_offerings_branch", "branch_id"),
        Index("ix_branch_offerings_service", "service_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
