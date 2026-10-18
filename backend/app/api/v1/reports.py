import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.services.case_access import counselor_can_access
from app.models.appointment import Appointment, Session as SessionModel
from app.models.assessment import Assessment, AssessmentStatus, ReviewAction
from app.models.audit import AuditEvent
from app.models.case import Case, CaseStatus
from app.models.consultation import ConsultationRequest
from app.models.import_job import ImportJob
from app.models.people import Applicant, Counselor
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(tags=["reports"])

STAFF_ROLES = ("ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "SYSTEM_ADMIN")


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def _clinical_access(db: Session, actor, case: Case) -> None:
    roles = _roles(actor)
    if "TECHNICAL_SUPERVISOR" in roles:
        return
    if "COUNSELOR" in roles:
        c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if c is not None and counselor_can_access(db, c.id, case):
            return
    raise HTTPException(status_code=404, detail="پرونده یافت نشد")


@router.post("/assessments/{assessment_id}/print", status_code=204)
def audit_print(assessment_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> Response:
    """ثبت رخداد چاپ فرم بالینی (بند ۱۴ سند)."""
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="ارزیابی یافت نشد")
    case = db.get(Case, a.case_id)
    _clinical_access(db, actor, case)
    record_audit(db, action="assessment.printed", actor_user_id=actor.id,
                 entity_type="assessment", entity_id=str(a.id))
    return Response(status_code=204)


def _empty_summary(days: int) -> dict:
    return {
        "view": "self", "days": days,
        "cases_by_status": {}, "appointments_by_status": {},
        "sessions_count": 0, "assessments_pending_review": 0,
        "applicants_total": 0, "users_active": 0, "counselors_active": 0,
        "counselor_workload": [], "recent_imports": [],
    }


@router.get("/reports/summary")
def report_summary(
    days: int = Query(default=30, ge=1, le=365),
    counselor_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    """داشبورد بند ۱۵ - تجمیعی و بی‌نام؛ بدون فهرست تشخیص افراد."""
    roles = _roles(actor)
    is_staff = bool(roles & set(STAFF_ROLES))
    counselor_self = None
    if not is_staff:
        if "COUNSELOR" not in roles:
            raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")
        counselor_self = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if counselor_self is None:
            return _empty_summary(days)

    since = datetime.now(timezone.utc) - timedelta(days=days)
    counselor_filter = counselor_self.id if counselor_self is not None else counselor_id

    q = select(Case.status, func.count()).group_by(Case.status)
    if counselor_filter is not None:
        q = q.where(Case.primary_counselor_id == counselor_filter)
    cases_by_status = {s: int(n) for s, n in db.execute(q).all()}

    q = select(Appointment.status, func.count()).group_by(Appointment.status).where(Appointment.scheduled_at >= since)
    if counselor_filter is not None:
        q = q.where(Appointment.counselor_id == counselor_filter)
    appts_by_status = {s: int(n) for s, n in db.execute(q).all()}

    q = select(func.count()).select_from(SessionModel).where(SessionModel.occurred_at >= since)
    if counselor_filter is not None:
        q = q.where(SessionModel.counselor_id == counselor_filter)
    sessions_count = int(db.scalar(q) or 0)

    q = select(func.count()).select_from(Assessment).where(Assessment.status == AssessmentStatus.PENDING_REVIEW)
    if counselor_filter is not None:
        q = q.where(Assessment.case_id.in_(select(Case.id).where(Case.primary_counselor_id == counselor_filter)))
    pending = int(db.scalar(q) or 0)

    out = _empty_summary(days)
    out["view"] = "staff" if is_staff else "self"
    out["cases_by_status"] = cases_by_status
    out["appointments_by_status"] = appts_by_status
    out["sessions_count"] = sessions_count
    out["assessments_pending_review"] = pending

    if is_staff:
        out["applicants_total"] = int(db.scalar(select(func.count()).select_from(Applicant)) or 0)
        out["users_active"] = int(db.scalar(select(func.count()).select_from(User).where(User.status == "active")) or 0)
        out["counselors_active"] = int(db.scalar(select(func.count()).select_from(Counselor).where(Counselor.status == "active")) or 0)

        cq = select(Counselor).where(Counselor.status == "active")
        if counselor_filter is not None:
            cq = cq.where(Counselor.id == counselor_filter)
        counselors = db.scalars(cq.order_by(Counselor.last_name)).all()
        active_counts = dict(db.execute(
            select(Case.primary_counselor_id, func.count())
            .where(Case.status == CaseStatus.ACTIVE)
            .group_by(Case.primary_counselor_id)
        ).all())
        sess_counts = dict(db.execute(
            select(SessionModel.counselor_id, func.count())
            .where(SessionModel.occurred_at >= since)
            .group_by(SessionModel.counselor_id)
        ).all())
        out["counselor_workload"] = [{
            "counselor_id": str(c.id),
            "counselor_name": f"{c.first_name} {c.last_name}",
            "active_cases": int(active_counts.get(c.id, 0)),
            "sessions_count": int(sess_counts.get(c.id, 0)),
        } for c in counselors]

        jobs = db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(5)).all()
        out["recent_imports"] = [{
            "import_type": j.import_type, "status": j.status,
            "created_rows": j.created_rows, "error_rows": j.error_rows,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        } for j in jobs]
    else:
        out["counselor_workload"] = [{
            "counselor_id": str(counselor_self.id),
            "counselor_name": f"{counselor_self.first_name} {counselor_self.last_name}",
            "active_cases": cases_by_status.get("active", 0),
            "sessions_count": sessions_count,
        }]
    return out


@router.get("/reports/admin-dashboard")
def admin_dashboard(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    """B24 سند جامع - داشبورد مدیر: KPI شفاف، روند پرونده/رزرو، عملکرد مشاوران.

    تجمیعی و بی‌نام (بند ۱۵): هیچ محتوای بالینی فردی در خروجی نیست.
    """
    roles = _roles(actor)
    if not roles & {"ORG_MANAGER", "SYSTEM_ADMIN"}:
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    day_start = now - timedelta(days=days)

    # ---- KPIها ----
    cases_by_status = {s: int(n) for s, n in db.execute(
        select(Case.status, func.count()).group_by(Case.status)
    ).all()}

    approved_count = int(db.scalar(
        select(func.count()).select_from(Assessment).where(Assessment.status == AssessmentStatus.APPROVED)
    ) or 0)
    pending_review = int(db.scalar(
        select(func.count()).select_from(Assessment).where(Assessment.status == AssessmentStatus.PENDING_REVIEW)
    ) or 0)

    # میانگین زمان اولین بررسی (نهایی‌سازی → اولین تصمیم داوری) - KPI شفاف B24
    first_review = (
        select(ReviewAction.assessment_id, func.min(ReviewAction.created_at).label("first_at"))
        .group_by(ReviewAction.assessment_id)
        .subquery()
    )
    avg_review_hours = db.scalar(
        select(func.avg(func.extract("epoch", first_review.c.first_at - Assessment.finalized_at) / 3600.0))
        .select_from(Assessment)
        .join(first_review, Assessment.id == first_review.c.assessment_id)
        .where(Assessment.finalized_at.is_not(None), first_review.c.first_at >= since)
    )
    avg_review_hours = round(float(avg_review_hours), 1) if avg_review_hours is not None else None

    appts_window = select(func.count()).select_from(Appointment).where(Appointment.scheduled_at >= since)
    appts_total_w = int(db.scalar(appts_window) or 0)
    appts_done = int(db.scalar(
        select(func.count()).select_from(Appointment)
        .where(Appointment.scheduled_at >= since, Appointment.status == "done")) or 0)
    appts_cancelled = int(db.scalar(
        select(func.count()).select_from(Appointment)
        .where(Appointment.scheduled_at >= since, Appointment.status == "cancelled")) or 0)
    appts_no_show = int(db.scalar(
        select(func.count()).select_from(Appointment)
        .where(Appointment.scheduled_at >= since, Appointment.status == "no_show")) or 0)
    appts_upcoming_7d = int(db.scalar(
        select(func.count()).select_from(Appointment)
        .where(Appointment.scheduled_at >= now,
               Appointment.scheduled_at <= now + timedelta(days=7),
               Appointment.status == "scheduled")) or 0)

    consult_total = int(db.scalar(
        select(func.count()).select_from(ConsultationRequest).where(ConsultationRequest.created_at >= since)) or 0)
    consult_with_slot = int(db.scalar(
        select(func.count()).select_from(ConsultationRequest)
        .where(ConsultationRequest.created_at >= since,
               ConsultationRequest.preferred_start_at.is_not(None))) or 0)
    consult_by_status = {s: int(n) for s, n in db.execute(
        select(ConsultationRequest.status, func.count())
        .where(ConsultationRequest.created_at >= since)
        .group_by(ConsultationRequest.status)
    ).all()}

    from app.models.booking import SlotClaim, SlotClaimStatus
    active_holds = int(db.scalar(
        select(func.count()).select_from(SlotClaim)
        .where(SlotClaim.status == SlotClaimStatus.ACTIVE,
               SlotClaim.expires_at > now)) or 0)
    confirmed_holds = int(db.scalar(
        select(func.count()).select_from(SlotClaim)
        .where(SlotClaim.status == SlotClaimStatus.CONFIRMED,
               SlotClaim.created_at >= since)) or 0)

    # ---- روند روزانه (پرونده جدید / درخواست رزرو) ----
    case_trend = {r[0]: int(r[1]) for r in db.execute(
        select(func.date(Case.created_at), func.count())
        .where(Case.created_at >= day_start)
        .group_by(func.date(Case.created_at))
    ).all()}
    consult_trend = {r[0]: int(r[1]) for r in db.execute(
        select(func.date(ConsultationRequest.created_at), func.count())
        .where(ConsultationRequest.created_at >= day_start)
        .group_by(func.date(ConsultationRequest.created_at))
    ).all()}

    def _series(src: dict) -> list[dict]:
        out = []
        for i in range(days):
            d = (now - timedelta(days=days - 1 - i)).date()
            key = d.isoformat()
            out.append({"date": key, "count": int(src.get(d, src.get(key, 0)))})
        return out

    # ---- بار کاری مشاوران ----
    counselors = db.scalars(
        select(Counselor).where(Counselor.status == "active").order_by(Counselor.last_name)
    ).all()
    active_counts = dict(db.execute(
        select(Case.primary_counselor_id, func.count())
        .where(Case.status == CaseStatus.ACTIVE)
        .group_by(Case.primary_counselor_id)
    ).all())
    sess_counts = dict(db.execute(
        select(SessionModel.counselor_id, func.count())
        .where(SessionModel.occurred_at >= since)
        .group_by(SessionModel.counselor_id)
    ).all())
    workload = [{
        "counselor_id": str(c.id),
        "counselor_name": f"{c.first_name} {c.last_name}",
        "active_cases": int(active_counts.get(c.id, 0)),
        "sessions_count": int(sess_counts.get(c.id, 0)),
    } for c in counselors]

    return {
        "days": days,
        "generated_at": now.isoformat(),
        "kpis": {
            "applicants_total": int(db.scalar(select(func.count()).select_from(Applicant)) or 0),
            "users_active": int(db.scalar(select(func.count()).select_from(User).where(User.status == "active")) or 0),
            "counselors_active": int(db.scalar(select(func.count()).select_from(Counselor).where(Counselor.status == "active")) or 0),
            "cases_total": sum(cases_by_status.values()),
            "cases_by_status": cases_by_status,
            "assessments_pending_review": pending_review,
            "assessments_approved": approved_count,
            "avg_review_hours": avg_review_hours,
            "appointments_window": appts_total_w,
            "appointments_done": appts_done,
            "appointments_cancelled": appts_cancelled,
            "appointments_no_show": appts_no_show,
            "no_show_rate": round(100 * appts_no_show / appts_total_w, 1) if appts_total_w else 0.0,
            "appointments_upcoming_7d": appts_upcoming_7d,
            "consultations_total": consult_total,
            "consultations_with_slot": consult_with_slot,
            "consultations_by_status": consult_by_status,
            "booking_active_holds": active_holds,
            "booking_confirmed_holds": confirmed_holds,
            "sessions_count": int(db.scalar(
                select(func.count()).select_from(SessionModel).where(SessionModel.occurred_at >= since)) or 0),
        },
        "trends": {
            "cases": _series(case_trend),
            "bookings": _series(consult_trend),
        },
        "counselor_workload": workload,
    }


@router.get("/audit-events")
def list_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    """بند ۱۲ و ۳.۲: مدیر سامانه کامل؛ مدیر سازمان/مسئول فنی فقط رخدادهای خودشان."""
    roles = _roles(actor)
    if "SYSTEM_ADMIN" in roles:
        q = select(AuditEvent)
        include_detail = True
    elif roles & {"ORG_MANAGER", "TECHNICAL_SUPERVISOR"}:
        q = select(AuditEvent).where(AuditEvent.actor_user_id == actor.id)
        include_detail = False
    else:
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")

    total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = db.scalars(
        q.order_by(AuditEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for e in rows:
        actor_u = db.get(User, e.actor_user_id) if e.actor_user_id else None
        items.append({
            "id": str(e.id),
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "result": e.result,
            "actor_name": actor_u.display_name if actor_u else None,
            "ip": e.ip,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "detail": (e.detail if include_detail else None),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
