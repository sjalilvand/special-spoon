"""APIهای عمومی سایت (بدون احراز هویت) — فاز ۱۰"""
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

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

    r = ConsultationRequest(
        full_name=payload.full_name.strip(),
        mobile=mobile,
        topic=payload.topic.strip(),
        preferred_date=preferred,
        preferred_slot=payload.preferred_slot,
        message=payload.message,
        city=payload.city,
        referral_source=payload.referral_source,
        ip=ip,
    )
    db.add(r)
    db.commit()
    record_audit(db, action="public.consultation_requested",
                 entity_type="consultation_request", entity_id=str(r.id), ip=ip)
    return {"status": "ok"}
