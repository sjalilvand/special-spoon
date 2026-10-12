"""ارجاع‌های پرونده (بند ۱۰.۱۰ و ۹.۱ سند v1.00) - فاز ۱۳"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.case import Case
from app.models.people import Counselor, ServiceLocation
from app.models.referral import Referral
from app.models.user import User
from app.services.audit import record_audit
from app.services.case_access import counselor_can_access

router = APIRouter(tags=["referrals"])


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
        raise HTTPException(status_code=403, detail="ثبت ارجاع فقط با نقش مشاور و تخصیص مجاز است")
    c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
    if c is None or not counselor_can_access(db, c.id, case):
        raise HTTPException(status_code=403, detail="این پرونده به شما تخصیص نیافته است")
    return c


def _get_case_or_404(db: Session, case_id) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    return case


class ReferralCreate(BaseModel):
    direction: str = Field(pattern="^(internal|cross_center|external)$")
    to_counselor_id: uuid.UUID | None = None
    to_service_location_id: uuid.UUID | None = None
    to_center_name: str | None = Field(default=None, max_length=300)
    reason: str = Field(min_length=3, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    referral_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


def _out(db: Session, r: Referral) -> dict:
    req = db.get(User, r.requested_by) if r.requested_by else None
    hnd = db.get(User, r.handled_by) if r.handled_by else None
    to_c = db.get(Counselor, r.to_counselor_id) if r.to_counselor_id else None
    to_sl = db.get(ServiceLocation, r.to_service_location_id) if r.to_service_location_id else None
    target = None
    if to_c is not None:
        target = f"مشاور: {to_c.first_name} {to_c.last_name}"
    elif to_sl is not None:
        target = f"مرکز: {to_sl.title}"
    elif r.to_center_name:
        target = f"خارجی: {r.to_center_name}"
    return {
        "id": str(r.id),
        "case_id": str(r.case_id),
        "direction": r.direction,
        "status": r.status,
        "target_label": target,
        "to_counselor_id": str(r.to_counselor_id) if r.to_counselor_id else None,
        "to_service_location_id": str(r.to_service_location_id) if r.to_service_location_id else None,
        "to_center_name": r.to_center_name,
        "reason": r.reason,
        "notes": r.notes,
        "outcome": r.outcome,
        "referral_date": r.referral_date.isoformat() if r.referral_date else None,
        "outcome_date": r.outcome_date.isoformat() if r.outcome_date else None,
        "requested_by_name": req.display_name if req else None,
        "handled_by_name": hnd.display_name if hnd else None,
        "row_version": r.row_version,
    }


DIRECTION_LABELS = {"internal": "داخلی", "cross_center": "بین‌مرکزی", "external": "خارجی"}


@router.get("/cases/{case_id}/referrals")
def list_referrals(case_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = _get_case_or_404(db, case_id)
    _view_access(db, actor, case)
    items = db.scalars(
        select(Referral).where(Referral.case_id == case.id).order_by(Referral.created_at.desc())
    ).all()
    return {"items": [_out(db, r) for r in items]}


@router.post("/cases/{case_id}/referrals", status_code=201)
def create_referral(case_id: uuid.UUID, payload: ReferralCreate, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = _get_case_or_404(db, case_id)
    c = _write_counselor(db, actor, case)

    to_counselor_id = None
    to_sl_id = None
    to_center_name = None

    if payload.direction == "internal":
        if payload.to_counselor_id is None:
            raise HTTPException(status_code=422, detail="برای ارجاع داخلی، انتخاب مشاور مقصد الزامی است")
        cc = db.get(Counselor, payload.to_counselor_id)
        if cc is None:
            raise HTTPException(status_code=422, detail="مشاور مقصد یافت نشد")
        to_counselor_id = cc.id
    elif payload.direction == "cross_center":
        if payload.to_service_location_id is None:
            raise HTTPException(status_code=422, detail="برای ارجاع بین‌مرکزی، انتخاب مرکز مقصد الزامی است")
        sl = db.get(ServiceLocation, payload.to_service_location_id)
        if sl is None:
            raise HTTPException(status_code=422, detail="مرکز مقصد یافت نشد")
        to_sl_id = sl.id
    else:
        if not (payload.to_center_name or "").strip():
            raise HTTPException(status_code=422, detail="برای ارجاع خارجی، نام مرکز مقصد الزامی است")
        to_center_name = payload.to_center_name.strip()

    referral_date = date.today()
    if payload.referral_date:
        try:
            referral_date = date.fromisoformat(payload.referral_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="تاریخ ارجاع نامعتبر است")

    r = Referral(
        case_id=case.id, direction=payload.direction, status="initiated",
        to_counselor_id=to_counselor_id, to_service_location_id=to_sl_id,
        to_center_name=to_center_name,
        reason=payload.reason.strip(), notes=payload.notes,
        referral_date=referral_date, requested_by=actor.id,
    )
    db.add(r)
    db.commit()
    record_audit(db, action="referral.created", actor_user_id=actor.id,
                 entity_type="referral", entity_id=str(r.id),
                 detail={"counselor_id": str(c.id), "direction": r.direction})
    return _out(db, r)


class ReferralUpdate(BaseModel):
    status: str = Field(pattern="^(initiated|accepted|completed|rejected|cancelled)$")
    outcome: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)


@router.patch("/referrals/{referral_id}")
def update_referral(referral_id: uuid.UUID, payload: ReferralUpdate, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    r = db.get(Referral, referral_id)
    if r is None:
        raise HTTPException(status_code=404, detail="ارجاع یافت نشد")
    case = db.get(Case, r.case_id)
    _view_access(db, actor, case)

    roles = _roles(actor)
    if not (roles & {"ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"}):
        _write_counselor(db, actor, case)

    if r.status in ("completed", "cancelled") and payload.status != r.status:
        raise HTTPException(status_code=409, detail="این ارجاع نهایی شده و قابل تغییر نیست")

    r.status = payload.status
    if payload.outcome is not None:
        r.outcome = payload.outcome
    if payload.notes is not None:
        r.notes = payload.notes
    if payload.status in ("completed", "rejected", "cancelled"):
        r.outcome_date = date.today()
    r.handled_by = actor.id
    r.row_version += 1
    db.commit()
    record_audit(db, action="referral.updated", actor_user_id=actor.id,
                 entity_type="referral", entity_id=str(r.id),
                 detail={"status": payload.status})
    return _out(db, r)


@router.get("/worklists/referrals")
def pending_referrals(db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    """کارتابل ارجاع‌های در انتظار پیگیری"""
    roles = _roles(actor)
    if not (roles & {"ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"}):
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")
    rows = db.execute(
        select(Referral, Case)
        .join(Case, Referral.case_id == Case.id)
        .where(Referral.status.in_(("initiated", "accepted")))
        .order_by(Referral.referral_date)
        .limit(50)
    ).all()
    items = []
    for r, c in rows:
        base = _out(db, r)
        base["case_number"] = c.case_number
        base["direction_label"] = DIRECTION_LABELS.get(r.direction, r.direction)
        items.append(base)
    return {"items": items}
