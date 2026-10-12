"""تشخیص‌ها و طرح‌های درمان مستقل (بند ۱۰.۱۰ سند v1.00) - فاز ۱۲"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.case import Case
from app.models.clinical import Diagnosis, TreatmentPlan
from app.models.people import Counselor
from app.models.user import User
from app.services.audit import record_audit
from app.services.case_access import counselor_can_access

router = APIRouter(tags=["clinical"])


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def _view_access(db: Session, actor, case: Case) -> None:
    roles = _roles(actor)
    if roles & {"ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"}:
        return
    if "COUNSELOR" in roles:
        c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if c is not None and counselor_can_access(db, c.id, case):
            return
    raise HTTPException(status_code=404, detail="پرونده یافت نشد")


def _write_counselor(db: Session, actor, case: Case) -> Counselor:
    if "COUNSELOR" not in _roles(actor):
        raise HTTPException(status_code=403, detail="ثبت تشخیص/طرح درمان فقط با نقش مشاور و تخصیص مجاز است")
    c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
    if c is None or not counselor_can_access(db, c.id, case):
        raise HTTPException(status_code=403, detail="این پرونده به شما تخصیص نیافته است")
    return c


def _get_case_or_404(db: Session, case_id) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    return case


class DiagnosisCreate(BaseModel):
    status: str = Field(pattern="^(confirmed|probable|under_review|none)$")
    title: str | None = Field(default=None, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    comorbid: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=2000)


def _dx_out(db: Session, d: Diagnosis) -> dict:
    u = db.get(User, d.recorded_by) if d.recorded_by else None
    return {
        "id": str(d.id), "case_id": str(d.case_id),
        "status": d.status, "title": d.title, "code": d.code,
        "comorbid": d.comorbid, "note": d.note,
        "recorded_by_name": u.display_name if u else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("/cases/{case_id}/diagnoses")
def list_diagnoses(case_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = _get_case_or_404(db, case_id)
    _view_access(db, actor, case)
    items = db.scalars(
        select(Diagnosis).where(Diagnosis.case_id == case.id).order_by(Diagnosis.created_at.desc())
    ).all()
    return {"items": [_dx_out(db, d) for d in items]}


@router.post("/cases/{case_id}/diagnoses", status_code=201)
def create_diagnosis(case_id: uuid.UUID, payload: DiagnosisCreate, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = _get_case_or_404(db, case_id)
    c = _write_counselor(db, actor, case)
    if payload.status != "none" and not (payload.title or "").strip():
        raise HTTPException(status_code=422, detail="با انتخاب وضعیت تشخیص، عنوان تشخیص الزامی است")
    d = Diagnosis(
        case_id=case.id, status=payload.status,
        title=(payload.title or "").strip() or None,
        code=payload.code, comorbid=payload.comorbid, note=payload.note,
        recorded_by=actor.id,
    )
    db.add(d)
    db.commit()
    record_audit(db, action="diagnosis.created", actor_user_id=actor.id,
                 entity_type="diagnosis", entity_id=str(d.id),
                 detail={"counselor_id": str(c.id)})
    return _dx_out(db, d)


class PlanCreate(BaseModel):
    goals: str | None = Field(default=None, max_length=3000)
    approach: str | None = Field(default=None, max_length=50)
    approach_note: str | None = Field(default=None, max_length=200)
    protocol_name: str | None = Field(default=None, max_length=200)
    sessions_count: int | None = Field(default=None, ge=1, le=500)
    session_interval: str | None = Field(default=None, max_length=50)
    interventions: str | None = Field(default=None, max_length=3000)
    external_referral: str | None = Field(default=None, max_length=500)
    review_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    remarks: str | None = Field(default=None, max_length=2000)


def _plan_out(db: Session, t: TreatmentPlan) -> dict:
    u = db.get(User, t.recorded_by) if t.recorded_by else None
    return {
        "id": str(t.id), "case_id": str(t.case_id),
        "version_no": t.version_no, "status": t.status,
        "goals": t.goals, "approach": t.approach, "approach_note": t.approach_note,
        "protocol_name": t.protocol_name, "sessions_count": t.sessions_count,
        "session_interval": t.session_interval, "interventions": t.interventions,
        "external_referral": t.external_referral,
        "review_date": t.review_date.isoformat() if t.review_date else None,
        "remarks": t.remarks,
        "recorded_by_name": u.display_name if u else None,
        "row_version": t.row_version,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/cases/{case_id}/treatment-plans")
def list_plans(case_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = _get_case_or_404(db, case_id)
    _view_access(db, actor, case)
    items = db.scalars(
        select(TreatmentPlan).where(TreatmentPlan.case_id == case.id).order_by(TreatmentPlan.version_no.desc())
    ).all()
    return {"items": [_plan_out(db, t) for t in items]}


@router.post("/cases/{case_id}/treatment-plans", status_code=201)
def create_plan(case_id: uuid.UUID, payload: PlanCreate, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = _get_case_or_404(db, case_id)
    c = _write_counselor(db, actor, case)
    last = db.scalar(select(func.max(TreatmentPlan.version_no)).where(TreatmentPlan.case_id == case.id)) or 0
    review = None
    if payload.review_date:
        try:
            review = date.fromisoformat(payload.review_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="تاریخ بازبینی نامعتبر است")
    t = TreatmentPlan(
        case_id=case.id, version_no=int(last) + 1,
        goals=payload.goals, approach=payload.approach, approach_note=payload.approach_note,
        protocol_name=payload.protocol_name, sessions_count=payload.sessions_count,
        session_interval=payload.session_interval, interventions=payload.interventions,
        external_referral=payload.external_referral, review_date=review,
        remarks=payload.remarks, recorded_by=actor.id,
    )
    db.add(t)
    db.commit()
    record_audit(db, action="treatment_plan.created", actor_user_id=actor.id,
                 entity_type="treatment_plan", entity_id=str(t.id),
                 detail={"counselor_id": str(c.id), "version": t.version_no})
    return _plan_out(db, t)


@router.patch("/treatment-plans/{plan_id}")
def update_plan(plan_id: uuid.UUID, payload: PlanCreate, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    t = db.get(TreatmentPlan, plan_id)
    if t is None:
        raise HTTPException(status_code=404, detail="طرح درمان یافت نشد")
    case = _get_case_or_404(db, t.case_id)
    _write_counselor(db, actor, case)
    expected = payload.goals is not None  # placeholder؛ نسخه‌بندی با فیلد زیر
    if payload.review_date:
        try:
            t.review_date = date.fromisoformat(payload.review_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="تاریخ بازبینی نامعتبر است")
    t.goals = payload.goals
    t.approach = payload.approach
    t.approach_note = payload.approach_note
    t.protocol_name = payload.protocol_name
    t.sessions_count = payload.sessions_count
    t.session_interval = payload.session_interval
    t.interventions = payload.interventions
    t.external_referral = payload.external_referral
    t.remarks = payload.remarks
    t.row_version += 1
    db.commit()
    record_audit(db, action="treatment_plan.updated", actor_user_id=actor.id,
                 entity_type="treatment_plan", entity_id=str(t.id))
    return _plan_out(db, t)
