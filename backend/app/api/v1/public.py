"""APIهای عمومی سایت (بدون احراز هویت) - فاز ۱۰ + رزرو آنلاین فاز ۲۱"""
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.booking import bookable_range, free_slots, validate_slot
from app.core.config import get_settings
from app.core.dates import normalize_digits
from app.db.session import get_db
from app.models.booking import SlotClaim, SlotClaimStatus
from app.models.consultation import ConsultationRequest
from app.models.people import Counselor
from app.services import booking_hold, otp as otp_service
from app.services.audit import record_audit

router = APIRouter(prefix="/public", tags=["public"])
settings = get_settings()

# محدودسازی نرخ ثبت درخواست: حداکثر ۵ درخواست در ساعت از هر IP
_req_ip: dict[str, list[float]] = {}
_RATE = 5
_WINDOW = 3600.0

# محدودسازی نرخ ساخت نگهداشت: حداکثر ۱۲ در ساعت از هر IP (فاز ۲۶ - B09)
_hold_ip: dict[str, list[float]] = {}
_HOLD_RATE = 12
_HOLD_WINDOW = 3600.0


def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    lst = [t for t in _req_ip.get(ip, []) if now - t < _WINDOW]
    if len(lst) >= _RATE:
        _req_ip[ip] = lst
        return False
    lst.append(now)
    _req_ip[ip] = lst
    return True


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _normalize_mobile(raw: str) -> str:
    return otp_service.normalize_mobile(raw)


def _hold_rate_ok(ip: str) -> bool:
    now = time.monotonic()
    lst = [t for t in _hold_ip.get(ip, []) if now - t < _HOLD_WINDOW]
    if len(lst) >= _HOLD_RATE:
        _hold_ip[ip] = lst
        return False
    lst.append(now)
    _hold_ip[ip] = lst
    return True


def _active_holds_for_ip(db: Session, ip: str) -> int:
    return int(db.scalar(
        select(func.count()).select_from(SlotClaim).where(
            SlotClaim.ip == ip,
            SlotClaim.status == SlotClaimStatus.ACTIVE,
            SlotClaim.expires_at > datetime.now(timezone.utc),
        )
    ) or 0)


class ConsultationCreate(BaseModel):
    full_name: str = Field(min_length=3, max_length=200)
    mobile: str = Field(min_length=10, max_length=20)
    topic: str = Field(min_length=2, max_length=100)
    preferred_date: str | None = Field(default=None, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    preferred_slot: str | None = Field(default=None, max_length=30)
    message: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=100)  # honeypot ضدربات
    city: str | None = Field(default=None, max_length=100)
    referral_source: str | None = Field(default=None, max_length=200)
    # فاز ۲۱ - رزرو آنلاین اسلات
    counselor_id: uuid.UUID | None = None
    start_at: str | None = Field(default=None, max_length=64)
    # فاز ۲۶ - B09/B02: توکن نگهداشت اسلات + توکن اثبات تأیید موبایل
    hold_token: str | None = Field(default=None, max_length=100)
    otp_token: str | None = Field(default=None, max_length=100)


@router.get("/counselors")
def public_counselors(db: Session = Depends(get_db)) -> dict:
    items = db.scalars(
        select(Counselor).where(Counselor.status == "active").order_by(Counselor.last_name)
    ).all()
    return {"items": [{
        "id": str(c.id),
        "name": f"{c.first_name} {c.last_name}",
        "professional_title": c.professional_title,
        "specialty": c.specialty,
        "photo_url": f"/api/v1/public/counselors/{c.id}/photo" if c.photo_path else None,
    } for c in items]}


_PHOTO_MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@router.get("/counselors/{counselor_id}/photo")
def counselor_photo(counselor_id: uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Counselor, counselor_id)
    if c is None or not c.photo_path:
        raise HTTPException(status_code=404, detail="عکس یافت نشد")
    base = Path("uploads").resolve()
    p = (base / c.photo_path).resolve()
    if not str(p).startswith(str(base)) or not p.is_file():
        raise HTTPException(status_code=404, detail="عکس یافت نشد")
    media = _PHOTO_MEDIA.get(p.suffix.lower(), "application/octet-stream")
    return FileResponse(p, media_type=media)


@router.get("/booking/slots")
def booking_slots(
    counselor_id: uuid.UUID,
    from_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
) -> dict:
    """اسلات‌های آزاد یک مشاور برای رزرو عمومی (فاز ۲۱)"""
    c = db.get(Counselor, counselor_id)
    if c is None or c.status != "active":
        raise HTTPException(status_code=404, detail="مشاور یافت نشد یا فعال نیست")
    f_default, t_default = bookable_range()
    try:
        f_day = date.fromisoformat(from_date) if from_date else f_default
        t_day = date.fromisoformat(to_date) if to_date else min(f_day + timedelta(days=13), t_default)
    except ValueError:
        raise HTTPException(status_code=422, detail="تاریخ نامعتبر است")
    if t_day < f_day:
        raise HTTPException(status_code=422, detail="بازه تاریخ نامعتبر است")
    return {
        "counselor": {
            "id": str(c.id),
            "name": f"{c.first_name} {c.last_name}",
            "specialty": c.specialty,
        },
        "range": {"from": f_day.isoformat(), "to": t_day.isoformat()},
        "days": free_slots(db, c.id, f_day, t_day),
    }


# ---------------- فاز ۲۶ - B09: نگهداشت موقت اسلات ----------------

class HoldCreate(BaseModel):
    counselor_id: uuid.UUID
    start_at: str = Field(max_length=64)


@router.post("/booking-holds", status_code=201)
def create_booking_hold(payload: HoldCreate, request: Request, db: Session = Depends(get_db)) -> dict:
    """نگهداشت موقت اسلات برای تکمیل فرم (پیش‌فرض ۱۰ دقیقه)."""
    ip = _client_ip(request)
    if not _hold_rate_ok(ip):
        raise HTTPException(status_code=429, detail="تلاش‌های نگهداشت زیاد است؛ کمی بعد دوباره تلاش کنید")
    if _active_holds_for_ip(db, ip) >= settings.booking_hold_max_per_ip:
        raise HTTPException(status_code=429, detail="نگهداشت‌های فعال شما زیاد است؛ یکی را تکمیل یا رها کنید")

    counselor = db.get(Counselor, payload.counselor_id)
    if counselor is None or counselor.status != "active":
        raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست")
    try:
        raw = datetime.fromisoformat(payload.start_at)
    except ValueError:
        raise HTTPException(status_code=422, detail="زمان رزرو نامعتبر است")

    booking_hold.expire_stale_holds(db)
    normalized = validate_slot(db, counselor.id, raw)
    if normalized is None:
        raise HTTPException(status_code=409, detail="این زمان در دسترس نیست؛ اسلات دیگری انتخاب کنید")

    res = booking_hold.create_hold(db, counselor.id, normalized, ip=ip)
    if res["conflict"]:
        raise HTTPException(status_code=409, detail="این اسلات هم‌اکنون توسط کاربر دیگری نگه داشته شده است")
    hold = res["hold"]
    record_audit(db, action="public.booking_hold_created",
                 entity_type="slot_claim", entity_id=str(hold.id), ip=ip)
    return {
        "hold_id": str(hold.id),
        "hold_token": res["token"],
        "expires_at": hold.expires_at.isoformat(),
        "remaining_seconds": booking_hold.remaining_seconds(hold),
        "counselor": {"id": str(counselor.id), "name": f"{counselor.first_name} {counselor.last_name}"},
        "start_at": normalized.isoformat(),
        "hold_minutes": settings.booking_hold_minutes,
    }


@router.get("/booking-holds/{hold_token}")
def get_booking_hold(hold_token: str, db: Session = Depends(get_db)) -> dict:
    """وضعیت نگهداشت برای همگام‌سازی شمارش معکوس سمت کاربر."""
    hold = booking_hold.get_hold_by_token(db, hold_token)
    if hold is None:
        raise HTTPException(status_code=404, detail="نگهداشت یافت نشد")
    st = booking_hold.effective_status(hold)
    c = db.get(Counselor, hold.counselor_id)
    return {
        "status": st,
        "start_at": hold.start_at.isoformat(),
        "expires_at": hold.expires_at.isoformat(),
        "remaining_seconds": booking_hold.remaining_seconds(hold),
        "counselor_name": f"{c.first_name} {c.last_name}" if c else None,
    }


@router.delete("/booking-holds/{hold_token}", status_code=204)
def release_booking_hold(hold_token: str, db: Session = Depends(get_db)) -> Response:
    hold = booking_hold.get_hold_by_token(db, hold_token)
    if hold is None:
        raise HTTPException(status_code=404, detail="نگهداشت یافت نشد")
    booking_hold.release_hold(db, hold)
    return Response(status_code=204)


@router.post("/consultation-requests", status_code=201)
def submit_consultation(payload: ConsultationCreate, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = _client_ip(request)
    # هانی‌پات: ربات‌ها فیلد مخفی را پر می‌کنند — پاسخ موفق جعلی بدون ذخیره
    if payload.website and payload.website.strip():
        return {"status": "ok"}
    if not _rate_ok(ip):
        raise HTTPException(status_code=429, detail="تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید")

    mobile = _normalize_mobile(payload.mobile)
    if not re.fullmatch(r"09\d{9}", mobile):
        raise HTTPException(status_code=422, detail="شماره موبایل معتبر نیست (نمونه: 09121234567)")

    # فاز ۲۶ - B02: تأیید موبایل با کد یک‌بارمصرف (الزامی وقتی BOOKING_REQUIRE_OTP=true)
    otp_ok = False
    if payload.otp_token:
        if not otp_service.consume_verify_token(db, payload.otp_token, mobile):
            raise HTTPException(status_code=403, detail="تأیید موبایل نامعتبر یا منقضی است؛ کد جدید بگیرید")
        otp_ok = True
    elif settings.booking_require_otp:
        raise HTTPException(status_code=403, detail="تأیید موبایل با کد یک‌بارمصرف الزامی است")

    preferred = None
    if payload.preferred_date:
        try:
            preferred = datetime.strptime(payload.preferred_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail="تاریخ نامعتبر است")

    # فاز ۲۱/۲۶ - اعتبارسنجی رزرو اسلات (با یا بدون نگهداشت)
    preferred_counselor_id = None
    preferred_start = None
    slot_label = payload.preferred_slot
    hold = None
    if payload.counselor_id is not None or payload.start_at or payload.hold_token:
        if payload.hold_token:
            # مسیر hold: اعتبارسنجی نگهداشت به‌جای اسلات (hold خودش اسلات را رزرو کرده است)
            if payload.counselor_id is None:
                raise HTTPException(status_code=422, detail="برای رزرو، انتخاب مشاور و زمان هر دو الزامی است")
            booking_hold.expire_stale_holds(db)
            hold = booking_hold.get_hold_by_token(db, payload.hold_token)
            if hold is None or booking_hold.effective_status(hold) != "active":
                raise HTTPException(status_code=409, detail="زمان نگهداشت منقضی شده است؛ لطفاً اسلات را دوباره انتخاب کنید")
            if str(hold.counselor_id) != str(payload.counselor_id):
                raise HTTPException(status_code=409, detail="نگهداشت با مشاور انتخاب‌شده مطابقت ندارد")
            counselor = db.get(Counselor, hold.counselor_id)
            if counselor is None or counselor.status != "active":
                raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست")
            preferred_counselor_id = counselor.id
            preferred_start = hold.start_at
            slot_label = preferred_start.strftime("%H:%M")
        else:
            if payload.counselor_id is None or not payload.start_at:
                raise HTTPException(status_code=422, detail="برای رزرو، انتخاب مشاور و زمان هر دو الزامی است")
            counselor = db.get(Counselor, payload.counselor_id)
            if counselor is None or counselor.status != "active":
                raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست")
            try:
                raw = datetime.fromisoformat(payload.start_at)
            except ValueError:
                raise HTTPException(status_code=422, detail="زمان رزرو نامعتبر است")
            normalized = validate_slot(db, counselor.id, raw)
            if normalized is None:
                raise HTTPException(status_code=409, detail="این زمان دیگر در دسترس نیست؛ لطفاً اسلات دیگری انتخاب کنید")
            preferred_counselor_id = counselor.id
            preferred_start = normalized
            slot_label = normalized.strftime("%H:%M")

    r = ConsultationRequest(
        full_name=payload.full_name.strip(),
        mobile=mobile,
        topic=payload.topic.strip(),
        preferred_date=preferred,
        preferred_slot=slot_label,
        message=payload.message,
        city=payload.city,
        referral_source=payload.referral_source,
        ip=ip,
        preferred_counselor_id=preferred_counselor_id,
        preferred_start_at=preferred_start,
    )
    db.add(r)
    try:
        db.commit()
    except IntegrityError:
        # ایندکس یکتای جزئی: دو رزرو هم‌زمان روی یک اسلات
        db.rollback()
        raise HTTPException(status_code=409, detail="این زمان هم‌اکنون رزرو شد؛ اسلات دیگری انتخاب کنید")
    # فاز ۲۶ - B09: تبدیل نگهداشت به رزرو تأییدشده
    if hold is not None:
        booking_hold.confirm_hold(db, hold, r.id, mobile)
    record_audit(db, action="public.consultation_requested",
                 entity_type="consultation_request", entity_id=str(r.id), ip=ip,
                 detail={"booking": preferred_start is not None,
                         "hold": hold is not None, "otp_verified": otp_ok})
    return {"status": "ok", "request_id": str(r.id)}