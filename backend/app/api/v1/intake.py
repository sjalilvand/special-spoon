"""پرسشنامه پذیرش مراجع — فرم XLSX کلینیک رز (فاز ۲۰ + اصلاح ماتریس دسترسی)"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.consultation import ConsultationRequest
from app.models.intake import IntakeQuestionnaire
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(tags=["intake"])

# خواندن: همه نقش‌های داخلی مرتبط؛ نوشتن/نهایی‌سازی: پذیرش، مدیر سازمان، مشاور
READ_ROLES = ("ORG_MANAGER", "RECEPTION", "COUNSELOR", "TECHNICAL_SUPERVISOR", "SYSTEM_ADMIN")
WRITE_ROLES = ("ORG_MANAGER", "RECEPTION", "COUNSELOR", "SYSTEM_ADMIN")


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def _check_read(actor) -> None:
    if not (_roles(actor) & set(READ_ROLES)):
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")


def _check_write(actor) -> None:
    if not (_roles(actor) & set(WRITE_ROLES)):
        raise HTTPException(status_code=403, detail="ویرایش پرسشنامه برای نقش شما مجاز نیست")


def _get_cr_or_404(db: Session, cr_id: uuid.UUID) -> ConsultationRequest:
    cr = db.get(ConsultationRequest, cr_id)
    if cr is None:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    return cr


def _get_or_none(db: Session, cr_id: uuid.UUID) -> IntakeQuestionnaire | None:
    return db.scalar(select(IntakeQuestionnaire).where(IntakeQuestionnaire.consultation_request_id == cr_id))


def _out(db: Session, q: IntakeQuestionnaire | None) -> dict:
    if q is None:
        return {"exists": False, "status": None, "data": {}, "filled_by_name": None, "updated_at": None}
    u = db.get(User, q.filled_by) if q.filled_by else None
    return {
        "exists": True, "status": q.status, "data": q.data or {},
        "filled_by_name": u.display_name if u else None,
        "updated_at": q.updated_at.isoformat() if q.updated_at else None,
    }


class IntakeData(BaseModel):
    data: dict[str, Any] = {}


@router.get("/consultation-requests/{cr_id}/intake")
def get_intake(cr_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    _check_read(actor)
    _get_cr_or_404(db, cr_id)
    return _out(db, _get_or_none(db, cr_id))


@router.post("/consultation-requests/{cr_id}/intake")
def save_intake(cr_id: uuid.UUID, payload: IntakeData, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    _check_read(actor)
    _check_write(actor)
    _get_cr_or_404(db, cr_id)
    q = _get_or_none(db, cr_id)
    if q is None:
        q = IntakeQuestionnaire(consultation_request_id=cr_id, filled_by=actor.id)
        db.add(q)
    if q.status == "final":
        raise HTTPException(status_code=409, detail="پرسشنامه نهایی شده و بی‌ردپا تغییر نمی‌کند")
    q.data = payload.data
    q.status = "draft"
    q.filled_by = actor.id
    db.commit()
    record_audit(db, action="intake.saved", actor_user_id=actor.id,
                 entity_type="intake_questionnaire", entity_id=str(q.id))
    return _out(db, q)


@router.post("/consultation-requests/{cr_id}/intake/finalize")
def finalize_intake(cr_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    _check_read(actor)
    _check_write(actor)
    _get_cr_or_404(db, cr_id)
    q = _get_or_none(db, cr_id)
    if q is None:
        raise HTTPException(status_code=404, detail="پرسشنامه‌ای برای ثبت وجود ندارد")
    if q.status == "final":
        raise HTTPException(status_code=409, detail="این پرسشنامه قبلاً نهایی شده است")
    required_keys = ("identity_full_name", "initial_problem_summary", "planning_goals")
    missing = [k for k in required_keys if not ((q.data or {}).get(k) or "").strip()]
    if missing:
        raise HTTPException(status_code=422, detail={
            "message": "نهایی‌سازی با اطلاعات ناقص مجاز نیست",
            "errors": [{"field": k, "error": "تکمیل الزامی است"} for k in missing],
        })
    q.status = "final"
    q.filled_by = actor.id
    db.commit()
    record_audit(db, action="intake.finalized", actor_user_id=actor.id,
                 entity_type="intake_questionnaire", entity_id=str(q.id))
    return _out(db, q)