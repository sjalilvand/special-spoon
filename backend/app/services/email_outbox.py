"""B12+ فاز ۲۷ - ارسال ایمیل اعلان‌ها از طریق SMTP (تصمیم D04 سند).

- صف EmailOutbox در سطح پایگاه داده (ADR-02: تا پیش از صف کار اختصاصی).
- process_outbox همیشه محدود و ایمن اجرا می‌شود؛ شکست SMTP جریان اصلی
  را متوقف نمی‌کند و در last_error ثبت می‌شود.
- در smtp_enabled=False، ردیف‌های صف به «disabled» علامت می‌خورند تا
  صف بی‌نهایت بزرگ نشود و وضعیت برای گزارش DPO شفاف باشد.
- سقف تلاش: email_outbox_max_attempts (پیش‌فرض ۵) سپس وضعیت failed.
"""

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.email_outbox import EmailOutbox, EmailOutboxStatus


def queue_email(
    db: Session,
    *,
    recipient_email: str,
    subject: str,
    body_text: str,
    notification_id=None,
) -> EmailOutbox | None:
    """افزودن ایمیل به صف - شکست جریان اصلی را متوقف نمی‌کند (SAVEPOINT)."""
    if not recipient_email:
        return None
    try:
        with db.begin_nested():
            row = EmailOutbox(
                notification_id=notification_id,
                recipient_email=recipient_email.strip()[:255],
                subject=subject[:200],
                body_text=body_text[:20000],
                status=EmailOutboxStatus.PENDING,
            )
            db.add(row)
            db.flush()
        return row
    except Exception:
        return None


def _smtp_send(settings: Settings, to_email: str, subject: str, body_text: str) -> None:
    """ارسال مستقیم SMTP (STARTTLS یا SMTPS) - در صورت خطا Exception برمی‌گردد."""
    msg = EmailMessage()
    msg["From"] = formataddr((settings.app_name, settings.smtp_from))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    if settings.smtp_use_ssl:
        client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with client:
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            client.starttls()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(msg)


def process_outbox(db: Session, *, limit: int = 25) -> dict:
    """ارسال ردیف‌های pending؛ خروجی شمارنده‌ها برای گزارش عملیاتی و DPO."""
    settings = get_settings()
    rows = db.scalars(
        select(EmailOutbox)
        .where(EmailOutbox.status == EmailOutboxStatus.PENDING)
        .order_by(EmailOutbox.created_at.asc())
        .limit(min(max(limit, 1), 200))
    ).all()

    smtp_ready = bool(settings.smtp_enabled and settings.smtp_host)
    sent = failed = disabled = 0
    for row in rows:
        if not smtp_ready:
            row.status = EmailOutboxStatus.DISABLED
            row.last_error = "SMTP پیکربندی نشده است (SMTP_ENABLED=false)"
            disabled += 1
            continue
        try:
            _smtp_send(settings, row.recipient_email, row.subject, row.body_text)
            row.status = EmailOutboxStatus.SENT
            row.sent_at = datetime.now(timezone.utc)
            row.last_error = None
            sent += 1
        except Exception as exc:
            row.attempts = (row.attempts or 0) + 1
            row.last_error = str(exc)[:500]
            if row.attempts >= settings.email_outbox_max_attempts:
                row.status = EmailOutboxStatus.FAILED
            else:
                row.status = EmailOutboxStatus.PENDING
            failed += 1
    db.commit()
    return {"queued": len(rows), "sent": sent, "failed": failed, "disabled": disabled}


def outbox_summary(db: Session) -> dict:
    """خلاصه وضعیت صف برای داشبورد مدیر و گزارش DPO."""
    statuses = dict(db.execute(
        select(EmailOutbox.status, func.count())
        .group_by(EmailOutbox.status)
    ).all())
    settings = get_settings()
    return {
        "by_status": {s: int(n) for s, n in statuses.items()},
        "smtp_enabled": bool(settings.smtp_enabled and settings.smtp_host),
    }
