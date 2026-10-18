import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


CONSENT_KINDS = ("treatment", "psych_test", "data_share", "marketing")


class ConsentVersion(Base):
    """B41 سند جامع - نسخه‌داری متن رضایت‌نامه.

    متن هر نسخه پس از ایجاد غیرقابل‌تغییر است؛ انتشار فقط با ایجاد
    نسخه جدید انجام می‌شود (immutable versioning).
    """

    __tablename__ = "consent_versions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('treatment','psych_test','data_share','marketing')",
            name="ck_consent_versions_kind",
        ),
        # ترکیب (کد، نسخه) یکتا - متن نسخه‌ها ثابت می‌ماند
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(30), default="treatment", index=True)
    version: Mapped[int] = mapped_column(default=1)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
