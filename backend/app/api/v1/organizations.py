"""فاز ۳۳ - B21 سند جامع: سازمان‌ها، قراردادها و سهم پرداخت.

قواعد پذیرش:
- slug سازمان یکتا (۴۰۹)؛ شناسه ملی سازمان در صورت ورود یکتا؛
- قرارداد: ۰ < درصد سهم ≤ ۱۰۰؛ بازه اعتبار معتبر (valid_to ≥ valid_from)؛
  وضعیت draft/active/terminated؛ «قرارداد منقضی یا پیش‌نویس در تقسیم سهم
  اعمال نمی‌شود»؛
- دامنه خدمت قرارداد: بدون ردیف = همه خدمات؛ با ردیف = فقط همان خدمات؛
- تقسیم سهم در ساخت سفارش (payments.create_order) snapshot می‌شود؛
- گزارش مطالبات از سازمان: جمع سهم سازمان سفارش‌های پرداخت‌شده.
"""
import re
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalog import Service
from app.models.org_contract import Contract, ContractService, Organization
from app.models.payment import Order, OrderStatus
from app.models.user import User

router = APIRouter(tags=["organizations"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
VIEW_ROLES = (*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "RECEPTION")

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?$")


# ---------------------------------------------------------------- schemas
class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=120)
    national_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    national_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class ContractCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    coverage_percent: float = Field(gt=0, le=100)
    coverage_cap_amount: int | None = Field(default=None, ge=0)
    valid_from: date
    valid_to: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    service_ids: list[uuid.UUID] = Field(default_factory=list)


class ContractUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    coverage_percent: float | None = Field(default=None, gt=0, le=100)
    coverage_cap_amount: int | None = Field(default=None, ge=0)
    valid_from: date | None = None
    valid_to: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    status: str | None = None
    service_ids: list[uuid.UUID] | None = None


# ---------------------------------------------------------------- helpers
def _validate_slug(slug: str) -> str:
    s = slug.strip().lower()
    if not _SLUG_RE.match(s):
        raise HTTPException(
            status_code=422, detail="slug فقط حروف کوچک لاتین، عدد و خط تیره است"
        )
    return s


def _contract_out(db: Session, c: Contract) -> dict:
    svc_rows = db.execute(
        select(ContractService, Service)
        .join(Service, Service.id == ContractService.service_id)
        .where(ContractService.contract_id == c.id)
        .order_by(Service.title)
    ).all()
    return {
        "id": str(c.id),
        "organization_id": str(c.organization_id),
        "organization_name": c.organization.name if c.organization else None,
        "title": c.title,
        "coverage_percent": float(c.coverage_percent),
        "coverage_cap_amount": float(c.coverage_cap_amount) if c.coverage_cap_amount else None,
        "valid_from": str(c.valid_from),
        "valid_to": str(c.valid_to) if c.valid_to else None,
        "status": c.status,
        "notes": c.notes,
        "services": [
            {"id": str(svc.id), "title": svc.title} for _cs, svc in svc_rows
        ],
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _org_out(db: Session, o: Organization) -> dict:
    contracts = db.scalars(
        select(Contract).where(Contract.organization_id == o.id).order_by(Contract.created_at)
    ).all()
    today = date.today()
    active_contract = next(
        (
            c
            for c in contracts
            if c.status == "active" and c.valid_from <= today and (c.valid_to is None or c.valid_to >= today)
        ),
        None,
    )
    return {
        "id": str(o.id),
        "name": o.name,
        "slug": o.slug,
        "national_id": o.national_id,
        "phone": o.phone,
        "email": o.email,
        "address": o.address,
        "note": o.note,
        "is_active": o.is_active,
        "contract_count": len(contracts),
        "active_contract": (
            {
                "id": str(active_contract.id),
                "title": active_contract.title,
                "coverage_percent": float(active_contract.coverage_percent),
                "valid_from": str(active_contract.valid_from),
                "valid_to": str(active_contract.valid_to) if active_contract.valid_to else None,
            }
            if active_contract
            else None
        ),
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _validate_contract_dates(valid_from: date, valid_to: date | None) -> None:
    if valid_to is not None and valid_to < valid_from:
        raise HTTPException(
            status_code=422, detail="تاریخ پایان اعتبار نمی‌تواند پیش از تاریخ شروع باشد"
        )


def _set_contract_services(db: Session, contract: Contract, service_ids: list[uuid.UUID]) -> None:
    seen: set[uuid.UUID] = set()
    for sid in service_ids:
        if sid in seen:
            continue
        seen.add(sid)
        if db.get(Service, sid) is None:
            raise HTTPException(status_code=404, detail=f"خدمت یافت نشد: {sid}")
        exists = db.scalars(
            select(ContractService).where(
                ContractService.contract_id == contract.id, ContractService.service_id == sid
            )
        ).first()
        if exists is None:
            db.add(ContractService(contract_id=contract.id, service_id=sid))


# ---------------------------------------------------------------- organizations
@router.get("/organizations")
def list_organizations(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    orgs = db.scalars(select(Organization).order_by(Organization.name)).all()
    return {"items": [_org_out(db, o) for o in orgs]}


@router.post("/organizations", status_code=201)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    slug = _validate_slug(payload.slug)
    dup = db.scalars(select(Organization.id).where(Organization.slug == slug)).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="این slug قبلاً استفاده شده است")
    if payload.national_id:
        dup_nid = db.scalars(
            select(Organization.id).where(Organization.national_id == payload.national_id.strip())
        ).first()
        if dup_nid is not None:
            raise HTTPException(status_code=409, detail="این شناسه ملی قبلاً ثبت شده است")
    org = Organization(
        name=payload.name.strip(),
        slug=slug,
        national_id=payload.national_id.strip() if payload.national_id else None,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        note=payload.note,
        is_active=payload.is_active,
        created_by=actor.id,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return _org_out(db, org)


@router.patch("/organizations/{org_id}")
def update_organization(
    org_id: uuid.UUID,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    for field in ("name", "phone", "email", "address", "note"):
        value = getattr(payload, field)
        if value is not None:
            setattr(org, field, value.strip() if isinstance(value, str) else value)
    if payload.national_id is not None:
        nid = payload.national_id.strip()
        if nid:
            dup_nid = db.scalars(
                select(Organization.id).where(
                    Organization.national_id == nid, Organization.id != org.id
                )
            ).first()
            if dup_nid is not None:
                raise HTTPException(status_code=409, detail="این شناسه ملی قبلاً ثبت شده است")
            org.national_id = nid
    if payload.is_active is not None:
        org.is_active = payload.is_active
    db.commit()
    db.refresh(org)
    return _org_out(db, org)


# ---------------------------------------------------------------- contracts
@router.get("/organizations/{org_id}/contracts")
def list_contracts(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    contracts = db.scalars(
        select(Contract).where(Contract.organization_id == org_id).order_by(Contract.created_at.desc())
    ).all()
    return {"items": [_contract_out(db, c) for c in contracts]}


@router.post("/organizations/{org_id}/contracts", status_code=201)
def create_contract(
    org_id: uuid.UUID,
    payload: ContractCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    _validate_contract_dates(payload.valid_from, payload.valid_to)
    contract = Contract(
        organization_id=org_id,
        title=payload.title.strip(),
        coverage_percent=payload.coverage_percent,
        coverage_cap_amount=payload.coverage_cap_amount,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        status="draft",
        notes=payload.notes,
        created_by=actor.id,
    )
    db.add(contract)
    db.flush()
    _set_contract_services(db, contract, payload.service_ids)
    db.commit()
    db.refresh(contract)
    return _contract_out(db, contract)


@router.patch("/contracts/{contract_id}")
def update_contract(
    contract_id: uuid.UUID,
    payload: ContractUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="قرارداد یافت نشد")
    if payload.status is not None and payload.status not in ("draft", "active", "terminated"):
        raise HTTPException(status_code=422, detail="وضعیت باید draft، active یا terminated باشد")
    for field in ("title", "notes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(contract, field, value)
    if payload.coverage_percent is not None:
        contract.coverage_percent = payload.coverage_percent
    if payload.coverage_cap_amount is not None:
        contract.coverage_cap_amount = payload.coverage_cap_amount
    if payload.valid_from is not None:
        contract.valid_from = payload.valid_from
    if payload.valid_to is not None:
        contract.valid_to = payload.valid_to
    _validate_contract_dates(contract.valid_from, contract.valid_to)
    if payload.status is not None:
        # قرارداد منقضی/ملغی فعال نمی‌شود؛ فعال‌سازی فقط از پیش‌نویس
        if payload.status == "active" and contract.status == "terminated":
            raise HTTPException(status_code=422, detail="قرارداد ملغی قابل فعال‌سازی مجدد نیست")
        contract.status = payload.status
    if payload.service_ids is not None:
        _set_contract_services(db, contract, payload.service_ids)
        keep = set(payload.service_ids)
        for row in db.scalars(
            select(ContractService).where(ContractService.contract_id == contract.id)
        ).all():
            if row.service_id not in keep:
                db.delete(row)
    db.commit()
    db.refresh(contract)
    return _contract_out(db, contract)


# ---------------------------------------------------------------- receivables
@router.get("/organizations/{org_id}/receivables")
def organization_receivables(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES, "TECHNICAL_SUPERVISOR")),
) -> dict:
    """مطالبه از سازمان: جمع سهم سازمان سفارش‌های پرداخت‌شده (بستانکاری سازمان)."""
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    rows = db.scalars(
        select(Order)
        .where(
            Order.organization_id == org_id,
            Order.status == OrderStatus.PAID,
            Order.org_share_amount.isnot(None),
        )
        .order_by(Order.created_at.desc())
        .limit(200)
    ).all()
    total_org = sum(int(o.org_share_amount or 0) for o in rows)
    total_amount = sum(int(o.amount) for o in rows)
    return {
        "organization_id": str(org_id),
        "organization_name": org.name,
        "paid_orders_with_share": len(rows),
        "total_amount": total_amount,
        "org_share_total": total_org,
        "applicant_share_total": total_amount - total_org,
        "note": "سهم سازمان سفارش‌های پرداخت‌شده؛ صورتحساب دوره‌ای سازمان خارج از دامنه فعلی است",
        "items": [
            {
                "order_id": str(o.id),
                "order_number": o.order_number,
                "title": o.title,
                "amount": int(o.amount),
                "coverage_percent": float(o.coverage_percent) if o.coverage_percent else None,
                "org_share_amount": int(o.org_share_amount or 0),
                "applicant_share_amount": int(o.applicant_share_amount or 0),
                "status": o.status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in rows
        ],
    }
