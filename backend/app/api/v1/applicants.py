import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import get_settings
from app.core.security import generate_activation_token
from app.db.session import get_db
from app.models.case import Case
from app.models.consultation import ConsultationRequest
from app.models.intake import IntakeQuestionnaire
from app.models.org_contract import Organization
from app.models.org_program import OrgProgram, OrgProgramMember
from app.models.people import Applicant, OrganizationUnit, ServiceLocation
from app.models.user import Role, User, UserStatus
from app.schemas.people import ApplicantCreate, ApplicantUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/applicants", tags=["applicants"])
settings = get_settings()

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION")
REQUEST_TYPES = ("in_person", "phone", "online")


def _out(a: Applicant, db: Session) -> dict:
    unit_title = loc_title = None
    if a.unit_id:
        u = db.get(OrganizationUnit, a.unit_id)
        unit_title = u.title if u else None
    if a.service_location_id:
        l = db.get(ServiceLocation, a.service_location_id)
        loc_title = l.title if l else None
    # فاز ۳۳ - B21: سازمان کارفرما
    org_name = None
    if a.organization_id:
        o = db.get(Organization, a.organization_id)
        org_name = o.name if o else None
    return {
        "id": str(a.id),
        "external_id": a.external_id,
        "employee_code": a.employee_code,
        "national_id": a.national_id,
        "first_name": a.first_name,
        "last_name": a.last_name,
        "birth_date": a.birth_date.isoformat() if a.birth_date else None,
        "gender": a.gender,
        "mobile": a.mobile,
        "unit_title": unit_title,
        "organization_id": str(a.organization_id) if a.organization_id else None,
        "organization_name": org_name,
        "service_location_title": loc_title,
        "referral_source": a.referral_source,
        "status": a.status,
        "record_source": a.record_source,
        "has_account": a.user_id is not None,
    }


def _check_identifier_unique(db: Session, value: str | None, column, label: str) -> None:
    if value and db.scalar(select(Applicant).where(column == value)):
        raise HTTPException(status_code=409, detail=f"این {label} قبلاً ثبت شده است")


@router.get("")
def list_applicants(
    search: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    q = select(Applicant)
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(
            Applicant.first_name.ilike(like), Applicant.last_name.ilike(like),
            Applicant.national_id.ilike(like), Applicant.employee_code.ilike(like), Applicant.external_id.ilike(like),
        ))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(q.order_by(Applicant.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_out(a, db) for a in items], "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=201)
def create_applicant(payload: ApplicantCreate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    # بند ۵.۱ سند: حداقل یکی از شناسه‌های مصوب
    if not any([payload.external_id, payload.employee_code, payload.national_id]):
        raise HTTPException(status_code=422, detail="حداقل یکی از شناسه‌ها (کد ملی/پرسنلی/شناسه جایگزین) الزامی است")
    _check_identifier_unique(db, payload.external_id, Applicant.external_id, "شناسه جایگزین")
    _check_identifier_unique(db, payload.employee_code, Applicant.employee_code, "شماره پرسنلی")
    _check_identifier_unique(db, payload.national_id, Applicant.national_id, "کد ملی")

    a = Applicant(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        external_id=payload.external_id or None,
        employee_code=payload.employee_code or None,
        national_id=payload.national_id or None,
        birth_date=payload.birth_date,
        gender=payload.gender,
        marital_status=payload.marital_status,
        education=payload.education,
        occupation=payload.occupation,
        mobile=payload.mobile,
        phone=payload.phone,
        unit_id=payload.unit_id,
        organization_id=payload.organization_id,
        service_location_id=payload.service_location_id,
        city=payload.city,
        address=payload.address,
        referral_source=payload.referral_source,
        referral_description=payload.referral_description,
        status="active",
        record_source="manual",
    )
    db.add(a)
    db.flush()
    if payload.create_account:
        if not payload.username:
            raise HTTPException(status_code=422, detail="برای ایجاد حساب، نام کاربری الزامی است")
        uname = payload.username.strip().lower()
        if db.scalar(select(User).where(User.username == uname)):
            raise HTTPException(status_code=409, detail="نام کاربری قبلاً ثبت شده است")
        u = User(username=uname, display_name=f"{a.first_name} {a.last_name}", status=UserStatus.PENDING, must_change_password=True)
        # فاز ۸۷: حساب متقاضی به سازمانِ متقاضی منتسب می‌شود (ایزولاسیون + آزمون سازمانی)
        u.organization_id = a.organization_id
        u.roles.append(db.get(Role, "APPLICANT"))
        db.add(u)
        db.flush()
        a.user_id = u.id
    db.commit()
    record_audit(db, action="applicant.created", actor_user_id=actor.id, entity_type="applicant", entity_id=str(a.id))
    return _out(a, db)


@router.get("/{applicant_id}")
def get_applicant(applicant_id: uuid.UUID, db: Session = Depends(get_db), _actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    a = db.get(Applicant, applicant_id)
    if a is None:
        raise HTTPException(status_code=404, detail="متقاضی یافت نشد")
    return _out(a, db)


@router.patch("/{applicant_id}")
def update_applicant(applicant_id: uuid.UUID, payload: ApplicantUpdate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    a = db.get(Applicant, applicant_id)
    if a is None:
        raise HTTPException(status_code=404, detail="متقاضی یافت نشد")
    changed: list[str] = []
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        if data["status"] not in ("active", "inactive", "archived"):
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        a.status = data["status"]
        changed.append("status")
    for f in ("birth_date", "gender", "marital_status", "education", "occupation", "mobile", "phone",
              "unit_id", "organization_id", "service_location_id", "city", "address", "referral_source", "referral_description"):
        if f in data and data[f] is not None:
            setattr(a, f, data[f])
            changed.append(f)
    # فاز ۸۷: تغییر سازمان متقاضی، سازمان حساب کاربری او را هم هم‌راستا می‌کند
    if "organization_id" in changed and a.user_id:
        u = db.get(User, a.user_id)
        if u is not None and u.organization_id != a.organization_id:
            u.organization_id = a.organization_id
            changed.append("user.organization_id")
    db.commit()
    record_audit(db, action="applicant.updated", actor_user_id=actor.id, entity_type="applicant", entity_id=str(a.id), detail={"changed": changed})
    return _out(a, db)


# ---------------------------------------------------------------------------
# فاز ۸۷ — جریان کامل متقاضی: حساب، توکن فعال‌سازی، درخواست حضوری/تلفنی،
# ثبت‌نام در برنامه‌های سازمانی و پروندهٔ الکترونیکی یکپارچه
# ---------------------------------------------------------------------------
class ApplicantAccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)


class ApplicantRequestCreate(BaseModel):
    """ثبت درخواست مشاورهٔ حضوری/تلفنی برای متقاضی از درون پنل."""

    topic: str = Field(min_length=2, max_length=100)
    message: str | None = Field(default=None, max_length=2000)
    preferred_date: str | None = Field(default=None, max_length=10)  # ISO
    request_type: str = Field(default="in_person")
    city: str | None = Field(default=None, max_length=100)


@router.post("/{applicant_id}/account", status_code=201)
def create_applicant_account(
    applicant_id: uuid.UUID,
    payload: ApplicantAccountCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """ساخت حساب کاربری برای متقاضیِ موجود (یوزر + نقش متقاضی + سازمان او)."""
    a = db.get(Applicant, applicant_id)
    if a is None:
        raise HTTPException(status_code=404, detail="متقاضی یافت نشد")
    if a.user_id:
        raise HTTPException(status_code=409, detail="این متقاضی از قبل حساب کاربری دارد")
    uname = payload.username.strip().lower()
    if db.scalar(select(User).where(User.username == uname)):
        raise HTTPException(status_code=409, detail="نام کاربری قبلاً ثبت شده است")
    u = User(
        username=uname,
        display_name=f"{a.first_name} {a.last_name}",
        status=UserStatus.PENDING,
        must_change_password=True,
        organization_id=a.organization_id,
    )
    u.roles.append(db.get(Role, "APPLICANT"))
    db.add(u)
    db.flush()
    a.user_id = u.id
    db.commit()
    record_audit(db, action="applicant.account_created", actor_user_id=actor.id,
                 entity_type="applicant", entity_id=str(a.id), detail={"username": uname})
    return {"ok": True, "username": uname, "user_id": str(u.id)}


@router.post("/{applicant_id}/activation-link")
def applicant_activation_link(
    applicant_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """صدور توکن فعال‌سازی برای حساب متقاضی — لینک یک‌بارمصرف تعیین رمز.

    خروجی: مسیر نسبی صفحهٔ فعال‌سازی پنل؛ فرانت آن را با آدرس جاری کامل می‌کند.
    """
    a = db.get(Applicant, applicant_id)
    if a is None:
        raise HTTPException(status_code=404, detail="متقاضی یافت نشد")
    if not a.user_id:
        raise HTTPException(status_code=409, detail="متقاضی حساب کاربری ندارد؛ ابتدا حساب بسازید")
    u = db.get(User, a.user_id)
    raw, token_hash = generate_activation_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.activation_token_expire_hours)
    from app.models.user import ActivationToken
    db.add(ActivationToken(user_id=u.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()
    record_audit(db, action="applicant.activation_link", actor_user_id=actor.id,
                 entity_type="applicant", entity_id=str(a.id))
    return {
        "username": u.username,
        "activation_path": f"/panel/activate?token={raw}",
        "expires_at": expires_at.isoformat(),
    }


@router.post("/{applicant_id}/requests", status_code=201)
def create_applicant_request(
    applicant_id: uuid.UUID,
    payload: ApplicantRequestCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """ثبت درخواست مشاورهٔ حضوری/تلفنی از روی پروفایل متقاضی (فاز ۸۷).

    بعد از ثبت متقاضی، پذیرش می‌تواند بدون خروج از صفحهٔ او، درخواست حضوری
    یا تلفنی ثبت کند؛ درخواست به همان متقاضی (applicant_id) متصل می‌شود و
    در پروندهٔ الکترونیکی‌اش ظاهر می‌گردد.
    """
    a = db.get(Applicant, applicant_id)
    if a is None:
        raise HTTPException(status_code=404, detail="متقاضی یافت نشد")
    if payload.request_type not in REQUEST_TYPES:
        raise HTTPException(status_code=422, detail="نوع درخواست باید in_person، phone یا online باشد")
    preferred = None
    if payload.preferred_date:
        from datetime import date as date_type
        try:
            preferred = date_type.fromisoformat(payload.preferred_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="تاریخ نامعتبر است")
    r = ConsultationRequest(
        full_name=f"{a.first_name} {a.last_name}".strip(),
        mobile=a.mobile or "",
        topic=payload.topic.strip(),
        message=payload.message,
        preferred_date=preferred,
        request_type=payload.request_type,
        applicant_id=a.id,
        city=payload.city or a.city,
        referral_source="ثبت در پنل",
        status="in_review",
    )
    db.add(r)
    db.commit()
    record_audit(db, action="consultation.created_for_applicant", actor_user_id=actor.id,
                 entity_type="consultation_request", entity_id=str(r.id),
                 detail={"applicant_id": str(a.id), "request_type": payload.request_type})
    return {
        "id": str(r.id),
        "full_name": r.full_name,
        "topic": r.topic,
        "request_type": r.request_type,
        "status": r.status,
    }


@router.post("/{applicant_id}/enroll-org-programs")
def enroll_org_programs(
    applicant_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """ثبت‌نام متقاضی در همهٔ برنامه‌های فعالِ سازمانِ او (فاز ۸۷).

    برای هر برنامهٔ فعال سازمانِ متقاضی، یک عضویت (OrgProgramMember) ساخته
    می‌شود؛ اگر متقاضی حساب کاربری داشته باشد عضویت به کاربرش می‌چسبد تا
    آزمون‌های سازمانی در پنل شخصی‌اش ظاهر شوند؛ وگرنه عضویت با نام/موبایل.
    idempotent: عضویت تکراری ساخته نمی‌شود.
    """
    a = db.get(Applicant, applicant_id)
    if a is None:
        raise HTTPException(status_code=404, detail="متقاضی یافت نشد")
    if not a.organization_id:
        raise HTTPException(status_code=422, detail="متقاضی به سازمانی متصل نیست؛ ابتدا سازمان را تعیین کنید")
    programs = db.scalars(
        select(OrgProgram).where(OrgProgram.organization_id == a.organization_id, OrgProgram.status == "active")
    ).all()
    if not programs:
        raise HTTPException(status_code=422, detail="برنامهٔ فعالی برای سازمانِ این متقاضی تعریف نشده است")
    added = 0
    for p in programs:
        dup = None
        if a.user_id:
            dup = db.scalar(
                select(OrgProgramMember).where(
                    OrgProgramMember.program_id == p.id, OrgProgramMember.user_id == a.user_id)
            )
        else:
            dup = db.scalar(
                select(OrgProgramMember).where(
                    OrgProgramMember.program_id == p.id, OrgProgramMember.full_name == f"{a.first_name} {a.last_name}".strip())
            )
        if dup is not None:
            continue
        db.add(OrgProgramMember(
            program_id=p.id,
            user_id=a.user_id,
            full_name=f"{a.first_name} {a.last_name}".strip(),
            employee_code=a.employee_code,
            mobile=a.mobile,
            note=f"ثبت‌نام خودکار از پروفایل متقاضی ({a.external_id or a.national_id or a.id})",
        ))
        added += 1
    db.commit()
    record_audit(db, action="applicant.enrolled_org_programs", actor_user_id=actor.id,
                 entity_type="applicant", entity_id=str(a.id),
                 detail={"programs": len(programs), "added": added})
    return {"ok": True, "programs": len(programs), "added": added}


@router.get("/{applicant_id}/summary")
def applicant_summary(
    applicant_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """پروندهٔ الکترونیکی متقاضی (فاز ۸۷) — همهٔ اطلاعات یک‌جا:

    مشخصات + سازمان + حساب کاربری + درخواست‌های مشاوره + پرسشنامه‌های پذیرش +
    پرونده‌های بالینی + آزمون‌های روان‌سنجی + نوبت‌ها — تاریخچهٔ کامل.
    """
    from app.services.counseling_file import file_out

    a = db.get(Applicant, applicant_id)
    if a is None:
        raise HTTPException(status_code=404, detail="متقاضی یافت نشد")
    org = db.get(Organization, a.organization_id) if a.organization_id else None
    unit = db.get(OrganizationUnit, a.unit_id) if a.unit_id else None

    user_info = None
    timeline_items: list[dict] = []
    if a.user_id:
        u = db.get(User, a.user_id)
        if u is not None:
            user_info = {
                "id": str(u.id),
                "username": u.username,
                "status": u.status,
                "token_hours": u.token_hours,
            }
            # خط زمانی استاندارد پرونده (آزمون + مشاوره + نوبت + پرسشنامه + ارزیابی)
            timeline_items = file_out(db, u, limit=200)["items"]
    else:
        # بدون حساب: درخواست‌های متصل به همین متقاضی
        rows = db.scalars(
            select(ConsultationRequest)
            .where(ConsultationRequest.applicant_id == a.id)
            .order_by(ConsultationRequest.created_at.desc())
            .limit(200)
        ).all()
        timeline_items = [{
            "kind": "consultation",
            "id": str(r.id),
            "title": r.topic or "درخواست مشاوره",
            "at": r.created_at.isoformat() if r.created_at else None,
            "status": r.status,
            "request_type": r.request_type,
        } for r in rows]

    requests = db.scalars(
        select(ConsultationRequest)
        .where(ConsultationRequest.applicant_id == a.id)
        .order_by(ConsultationRequest.created_at.desc())
        .limit(100)
    ).all()
    req_ids = [r.id for r in requests]
    intakes = db.scalars(
        select(IntakeQuestionnaire).where(IntakeQuestionnaire.consultation_request_id.in_(req_ids))
    ).all() if req_ids else []
    cases = db.scalars(
        select(Case).where(Case.applicant_id == a.id).order_by(Case.created_at.desc()).limit(50)
    ).all()

    return {
        "applicant": _out(a, db),
        "organization_name": org.name if org else None,
        "unit_title": unit.title if unit else None,
        "user": user_info,
        "requests": [{
            "id": str(r.id),
            "topic": r.topic,
            "status": r.status,
            "request_type": r.request_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "case_id": str(r.case_id) if r.case_id else None,
        } for r in requests],
        "intakes": [{
            "id": str(q.id),
            "request_id": str(q.consultation_request_id),
            "status": q.status,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        } for q in intakes],
        "cases": [{
            "id": str(c.id),
            "case_number": c.case_number,
            "status": c.status,
            "acceptance_date": c.acceptance_date.isoformat() if c.acceptance_date else None,
        } for c in cases],
        "timeline": timeline_items,
    }
