"""فاز ۴۲ - ADR-05 گام ۳: ثبت اثر عملیات مالی با کلید یکتای کلاینت.

طرح ADR-05 (گام ۳): جدول ``idempotency_keys(key PK, endpoint, payload_hash,
response_snapshot, created_at)`` — سرور کلید را همراه اثر عملیات ذخیره
می‌کند و تکرار همان کلید → همان پاسخ قبلی (بدون ایجاد ردیف دوم).

- ``key``: UUID کلاینت (هدر ``Idempotency-Key``)؛ PK یکتا → تضمین DB در برابر
  مسابقه درخواست‌های هم‌زمان با کلید واحد (INSERT دوم با IntegrityError رد می‌شود)؛
- ``endpoint``: مسیر نرمال‌شده پس از حذف پیشوند نسخه (/api/v1|/api/v2) —
  بازپخش یک کلید بین دو نسخه مجاز، اما استفاده روی منبع دیگر (مسیر متفاوت)
  تعارض ۴۰۹ است؛
- ``payload_hash``: اثر انگشت SHA-256 بدنه — «همان کلید، درخواست متفاوت»
  هرگز بی‌صدا بازپخش نمی‌شود (۴۰۹)؛
- ``response_snapshot``: JSON {status_code, body} پاسخ موفق — تا پاسخ تکرار
  عیناً همان پاسخ اول باشد؛ NULL یعنی رزرو «در جریان» است؛
- پاک‌سازی ردیف‌های کهنه (>۲۴ ساعت) با ``purge_expired`` — روت ادمین اکنون،
  beat صف کار (ADR-02) در آینده.
"""

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(200))
    payload_hash: Mapped[str] = mapped_column(String(64))
    # none_as_null: None پایتون = SQL NULL (نه JSON 'null') — شرط‌های
    # «response_snapshot IS NULL» در reserve/release/store_snapshot فقط با
    # این تنظیم درست کار می‌کنند (NULL = رزرو در جریان، قرارداد جدول)
    response_snapshot: Mapped[dict | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
