import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.org_contract import Organization
from app.models.people import Applicant, OrganizationUnit, ServiceLocation
from app.models.user import Role, User, UserStatus
from app.schemas.people import ApplicantCreate, ApplicantUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/applicants", tags=["applicants"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION")


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
    page: int = Query(default=1, ge=1),
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
    db.commit()
    record_audit(db, action="applicant.updated", actor_user_id=actor.id, entity_type="applicant", entity_id=str(a.id), detail={"changed": changed})
    return _out(a, db)
