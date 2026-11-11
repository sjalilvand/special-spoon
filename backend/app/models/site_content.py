"""فاز ۸۴ — ویرایشگر وردپرسی‌وار صفحات عمومی سایت.

مدل محتوای صفحات عمومی اپ site (روی مسیر /): هر «صفحه» یک ردیف با کلید
page_key دارد و دو سند جدا:
- draft_content: پیش‌نویس ویرایشگر پنل — هیچ اثری روی سایت ندارد تا «انتشار»؛
- published_content: سند منتشرشده که GET عمومی برمی‌گرداند.

اگر ردیفی نبود یا سندی منتشر نشده بود، اپ site به متن‌های پیش‌فرضِ داخل باندل
خودش (site/src/content/texts.ts و psycho.ts و payRules.ts و clinics.ts و
specialist.ts) برمی‌گردد — یعنی بدون این جدول هم سایت کامل است و ویرایش ادمین
فقط «بازنویسیِ روی پیش‌فرض» است.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# کلیدهای مجاز صفحات — هماهنگ با اپ site (content/override.ts) و فایل
# app/data/site_content_defaults.json (متن‌های پیش‌فرض برای ویرایشگر پنل)
# فاز ۸۵: «clinics» و «specialist» هم اضافه شدند (بدون تغییر DDL — کلید رشته‌ای است)
SITE_PAGE_KEYS = ("home", "psycho", "payment-rules", "clinics", "specialist")

SITE_PAGE_TITLES = {
    "home": "صفحهٔ اصلی سایت",
    "psycho": "صفحهٔ روان‌درمانی",
    "payment-rules": "قوانین پرداخت و استرداد وجه",
    "clinics": "شبکهٔ کلینیک‌های رز",
    "specialist": "صفحهٔ متخصص و رزرو نوبت",
}


class SitePageContent(Base):
    """محتوای ویرایش‌پذیر یک صفحهٔ عمومی — پیش‌نویس و نسخهٔ منتشرشده.

    قاعدهٔ D08-مانند فاز ۸۳: هیچ تغییری تا «انتشار» روی سایت اعمال نمی‌شود؛
    انتشار = کپی draft → published؛ بازگردانی پیش‌نویس = کپی معکوس؛
    بازنشانی = حذف ردیف → سایت به متن‌های پیش‌فرض کد برمی‌گردد.
    """

    __tablename__ = "site_page_content"

    page_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    draft_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    published_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # هویت آخرین ویرایشگر/ناشر — بدون FK تا حذف حساب کاربری محتوا را نسوزاند
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
