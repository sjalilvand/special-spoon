import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.people import Counselor, ServiceLocation
from app.models.user import Role, User, UserStatus
from app.schemas.people import CounselorCreate, CounselorUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/counselors", tags=["counselors"])

VIEW_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR")
MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")


def _out(c: Counselor, db: Session) -> dict:
    loc_title = None
    if c.service_location_id:
        loc = db.get(ServiceLocation, c.service_location_id)
        loc_title = loc.title if loc else None
    return {
        "id": str(c.id),
        "counselor_code": c.counselor_code,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "national_id": c.national_id,
        "professional_title": c.professional_title,
        "degree": c.degree,
        "specialty": c.specialty,
        "license_number": c.license_number,
        "license_expiry_date": c.license_expiry_date.isoformat() if c.license_expiry_date else None,
        "work_mobile": c.work_mobile,
        "email": c.email,
        "capacity": c.capacity,
        "service_location_title": loc_title,
        "status": c.status,
        "has_account": c.user_id is not None,
    }


@router.get("")
def list_counselors(
    search: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(Counselor)
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(Counselor.counselor_code.ilike(like), Counselor.first_name.ilike(like), Counselor.last_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(q.order_by(Counselor.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_out(c, db) for c in items], "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=201)
def create_counselor(payload: CounselorCreate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    code = payload.counselor_code.strip()
    if db.scalar(select(Counselor).where(Counselor.counselor_code == code)):
        raise HTTPException(status_code=409, detail="این کد مشاور قبلاً ثبت شده است")
    if payload.national_id and db.scalar(select(Counselor).where(Counselor.national_id == payload.national_id)):
        raise HTTPException(status_code=409, detail="این کد ملی قبلاً ثبت شده است")
    if payload.service_location_id and db.get(ServiceLocation, payload.service_location_id) is None:
        raise HTTPException(status_code=422, detail="محل خدمت نامعتبر است")

    c = Counselor(
        counselor_code=code,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        national_id=payload.national_id or None,
        professional_title=payload.professional_title,
        degree=payload.degree,
        specialty=payload.specialty,
        license_number=payload.license_number,
        license_expiry_date=payload.license_expiry_date,
        work_mobile=payload.work_mobile,
        email=payload.email,
        service_location_id=payload.service_location_id,
        capacity=payload.capacity,
        status="active",
    )
    db.add(c)
    db.flush()
    if payload.create_account:
        if not payload.username:
            raise HTTPException(status_code=422, detail="برای ایجاد حساب، نام کاربری الزامی است")
        uname = payload.username.strip().lower()
        if db.scalar(select(User).where(User.username == uname)):
            raise HTTPException(status_code=409, detail="نام کاربری قبلاً ثبت شده است")
        u = User(username=uname, display_name=f"{c.first_name} {c.last_name}", status=UserStatus.PENDING, must_change_password=True)
        u.roles.append(db.get(Role, "COUNSELOR"))
        db.add(u)
        db.flush()
        c.user_id = u.id
    db.commit()
    record_audit(db, action="counselor.created", actor_user_id=actor.id, entity_type="counselor", entity_id=str(c.id))
    return _out(c, db)


@router.get("/{counselor_id}")
def get_counselor(counselor_id: uuid.UUID, db: Session = Depends(get_db), _actor=Depends(require_roles(*VIEW_ROLES))) -> dict:
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    return _out(c, db)


@router.patch("/{counselor_id}")
def update_counselor(counselor_id: uuid.UUID, payload: CounselorUpdate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    changed: list[str] = []
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        if data["status"] not in ("active", "inactive", "suspended"):
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        c.status = data["status"]
        changed.append("status")
    for f in ("professional_title", "degree", "specialty", "license_number", "work_mobile", "email", "capacity", "license_expiry_date", "service_location_id"):
        if f in data and data[f] is not None:
            setattr(c, f, data[f])
            changed.append(f)
    db.commit()
    record_audit(db, action="counselor.updated", actor_user_id=actor.id, entity_type="counselor", entity_id=str(c.id), detail={"changed": changed})
    return _out(c, db)
