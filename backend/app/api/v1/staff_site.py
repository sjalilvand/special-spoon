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
from app.models.case import Case, CaseAssignment, CaseStatus
from app.models.people import Applicant
from app.api.v1.cases import generate_case_number
from datetime import date as date_type

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


class ConvertRequest(BaseModel):
    create_case: bool = False
    counselor_id: uuid.UUID | None = None
    service_location_id: uuid.UUID | None = None


@router.post("/consultation-requests/{request_id}/convert")
def convert_request(request_id: uuid.UUID, payload: ConvertRequest, db: Session = Depends(get_db), actor=Depends(require_roles("ORG_MANAGER", "RECEPTION"))) -> dict:
    r = db.get(ConsultationRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    if r.status not in ("new", "in_review"):
        raise HTTPException(status_code=409, detail="این درخواست قبلاً تبدیل یا بایگانی شده است")

    full_name = (r.full_name or "").strip()
    parts = full_name.split(" ", 1)
    first = parts[0] if parts else full_name
    last = parts[1] if len(parts) > 1 else "—"

    applicant = db.scalar(select(Applicant).where(Applicant.mobile == r.mobile))
    created_applicant = False
    if applicant is None:
        applicant = Applicant(
            first_name=first, last_name=last, mobile=r.mobile,
            status="active", record_source="manual",
        )
        db.add(applicant)
        db.flush()
        created_applicant = True

    case_id = None
    case_number = None
    if payload.create_case:
        counselor_id = payload.counselor_id
        if counselor_id is not None:
            cc = db.get(Counselor, counselor_id)
            if cc is None or cc.status != "active":
                raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست")
        case = Case(
            case_number=generate_case_number(db),
            applicant_id=applicant.id,
            acceptance_date=date_type.today(),
            service_location_id=payload.service_location_id,
            service_type=r.topic,
            created_by=actor.id,
        )
        db.add(case)
        db.flush()
        if counselor_id is not None:
            db.add(CaseAssignment(
                case_id=case.id, counselor_id=counselor_id,
                reason="تبدیل از درخواست مشاوره سایت", assigned_by=actor.id, role_in_case="primary",
            ))
            case.primary_counselor_id = counselor_id
            case.status = CaseStatus.ACTIVE
        else:
            case.status = CaseStatus.AWAITING_ASSIGNMENT
        case_id = case.id
        case_number = case.case_number

    r.status = "converted"
    r.applicant_id = applicant.id
    r.case_id = case_id
    r.handled_by = actor.id
    from datetime import datetime as dt, timezone as tz
    r.handled_at = dt.now(tz.utc)
    db.commit()
    record_audit(db, action="consultation.converted", actor_user_id=actor.id,
                 entity_type="consultation_request", entity_id=str(r.id),
                 detail={"applicant_id": str(applicant.id), "case_id": str(case_id) if case_id else None})
    return {
        "status": "converted",
        "applicant_id": str(applicant.id),
        "applicant_created": created_applicant,
        "case_id": str(case_id) if case_id else None,
        "case_number": case_number,
    }