import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SlotClaimStatus:
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    EXPIRED = "expired"


class SlotClaim(Base):
    """B09 سند جامع - نگهداشت موقت اسلات (booking hold).

    کاربر هنگام انتخاب اسلات، آن را برای مدت کوتاه نگه می‌دارد تا فرم را
    کامل کند؛ انقضای hold به‌صورت تنبل (lazy) در اولین دسترسی آزاد می‌شود
    و اسلات بدون کارگر پس‌زمینه در دسترس بقیه برمی‌گردد.
    توکن hold فقط به‌صورت hash ذخیره می‌شود (اشتراک با رویه امن سامانه).
    """

    __tablename__ = "slot_claims"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','confirmed','released','expired')",
            name="ck_slot_claims_status",
        ),
        # فقط یک نگهداشت فعال برای هر (مشاور، اسلات) - منع تعارض B09
        Index(
            "uq_slot_claims_active_slot",
            "counselor_id", "start_at",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    counselor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselors.id", ondelete="CASCADE"), index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default=SlotClaimStatus.ACTIVE, index=True)
    hold_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    mobile: Mapped[str | None] = mapped_column(String(15), nullable=True, index=True)
    consultation_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consultation_requests.id", ondelete="SET NULL"), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
