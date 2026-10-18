import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CaseStatus:
    NEW = "new"
    AWAITING_ASSIGNMENT = "awaiting_assignment"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    ARCHIVED = "archived"


CASE_STATUSES = ("new", "awaiting_assignment", "active", "suspended", "closed", "archived")
CONSENT_STATUSES = ("granted", "revoked")


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','awaiting_assignment','active','suspended','closed','archived')",
            name="ck_cases_status",
        ),
        CheckConstraint("consent_status IN ('none','granted','revoked')", name="ck_cases_consent_status"),
        CheckConstraint("priority IN ('low','normal','high')", name="ck_cases_priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applicants.id", ondelete="RESTRICT"), index=True
    )
    acceptance_date: Mapped[date] = mapped_column(Date)
    service_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True
    )
    service_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_counselor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselors.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[str] = mapped_column(String(30), default=CaseStatus.AWAITING_ASSIGNMENT)
    consent_status: Mapped[str] = mapped_column(String(20), default="none")
    close_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # بند ۱۱.۲ سند: کنترل ویرایش هم‌زمان
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CaseAssignment(Base):
    __tablename__ = "case_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), index=True
    )
    counselor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselors.id", ondelete="RESTRICT"), index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role_in_case: Mapped[str] = mapped_column(String(20), default="primary")
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Consent(Base):
    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint("status IN ('granted','revoked')", name="ck_consents_status"),
        # هر ثبت یک نسخه جدید؛ سوابق حفظ می‌شوند (بند ۷.۲)
        CheckConstraint("version >= 1", name="ck_consents_version"),
        CheckConstraint("kind IN ('treatment','psych_test','data_share','marketing')", name="ck_consents_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    consent_date: Mapped[date] = mapped_column(Date)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # B41 سند جامع: نوع رضایت، اتصال به متن نسخه‌دار و ابطال با حفظ سابقه
    kind: Mapped[str] = mapped_column(String(30), default="treatment")
    consent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consent_versions.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoke_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
