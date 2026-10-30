"""فاز ۶۴ - جدول پایهٔ استان‌های ایران با کد رسمی (۰۱ تا ۳۱).

کدها مطابق کدگذاری رسمی استان‌ها (ترتیب الفبای فارسی) است که در فایل
ورود مشاوران (ستون «کد استانها») نیز استفاده می‌شود. داده‌های پایه در
مهاجرت 0040_provinces_counselor_fields درج می‌شوند تا روی هر نصبی
موجود باشند؛ این فهرست فقط مرجع اجرایی برنامه (قالب ورود، اعتبارسنجی)
است.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# (کد رسمی، استان، مرکز، کد تلفن) — کد رسمی ۰۱..۳۱ مطابق ترتیب الفبای فارسی
IRAN_PROVINCE_SEED: list[tuple[str, str, str, str]] = [
    ("01", "آذربایجان شرقی", "تبریز", "041"),
    ("02", "آذربایجان غربی", "ارومیه", "044"),
    ("03", "اردبیل", "اردبیل", "045"),
    ("04", "اصفهان", "اصفهان", "031"),
    ("05", "البرز", "کرج", "026"),
    ("06", "ایلام", "ایلام", "084"),
    ("07", "بوشهر", "بوشهر", "077"),
    ("08", "تهران", "تهران", "021"),
    ("09", "چهارمحال و بختیاری", "شهرکرد", "038"),
    ("10", "خراسان جنوبی", "بیرجند", "056"),
    ("11", "خراسان رضوی", "مشهد", "051"),
    ("12", "خراسان شمالی", "بجنورد", "058"),
    ("13", "خوزستان", "اهواز", "061"),
    ("14", "زنجان", "زنجان", "024"),
    ("15", "سمنان", "سمنان", "023"),
    ("16", "سیستان و بلوچستان", "زاهدان", "054"),
    ("17", "فارس", "شیراز", "071"),
    ("18", "قزوین", "قزوین", "028"),
    ("19", "قم", "قم", "025"),
    ("20", "کردستان", "سنندج", "087"),
    ("21", "کرمان", "کرمان", "034"),
    ("22", "کرمانشاه", "کرمانشاه", "083"),
    ("23", "کهگیلویه و بویراحمد", "یاسوج", "074"),
    ("24", "گلستان", "گرگان", "017"),
    ("25", "گیلان", "رشت", "013"),
    ("26", "لرستان", "خرم‌آباد", "066"),
    ("27", "مازندران", "ساری", "011"),
    ("28", "مرکزی", "اراک", "086"),
    ("29", "هرمزگان", "بندرعباس", "076"),
    ("30", "همدان", "همدان", "081"),
    ("31", "یزد", "یزد", "035"),
]


class Province(Base):
    __tablename__ = "provinces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # کد رسمی دو رقمی "01".."31" — رشته (نه عدد) تا صفر ابتدایی حفظ شود
    code: Mapped[str] = mapped_column(String(2), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    capital: Mapped[str | None] = mapped_column(String(80), nullable=True)
    area_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
