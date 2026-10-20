"""فاز ۳۶ - B28 سند جامع: یکپارچه‌سازی‌های بیرونی — سرویس پیامک پلاگین‌پذیر.

تصمیم معماری (همان الگوی D02/D03/D07):
- سرویس پیامک آداپتور قابل‌جایگزین با config است؛
  sms_provider = "log" | "kavenegar" | "smsir"
- پیش‌فرض «log» — قطعی، بدون کلید و بدون هزینه؛ پیام در لاگ سرور می‌رود و
  ردیف صف با provider='log' sent می‌شود (مناسب توسعه/آزمون پذیرش).
- «kavenegar»/«smsir» فقط با SMS_API_KEY فعال می‌شوند؛ در نبود کلید به‌جای
  شکست به log سقوط می‌کند (fail-soft مثل D03/D07) و fallback در config_out
  شفاف گزارش می‌شود؛ کلید هرگز به کلاینت و به لاگ نمی‌رود.
- صف ارسال در سطح پایگاه‌داده است (ADR-02: تا پیش از صف کار اختصاصی)؛
  process محدود و ایمن است و شکست هر پیامک جریان اصلی را متوقف نمی‌کند.
- سقف تلاش: sms_max_attempts (پیش‌فرض ۵) سپس وضعیت failed.

GET /integrations/config وضعیت همه یکپارچه‌سازی‌های بیرونی سامانه را بدون
هیچ کلیدی نشان می‌دهد: پرداخت (D02)، نقشه (D03)، ایمیل (D04)، هوش مصنوعی
(D07)، پیامک (B28) و ذخیره‌سازی فایل (ADR-04 — فاز ۳۷).
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.file import StoredFile
from app.models.integration import SmsOutbox, SmsOutboxStatus
from app.services.object_storage import storage_status

SMS_PROVIDERS = ("log", "kavenegar", "smsir")

_SMS_FOOTER = "\n- سامانه Rosepsy"


# ---------------------------------------------------------------- provider resolution
def configured_sms_provider(s: Settings | None = None) -> str:
    """نام آداپتور پیکربندی‌شده (پیش‌فرض log)."""
    s = s or get_settings()
    provider = (getattr(s, "sms_provider", "log") or "log").strip().lower()
    return provider if provider in SMS_PROVIDERS else "log"


def active_sms_provider(s: Settings | None = None) -> tuple[str, bool]:
    """آداپتور فعال واقعی + پرچم fallback — آداپتور کلیددار بدون کلید → log (fail-soft)."""
    s = s or get_settings()
    configured = configured_sms_provider(s)
    if configured in ("kavenegar", "smsir") and not (getattr(s, "sms_api_key", "") or "").strip():
        return "log", True
    return configured, False


def sms_config_out(s: Settings | None = None) -> dict:
    """متادیتای شفاف پیامک — بدون هیچ کلیدی."""
    s = s or get_settings()
    configured = configured_sms_provider(s)
    active, fallback = active_sms_provider(s)
    return {
        "channel": "sms",
        "enabled": bool(getattr(s, "sms_enabled", False)),
        "configured_provider": configured,
        "active_provider": active,
        "fallback_applied": fallback,
        "max_attempts": int(getattr(s, "sms_max_attempts", 5)),
    }


def integrations_config_out(db: Session | None = None) -> dict:
    """وضعیت همه یکپارچه‌سازی‌های بیرونی — بدون هیچ کلیدی (شفافیت B28).

    فاز ۴۱ (ADR-04 گام ۴): اگر db داده شود، شمارش ردیف‌های هنوز local
    (``local_rows``) هم می‌آید تا اپراتور بداند تسویه volume محلی کی ممکن است
    (صفر شدن این شمارش = پیش‌نیاز «فقط-خواندنی/حذف volume» مطابق طرح).
    """
    s = get_settings()
    payment_ready = bool(
        (s.payment_gateway == "sandbox") or (s.payment_gateway == "zarinpal" and s.zarinpal_merchant_id)
    )
    map_ready = bool(s.map_provider == "osm" or getattr(s, f"{s.map_provider}_api_key", ""))
    smtp_ready = bool(s.smtp_enabled and s.smtp_host)
    out = {
        "payment_gateway": {
            "configured": s.payment_gateway,
            "ready": payment_ready,
            "decision": "D02",
        },
        "maps": {
            "configured": s.map_provider,
            "ready": map_ready,
            "decision": "D03",
        },
        "email": {
            "configured": "smtp",
            "ready": smtp_ready,
            "decision": "D04",
        },
        "ai": {
            "configured": s.ai_provider,
            "ready": bool(s.ai_provider == "rule" or s.ai_api_key),
            "decision": "D07",
        },
        "sms": {**sms_config_out(s), "decision": "B28"},
        # فاز ۳۷ - ADR-04: ذخیره‌سازی فایل (local پیش‌فرض | s3/MinIO)
        # همیشه ready: پیش‌فرض local بدون کلید کار می‌کند؛ S3 ناقص → fallback شفاف
        "storage": {**storage_status(s), "ready": True, "decision": "ADR-04"},
    }
    if db is not None:
        # فاز ۴۱ - گام ۴ طرح ADR-04: دید عملیاتی تسویه volume محلی (بدون کلید)
        local_rows = (
            db.execute(
                select(func.count())
                .select_from(StoredFile)
                .where(StoredFile.storage == "local")
            ).scalar()
            or 0
        )
        out["storage"]["local_rows"] = int(local_rows)
        out["storage"]["settlement_ready"] = int(local_rows) == 0
    return out


# ---------------------------------------------------------------- queue
def queue_sms(
    db: Session,
    *,
    recipient_mobile: str | None,
    purpose: str,
    body: str,
    notification_id=None,
) -> SmsOutbox | None:
    """افزودن پیامک به صف — شکست جریان اصلی را متوقف نمی‌کند (SAVEPOINT)."""
    mobile = (recipient_mobile or "").strip()
    if not mobile:
        return None
    provider, _fallback = active_sms_provider()
    try:
        with db.begin_nested():
            row = SmsOutbox(
                notification_id=notification_id,
                recipient_mobile=mobile[:20],
                purpose=(purpose or "notification")[:30],
                body=body[:1000],
                provider=provider,
                status=SmsOutboxStatus.PENDING,
            )
            db.add(row)
            db.flush()
        return row
    except Exception:
        return None


# ---------------------------------------------------------------- adapters
def _http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: float = 15.0) -> dict:
    """تماس REST بیرونی — فقط در آزمون monkeypatch می‌شود؛ در خطای شبکه Exception."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _send_via_kavenegar(settings: Settings, mobile: str, body: str) -> None:
    """Kavenegar REST v1 — کلید در URL نمی‌تواند لاگ عمومی بگیرد؛ خطا بالا می‌رود."""
    key = (settings.sms_api_key or "").strip()
    if not key:
        raise RuntimeError("کلید کاوه‌نگار تنظیم نشده است")
    payload = {"receptor": mobile, "message": body}
    if (settings.sms_sender or "").strip():
        payload["sender"] = settings.sms_sender.strip()
    result = _http_post_json(f"https://api.kavenegar.com/v1/{key}/sms/send.json", payload)
    status = int(result.get("return", {}).get("status", 0))
    if status != 200:
        raise RuntimeError(f"کاوه‌نگار ارسال را نپذیرفت (status={status})")


def _send_via_smsir(settings: Settings, mobile: str, body: str) -> None:
    """SMS.ir REST v1 — کلید در هدر؛ خطا بالا می‌رود."""
    key = (settings.sms_api_key or "").strip()
    if not key:
        raise RuntimeError("کلید SMS.ir تنظیم نشده است")
    result = _http_post_json(
        "https://api.sms.ir/v1/send/bulk",
        {"messageText": body, "mobiles": [mobile], "sender": (settings.sms_sender or "").strip() or None},
        headers={"x-api-key": key, "SECRET-KEY": key},
    )
    if int(result.get("status", 0)) != 1:
        raise RuntimeError(f"SMS.ir ارسال را نپذیرفت (status={result.get('status')})")


def _send_via_log(settings: Settings, mobile: str, body: str) -> None:
    """آداپتور پیش‌فرض توسعه/آزمون — قطعی؛ متن پیام در لاگ سرور می‌رود."""
    print(f"[SMS:{settings.sms_provider}] mobile={mobile} body={body}")


def _send(settings: Settings, provider: str, mobile: str, body: str) -> None:
    if provider == "kavenegar":
        _send_via_kavenegar(settings, mobile, body)
    elif provider == "smsir":
        _send_via_smsir(settings, mobile, body)
    else:
        _send_via_log(settings, mobile, body)


# ---------------------------------------------------------------- process
def process_sms_outbox(db: Session, *, limit: int = 25) -> dict:
    """ارسال ردیف‌های pending؛ خروجی شمارنده‌ها برای گزارش عملیاتی."""
    settings = get_settings()
    rows = db.scalars(
        select(SmsOutbox)
        .where(SmsOutbox.status == SmsOutboxStatus.PENDING)
        .order_by(SmsOutbox.created_at.asc())
        .limit(min(max(limit, 1), 200))
    ).all()

    sms_ready = bool(getattr(settings, "sms_enabled", False))
    provider, fallback = active_sms_provider(settings)
    sent = failed = disabled = 0
    for row in rows:
        if not sms_ready:
            row.status = SmsOutboxStatus.DISABLED
            row.last_error = "سرویس پیامک پیکربندی نشده است (SMS_ENABLED=false)"
            disabled += 1
            continue
        try:
            _send(settings, provider, row.recipient_mobile, row.body)
            row.status = SmsOutboxStatus.SENT
            row.provider = provider
            row.sent_at = datetime.now(timezone.utc)
            row.last_error = None
            sent += 1
        except Exception as exc:
            row.attempts = (row.attempts or 0) + 1
            row.last_error = str(exc)[:500]
            if row.attempts >= settings.sms_max_attempts:
                row.status = SmsOutboxStatus.FAILED
            else:
                row.status = SmsOutboxStatus.PENDING
            failed += 1
    db.commit()
    return {
        "queued": len(rows),
        "sent": sent,
        "failed": failed,
        "disabled": disabled,
        "active_provider": provider,
        "fallback_applied": fallback,
    }


def sms_outbox_summary(db: Session) -> dict:
    """خلاصه وضعیت صف برای داشبورد مدیر."""
    statuses = dict(db.execute(
        select(SmsOutbox.status, func.count())
        .group_by(SmsOutbox.status)
    ).all())
    settings = get_settings()
    active, fallback = active_sms_provider(settings)
    return {
        "by_status": {st: int(n) for st, n in statuses.items()},
        "sms_enabled": bool(getattr(settings, "sms_enabled", False)),
        "active_provider": active,
        "fallback_applied": fallback,
    }
