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
        # فاز ۴۸ - روند کارها برای نمودارهای داشبورد
        "trends": {"cases": [], "sessions": [], "appointments": []},
        "psych_attempts": 0,
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

    # فاز ۴۸ - روند روزانه پرونده/جلسه/نوبت + تعداد اجرای آزمون‌های روان‌شناسی
    from app.models.psych_test import PsychAttempt
    day_start = datetime.now(timezone.utc) - timedelta(days=days)

    case_trend_rows = select(func.date(Case.created_at), func.count()).where(Case.created_at >= day_start)
    if counselor_filter is not None:
        case_trend_rows = case_trend_rows.where(Case.primary_counselor_id == counselor_filter)
    case_trend = {r[0]: int(r[1]) for r in db.execute(
        case_trend_rows.group_by(func.date(Case.created_at))
    ).all()}
    session_trend = {r[0]: int(r[1]) for r in db.execute(
        select(func.date(SessionModel.occurred_at), func.count())
        .where(SessionModel.occurred_at >= day_start)
        .group_by(func.date(SessionModel.occurred_at))
    ).all()}
    appt_trend = {r[0]: int(r[1]) for r in db.execute(
        select(func.date(Appointment.scheduled_at), func.count())
        .where(Appointment.scheduled_at >= day_start)
        .group_by(func.date(Appointment.scheduled_at))
    ).all()}
    if counselor_filter is not None:
        session_trend = {r[0]: int(r[1]) for r in db.execute(
            select(func.date(SessionModel.occurred_at), func.count())
            .where(SessionModel.occurred_at >= day_start, SessionModel.counselor_id == counselor_filter)
            .group_by(func.date(SessionModel.occurred_at))
        ).all()}
        appt_trend = {r[0]: int(r[1]) for r in db.execute(
            select(func.date(Appointment.scheduled_at), func.count())
            .where(Appointment.scheduled_at >= day_start, Appointment.counselor_id == counselor_filter)
            .group_by(func.date(Appointment.scheduled_at))
        ).all()}

    now = datetime.now(timezone.utc)

    def _series(src: dict, key: str = "count") -> list[dict]:
        out = []
        for i in range(days):
            d = (now - timedelta(days=days - 1 - i)).date()
            k = d.isoformat()
            out.append({"date": k, key: int(src.get(d, src.get(k, 0)))})
        return out

    psych_attempts_total = int(db.scalar(
        select(func.count()).select_from(PsychAttempt).where(PsychAttempt.created_at >= day_start)
    ) or 0)

    out = _empty_summary(days)
    out["view"] = "staff" if is_staff else "self"
    out["cases_by_status"] = cases_by_status
    out["appointments_by_status"] = appts_by_status
    out["sessions_count"] = sessions_count
    out["assessments_pending_review"] = pending
    out["trends"] = {
        "cases": _series(case_trend),
        "sessions": _series(session_trend),
        "appointments": _series(appt_trend),
    }
    out["psych_attempts"] = psych_attempts_total

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

    # ---- فروش (B24 × B10؛ پس از تصمیم D02) — خالص پس از استرداد (فاز ۳۰ B20) ----
    from app.models.payment import Order, OrderStatus, Payment
    from app.models.payment import PaymentStatus as PayStatus
    paid_orders_window = int(db.scalar(
        select(func.count()).select_from(Order)
        .where(Order.status == OrderStatus.PAID, Order.created_at >= since)) or 0)
    paid_amount_window = float(db.scalar(
        select(func.coalesce(func.sum(Order.payable_amount - Order.refunded_amount), 0))
        .where(Order.status == OrderStatus.PAID, Order.created_at >= since)) or 0)
    refunded_amount_window = float(db.scalar(
        select(func.coalesce(func.sum(Order.refunded_amount), 0))
        .where(Order.status == OrderStatus.PAID, Order.created_at >= since)) or 0)
    pending_orders = int(db.scalar(
        select(func.count()).select_from(Order)
        .where(Order.status == OrderStatus.PENDING)) or 0)
    sales_trend_rows = db.execute(
        select(func.date(Payment.paid_at), func.sum(Payment.amount))
        .where(Payment.status == PayStatus.SUCCESS, Payment.paid_at >= day_start)
        .group_by(func.date(Payment.paid_at))
    ).all()
    sales_trend = {r[0]: float(r[1] or 0) for r in sales_trend_rows}

    # ---- مالی (B24 × B22): فروش گزارش با داده مالی تطبیق کند ----
    finance_block: dict = {}
    try:
        from app.services.accounting import reconciliation as acc_reconciliation
        recon = acc_reconciliation(db)
        finance_block = {
            "ledger_balanced": recon["ledger"]["is_balanced"],
            "ledger_total_debit": recon["ledger"]["total_debit"],
            "ledger_total_credit": recon["ledger"]["total_credit"],
            "uncovered_events": (
                recon["events"]["payments"]["uncovered"]
                + recon["events"]["refunds"]["uncovered"]
                + recon["events"]["wallet_adjustments"]["uncovered"]
            ),
            "sales_reconciled": recon["sales_reconciliation"]["reconciled"],
            "sales_report_amount": recon["sales_reconciliation"]["sales_report_amount"],
            "journal_revenue_amount": recon["sales_reconciliation"]["journal_revenue_amount"],
        }
    except Exception:  # سند هرگز داشبورد را نمی‌شکند
        finance_block = {}

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
    # فاز ۴۸ - روند جلسات انجام‌شده و اجرای آزمون‌ها برای داشبورد مدیر
    session_trend = {r[0]: int(r[1]) for r in db.execute(
        select(func.date(SessionModel.occurred_at), func.count())
        .where(SessionModel.occurred_at >= day_start)
        .group_by(func.date(SessionModel.occurred_at))
    ).all()}

    def _series(src: dict) -> list[dict]:
        out = []
        for i in range(days):
            d = (now - timedelta(days=days - 1 - i)).date()
            key = d.isoformat()
            out.append({"date": key, "count": int(src.get(d, src.get(key, 0)))})
        return out

    def _amount_series(src: dict) -> list[dict]:
        out = []
        for i in range(days):
            d = (now - timedelta(days=days - 1 - i)).date()
            key = d.isoformat()
            out.append({"date": key, "amount": float(src.get(d, src.get(key, 0)))})
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
            "sales_paid_orders": paid_orders_window,
            "sales_paid_amount": paid_amount_window,
            "sales_refunded_amount": refunded_amount_window,
            "sales_pending_orders": pending_orders,
            "finance": finance_block,
            "sessions_count": int(db.scalar(
                select(func.count()).select_from(SessionModel).where(SessionModel.occurred_at >= since)) or 0),
        },
        "trends": {
            "cases": _series(case_trend),
            "bookings": _series(consult_trend),
            "sessions": _series(session_trend),
            "sales": _amount_series(sales_trend),
        },
        "counselor_workload": workload,
    }


@router.get("/audit-events")
def list_audit_events(
    page: int = Query(default=1, ge=1, le=1_000_000),
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


# ---------------------------------------------------------------------------
# فاز ۷۶ (v0.59.0) - گزارش‌ساز و داشبوردساز
#
# موتور تجمیع عمومی: هر «مجموعه‌داده» (dataset) روی یک مدل اصلی سوار است و
# گروه‌بندی روی ابعاد مشخص (وضعیت/مشاور/روز/ماه/...) با سنجهٔ تعداد یا مبلغ
# را پشتیبانی می‌کند. همهٔ نقاط پایانی GET هستند تا با ماتریس دسترسی منو
# (سطح دیدن/خواندن) هم‌راستا بمانند؛ خروجی CSV با BOM برای Excel فارسی.
# ---------------------------------------------------------------------------

from sqlalchemy import String as SAString, cast as sa_cast  # noqa: E402

from app.models.payment import Order, Payment  # noqa: E402
from app.models.psych_test import PsychAttempt  # noqa: E402
from app.models.reviews import CounselorReview  # noqa: E402

REPORT_STAFF_ROLES = STAFF_ROLES + ("DPO",)

_STATUS_LABELS: dict[str, str] = {
    # نوبت
    "scheduled": "برنامه‌ریزی‌شده", "done": "انجام‌شده", "cancelled": "لغوشده", "no_show": "عدم حضور",
    # پرونده
    "new": "جدید", "awaiting_assignment": "در انتظار تخصیص", "active": "فعال",
    "suspended": "معلق", "closed": "بسته", "archived": "بایگانی",
    # درخواست مشاوره
    "in_review": "در حال بررسی", "converted": "تبدیل به پرونده",
    # سفارش و پرداخت
    "pending": "در انتظار پرداخت", "paid": "پرداخت‌شده", "failed": "ناموفق",
    "initiated": "آغازشده", "success": "موفق",
    # ارزیابی
    "draft": "پیش‌نویس", "finalized": "نهایی", "pending_review": "در انتظار بررسی",
    "returned": "برگشت‌خورده", "approved": "تأییدشده",
    # کاربر
    "active": "فعال", "disabled": "غیرفعال",
}
_KIND_LABELS: dict[str, str] = {
    "service": "خدمت مشاوره", "topup": "شارژ کیف پول", "course": "دوره آموزشی", "exam": "آزمون",
}
_GATEWAY_LABELS: dict[str, str] = {"sandbox": "درگاه شبیه‌ساز", "zarinpal": "زرین‌پال", "wallet": "کیف پول"}
_PRIORITY_LABELS: dict[str, str] = {"low": "کم", "normal": "معمولی", "high": "بالا", "urgent": "فوری"}
_RATING_LABELS: dict[str, str] = {str(i): f"امتیاز {i} از ۵" for i in range(1, 6)}

_DAY_LABEL = "روز (تقویم میلادی)"
_MONTH_LABEL = "ماه"

REPORT_DATASETS: dict[str, dict] = {
    "appointments": {
        "title": "نوبت‌ها",
        "model": Appointment,
        "date_field": Appointment.scheduled_at,
        "dims": ["status", "counselor", "day", "month"],
        "metrics": ["count", "amount"],
        "amount_field": Appointment.price_amount,
        "filters": ["status", "counselor_id"],
        "labels": {"status": _STATUS_LABELS},
    },
    "sessions": {
        "title": "جلسات درمان",
        "model": SessionModel,
        "date_field": SessionModel.occurred_at,
        "dims": ["counselor", "day", "month"],
        "metrics": ["count"],
        "filters": ["counselor_id"],
        "labels": {},
    },
    "cases": {
        "title": "پرونده‌ها",
        "model": Case,
        "date_field": Case.created_at,
        "dims": ["status", "priority", "counselor", "day", "month"],
        "metrics": ["count"],
        "filters": ["status", "counselor_id"],
        "labels": {"status": _STATUS_LABELS, "priority": _PRIORITY_LABELS},
    },
    "consultations": {
        "title": "درخواست‌های مشاوره (سایت)",
        "model": ConsultationRequest,
        "date_field": ConsultationRequest.created_at,
        "dims": ["status", "day", "month"],
        "metrics": ["count"],
        "filters": ["status"],
        "labels": {"status": _STATUS_LABELS},
    },
    "orders": {
        "title": "سفارش‌ها (فروش)",
        "model": Order,
        "date_field": Order.created_at,
        "dims": ["status", "kind", "day", "month"],
        "metrics": ["count", "amount"],
        "amount_field": Order.payable_amount,
        "filters": ["status"],
        "labels": {"status": _STATUS_LABELS, "kind": _KIND_LABELS},
    },
    "payments": {
        "title": "پرداخت‌ها (درگاه‌ها)",
        "model": Payment,
        "date_field": Payment.paid_at,
        "date_nullable": True,
        "dims": ["status", "gateway", "day", "month"],
        "metrics": ["count", "amount"],
        "amount_field": Payment.amount,
        "filters": ["status"],
        "labels": {"status": _STATUS_LABELS, "gateway": _GATEWAY_LABELS},
    },
    "psych_attempts": {
        "title": "آزمون‌های روان‌شناسی",
        "model": PsychAttempt,
        "date_field": PsychAttempt.created_at,
        "dims": ["test", "day", "month"],
        "metrics": ["count", "score_avg"],
        "filters": ["test_id"],
        "labels": {},
    },
    "assessments": {
        "title": "ارزیابی‌های بالینی",
        "model": Assessment,
        "date_field": Assessment.created_at,
        "dims": ["status", "day", "month"],
        "metrics": ["count"],
        "filters": ["status"],
        "labels": {"status": _STATUS_LABELS},
    },
    "reviews": {
        "title": "نظرات مشاوران (سایت)",
        "model": CounselorReview,
        "date_field": CounselorReview.created_at,
        "dims": ["rating", "counselor", "day", "month"],
        "metrics": ["count"],
        "filters": ["counselor_id"],
        "labels": {"rating": _RATING_LABELS},
    },
}

_DIM_TITLES = {
    "status": "وضعیت", "counselor": "مشاور", "priority": "اولویت", "kind": "نوع سفارش",
    "gateway": "درگاه پرداخت", "rating": "امتیاز", "test": "آزمون",
    "day": _DAY_LABEL, "month": _MONTH_LABEL,
}
_METRIC_TITLES = {"count": "تعداد", "amount": "مبلغ (ریال)", "score_avg": "میانگین نمره"}


def _month_bucket(field):
    """باکس ماهانه قابل‌حمل (PostgreSQL/SQLite): substr(CAST(date(col) AS varchar),1,7)."""
    return func.substr(sa_cast(func.date(field), SAString), 1, 7)


def _resolve_names(db: Session, kind: str, keys: list[str]) -> dict[str, str]:
    """نام انسانی برای ابعاد شناسه‌دار (مشاور/آزمون)."""
    out: dict[str, str] = {}
    if kind == "counselor":
        ids = [uuid.UUID(k) for k in keys if k]
        if not ids:
            return out
        rows = db.execute(
            select(Counselor.id, Counselor.first_name, Counselor.last_name).where(Counselor.id.in_(ids))
        ).all()
        for cid, fn, ln in rows:
            out[str(cid)] = f"{fn or ''} {ln or ''}".strip() or str(cid)[:8]
    elif kind == "test":
        from app.models.psych_test import PsychTest
        ids = [uuid.UUID(k) for k in keys if k]
        if not ids:
            return out
        rows = db.execute(select(PsychTest.id, PsychTest.title).where(PsychTest.id.in_(ids))).all()
        for tid, title in rows:
            out[str(tid)] = title or str(tid)[:8]
    return out


def _require_report_access(actor) -> None:
    if not (_roles(actor) & set(REPORT_STAFF_ROLES)):
        raise HTTPException(status_code=403, detail="دسترسی به گزارش‌ساز مجاز نیست")


@router.get("/reports/datasets")
def report_datasets(actor=Depends(get_current_user)) -> dict:
    """فهرست مجموعه‌داده‌های گزارش‌ساز + ابعاد/سنجه‌های هرکدام (برای فرم‌ساز پنل)."""
    _require_report_access(actor)
    items = []
    for key, ds in REPORT_DATASETS.items():
        items.append({
            "key": key,
            "title": ds["title"],
            "dims": [{"key": d, "title": _DIM_TITLES.get(d, d)} for d in ds["dims"]],
            "metrics": [{"key": m, "title": _METRIC_TITLES.get(m, m)} for m in ds["metrics"]],
            "filters": ds["filters"],
        })
    return {"items": items}


def _run_report(
    db: Session,
    dataset: str,
    group_by: str,
    metric: str = "count",
    days: int = 30,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    counselor_id: str | None = None,
    test_id: str | None = None,
    limit: int = 200,
) -> dict:
    ds = REPORT_DATASETS.get(dataset)
    if ds is None:
        raise HTTPException(status_code=404, detail="مجموعه‌دادهٔ گزارش یافت نشد")
    if group_by not in ds["dims"]:
        raise HTTPException(status_code=422, detail=f"بعد «{group_by}» برای این مجموعه‌داده مجاز نیست")
    if metric not in ds["metrics"]:
        raise HTTPException(status_code=422, detail=f"سنجهٔ «{metric}» برای این مجموعه‌داده مجاز نیست")

    model = ds["model"]
    date_field = ds["date_field"]
    conds = []
    until = None
    if date_from or date_to:
        try:
            if date_from:
                frm = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
                conds.append(date_field >= frm)
            if date_to:
                until = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
                conds.append(date_field <= until)
        except ValueError:
            raise HTTPException(status_code=422, detail="قالب تاریخ نامعتبر است (نمونه: 2025-01-31)")
    else:
        frm = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 3650)))
        conds.append(date_field >= frm)

    # زمانی که ستون تاریخ nullable است (مثل paid_at) ردیف‌های خالی از فیلتر روز/ماه کنار گذاشته می‌شوند
    if ds.get("date_nullable"):
        conds.append(date_field.isnot(None))

    if status and "status" in ds["filters"]:
        conds.append(model.status.in_([s.strip() for s in status.split(",") if s.strip()]))
    if counselor_id and "counselor_id" in ds["filters"]:
        try:
            conds.append(_counselor_col(ds) == uuid.UUID(counselor_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="شناسهٔ مشاور نامعتبر است")
    if test_id and "test_id" in ds["filters"]:
        try:
            conds.append(model.test_id == uuid.UUID(test_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="شناسهٔ آزمون نامعتبر است")

    # عبارت بعد گروه‌بندی
    if group_by == "status":
        dim = model.status
        label_map = ds["labels"].get("status", {})
        resolver = None
    elif group_by == "priority":
        dim = model.priority
        label_map = ds["labels"].get("priority", {})
        resolver = None
    elif group_by == "kind":
        dim = model.kind
        label_map = ds["labels"].get("kind", {})
        resolver = None
    elif group_by == "gateway":
        dim = model.gateway
        label_map = ds["labels"].get("gateway", {})
        resolver = None
    elif group_by == "rating":
        dim = sa_cast(model.rating, SAString)
        label_map = ds["labels"].get("rating", {})
        resolver = None
    elif group_by == "counselor":
        dim = _counselor_col(ds)
        label_map = {}
        resolver = "counselor"
    elif group_by == "test":
        dim = model.test_id
        label_map = {}
        resolver = "test"
    elif group_by == "day":
        dim = func.date(date_field)
        label_map = {}
        resolver = None
    else:  # month
        dim = _month_bucket(date_field)
        label_map = {}
        resolver = None

    if metric == "count":
        agg = func.count()
    elif metric == "amount":
        agg = func.coalesce(func.sum(ds["amount_field"]), 0)
    else:  # score_avg
        agg = func.avg(model.score)

    rows = db.execute(
        select(dim.label("k"), agg.label("v"))
        .where(*conds)
        .group_by(dim)
        .order_by(func.count() if metric == "count" else agg)
        .limit(max(1, min(limit, 500)))
    ).all()
    rows = list(rows)
    # نزولی‌سازی در پایتون (ترتیب ارزش نزولی برای نمودارها)
    rows.sort(key=lambda r: float(r.v or 0), reverse=True)

    name_map = _resolve_names(db, resolver, [str(r.k) for r in rows]) if resolver else {}

    items = []
    for r in rows:
        k = r.k
        key = str(k) if k is not None else "—"
        if resolver:
            label = name_map.get(key) or key[:8]
        elif key in label_map:
            label = label_map[key]
        elif key == "—":
            label = "نامشخص/بدون مقدار"
        else:
            label = key
        value = float(r.v or 0)
        items.append({
            "key": key,
            "label": label,
            "value": round(value, 1) if metric == "score_avg" else int(value),
        })
    total = sum(int(i["value"]) for i in items) if metric != "score_avg" else (
        round(sum(float(i["value"]) for i in items) / len(items), 1) if items else 0
    )
    return {
        "dataset": dataset,
        "title": ds["title"],
        "group_by": group_by,
        "group_by_title": _DIM_TITLES.get(group_by, group_by),
        "metric": metric,
        "metric_title": _METRIC_TITLES.get(metric, metric),
        "rows": items,
        "total": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _counselor_col(ds: dict):
    """ستون شناسهٔ مشاور برای هر مجموعه‌داده."""
    model = ds["model"]
    if hasattr(model, "counselor_id"):
        return model.counselor_id
    if hasattr(model, "primary_counselor_id"):
        return model.primary_counselor_id
    raise HTTPException(status_code=422, detail="این مجموعه‌داده فیلتر مشاور ندارد")


@router.get("/reports/query")
def report_query(
    dataset: str,
    group_by: str = "status",
    metric: str = "count",
    days: int = Query(default=30, ge=1, le=3650),
    date_from: str | None = Query(default=None, max_length=10),
    date_to: str | None = Query(default=None, max_length=10),
    status: str | None = Query(default=None, max_length=400),
    counselor_id: str | None = Query(default=None, max_length=64),
    test_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    """اجرای یک گزارش تجمیعی دلخواه (گزارش‌ساز - فاز ۷۶)."""
    _require_report_access(actor)
    return _run_report(db, dataset, group_by, metric, days, date_from, date_to,
                       status, counselor_id, test_id, limit)


@router.get("/reports/query/export")
def report_query_export(
    dataset: str,
    group_by: str = "status",
    metric: str = "count",
    days: int = Query(default=30, ge=1, le=3650),
    date_from: str | None = Query(default=None, max_length=10),
    date_to: str | None = Query(default=None, max_length=10),
    status: str | None = Query(default=None, max_length=400),
    counselor_id: str | None = Query(default=None, max_length=64),
    test_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> Response:
    """خروجی CSV همان گزارش — سازگار با Excel فارسی (BOM + جداسازی کاما)."""
    _require_report_access(actor)
    data = _run_report(db, dataset, group_by, metric, days, date_from, date_to,
                       status, counselor_id, test_id, limit)
    import csv as _csv
    import io as _io

    buf = _io.StringIO()
    buf.write("\ufeff")  # BOM برای نمایش درست فارسی در Excel
    w = _csv.writer(buf)
    w.writerow(["مجموعه‌داده", data["title"]])
    w.writerow(["گروه‌بندی", data["group_by_title"]])
    w.writerow(["سنجه", data["metric_title"]])
    w.writerow(["جمع", data["total"]])
    w.writerow([])
    w.writerow(["ردیف", "برچسب", "مقدار"])
    for i, row in enumerate(data["rows"], 1):
        w.writerow([i, row["label"], row["value"]])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="rosepsy-report.csv"'},
    )
