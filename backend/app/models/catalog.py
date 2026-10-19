"""فاز ۲۸ - B05/B06/B07 سند جامع: صلاحیت مشاور، خدمات و تعرفه نسخه‌دار.

- B05: مدرک/مجوز مشاور با چرخه تأیید (verification-review)؛ مشاور بدون
  صلاحیت معتبر در فهرست قابل رزرو قرار نمی‌گیرد.
- B06: تخصص و خدمت (مدت مثبت، نوع جلسه، وضعیت ارائه)؛ خدمت غیرفعال
  رزرو جدید نمی‌گیرد.
- B07: تعرفه نسخه‌دار (مبلغ، ارز، بازه اعتبار)؛ بازه‌های هم‌پوشان
  ناسازگار رد می‌شوند و قیمت نوبت/سفارش گذشته به‌صورت snapshot
  در جدول نوبت ذخیره می‌شود تا با تغییر تعرفه تغییر نکند.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CredentialVerificationStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CredentialKind:
    LICENSE = "license"
    DEGREE = "degree"
    CERTIFICATE = "certificate"
    ALL = (LICENSE, DEGREE, CERTIFICATE)


class CounselorCredential(Base):
    """B05 - مدرک/مجوز مشاور + نتیجه بازبینی صلاحیت."""

    __tablename__ = "counselor_credentials"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('pending','approved','rejected')",
            name="ck_counselor_credentials_status",
        ),
        CheckConstraint(
            "expires_at IS NULL OR issued_at IS NULL OR expires_at >= issued_at",
            name="ck_counselor_credentials_range",
        ),
        Index("ix_counselor_credentials_counselor", "counselor_id"),
        Index("ix_counselor_credentials_status", "verification_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    counselor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselors.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), default=CredentialKind.LICENSE)
    title: Mapped[str] = mapped_column(String(200))
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(20), default=CredentialVerificationStatus.PENDING
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Specialty(Base):
    """B06 - تخصص موضوعی خدمات."""

    __tablename__ = "specialties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ServiceSessionType:
    IN_PERSON = "in_person"
    ONLINE = "online"
    PHONE = "phone"
    ALL = (IN_PERSON, ONLINE, PHONE)


class ServiceStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"


class Service(Base):
    """B06 - خدمت: تخصص، مدت مثبت، نوع جلسه و وضعیت ارائه."""

    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="ck_services_duration_positive"),
        CheckConstraint(
            "session_type IN ('in_person','online','phone')",
            name="ck_services_session_type",
        ),
        CheckConstraint("status IN ('active','inactive')", name="ck_services_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    specialty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("specialties.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    session_type: Mapped[str] = mapped_column(String(20), default=ServiceSessionType.IN_PERSON)
    status: Mapped[str] = mapped_column(String(20), default=ServiceStatus.ACTIVE)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TariffVersion(Base):
    """B07 - نسخه تعرفه: مبلغ، ارز و بازه اعتبار با شمول دو سر روز.

    valid_to = NULL یعنی بدون تاریخ پایان (باز-پایان)؛ برای افزودن نسخه جدید
    باید نسخه باز-پایان قبلی با PATCH بسته شود تا هم‌پوشانی رخ ندهد.
    """

    __tablename__ = "tariff_versions"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_tariff_amount_nonneg"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_tariff_range"),
        Index("ix_tariff_versions_service_from", "service_id", "valid_from"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[int] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
