import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StoredFile(Base):
    """B39 سند جامع - بارگذاری و دانلود امن فایل.

    فایل فیزیکی در فضای ذخیره‌سازی (دایرکتوری volume) نگه داشته می‌شود
    و در پایگاه داده فقط فراداده، مالکیت، checksum و کلید ذخیره می‌آید.
    """

    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(
            "scan_status IN ('pending','clean','quarantined','failed')",
            name="ck_files_scan_status",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_files_size"),
        # فاز ۳۷ - ADR-04: پروایدر واقعیِ ذخیره هر فایل (منبع حقیقت دانلود)
        CheckConstraint("storage IN ('local','s3')", name="ck_files_storage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    context: Mapped[str] = mapped_column(String(40), default="case_document", index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(120), unique=True)
    # فاز ۳۷ - ADR-04: local (پیش‌فرض) | s3 — مهاجرت تدریجی ممکن می‌شود
    storage: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(20), default="confidential")
    scan_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FileScan(Base):
    """سوابق اسکن فایل - قرنطینه و نتیجه بررسی بدافزار (B39)."""

    __tablename__ = "file_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), index=True
    )
    scanner: Mapped[str] = mapped_column(String(60), default="builtin-stub")
    status: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
