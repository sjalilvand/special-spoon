"""B09 سند جامع - نگهداشت موقت اسلات (booking hold).

چرخه: انتخاب اسلات → hold فعال با انقضای کوتاه → ثبت درخواست با
hold_token (تأیید) یا انقضا/آزادسازی. انقضای hold به‌صورت تنبل در
اولین دسترسی انجام می‌شود؛ اسلات منقضی بدون کارگر پس‌زمینه آزاد می‌گردد.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.booking import SlotClaim, SlotClaimStatus

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def expire_stale_holds(db: Session) -> int:
    """آزادسازی خودکار holdهای منقضی - الزام «hold منقضی آزاد شود» (B09)."""
    res = db.execute(
        update(SlotClaim)
        .where(SlotClaim.status == SlotClaimStatus.ACTIVE,
               SlotClaim.expires_at <= _now())
        .values(status=SlotClaimStatus.EXPIRED)
    )
    db.commit()
    return res.rowcount or 0


def active_hold_intervals(db: Session, counselor_id, from_day, to_day) -> list[tuple[datetime, datetime]]:
    """بازه‌های اشغال‌شده توسط holdهای فعال - در محاسبه اسلات آزاد استفاده می‌شود."""
    start_dt = datetime.combine(from_day, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(to_day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    rows = db.scalars(
        select(SlotClaim).where(
            SlotClaim.counselor_id == counselor_id,
            SlotClaim.status == SlotClaimStatus.ACTIVE,
            SlotClaim.expires_at > _now(),
            SlotClaim.start_at >= start_dt,
            SlotClaim.start_at < end_dt,
        )
    ).all()
    out = []
    for h in rows:
        s = h.start_at
        if s.tzinfo is None:
            s = s.replace(tzinfo=timezone.utc)
        out.append((s, s + timedelta(minutes=60)))
    return out


def create_hold(db: Session, counselor_id, start_at: datetime, ip: str | None = None) -> dict:
    """ساخت hold جدید؛ اسلات باید آزاد باشد (بدون نوبت، بدون درخواست معلق، بدون hold فعال)."""
    expire_stale_holds(db)
    token = secrets.token_urlsafe(24)
    now = _now()
    hold = SlotClaim(
        counselor_id=counselor_id,
        start_at=start_at,
        hold_token_hash=hashlib.sha256(token.encode()).hexdigest(),
        ip=ip,
        expires_at=now + timedelta(minutes=settings.booking_hold_minutes),
    )
    db.add(hold)
    try:
        db.commit()
    except Exception:
        # نقض ایندکس یکتای جزئی: هم‌زمان hold دیگری روی همین اسلات
        db.rollback()
        return {"hold": None, "conflict": True, "token": None}
    return {"hold": hold, "conflict": False, "token": token}


def get_hold_by_token(db: Session, token: str) -> SlotClaim | None:
    if not token:
        return None
    return db.scalar(
        select(SlotClaim).where(SlotClaim.hold_token_hash == hashlib.sha256(token.strip().encode()).hexdigest())
    )


def effective_status(hold: SlotClaim) -> str:
    """وضعیت عملی hold - active منقضی‌شده در نگاه اول expired دیده می‌شود."""
    if hold.status == SlotClaimStatus.ACTIVE and hold.expires_at <= _now():
        return SlotClaimStatus.EXPIRED
    return hold.status


def release_hold(db: Session, hold: SlotClaim) -> None:
    if hold.status == SlotClaimStatus.ACTIVE:
        hold.status = SlotClaimStatus.RELEASED
        hold.released_at = _now()
        db.commit()


def confirm_hold(db: Session, hold: SlotClaim, consultation_request_id, mobile: str) -> None:
    hold.status = SlotClaimStatus.CONFIRMED
    hold.consultation_request_id = consultation_request_id
    hold.mobile = mobile
    db.commit()


def remaining_seconds(hold: SlotClaim) -> int:
    if effective_status(hold) != SlotClaimStatus.ACTIVE:
        return 0
    return max(0, int((hold.expires_at - _now()).total_seconds()))
