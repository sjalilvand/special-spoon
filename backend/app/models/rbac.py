"""فاز ۵۲ - مدیریت کاربران پیشرفته: نقش‌ها با ماتریس دسترسی گرافیکی.

طراحی:
- ``permissions`` کاتالوگ مرکزی دسترسی‌ها است (کد + بخش + عنوان فارسی + ترتیب).
  بخش‌ها (section) صفحه‌های پنل را روی نقشهٔ منو بازتاب می‌دهند و ستون‌های
  ماتریس در رابط گرافیکی «نقش‌ها و دسترسی‌ها» از همین کاتالوگ ساخته می‌شوند.
- ``role_permissions`` پیوند چند‌به‌چند نقش ↔ دسترسی است؛ اثربخشی کاربر =
  اجتماع دسترسی‌های همهٔ نقش‌های او.
- ``roles.data_scope`` سطح دسترسی **روی داده** است:
    all      → همهٔ داده‌های سامانه
    own      → فقط داده‌های مرتبط با خود کاربر
    assigned → داده‌های تخصیص‌یافته (پرونده/نوبت‌های واگذارشده)
- دسترسی کاربر SYSTEM_ADMIN همیشه کامل است (bypass در deps.require_perm) تا
  مدیر سامانه هرگز خودش را از سامانه قفل نکند.
"""
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# مقادیر مجاز data_scope - سطح دسترسی روی داده
DATA_SCOPES = ("all", "own", "assigned")

DATA_SCOPE_TITLES = {
    "all": "همهٔ داده‌ها",
    "own": "فقط داده‌های خودم",
    "assigned": "داده‌های تخصیص‌یافته به من",
}


class Permission(Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    section: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(200))
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


role_permissions_table = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_code",
        String(50),
        ForeignKey("roles.code", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_code",
        String(100),
        ForeignKey("permissions.code", ondelete="CASCADE"),
        primary_key=True,
    ),
)


def effective_permissions(role_rows) -> set[str]:
    """اجتماع کدهای دسترسی از مجموعه نقش‌ها (ورودی: رکوردهای Role)."""
    perms: set[str] = set()
    for role in role_rows:
        if role.code == "SYSTEM_ADMIN":
            return {"*"}
        for p in getattr(role, "permissions", []):
            perms.add(p.code)
    return perms
