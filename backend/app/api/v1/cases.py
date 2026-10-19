import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.case import CASE_STATUSES, Case, CaseAssignment, CaseStatus, Consent
from app.models.consent import ConsentVersion
from app.models.people import Applicant, Counselor, ServiceLocation
from app.models.user import User
from app.schemas.case import (
    AssignmentCreate,
    CaseActionRequest,
    CaseCreate,
    CaseUpdate,
    ConsentCreate,
)
from app.services.audit import record_audit
from app.services.notifications import notify_roles
from app.services.case_access import counselor_can_access

router = APIRouter(prefix="/cases", tags=["cases"])

# ماتریس دسترسی بند ۳.۲ سند - مدیر سامانه عمداً در فهرست نیست
CASE_VIEW_ROLES = ("ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")
CASE_MANAGE_ROLES = ("ORG_MANAGER", "RECEPTION")
ASSIGN_ROLES = ("ORG_MANAGER", "TECHNICAL_SUPERVISOR")
REOPEN_ROLES = ("ORG_MANAGER",)


def generate_case_number(db: Session) -> str:
    """شماره پرونده از Sequence تراکنشی - بدون MAX+1 (بند ۶.۱ سند)"""
    seq = db.execute(text("SELECT nextval('case_number_seq')")).scalar_one()
    return f"RS-{date.today().year}-{int(seq):06d}"


def _case_out(db: Session, c: Case) -> dict:
    a = db.get(Applicant, c.applicant_id)
    counselor_name = None
    if c.primary_counselor_id:
        cc = db.get(Counselor, c.primary_counselor_id)
        counselor_name = f"{cc.first_name} {cc.last_name}" if cc else None
    loc_title = None
    if c.service_location_id:
        loc = db.get(ServiceLocation, c.service_location_id)
        loc_title = loc.title if loc else None
    return {
        "id": str(c.id),
        "case_number": c.case_number,
        "applicant_name": f"{a.first_name} {a.last_name}" if a else None,
        "applicant_national_id": a.national_id if a else None,
        "acceptance_date": c.acceptance_date.isoformat(),
        "service_location_title": loc_title,
        "service_type": c.service_type,
        "primary_counselor_name": counselor_name,
        "priority": c.priority,
        "status": c.status,
        "consent_status": c.consent_status,
        "close_reason": c.close_reason,
        "close_date": c.close_date.isoformat() if c.close_date else None,
        "version": c.version,
    }


def _detail_out(db: Session, c: Case) -> dict:
    data = _case_out(db, c)
    assignments = db.scalars(
        select(CaseAssignment)
        .where(CaseAssignment.case_id == c.id)
        .order_by(CaseAssignment.start_at.desc())
    ).all()
    out_assignments = []
    for asg in assignments:
        cc = db.get(Counselor, asg.counselor_id)
        out_assignments.append({
            "id": str(asg.id),
            "counselor_name": f"{cc.first_name} {cc.last_name}" if cc else "—",
            "start_at": asg.start_at.isoformat() if asg.start_at else None,
            "end_at": asg.end_at.isoformat() if asg.end_at else None,
            "reason": asg.reason,
            "end_reason": asg.end_reason,
            "role": getattr(asg, "role_in_case", "primary"),
            "is_current": asg.end_at is None,
        })
    data["assignments"] = out_assignments

    consents = db.scalars(
        select(Consent).where(Consent.case_id == c.id).order_by(Consent.version.desc())
    ).all()
    out_consents = []
    for x in consents:
        recorder = db.get(User, x.recorded_by) if x.recorded_by else None
        out_consents.append({
            "id": str(x.id),
            "version": x.version,
            "status": x.status,
            "note": x.note,
            "kind": x.kind,
            "consent_version_id": str(x.consent_version_id) if x.consent_version_id else None,
            "revoked_at": x.revoked_at.isoformat() if x.revoked_at else None,
            "revoke_reason": x.revoke_reason,
            "consent_date": x.consent_date.isoformat() if x.consent_date else None,
            "recorded_by_name": recorder.display_name if recorder else None,
        })
    data["consents"] = out_consents
    return data


def _require_case_access(db: Session, actor, case: Case) -> None:
    """مشاور فقط پرونده تخصیص‌یافته جاری را می‌بیند؛ غیرمجاز = 404 (بند ۳.۲ و ۷.۲)"""
    roles = {r.code for r in actor.roles}
    if roles & {"ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"}:
        return
    if "COUNSELOR" in roles:
        c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if c is not None and case.primary_counselor_id == c.id:
            return
    raise HTTPException(status_code=404, detail="پرونده یافت نشد")


# ---------- گزینه‌ها (قبل از مسیرهای /{case_id} اعلان شوند) ----------

@router.get("/applicant-options")
def applicant_options(
    search: str = Query(default="", max_length=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*CASE_MANAGE_ROLES)),
) -> dict:
    q = select(Applicant).where(Applicant.status == "active")
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(
            Applicant.first_name.ilike(like), Applicant.last_name.ilike(like),
            Applicant.national_id.ilike(like), Applicant.employee_code.ilike(like),
            Applicant.external_id.ilike(like),
        ))
    items = db.scalars(q.order_by(Applicant.last_name).limit(50)).all()
    return {"items": [{
        "id": str(a.id),
        "label": f"{a.first_name} {a.last_name}" + (f" — {a.national_id or a.employee_code or a.external_id or ''}" if (a.national_id or a.employee_code or a.external_id) else ""),
    } for a in items]}


@router.get("/counselor-options")
def counselor_options(
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*ASSIGN_ROLES)),
) -> dict:
    items = db.scalars(
        select(Counselor).where(Counselor.status == "active").order_by(Counselor.last_name)
    ).all()
    return {"items": [{"id": str(c.id), "label": f"{c.first_name} {c.last_name} ({c.counselor_code})"} for c in items]}


# ---------- CRUD پرونده ----------

@router.get("")
def list_cases(
    status: str = Query(default="", max_length=30),
    search: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*CASE_VIEW_ROLES)),
) -> dict:
    q = select(Case)
    actor_roles = {r.code for r in actor.roles}
    if not (actor_roles & {"ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"}):
        counselor = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if counselor is None:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        q = q.where(or_(
            Case.primary_counselor_id == counselor.id,
            Case.id.in_(select(CaseAssignment.case_id).where(
                CaseAssignment.counselor_id == counselor.id,
                CaseAssignment.end_at.is_(None),
            )),
        ))
    if status and status in CASE_STATUSES:
        q = q.where(Case.status == status)
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.join(Applicant, Case.applicant_id == Applicant.id).where(
            or_(Case.case_number.ilike(like), Applicant.first_name.ilike(like), Applicant.last_name.ilike(like))
        )
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(q.order_by(Case.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_case_out(db, c) for c in items], "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=201)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*CASE_MANAGE_ROLES)),
) -> dict:
    applicant = db.get(Applicant, payload.applicant_id)
    if applicant is None or applicant.status != "active":
        raise HTTPException(status_code=422, detail="متقاضی یافت نشد یا فعال نیست")
    if payload.service_location_id and db.get(ServiceLocation, payload.service_location_id) is None:
        raise HTTPException(status_code=422, detail="محل خدمت نامعتبر است")
    counselor: Counselor | None = None
    if payload.counselor_id:
        counselor = db.get(Counselor, payload.counselor_id)
        if counselor is None:
            raise HTTPException(status_code=422, detail="مشاور یافت نشد")
        if counselor.status != "active":
            raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست")

    case = Case(
        case_number=generate_case_number(db),
        applicant_id=payload.applicant_id,
        acceptance_date=date.today(),
        service_location_id=payload.service_location_id,
        service_type=payload.service_type,
        priority=payload.priority,
        created_by=actor.id,
    )
    db.add(case)
    db.flush()
    if counselor is not None:
        db.add(CaseAssignment(
            case_id=case.id, counselor_id=counselor.id,
            reason=payload.assignment_reason, assigned_by=actor.id,
        ))
        case.primary_counselor_id = counselor.id
        case.status = CaseStatus.ACTIVE
    else:
        case.status = CaseStatus.AWAITING_ASSIGNMENT
    db.commit()
    record_audit(db, action="case.created", actor_user_id=actor.id,
                 entity_type="case", entity_id=str(case.id),
                 detail={"case_number": case.case_number})
    return _detail_out(db, case)


@router.get("/{case_id}")
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(require_roles(*CASE_VIEW_ROLES))) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    _require_case_access(db, actor, case)
    return _detail_out(db, case)


@router.patch("/{case_id}")
def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*CASE_MANAGE_ROLES)),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    # بند ۱۱.۲: تعارض نسخه → 409
    if payload.expected_version != case.version:
        raise HTTPException(status_code=409, detail="این پرونده توسط کاربر دیگری تغییر کرده است؛ صفحه را بازخوانی و دوباره تلاش کنید")
    changed: list[str] = []
    if payload.service_type is not None:
        case.service_type = payload.service_type
        changed.append("service_type")
    if payload.priority is not None:
        case.priority = payload.priority
        changed.append("priority")
    if payload.service_location_id is not None:
        if db.get(ServiceLocation, payload.service_location_id) is None:
            raise HTTPException(status_code=422, detail="محل خدمت نامعتبر است")
        case.service_location_id = payload.service_location_id
        changed.append("service_location")
    if payload.status is not None:
        if case.status not in (CaseStatus.ACTIVE, CaseStatus.SUSPENDED):
            raise HTTPException(status_code=422, detail="توقف/ادامه فقط برای پرونده فعال یا متوقف امکان‌پذیر است")
        case.status = payload.status
        changed.append("status")
    if changed:
        case.version += 1
    db.commit()
    record_audit(db, action="case.updated", actor_user_id=actor.id,
                 entity_type="case", entity_id=str(case.id), detail={"changed": changed})
    return _detail_out(db, case)


# ---------- تخصیص / انتقال مشاور (بند ۷.۲) ----------

@router.post("/{case_id}/assignments", status_code=201)
def assign_counselor(
    case_id: uuid.UUID,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*ASSIGN_ROLES)),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    if payload.expected_version is not None and payload.expected_version != case.version:
        raise HTTPException(status_code=409, detail="این پرونده توسط کاربر دیگری تغییر کرده است؛ صفحه را بازخوانی کنید")
    counselor = db.get(Counselor, payload.counselor_id)
    if counselor is None:
        raise HTTPException(status_code=422, detail="مشاور یافت نشد")
    if counselor.status != "active":
        raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست")

    role = payload.role_in_case or "primary"
    reason = (payload.reason or "").strip()

    if role == "primary":
        if case.primary_counselor_id == counselor.id:
            raise HTTPException(status_code=422, detail="این مشاور هم‌اکنون مشاور اصلی این پرونده است")
        is_transfer = case.primary_counselor_id is not None
        if is_transfer and not reason:
            raise HTTPException(status_code=422, detail="برای انتقال مشاور، ثبت علت الزامی است")
        now = datetime.now(timezone.utc)
        if is_transfer:
            current = db.scalar(
                select(CaseAssignment)
                .where(
                    CaseAssignment.case_id == case.id,
                    CaseAssignment.counselor_id == case.primary_counselor_id,
                    CaseAssignment.end_at.is_(None),
                )
                .order_by(CaseAssignment.start_at.desc())
            )
            if current is not None:
                current.end_at = now
                current.end_reason = reason
        db.add(CaseAssignment(
            case_id=case.id, counselor_id=counselor.id,
            reason=reason or None, assigned_by=actor.id, role_in_case="primary",
        ))
        case.primary_counselor_id = counselor.id
        if case.status in (CaseStatus.NEW, CaseStatus.AWAITING_ASSIGNMENT):
            case.status = CaseStatus.ACTIVE
    else:
        # همکار پرونده - بدون تغییر مشاور اصلی (سند v1.00)
        if case.primary_counselor_id == counselor.id:
            raise HTTPException(status_code=422, detail="این مشاور هم‌اکنون مشاور اصلی این پرونده است")
        dup = db.scalar(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case.id,
                CaseAssignment.counselor_id == counselor.id,
                CaseAssignment.end_at.is_(None),
            )
        )
        if dup is not None:
            raise HTTPException(status_code=422, detail="این مشاور از قبل به‌عنوان همکار فعال این پرونده ثبت شده است")
        db.add(CaseAssignment(
            case_id=case.id, counselor_id=counselor.id,
            reason=reason or None, assigned_by=actor.id, role_in_case="collaborator",
        ))

    case.version += 1
    db.commit()
    record_audit(db, action="case.counselor_assigned", actor_user_id=actor.id,
                 entity_type="case", entity_id=str(case.id),
                 detail={"counselor_id": str(counselor.id), "role": role})
    return _detail_out(db, case)

# ---------- بستن / بازگشایی (بند ۷.۲) ----------

@router.post("/{case_id}/close")
def close_case(
    case_id: uuid.UUID,
    payload: CaseActionRequest,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*CASE_MANAGE_ROLES)),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    if case.status == CaseStatus.CLOSED:
        raise HTTPException(status_code=409, detail="این پرونده قبلاً بسته شده است")
    if case.status == CaseStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="پرونده بایگانی قابل بستن نیست")
    case.status = CaseStatus.CLOSED
    case.close_reason = payload.reason
    case.close_date = date.today()
    case.version += 1
    db.commit()
    record_audit(db, action="case.closed", actor_user_id=actor.id,
                 entity_type="case", entity_id=str(case.id), detail={"reason": payload.reason})
    return _detail_out(db, case)


@router.post("/{case_id}/reopen")
def reopen_case(
    case_id: uuid.UUID,
    payload: CaseActionRequest,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*REOPEN_ROLES)),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    if case.status != CaseStatus.CLOSED:
        raise HTTPException(status_code=409, detail="فقط پرونده بسته‌شده قابل بازگشایی است")
    case.status = CaseStatus.ACTIVE
    case.close_reason = None
    case.close_date = None
    case.version += 1
    db.commit()
    record_audit(db, action="case.reopened", actor_user_id=actor.id,
                 entity_type="case", entity_id=str(case.id), detail={"reason": payload.reason})
    return _detail_out(db, case)


# ---------- رضایت‌نامه‌ها (نسخه‌دار - بند ۷.۲) ----------

@router.get("/{case_id}/consents")
def list_consents(case_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(require_roles(*CASE_VIEW_ROLES))) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    _require_case_access(db, actor, case)
    return _detail_out(db, case)["consents"] and {"items": _detail_out(db, case)["consents"]} or {"items": []}


@router.post("/{case_id}/consents", status_code=201)
def add_consent(
    case_id: uuid.UUID,
    payload: ConsentCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*CASE_MANAGE_ROLES)),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    if payload.consent_version_id is not None:
        cv = db.get(ConsentVersion, payload.consent_version_id)
        # B41: ثبت رضایت فقط با متن نسخه‌دار معتبر و فعال
        if cv is None or not cv.is_active:
            raise HTTPException(status_code=404, detail="نسخه متن رضایت یافت نشد یا غیرفعال است")
    last_version = db.scalar(select(func.max(Consent.version)).where(Consent.case_id == case.id)) or 0
    consent = Consent(
        case_id=case.id,
        version=int(last_version) + 1,
        status=payload.status,
        note=payload.note,
        consent_date=date.today(),
        recorded_by=actor.id,
        kind=payload.kind,
        consent_version_id=payload.consent_version_id,
    )
    db.add(consent)
    # پس‌گرفتن رضایت سوابق را حذف نمی‌کند؛ فقط وضعیت جاری تغییر می‌کند (بند ۷.۲)
    case.consent_status = payload.status
    case.version += 1
    db.commit()
    record_audit(db, action="case.consent_recorded", actor_user_id=actor.id,
                 entity_type="case", entity_id=str(case.id),
                 detail={"status": payload.status, "consent_version": consent.version,
                         "kind": consent.kind})
    if payload.status == "revoked":
        # B12: اطلاع‌رسانی پس‌گرفتن رضایت به نقش‌های ناظر
        notify_roles(db, role_codes=("TECHNICAL_SUPERVISOR", "ORG_MANAGER"),
                     event_code="consent.revoked",
                     title=f"رضایت پرونده {case.case_number} پس گرفته شد",
                     category="consent", severity="warning",
                     entity_type="case", entity_id=str(case.id))
    return _detail_out(db, case)
