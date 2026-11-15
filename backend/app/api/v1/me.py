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


# ---------------------------------------------------------------------------
# فاز ۸۷ — آزمون‌های سازمانی من: کاربرِ متقاضی (عضو برنامه‌های سازمانش)
# فهرست آزمون‌های تعیین‌شدهٔ برنامه‌های فعال سازمان خودش را می‌بیند، وضعیت
# انجام هرکدام (نمره/تفسیر آخرین تلاش) و می‌تواند مستقیم آزمون را بگیرد.
# ---------------------------------------------------------------------------
@router.get("/org-exams")
def my_org_exams(db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    from app.models.org_program import OrgProgram, OrgProgramMember, OrgProgramTest
    from app.models.psych_test import PsychAttempt, PsychTest

    org_id = actor.organization_id
    if org_id is None:
        return {"items": []}

    member_rows = db.scalars(
        select(OrgProgramMember).where(OrgProgramMember.user_id == actor.id)
    ).all()
    member_program_ids = {m.program_id for m in member_rows}

    programs = db.scalars(
        select(OrgProgram).where(
            OrgProgram.organization_id == org_id,
            OrgProgram.status == "active",
        ).order_by(OrgProgram.created_at.desc())
    ).all()
    # کاربرِ عضو همهٔ برنامه‌های فعال سازمانش را می‌بیند؛ اگر عضویت صریح ندارد،
    # برنامه به‌عنوان «در انتظار عضویت» نمایش داده نمی‌شود (فقط عضوها).
    items: list[dict] = []
    for p in programs:
        if p.id not in member_program_ids:
            continue
        tests = db.execute(
            select(OrgProgramTest, PsychTest)
            .join(PsychTest, OrgProgramTest.test_id == PsychTest.id)
            .where(OrgProgramTest.program_id == p.id)
            .order_by(OrgProgramTest.sort_order)
        ).all()
        test_items = []
        for pt, t in tests:
            last = db.scalar(
                select(PsychAttempt)
                .where(PsychAttempt.user_id == actor.id, PsychAttempt.test_id == t.id)
                .order_by(PsychAttempt.created_at.desc())
            )
            test_items.append({
                "test_id": str(t.id),
                "test_slug": t.slug,
                "title": pt.display_title or t.title,
                "is_required": pt.is_required,
                "done": last is not None,
                "score": int(last.score or 0) if last else None,
                "interpretation_label": last.interpretation_label if last else None,
                "completed_at": last.created_at.isoformat() if last else None,
            })
        items.append({
            "id": str(p.id),
            "title": p.title,
            "due_date": p.due_date.isoformat() if p.due_date else None,
            "tests": test_items,
        })
    return {"items": items}
