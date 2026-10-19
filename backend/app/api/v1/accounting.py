"""فاز ۳۱ - B22 سند جامع: API حسابداری — کدینگ، سند، تسویه، تراز و مغایرت.

دسترسی: SYSTEM_ADMIN و ORG_MANAGER (مدیریت مالی)؛
applicant/مشاور/پذیرش مجاز نیستند (محتوای مالی محرمانه است).
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.accounting import (
    Account,
    JournalEntry,
    JournalSource,
    Settlement,
    SettlementStatus,
)
from app.models.user import User
from app.services import accounting as acc
from app.services import settlements as stl

router = APIRouter(tags=["accounting"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")


def _acc_error(exc: acc.AccountingError, status: int = 422) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


# ---------------------------------------------------------------- کدینگ
@router.get("/accounts")
def list_accounts(
    include_inactive: bool = Query(default=True),
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    acc.ensure_chart(db)
    db.commit()
    q = select(Account).order_by(Account.code)
    if not include_inactive:
        q = q.where(Account.is_active.is_(True))
    accounts = db.scalars(q).all()
    return {"items": [acc.account_out(a) for a in accounts]}


class AccountCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[0-9]{2,20}$")
    name: str = Field(min_length=2, max_length=200)
    type: str = Field(pattern="^(asset|liability|equity|revenue|expense)$")
    parent_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)


@router.post("/accounts", status_code=201)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    if db.scalars(select(Account).where(Account.code == payload.code)).first() is not None:
        raise HTTPException(status_code=409, detail="این کد حساب قبلاً ثبت شده است")
    if payload.parent_id is not None and db.get(Account, payload.parent_id) is None:
        raise HTTPException(status_code=404, detail="حساب والد یافت نشد")
    item = Account(
        code=payload.code,
        name=payload.name,
        type=payload.type,
        parent_id=payload.parent_id,
        description=payload.description,
        is_active=True,
        is_system=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return acc.account_out(item)


class AccountPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


@router.patch("/accounts/{account_id}")
def patch_account(
    account_id: uuid.UUID,
    payload: AccountPatch,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    item = db.get(Account, account_id)
    if item is None:
        raise HTTPException(status_code=404, detail="حساب یافت نشد")
    if payload.name is not None:
        item.name = payload.name
    if payload.description is not None:
        item.description = payload.description
    if payload.is_active is not None:
        item.is_active = payload.is_active
    db.commit()
    db.refresh(item)
    return acc.account_out(item)


# ---------------------------------------------------------------- اسناد
@router.get("/journal-entries")
def list_journal_entries(
    source_type: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    from app.models.accounting import JournalLine

    q = select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(limit)
    if source_type:
        q = q.where(JournalEntry.source_type == source_type)
    if kind:
        q = q.where(JournalEntry.kind == kind)
    if date_from:
        q = q.where(JournalEntry.entry_date >= date_from)
    if date_to:
        q = q.where(JournalEntry.entry_date <= date_to)
    if account_id:
        q = q.where(JournalEntry.id.in_(
            select(JournalLine.entry_id).where(JournalLine.account_id == account_id)
        ))
    entries = db.scalars(q).all()
    return {"items": [acc.entry_out(e, db) for e in entries]}


@router.get("/journal-entries/{entry_id}")
def get_journal_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    return acc.entry_out(entry, db)


class LineIn(BaseModel):
    account_id: uuid.UUID
    debit: float = Field(default=0, ge=0)
    credit: float = Field(default=0, ge=0)
    description: str | None = Field(default=None, max_length=300)


class EntryCreate(BaseModel):
    description: str = Field(min_length=3, max_length=500)
    entry_date: date | None = None
    lines: list[LineIn] = Field(min_length=2)


@router.post("/journal-entries", status_code=201)
def create_manual_entry(
    payload: EntryCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """سند دستی — قاعده «سند متوازن» در سرویس کنترل می‌شود (خطا = 422)."""
    for ln in payload.lines:
        if db.get(Account, ln.account_id) is None:
            raise HTTPException(status_code=404, detail="یکی از سرفصل‌ها یافت نشد")
    try:
        entry = acc.post_entry(
            db,
            lines=[l.model_dump() for l in payload.lines],
            description=payload.description,
            kind="manual",
            source_type=JournalSource.MANUAL,
            source_id=None,
            entry_date=payload.entry_date,
            created_by=actor.id,
            commit=False,
        )
        db.commit()
        db.refresh(entry)
    except acc.AccountingError as exc:
        db.rollback()
        raise _acc_error(exc) from exc
    return acc.entry_out(entry, db)


@router.post("/journal-entries/{entry_id}/reverse", status_code=201)
def reverse_journal_entry(
    entry_id: uuid.UUID,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    try:
        mirror = acc.reverse_entry(db, entry, reason=reason, actor=actor, commit=False)
        db.commit()
        db.refresh(mirror)
    except acc.AccountingError as exc:
        db.rollback()
        raise _acc_error(exc, status=409) from exc
    return acc.entry_out(mirror, db)


@router.post("/journal-entries/backfill")
def backfill(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """سند زدن رویدادهای مالی بدون سند — idempotent (تکرار = صفر جدید)."""
    try:
        created = acc.backfill_financial_events(db, actor=actor)
    except acc.AccountingError as exc:
        db.rollback()
        raise _acc_error(exc, status=409) from exc
    return {"created": created}


# ---------------------------------------------------------------- تسویه
@router.get("/settlements")
def list_settlements(
    status: str | None = Query(default=None),
    gateway: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    q = select(Settlement).order_by(Settlement.created_at.desc())
    if status:
        q = q.where(Settlement.status == status)
    if gateway:
        q = q.where(Settlement.gateway == gateway)
    rows = db.scalars(q).all()
    return {"items": [stl.settlement_out(db, s) for s in rows]}


@router.get("/settlements/{settlement_id}")
def get_settlement(
    settlement_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    st = db.get(Settlement, settlement_id)
    if st is None:
        raise HTTPException(status_code=404, detail="تسویه یافت نشد")
    return stl.settlement_out(db, st, with_items=True)


class SettlementCreate(BaseModel):
    gateway: str = Field(pattern="^(sandbox|zarinpal)$")
    period_start: date | None = None
    period_end: date | None = None
    note: str | None = Field(default=None, max_length=300)


@router.post("/settlements", status_code=201)
def create_settlement(
    payload: SettlementCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    try:
        st = stl.create_draft(
            db, gateway=payload.gateway,
            period_start=payload.period_start, period_end=payload.period_end,
            actor=actor, note=payload.note,
        )
    except stl.SettlementError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return stl.settlement_out(db, st, with_items=True)


class SettlementExec(BaseModel):
    fee_amount: int = Field(ge=0)


@router.post("/settlements/{settlement_id}/settle")
def settle_settlement(
    settlement_id: uuid.UUID,
    payload: SettlementExec,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    st = db.get(Settlement, settlement_id)
    if st is None:
        raise HTTPException(status_code=404, detail="تسویه یافت نشد")
    try:
        st = stl.settle(db, st, fee_amount=payload.fee_amount, actor=actor)
    except stl.SettlementError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return stl.settlement_out(db, st, with_items=True)


# ---------------------------------------------------------------- گزارش مالی
@router.get("/reports/trial-balance")
def get_trial_balance(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    return acc.trial_balance(db)


@router.get("/reports/financial-reconciliation")
def get_reconciliation(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    return acc.reconciliation(db)
