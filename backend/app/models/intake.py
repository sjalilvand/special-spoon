import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IntakeQuestionnaire(Base):
    """پرسشنامه پذیرش مراجع — مطابق فرم XLSX کلینیک رز (فاز ۲۰)"""

    __tablename__ = "intake_questionnaires"
    __table_args__ = (
        CheckConstraint("status IN ('draft','final')", name="ck_intake_status"),
        UniqueConstraint("consultation_request_id", name="uq_intake_per_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consultation_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consultation_requests.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    filled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
