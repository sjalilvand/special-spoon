import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Referral(Base):
    """ارجاع پرونده (بند ۱۰.۱۰ و ۹.۱ سند v1.00)

    direction:
      internal     — ارجاع به مشاور دیگر در همان مرکز
      cross_center — ارجاع به مرکز/شعبه دیگر سازمان
      external     — ارجاع به مرکز/پزشک خارج از سازمان
    """

    __tablename__ = "referrals"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('internal','cross_center','external')",
            name="ck_referrals_direction",
        ),
        CheckConstraint(
            "status IN ('initiated','accepted','completed','rejected','cancelled')",
            name="ck_referrals_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), index=True
    )
    direction: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="initiated")

    # مقصد ارجاع — بسته به direction یکی از این‌ها پر می‌شود
    to_counselor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselors.id", ondelete="SET NULL"), nullable=True
    )
    to_service_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True
    )
    to_center_name: Mapped[str | None] = mapped_column(String(300), nullable=True)

    reason: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)

    referral_date: Mapped[date] = mapped_column(Date)
    outcome_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
