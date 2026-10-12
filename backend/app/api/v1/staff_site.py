"""عملیات پنلی مرتبط با سایت عمومی — فاز ۱۰"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.consultation import ConsultationRequest
from app.models.people import Counselor
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(tags=["site-ops"])

PHOTO_MAX = 2 * 1024 * 1024


def _detect_image(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"\x89PNG":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


@router.post("/counselors/{counselor_id}/photo", status_code=201)
async def upload_counselor_photo(
    counselor_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor=Depends(require_roles("ORG_MANAGER", "SYSTEM_ADMIN")),
) -> dict:
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    data = await file.read()
    if len(data) > PHOTO_MAX:
        raise HTTPException(status_code=422, detail="حجم عکس باید کمتر از ۲ مگابایت باشد")
    ext = _detect_image(data)
    if ext is None:
        raise HTTPException(status_code=422, detail="فقط تصویر JPEG/PNG/WebP پذیرفته می‌شود")

    folder = Path("uploads") / "counselor_photos"
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}.{ext}"
    (folder / fname).write_bytes(data)

    # حذف عکس قبلی (best-effort)
    if c.photo_path:
        old = Path("uploads") / c.photo_path
        try:
            if old.is_file():
                old.unlink()
        except OSError:
            pass

    c.photo_path = f"counselor_photos/{fname}"
    db.commit()
    record_audit(db, action="counselor.photo_uploaded", actor_user_id=actor.id,
                 entity_type="counselor", entity_id=str(c.id))
    return {"photo_url": f"/api/v1/public/counselors/{c.id}/photo"}


class ConsultStatusUpdate(BaseModel):
    status: str = Field(pattern="^(new|in_review|converted|archived)$")


def _out(db: Session, r: ConsultationRequest) -> dict:
    handler = db.get(User, r.handled_by) if r.handled_by else None
    return {
        "id": str(r.id),
        "full_name": r.full_name,
        "mobile": r.mobile,
        "topic": r.topic,
        "preferred_date": r.preferred_date.isoformat() if r.preferred_date else None,
        "preferred_slot": r.preferred_slot,
        "message": r.message,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "handled_by_name": handler.display_name if handler else None,
    }


@router.get("/consultation-requests")
def list_consultation_requests(
    status: str = Query(default="", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles("ORG_MANAGER", "RECEPTION")),
) -> dict:
    q = select(ConsultationRequest)
    if status in ("new", "in_review", "converted", "archived"):
        q = q.where(ConsultationRequest.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(ConsultationRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [_out(db, r) for r in items], "total": total, "page": page, "page_size": page_size}


@router.patch("/consultation-requests/{request_id}")
def update_consultation_request(
    request_id: uuid.UUID,
    payload: ConsultStatusUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles("ORG_MANAGER", "RECEPTION")),
) -> dict:
    r = db.get(ConsultationRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    r.status = payload.status
    r.handled_by = actor.id
    r.handled_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, action="consultation.status_changed", actor_user_id=actor.id,
                 entity_type="consultation_request", entity_id=str(r.id),
                 detail={"status": payload.status})
    return _out(db, r)
