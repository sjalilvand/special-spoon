from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.case import Case
from app.models.people import Applicant, Counselor, OrganizationUnit, ServiceLocation
from app.models.recommendation import Recommendation

router = APIRouter(prefix="/me", tags=["me"])


def _linked_applicant(db: Session, actor) -> Applicant | None:
    if "APPLICANT" not in {r.code for r in actor.roles}:
        return None
    return db.scalar(select(Applicant).where(Applicant.user_id == actor.id))


def _require_linked(db: Session, actor) -> Applicant:
    a = _linked_applicant(db, actor)
    if a is None:
        raise HTTPException(status_code=404, detail="حساب شما به پروفایل متقاضی متصل نیست؛ از پذیرش پیگیری کنید")
    return a


@router.get("/profile")
def my_profile(db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    a = _require_linked(db, actor)
    unit = db.get(OrganizationUnit, a.unit_id) if a.unit_id else None
    loc = db.get(ServiceLocation, a.service_location_id) if a.service_location_id else None
    return {
        "first_name": a.first_name,
        "last_name": a.last_name,
        "national_id": a.national_id,
        "employee_code": a.employee_code,
        "mobile": a.mobile,
        "unit_title": unit.title if unit else None,
        "service_location_title": loc.title if loc else None,
    }


@router.get("/cases")
def my_cases(db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    """بند ۹.۳: وضعیت کلی پرونده بدون نمایش تشخیص یا محتوای بالینی."""
    a = _require_linked(db, actor)
    rows = db.execute(
        select(Case, Counselor)
        .outerjoin(Counselor, Case.primary_counselor_id == Counselor.id)
        .where(Case.applicant_id == a.id)
        .order_by(Case.created_at.desc())
    ).all()
    items = [{
        "id": str(c.id),
        "case_number": c.case_number,
        "status": c.status,
        "acceptance_date": c.acceptance_date.isoformat(),
        "counselor_name": (f"{cc.first_name} {cc.last_name}" if cc else None),
        "consent_status": c.consent_status,
        "service_type": c.service_type,
    } for c, cc in rows]
    return {"items": items}


@router.get("/appointments")
def my_appointments(db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    a = _require_linked(db, actor)
    case_ids = db.scalars(select(Case.id).where(Case.applicant_id == a.id)).all()
    if not case_ids:
        return {"items": []}
    rows = db.execute(
        select(Appointment, Case)
        .join(Case, Appointment.case_id == Case.id)
        .where(Appointment.case_id.in_(case_ids))
        .order_by(Appointment.scheduled_at.desc())
        .limit(30)
    ).all()
    items = [{
        "id": str(ap.id),
        "case_number": c.case_number,
        "scheduled_at": ap.scheduled_at.isoformat(),
        "status": ap.status,
        "location": ap.location,
    } for ap, c in rows]
    return {"items": items}


@router.get("/recommendations")
def my_recommendations(db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    """فقط توصیه‌های صریحاً منتشرشده (بند ۹.۳)."""
    a = _require_linked(db, actor)
    case_ids = db.scalars(select(Case.id).where(Case.applicant_id == a.id)).all()
    if not case_ids:
        return {"items": []}
    rows = db.execute(
        select(Recommendation, Case)
        .join(Case, Recommendation.case_id == Case.id)
        .where(Recommendation.case_id.in_(case_ids), Recommendation.is_published.is_(True))
        .order_by(Recommendation.published_at.desc())
        .limit(30)
    ).all()
    items = [{
        "id": str(r.id),
        "case_number": c.case_number,
        "content": r.content,
        "published_at": r.published_at.isoformat() if r.published_at else None,
    } for r, c in rows]
    return {"items": items}
