"""فاز ۴۲ - ADR-05 گام ۳: منطق Idempotency-Key واقعی عملیات مالی.

چرخه هر درخواست مالی دارای کلید (الگوی دو-فازی، مستقل از تراکنش کسب‌وکار):

1. ``reserve`` — رزرو کلید با INSERT (PK یکتا) در تراکنش کوتاه مستقل؛
   چهار حالت: owner (رزرو با موفقیت) | replay (پاسخ آماده بازپخش) |
   inflight (کلید هم‌اکنون توسط درخواست دیگری در جریان است) | conflict
   (همان کلید با مسیر/بدنه متفاوت — ۴۰۹)؛
2. اجرای هندلر به روش عادی (تراکنش کسب‌وکار خودش را دارد)؛
3. ``store_snapshot`` — ثبت پاسخ موفق JSON در همان ردیف (فقط رزروهای
   هنوز-pending)؛ ``release`` — حذف رزرو در خطا/پاسخ غیر-JSON تا کلاینت
   بتواند با همان کلید دوباره تلاش کند.

ایمنی‌ها:
- رزرو بدون snapshot قدیمی‌تر از ``idempotency_pending_ttl_seconds`` (سقوط
  سرور بین دو فاز) «کهنه» است و جایگزین می‌شود — ردیف رهاشده هرگز کلاینت
  را برای همیشه قفل نمی‌کند؛
- حذف/به‌روزرسانی هرگز روی ردیف snapshot‌دار انجام نمی‌شود (WHERE
  response_snapshot IS NULL) — پاسخ ثبت‌شده تغییرناپذیر است؛
- ``purge_expired`` ردیف‌های کهنه (>۲۴ ساعت) را پاک می‌کند — روت ادمین
  اکنون، beat صف کار (ADR-02) در آینده؛ ``lazy purge`` ساعتی داخل
  reserve برای نگهداری خودکار بدون وابستگی عملیاتی.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.idempotency import IdempotencyKey

# حالت‌های reserve
OWNER = "owner"
REPLAY = "replay"
INFLIGHT = "inflight"
CONFLICT = "conflict"

# پاک‌سازی تنبل: حداقل فاصله بین دو اجرای خودکار داخل reserve
_last_lazy_purge = 0.0


def _age_seconds(row: IdempotencyKey) -> float:
    """سن ردیف بر حسب ثانیه — created_at بدون tz به‌عنوان UTC تفسیر می‌شود."""
    created = row.created_at
    if created is None:
        return float("inf")
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds()


def reserve(db: Session, key: str, endpoint: str, payload_hash: str) -> tuple[str, dict | None]:
    """فاز ۱ — رزرو کلید؛ خروجی (state, snapshot) طبق سربرگ ماژول."""
    s = get_settings()
    row = db.get(IdempotencyKey, key)
    if row is None:
        db.add(IdempotencyKey(key=key, endpoint=endpoint, payload_hash=payload_hash))
        try:
            db.commit()
            _lazy_purge()
            return OWNER, None
        except IntegrityError:
            # مسابقه درخواست هم‌زمان — برنده قبلی را می‌خوانیم
            db.rollback()
            row = db.get(IdempotencyKey, key)
            if row is None:  # pragma: no cover - محافظه‌کارانه
                db.add(IdempotencyKey(key=key, endpoint=endpoint, payload_hash=payload_hash))
                db.commit()
                return OWNER, None

    if row.endpoint != endpoint or row.payload_hash != payload_hash:
        return CONFLICT, None

    if row.response_snapshot is not None:
        return REPLAY, row.response_snapshot

    ttl = int(getattr(s, "idempotency_pending_ttl_seconds", 600))
    if _age_seconds(row) > ttl:
        # رزرو رهاشده (سقوط بین دو فاز) — جایگزینی اتمیک فقط در حالت pending
        res = db.execute(
            update(IdempotencyKey)
            .where(
                IdempotencyKey.key == key,
                IdempotencyKey.response_snapshot.is_(None),
            )
            .values(endpoint=endpoint, payload_hash=payload_hash, created_at=func.now())
        )
        # rowcount باید پیش از commit خوانده شود (cursor پس از commit ریست می‌شود)
        replaced = res.rowcount
        db.commit()
        if replaced == 1:
            return OWNER, None
        row = db.get(IdempotencyKey, key)
        if row is not None and row.response_snapshot is not None:
            return REPLAY, row.response_snapshot
        return INFLIGHT, None

    return INFLIGHT, None


def store_snapshot(db: Session, key: str, status_code: int, body) -> None:
    """فاز ۲ — ثبت پاسخ موفق؛ فقط رزرو pending، هرگز ردیف snapshot‌دار."""
    db.execute(
        update(IdempotencyKey)
        .where(IdempotencyKey.key == key, IdempotencyKey.response_snapshot.is_(None))
        .values(response_snapshot={"status_code": int(status_code), "body": body})
    )
    db.commit()


def release(db: Session, key: str) -> None:
    """حذف رزرو در خطا/پاسخ غیر-JSON — تلاش مجدد با همان کلید آزاد می‌ماند."""
    db.execute(
        delete(IdempotencyKey).where(
            IdempotencyKey.key == key, IdempotencyKey.response_snapshot.is_(None)
        )
    )
    db.commit()


def purge_expired(db: Session, *, before_hours: int | None = None, limit: int = 1000) -> int:
    """پاک‌سازی ردیف‌های کهنه (پیش‌فرض: retention تنظیمات؛ سقف حذف در هر اجرا)."""
    hours = int(before_hours or getattr(get_settings(), "idempotency_retention_hours", 24))
    threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    ids = db.scalars(
        select(IdempotencyKey.key)
        .where(IdempotencyKey.created_at < threshold)
        .limit(limit)
    ).all()
    if not ids:
        return 0
    db.execute(delete(IdempotencyKey).where(IdempotencyKey.key.in_(ids)))
    db.commit()
    return len(ids)


def _lazy_purge() -> None:
    """پاک‌سازی خودکار کم‌بسامد (حداکثر هر idempotency_lazy_purge_interval_seconds)."""
    global _last_lazy_purge
    s = get_settings()
    interval = int(getattr(s, "idempotency_lazy_purge_interval_seconds", 3600))
    now = time.monotonic()
    if now - _last_lazy_purge < interval:
        return
    _last_lazy_purge = now
    from app.db.session import SessionLocal

    try:
        db = SessionLocal()
        try:
            purge_expired(db, limit=500)
        finally:
            db.close()
    except SQLAlchemyError:  # fail-soft — هرگز جریان مالی را متوقف نمی‌کند
        pass


def keys_summary(db: Session) -> dict:
    """آمار شفافیت برای روت ادمین: کل/در جریان/ثبت‌شده."""
    total = int(db.scalar(select(func.count()).select_from(IdempotencyKey)) or 0)
    pending = int(
        db.scalar(
            select(func.count())
            .select_from(IdempotencyKey)
            .where(IdempotencyKey.response_snapshot.is_(None))
        )
        or 0
    )
    return {"total": total, "pending": pending, "snapshotted": total - pending}


def key_out(row: IdempotencyKey) -> dict:
    return {
        "key": row.key,
        "endpoint": row.endpoint,
        "payload_hash": row.payload_hash[:12],
        "has_snapshot": row.response_snapshot is not None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
