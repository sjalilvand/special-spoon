"""APIهای عمومی سایت (بدون احراز هویت) - فاز ۱۰ + رزرو آنلاین فاز ۲۱"""
import re
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.booking import bookable_range, free_slots, validate_slot
from app.core.dates import normalize_digits
from app.db.session import get_db
from app.models.consultation import ConsultationRequest
from app.models.people import Counselor
from app.services.audit import record_audit

router = APIRouter(prefix="/public", tags=["public"])

# محدودسازی نرخ ثبت درخواست: حداکثر ۵ درخواست در ساعت از هر IP
_req_ip: dict[str, list[float]] = {}
_RATE = 5
_WINDOW = 3600.0


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
    s = normalize_digits(raw).replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    return s


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

    preferred = None
    if payload.preferred_date:
        try:
            preferred = datetime.strptime(payload.preferred_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail="تاریخ نامعتبر است")

    # فاز ۲۱ - اعتبارسنجی رزرو اسلات
    preferred_counselor_id = None
    preferred_start = None
    slot_label = payload.preferred_slot
    if payload.counselor_id is not None or payload.start_at:
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
    record_audit(db, action="public.consultation_requested",
                 entity_type="consultation_request", entity_id=str(r.id), ip=ip,
                 detail={"booking": preferred_start is not None})
    return {"status": "ok", "request_id": str(r.id)}