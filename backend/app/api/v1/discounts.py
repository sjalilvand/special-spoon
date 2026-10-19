"""فاز ۳۰ - B19 سند جامع: API کدهای تخفیف.

- مدیر: ایجاد/ویرایش/فهرست کدها + مشاهده مصرف مؤثر.
- اعتبارسنجی برای UI: POST /discounts/validate (مبلغ تخفیف پیش از ثبت سفارش).
- اعمال کد هنگام ساخت سفارش در create_order (app/api/v1/payments.py) انجام
  می‌شود تا «مصرف هم‌زمان بیش از سقف» داخل همان تراکنش سفارش کنترل شود.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.discount import Discount, DiscountKind
from app.models.user import User
from app.services import discounts as disc_svc
from app.services.discounts import DiscountError

router = APIRouter(tags=["discounts"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
VIEW_ROLES = (*MANAGE_ROLES, "RECEPTION", "TECHNICAL_SUPERVISOR")


class DiscountCreate(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    kind: str = Field(description="amount | percent")
    value: int = Field(gt=0)
    currency: str = Field(default="IRR", max_length=3)
    max_uses: int | None = Field(default=None, ge=1)
    max_uses_per_user: int | None = Field(default=None, ge=1)
    starts_at: date | None = None
    expires_at: date | None = None
    min_order_amount: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=300)


class DiscountUpdate(BaseModel):
    is_active: bool | None = None
    expires_at: date | None = None
    max_uses: int | None = Field(default=None, ge=1)
    max_uses_per_user: int | None = Field(default=None, ge=1)
    note: str | None = Field(default=None, max_length=300)


class ValidatePayload(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    amount: int = Field(gt=0)


@router.get("/discounts")
def list_discounts(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    items = db.scalars(select(Discount).order_by(Discount.created_at.desc()).limit(200)).all()
    return {"items": [disc_svc.discount_out(db, d) for d in items]}


@router.post("/discounts", status_code=201)
def create_discount(
    payload: DiscountCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    code = payload.code.strip().upper()
    if payload.kind not in DiscountKind.ALL:
        raise HTTPException(status_code=422, detail="نوع تخفیف باید amount یا percent باشد")
    if payload.kind == DiscountKind.PERCENT and payload.value > 100:
        raise HTTPException(status_code=422, detail="درصد تخفیف نمی‌تواند بیش از ۱۰۰ باشد")
    if payload.starts_at and payload.expires_at and payload.expires_at < payload.starts_at:
        raise HTTPException(status_code=422, detail="بازه اعتبار نامعتبر است")
    dup = db.scalars(select(Discount.id).where(Discount.code == code)).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="این کد قبلاً ثبت شده است")
    disc = Discount(
        code=code,
        kind=payload.kind,
        value=payload.value,
        currency=payload.currency,
        max_uses=payload.max_uses,
        max_uses_per_user=payload.max_uses_per_user,
        starts_at=payload.starts_at,
        expires_at=payload.expires_at,
        min_order_amount=payload.min_order_amount,
        note=payload.note,
        created_by=actor.id,
    )
    db.add(disc)
    db.commit()
    db.refresh(disc)
    return disc_svc.discount_out(db, disc)


@router.patch("/discounts/{discount_id}")
def update_discount(
    discount_id: uuid.UUID,
    payload: DiscountUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    disc = db.get(Discount, discount_id)
    if disc is None:
        raise HTTPException(status_code=404, detail="کد تخفیف یافت نشد")
    # مبلغ/درصد و کد پس از انتشار تغییر نمی‌کند (سازگاری مصرف‌های گذشته)
    if payload.is_active is not None:
        disc.is_active = payload.is_active
    if payload.expires_at is not None:
        if disc.starts_at and payload.expires_at < disc.starts_at:
            raise HTTPException(status_code=422, detail="تاریخ پایان قبل از شروع است")
        disc.expires_at = payload.expires_at
    if payload.max_uses is not None:
        disc.max_uses = payload.max_uses
    if payload.max_uses_per_user is not None:
        disc.max_uses_per_user = payload.max_uses_per_user
    if payload.note is not None:
        disc.note = payload.note
    db.commit()
    db.refresh(disc)
    return disc_svc.discount_out(db, disc)


@router.post("/discounts/validate")
def validate_discount(
    payload: ValidatePayload,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """پیش‌نمایش تخفیف برای UI — مصرفی ثبت نمی‌شود."""
    try:
        _disc, amount = disc_svc.validate(db, payload.code, payload.amount, actor.id)
    except DiscountError as exc:
        return {"valid": False, "reason": str(exc), "discount_amount": 0}
    return {"valid": True, "reason": None, "discount_amount": amount}
