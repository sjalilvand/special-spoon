import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Diagnosis(Base):
    """تشخیص مستقل پرونده (بند ۱۰.۱۰ سند v1.00) - جدا از فرم ارزیابی"""

    __tablename__ = "diagnoses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('confirmed','probable','under_review','none')",
            name="ck_diagnoses_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    comorbid: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TreatmentPlan(Base):
    """طرح درمان ساختار یافته (بند ۴.۵ سند v1.00) - نسخه‌دار"""

    __tablename__ = "treatment_plans"
    __table_args__ = (
        CheckConstraint("status IN ('draft','active','archived')", name="ck_treatment_plans_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    approach: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approach_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    protocol_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sessions_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_interval: Mapped[str | None] = mapped_column(String(50), nullable=True)
    interventions: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_referral: Mapped[str | None] = mapped_column(String(500), nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
