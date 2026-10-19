"""فاز ۲۸ - B06/B07 سند جامع: خدمات، تخصص‌ها و تعرفه نسخه‌دار.

- B06 پذیرش: مدت خدمت باید مثبت باشد؛ خدمت غیرفعال رزرو جدید نمی‌گیرد
  (این قاعده در نقاط رزرو - consultation/appointment - اعمال می‌شود).
- B07 پذیرش: هم‌پوشانی ناسازگار بازه‌های اعتبار یک خدمت رد می‌شود (409) و
  قیمت سفارش گذشته به‌صورت snapshot روی نوبت ذخیره می‌شود تا تغییر تعرفه
  روی سوابق مالی اثر نگذارد.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.catalog import (
    Service,
    ServiceSessionType,
    ServiceStatus,
    Specialty,
    TariffVersion,
)
from app.services.audit import record_audit

router = APIRouter(tags=["catalog"])

VIEW_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")
MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")


def _money(v) -> float | None:
    return float(v) if v is not None else None


# ----------------------------- B06: تخصص‌ها -----------------------------

class SpecialtyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class SpecialtyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


def _specialty_out(s: Specialty) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "description": s.description,
        "is_active": s.is_active,
    }


@router.get("/specialties")
def list_specialties(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(Specialty).order_by(Specialty.name)
    if not include_inactive:
        q = q.where(Specialty.is_active.is_(True))
    items = db.scalars(q).all()
    return {"items": [_specialty_out(s) for s in items], "total": len(items)}


@router.post("/specialties", status_code=201)
def create_specialty(payload: SpecialtyCreate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    name = payload.name.strip()
    if db.scalar(select(Specialty).where(Specialty.name == name)):
        raise HTTPException(status_code=409, detail="تخصصی با این نام قبلاً ثبت شده است")
    s = Specialty(name=name, description=payload.description)
    db.add(s)
    db.commit()
    record_audit(db, action="specialty.created", actor_user_id=actor.id,
                 entity_type="specialty", entity_id=str(s.id))
    return _specialty_out(s)


@router.patch("/specialties/{specialty_id}")
def update_specialty(specialty_id: uuid.UUID, payload: SpecialtyUpdate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    s = db.get(Specialty, specialty_id)
    if s is None:
        raise HTTPException(status_code=404, detail="تخصص یافت نشد")
    data = payload.model_dump(exclude_unset=True)
    changed: list[str] = []
    if "name" in data and data["name"]:
        name = data["name"].strip()
        dup = db.scalar(select(Specialty).where(Specialty.name == name, Specialty.id != s.id))
        if dup:
            raise HTTPException(status_code=409, detail="تخصصی با این نام قبلاً ثبت شده است")
        s.name = name
        changed.append("name")
    if "description" in data:
        s.description = data["description"]
        changed.append("description")
    if "is_active" in data and data["is_active"] is not None:
        s.is_active = bool(data["is_active"])
        changed.append("is_active")
    db.commit()
    record_audit(db, action="specialty.updated", actor_user_id=actor.id,
                 entity_type="specialty", entity_id=str(s.id), detail={"changed": changed})
    return _specialty_out(s)


# ----------------------------- B06: خدمات -----------------------------

class ServiceCreate(BaseModel):
    specialty_id: uuid.UUID
    title: str = Field(min_length=2, max_length=200)
    duration_minutes: int = Field(ge=1, le=600)
    session_type: str = Field(default=ServiceSessionType.IN_PERSON, max_length=20)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=1000)


class ServiceUpdate(BaseModel):
    specialty_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    session_type: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=20)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=1000)


def _service_out(db: Session, s: Service) -> dict:
    sp = db.get(Specialty, s.specialty_id)
    current = current_tariff(db, s.id)
    return {
        "id": str(s.id),
        "specialty_id": str(s.specialty_id),
        "specialty_name": sp.name if sp else None,
        "code": s.code,
        "title": s.title,
        "description": s.description,
        "duration_minutes": s.duration_minutes,
        "session_type": s.session_type,
        "status": s.status,
        "current_price": _money(current.amount) if current else None,
        "current_currency": current.currency if current else None,
    }


def current_tariff(db: Session, service_id, on: date | None = None) -> TariffVersion | None:
    """تعرفه معتبر یک خدمت در تاریخ مشخص (پیش‌فرض امروز) - B07."""
    on = on or date.today()
    q = select(TariffVersion).where(
        TariffVersion.service_id == service_id,
        TariffVersion.valid_from <= on,
        (TariffVersion.valid_to.is_(None)) | (TariffVersion.valid_to >= on),
    ).order_by(TariffVersion.valid_from.desc()).limit(1)
    return db.scalar(q)


@router.get("/services")
def list_services(
    specialty_id: uuid.UUID | None = Query(default=None),
    status: str = Query(default="", max_length=20),
    search: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(Service)
    if specialty_id is not None:
        q = q.where(Service.specialty_id == specialty_id)
    if status in (ServiceStatus.ACTIVE, ServiceStatus.INACTIVE):
        q = q.where(Service.status == status)
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.where(Service.title.ilike(like))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(Service.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [_service_out(db, s) for s in items], "total": total, "page": page, "page_size": page_size}


@router.post("/services", status_code=201)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    sp = db.get(Specialty, payload.specialty_id)
    if sp is None:
        raise HTTPException(status_code=422, detail="تخصص نامعتبر است")
    if payload.session_type not in ServiceSessionType.ALL:
        raise HTTPException(status_code=422, detail="نوع جلسه نامعتبر است")
    if payload.duration_minutes <= 0:
        raise HTTPException(status_code=422, detail="مدت خدمت باید مثبت باشد")
    if payload.code:
        code = payload.code.strip()
        if db.scalar(select(Service).where(Service.code == code)):
            raise HTTPException(status_code=409, detail="کد خدمت قبلاً ثبت شده است")
    s = Service(
        specialty_id=payload.specialty_id,
        title=payload.title.strip(),
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        session_type=payload.session_type,
        code=payload.code.strip() if payload.code else None,
        created_by=actor.id,
        status=ServiceStatus.ACTIVE,
    )
    db.add(s)
    db.commit()
    record_audit(db, action="service.created", actor_user_id=actor.id,
                 entity_type="service", entity_id=str(s.id),
                 detail={"title": s.title, "duration_minutes": s.duration_minutes})
    return _service_out(db, s)


@router.get("/services/{service_id}")
def get_service(service_id: uuid.UUID, db: Session = Depends(get_db), _actor=Depends(require_roles(*VIEW_ROLES))) -> dict:
    s = db.get(Service, service_id)
    if s is None:
        raise HTTPException(status_code=404, detail="خدمت یافت نشد")
    return _service_out(db, s)


@router.patch("/services/{service_id}")
def update_service(service_id: uuid.UUID, payload: ServiceUpdate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    s = db.get(Service, service_id)
    if s is None:
        raise HTTPException(status_code=404, detail="خدمت یافت نشد")
    data = payload.model_dump(exclude_unset=True)
    changed: list[str] = []
    if "specialty_id" in data and data["specialty_id"] is not None:
        if db.get(Specialty, data["specialty_id"]) is None:
            raise HTTPException(status_code=422, detail="تخصص نامعتبر است")
        s.specialty_id = data["specialty_id"]
        changed.append("specialty_id")
    if "title" in data and data["title"]:
        s.title = data["title"].strip()
        changed.append("title")
    if "description" in data:
        s.description = data["description"]
        changed.append("description")
    if "duration_minutes" in data and data["duration_minutes"] is not None:
        if data["duration_minutes"] <= 0:
            raise HTTPException(status_code=422, detail="مدت خدمت باید مثبت باشد")
        s.duration_minutes = data["duration_minutes"]
        changed.append("duration_minutes")
    if "session_type" in data and data["session_type"] is not None:
        if data["session_type"] not in ServiceSessionType.ALL:
            raise HTTPException(status_code=422, detail="نوع جلسه نامعتبر است")
        s.session_type = data["session_type"]
        changed.append("session_type")
    if "status" in data and data["status"] is not None:
        if data["status"] not in (ServiceStatus.ACTIVE, ServiceStatus.INACTIVE):
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        s.status = data["status"]
        changed.append("status")
    if "code" in data and data["code"] is not None:
        code = data["code"].strip() or None
        if code and db.scalar(select(Service).where(Service.code == code, Service.id != s.id)):
            raise HTTPException(status_code=409, detail="کد خدمت قبلاً ثبت شده است")
        s.code = code
        changed.append("code")
    db.commit()
    record_audit(db, action="service.updated", actor_user_id=actor.id,
                 entity_type="service", entity_id=str(s.id), detail={"changed": changed})
    return _service_out(db, s)


# ----------------------------- B07: تعرفه نسخه‌دار -----------------------------

class TariffCreate(BaseModel):
    service_id: uuid.UUID
    amount: float = Field(ge=0, le=10**14)
    currency: str = Field(default="IRR", min_length=3, max_length=3)
    valid_from: date
    valid_to: date | None = None
    note: str | None = Field(default=None, max_length=500)


class TariffUpdate(BaseModel):
    """فقط بستن بازه (valid_to) و یادداشت قابل ویرایش است؛ مبلغ نسخه‌های
    منتشرشده تغییر نمی‌کند تا تاریخچه قیمت دست‌نخورده بماند (B07)."""

    valid_to: date | None = None
    note: str | None = Field(default=None, max_length=500)


def _tariff_out(t: TariffVersion) -> dict:
    return {
        "id": str(t.id),
        "service_id": str(t.service_id),
        "amount": _money(t.amount),
        "currency": t.currency,
        "valid_from": t.valid_from.isoformat(),
        "valid_to": t.valid_to.isoformat() if t.valid_to else None,
        "note": t.note,
    }


def _check_tariff_overlap(db: Session, service_id, valid_from: date, valid_to: date | None, exclude_id=None) -> None:
    """بازه اعتبار با شمول دو سر روز است (valid_to = آخرین روز اعتبار).

    هم‌پوشانی بازه جدید با هر نسخه موجودِ همان خدمت مجاز نیست (B07)؛
    بازه‌های مجاور (پایان Jun30 / شروع Jul1) هم‌پوشان محسوب نمی‌شوند.
    """
    q = select(TariffVersion).where(TariffVersion.service_id == service_id)
    if exclude_id is not None:
        q = q.where(TariffVersion.id != exclude_id)
    new_end = valid_to if valid_to is not None else date.max
    for t in db.scalars(q):
        existing_start = t.valid_from
        existing_end = t.valid_to if t.valid_to is not None else date.max
        if valid_from <= existing_end and existing_start <= new_end:
            raise HTTPException(
                status_code=409,
                detail=f"بازه اعتبار با نسخه موجود ({t.valid_from.isoformat()} تا "
                       f"{t.valid_to.isoformat() if t.valid_to else 'بدون پایان'}) هم‌پوشانی دارد",
            )


@router.get("/tariffs")
def list_tariffs(
    service_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    items = db.scalars(
        select(TariffVersion)
        .where(TariffVersion.service_id == service_id)
        .order_by(TariffVersion.valid_from.desc())
    ).all()
    return {"items": [_tariff_out(t) for t in items], "total": len(items)}


@router.post("/tariffs", status_code=201)
def create_tariff(payload: TariffCreate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    s = db.get(Service, payload.service_id)
    if s is None:
        raise HTTPException(status_code=404, detail="خدمت یافت نشد")
    if payload.valid_to is not None and payload.valid_to < payload.valid_from:
        raise HTTPException(status_code=422, detail="پایان بازه اعتبار نمی‌تواند قبل از شروع آن باشد")
    _check_tariff_overlap(db, payload.service_id, payload.valid_from, payload.valid_to)
    t = TariffVersion(
        service_id=payload.service_id,
        amount=payload.amount,
        currency=payload.currency.upper(),
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        note=payload.note,
        created_by=actor.id,
    )
    db.add(t)
    db.commit()
    record_audit(db, action="tariff.created", actor_user_id=actor.id,
                 entity_type="tariff_version", entity_id=str(t.id),
                 detail={"service_id": str(payload.service_id), "amount": payload.amount,
                         "valid_from": payload.valid_from.isoformat()})
    return _tariff_out(t)


@router.patch("/tariffs/{tariff_id}")
def update_tariff(tariff_id: uuid.UUID, payload: TariffUpdate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    t = db.get(TariffVersion, tariff_id)
    if t is None:
        raise HTTPException(status_code=404, detail="نسخه تعرفه یافت نشد")
    data = payload.model_dump(exclude_unset=True)
    if "valid_to" in data and data["valid_to"] is not None:
        if data["valid_to"] < t.valid_from:
            raise HTTPException(status_code=422, detail="پایان بازه اعتبار نمی‌تواند قبل از شروع آن باشد")
        _check_tariff_overlap(db, t.service_id, t.valid_from, data["valid_to"], exclude_id=t.id)
        t.valid_to = data["valid_to"]
    if "note" in data:
        t.note = data["note"]
    db.commit()
    record_audit(db, action="tariff.updated", actor_user_id=actor.id,
                 entity_type="tariff_version", entity_id=str(t.id))
    return _tariff_out(t)


@router.get("/pricing/quote")
def pricing_quote(
    service_id: uuid.UUID = Query(...),
    date_q: str | None = Query(default=None, alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    """استعلام قیمت خدمت در تاریخ مشخص - مبنای snapshot نوبت (B07)."""
    on = date.fromisoformat(date_q) if date_q else date.today()
    s = db.get(Service, service_id)
    if s is None:
        raise HTTPException(status_code=404, detail="خدمت یافت نشد")
    t = current_tariff(db, service_id, on)
    if t is None:
        raise HTTPException(status_code=404, detail="برای این خدمت در تاریخ درخواست، تعرفه‌ای معتبر وجود ندارد")
    return {
        "service_id": str(service_id),
        "date": on.isoformat(),
        "tariff_version_id": str(t.id),
        "amount": _money(t.amount),
        "currency": t.currency,
        "valid_from": t.valid_from.isoformat(),
        "valid_to": t.valid_to.isoformat() if t.valid_to else None,
    }
