"""فاز ۸۸ — فراخوان همکاری (پورت فرم مرجع Samaneh-IT-rose/farakhan در سامانه).

سه جدول:
- ``farakhan_locations``: استان/شهرستان‌های ایران (seed مایگریشن 0053) —
  فهرست فرم عمومی فراخوان؛ snapshot نام استان/شهرستان در لحظهٔ ثبت روی خود
  رکورد ذخیره می‌شود (الگوی فرم مرجع) تا تغییر دادهٔ پایه، رکوردهای قبلی را
  نمی‌شکند.
- ``farakhan_submissions``: یک ردیف به‌ازای هر ثبت‌نام فراخوان همکاری.
  ``tracking_code`` یکتا و بدون دادهٔ شخصی است (الگوی فرم مرجع FRK-XXXX…).
- ``farakhan_files``: پیوند هر فایل آپلودی به ثبت‌نام + کلید فیلد فرم.
  محتوای فیزیکی همان زیرساخت امن فایل سامانه (files/objstore؛ local|s3) است —
  دانلود فقط با بلیت امضاشدهٔ کوتاه‌مدت از مسیر /files (بند B39).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# وضعیت بررسی ثبت‌نام (پنل)
FARAKHAN_STATUSES = ("new", "reviewed", "accepted", "rejected")


class FarakhanLocation(Base):
    """استان/شهرستان فرم فراخوان — ردیف استان: county برابر NULL."""

    __tablename__ = "farakhan_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    province_name: Mapped[str] = mapped_column(String(80), index=True)
    # NULL = ردیف استان؛ مقدار = شهرستان همان استان
    county_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FarakhanSubmission(Base):
    """یک ثبت‌نام کامل فراخوان همکاری (پورت فیلدهای فرم مرجع)."""

    __tablename__ = "farakhan_submissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','reviewed','accepted','rejected')",
            name="ck_farakhan_status",
        ),
        CheckConstraint("gender IN ('male','female')", name="ck_farakhan_gender"),
        CheckConstraint(
            "education_degree IN ('bachelor','master','phd')",
            name="ck_farakhan_degree",
        ),
        CheckConstraint(
            "license_status IN ('valid','in_progress','none')",
            name="ck_farakhan_license_status",
        ),
        CheckConstraint(
            "center_ownership IN ('owned','rented','other')",
            name="ck_farakhan_ownership",
        ),
        # فاز ۹۳ — هر کد ملی فقط یک ثبت‌نامِ «فعال» (ایندکس یکتای جزئی؛ مایگریشن 0055).
        # ثبت‌نامِ «ردشده» مستثنا است تا متقاضی بتواند دوباره ثبت‌نام کند.
        Index(
            "ux_farakhan_nc_active",
            "national_code",
            unique=True,
            postgresql_where=text("status <> 'rejected'"),
            sqlite_where=text("status <> 'rejected'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracking_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    # ── مشخصات فردی ──
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    national_code: Mapped[str] = mapped_column(String(10), index=True)
    gender: Mapped[str] = mapped_column(String(10))
    birth_date_jalali: Mapped[str] = mapped_column(String(10))
    birth_date_gregorian: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # ── سربازی (فقط آقایان) ──
    military_status: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # ── تحصیلات ──
    education_degree: Mapped[str] = mapped_column(String(30))
    education_field: Mapped[str] = mapped_column(String(120))

    # ── پروانه فعالیت مرکز ──
    license_status: Mapped[str] = mapped_column(String(20))
    license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── مرکز ──
    center_ownership: Mapped[str] = mapped_column(String(20))
    province_name: Mapped[str] = mapped_column(String(80))
    county_name: Mapped[str] = mapped_column(String(80))

    # ── تماس و نشانی ──
    phone: Mapped[str] = mapped_column(String(15))
    mobile_number: Mapped[str | None] = mapped_column(String(15), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── ظرفیت مرکز ──
    individual_rooms: Mapped[int] = mapped_column(Integer, default=0)
    group_rooms: Mapped[int] = mapped_column(Integer, default=0)
    child_rooms: Mapped[int] = mapped_column(Integer, default=0)
    counselors_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── امکانات ──
    has_waiting_space: Mapped[bool] = mapped_column(Boolean, default=False)
    accepts_company_pattern: Mapped[bool] = mapped_column(Boolean, default=False)
    has_accessibility: Mapped[bool] = mapped_column(Boolean, default=False)

    # پذیرش قوانین — مهر زمانی فقط سمت سرور
    terms_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # ── بررسی پنل ──
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # IP متقاضی (فقط عملیاتی؛ در خروجی اکسل هم می‌آید)
    submit_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FarakhanFile(Base):
    """پیوند فایل آپلودی (files) به ثبت‌نام فراخوان + کلید فیلد فرم."""

    __tablename__ = "farakhan_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farakhan_submissions.id", ondelete="CASCADE"),
        index=True,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="RESTRICT"), index=True
    )
    # کلید فیلد فرم (military_card / national_id_card / …)
    field_key: Mapped[str] = mapped_column(String(40))
    original_name: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
