import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OtpPurpose:
    BOOKING = "booking"
    LOGIN = "login"


class OtpChallenge(Base):
    """B02 سند جامع - چالش کد یک‌بارمصرف (otp_challenges).

    کد فقط به‌صورت hash (با pepper کلید سامانه) ذخیره می‌شود؛ انقضا، سقف
    تلاش و مصرف‌شدن یک‌باره در سرویس otp کنترل می‌شود. کد مصرف‌شده
    دوباره پذیرفته نمی‌شود (الزام صریح B02).
    """

    __tablename__ = "otp_challenges"
    __table_args__ = (
        CheckConstraint("purpose IN ('booking','login')", name="ck_otp_purpose"),
        CheckConstraint("attempts >= 0", name="ck_otp_attempts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mobile: Mapped[str] = mapped_column(String(15), index=True)
    purpose: Mapped[str] = mapped_column(String(20), default=OtpPurpose.BOOKING)
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # توکن اثبات تأیید موبایل پس از مصرف موفق کد (یک‌بارمصرف)
    verify_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    verify_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
