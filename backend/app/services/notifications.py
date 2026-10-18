"""B12/B38 سند جامع - مرکز اعلان درون‌برنامه‌ای.

قواعد سند:
- شکست یا نبود اعلان هرگز جریان اصلی (پرداخت/نهایی‌سازی) را برنمی‌گرداند؛
  لذا همه emit ها در try/except ایمن شده‌اند.
- محتوای حساس بالینی در متن اعلان نمی‌آید؛ فقط عنوان کلی و ارجاع.
- بستر SMS/ایمیل نیازمند تصمیم D04 سند است؛ فعلاً کانال درون‌برنامه‌ای.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import Role, User

# دسته‌بندی‌های مجاز
CATEGORIES = ("case", "assessment", "appointment", "consent", "system")
SEVERITIES = ("info", "warning", "critical")


def notify_user(
    db: Session,
    *,
    recipient_user_id: uuid.UUID,
    event_code: str,
    title: str,
    body: str | None = None,
    category: str = "system",
    severity: str = "info",
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> Notification | None:
    """ثبت اعلان برای یک کاربر - خطا جریان اصلی را متوقف نمی‌کند (SAVEPOINT)."""
    try:
        with db.begin_nested():
            n = Notification(
                recipient_user_id=recipient_user_id,
                event_code=event_code[:60],
                title=title[:200],
                body=body[:500] if body else None,
                category=category if category in CATEGORIES else "system",
                severity=severity if severity in SEVERITIES else "info",
                entity_type=entity_type[:60] if entity_type else None,
                entity_id=entity_id,
            )
            db.add(n)
            db.flush()
        return n
    except Exception:
        return None


def notify_roles(
    db: Session,
    *,
    role_codes: tuple[str, ...] | list[str],
    event_code: str,
    title: str,
    body: str | None = None,
    category: str = "system",
    severity: str = "info",
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> int:
    """ثبت اعلان برای همه کاربران فعالِ نقش‌های داده‌شده."""
    user_ids = db.scalars(
        select(User.id)
        .join(User.roles)
        .where(Role.code.in_(list(role_codes)))
    ).all()
    count = 0
    for uid in user_ids:
        if notify_user(
            db,
            recipient_user_id=uid,
            event_code=event_code,
            title=title,
            body=body,
            category=category,
            severity=severity,
            entity_type=entity_type,
            entity_id=entity_id,
        ) is not None:
            count += 1
    return count
