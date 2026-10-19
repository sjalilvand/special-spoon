"""B12/B38 سند جامع - مرکز اعلان درون‌برنامه‌ای.

قواعد سند:
- شکست یا نبود اعلان هرگز جریان اصلی (پرداخت/نهایی‌سازی) را برنمی‌گرداند؛
  لذا همه emit ها در try/except ایمن شده‌اند.
- محتوای حساس بالینی در متن اعلان نمی‌آید؛ فقط عنوان کلی و ارجاع.
- فاز ۲۷ (B12+): برای گیرنده دارای ایمیل، ردیفی در صف خروجی SMTP ساخته
  می‌شود؛ ارسال غیرهمگام و شکست آن جریان اصلی را متوقف نمی‌کند.
- فاز ۳۶ (B28): برای گیرنده دارای موبایل و فعال بودن سرویس پیامک، ردیفی
  در صف خروجی پیامک ساخته می‌شود (آداپتور پلاگین‌پذیر همان الگو)؛ محتوای
  حساس بالینی هرگز در متن پیامک نمی‌آید.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.notification import Notification
from app.models.user import Role, User

# دسته‌بندی‌های مجاز
CATEGORIES = ("case", "assessment", "appointment", "consent", "system")
SEVERITIES = ("info", "warning", "critical")

_EMAIL_FOOTER = "این پیام به‌صورت خودکار توسط سامانه Rosepsy ارسال شده است؛ به این ایمیل پاسخ ندهید."
_SMS_FOOTER = "\n- سامانه Rosepsy"


def _queue_sms_copy(db: Session, user: User, title: str, body: str | None, notification_id) -> None:
    """B28 فاز ۳۶: قرار دادن کپی پیامک اعلان در صف خروجی (بدون توقف جریان)."""
    try:
        if not get_settings().notifications_sms_enabled:
            return
        if not user.mobile:
            return
        from app.services.integrations import queue_sms

        text = "\n".join(filter(None, [title, body])) + _SMS_FOOTER
        queue_sms(
            db,
            recipient_mobile=user.mobile,
            purpose="notification",
            body=text[:1000],
            notification_id=notification_id,
        )
    except Exception:
        pass


def _queue_email_copy(db: Session, user: User, title: str, body: str | None, notification_id) -> None:
    """B12+ فاز ۲۷: قرار دادن کپی ایمیل اعلان در صف خروجی (بدون توقف جریان)."""
    try:
        if not get_settings().notifications_email_enabled:
            return
        if not user.email:
            return
        from app.services.email_outbox import queue_email

        text = "\n".join(filter(None, [title, body, "", _EMAIL_FOOTER]))
        queue_email(
            db,
            recipient_email=user.email,
            subject=title[:200],
            body_text=text[:20000],
            notification_id=notification_id,
        )
    except Exception:
        pass


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
            # B12+ فاز ۲۷: کپی ایمیل برای گیرنده دارای ایمیل
            # B28 فاز ۳۶: کپی پیامک برای گیرنده دارای موبایل
            user = db.get(User, recipient_user_id)
            if user is not None:
                _queue_email_copy(db, user, n.title, n.body, n.id)
                _queue_sms_copy(db, user, n.title, n.body, n.id)
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
