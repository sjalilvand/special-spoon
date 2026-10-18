"""B41 سند جامع - رضایت‌نامه و حاکمیت داده.

- نسخه‌های متن رضایت پس از ایجاد غیرقابل‌تغییرند (تغییر = نسخه جدید).
- ابطال، آینده را قطع می‌کند و سابقه را حفظ می‌کند (حذف فیزیکی ممنوع).
- هر ثبت/ابطال در audit ثبت و به ناظران اعلان ارسال می‌شود.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.case import Case, Consent
from app.models.consent import CONSENT_KINDS, ConsentVersion
from app.services.audit import record_audit
from app.services.notifications import notify_roles

router = APIRouter(tags=["consents"])


class ConsentVersionCreate(BaseModel):
    kind: str = Field(pattern="^(treatment|psych_test|data_share|marketing)$")
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=20000)


class ConsentRevoke(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


def _version_out(cv: ConsentVersion, include_body: bool = True) -> dict:
    out = {
        "id": str(cv.id),
        "kind": cv.kind,
        "version": cv.version,
        "title": cv.title,
        "is_active": cv.is_active,
        "created_at": cv.created_at.isoformat() if cv.created_at else None,
    }
    if include_body:
        out["body"] = cv.body
    return out


@router.get("/consent-versions")
def list_consent_versions(
    kind: str | None = None,
    include_inactive: bool = False,
    include_body: bool = Query(False, description="متن کامل فقط در صورت نیاز"),
    db: Session = Depends(get_db),
    _actor=Depends(get_current_user),
) -> dict:
    q = select(ConsentVersion)
    if kind:
        if kind not in CONSENT_KINDS:
            raise HTTPException(status_code=422, detail="نوع رضایت نامعتبر است")
        q = q.where(ConsentVersion.kind == kind)
    if not include_inactive:
        q = q.where(ConsentVersion.is_active.is_(True))
    rows = db.scalars(
        q.order_by(ConsentVersion.kind, ConsentVersion.version.desc())
    ).all()
    return {"items": [_version_out(cv, include_body) for cv in rows]}


@router.post("/consent-versions", status_code=201)
def create_consent_version(
    payload: ConsentVersionCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles("SYSTEM_ADMIN")),
) -> dict:
    """انتشار متن رضایت جدید = نسخه جدید؛ متن نسخه‌های قبلی هرگز تغییر نمی‌کند."""
    last = db.scalar(
        select(ConsentVersion.version)
        .where(ConsentVersion.kind == payload.kind)
        .order_by(ConsentVersion.version.desc())
        .limit(1)
    )
    cv = ConsentVersion(
        kind=payload.kind,
        version=(last or 0) + 1,
        title=payload.title.strip(),
        body=payload.body,
        is_active=True,
        created_by=actor.id,
    )
    db.add(cv)
    db.flush()
    record_audit(
        db,
        action="consent_version.published",
        actor_user_id=actor.id,
        entity_type="consent_version",
        entity_id=str(cv.id),
        detail={"kind": cv.kind, "version": cv.version},
    )
    db.commit()
    return _version_out(cv)


@router.post("/consents/{consent_id}/revoke")
def revoke_consent(
    consent_id: uuid.UUID,
    payload: ConsentRevoke,
    db: Session = Depends(get_db),
    actor=Depends(require_roles("ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR")),
) -> dict:
    """ابطال با حفظ سابقه - رکورد سابق حذف نمی‌شود؛ وضعیت و زمان ابطال ثبت می‌شود."""
    consent = db.get(Consent, consent_id)
    if consent is None:
        raise HTTPException(status_code=404, detail="رکورد رضایت یافت نشد")
    if consent.status == "revoked":
        raise HTTPException(status_code=409, detail="این رضایت قبلاً باطل شده است")
    consent.status = "revoked"
    consent.revoked_at = datetime.now(timezone.utc)
    consent.revoked_by = actor.id
    consent.revoke_reason = payload.reason.strip()
    consent.note = consent.note  # سابقه دست‌نخورده می‌ماند

    case = db.get(Case, consent.case_id)
    if case is not None:
        # اگر هیچ رضایت معتبر دیگری باقی نمانده باشد، وضعیت پرونده به revoked می‌رود
        remaining = db.scalar(
            select(Consent.id).where(
                Consent.case_id == case.id,
                Consent.status == "granted",
                Consent.id != consent.id,
            )
        )
        if remaining is None:
            case.consent_status = "revoked"
            case.version += 1

    record_audit(
        db,
        action="consent.revoked",
        actor_user_id=actor.id,
        entity_type="consent",
        entity_id=str(consent.id),
        detail={"case_id": str(consent.case_id), "reason": consent.revoke_reason},
    )
    notify_roles(
        db,
        role_codes=("TECHNICAL_SUPERVISOR",),
        event_code="consent.revoked",
        title=f"ابطال رضایت - پرونده {case.case_number if case else '-'}",
        body="یک رضایت معتبر باطل شد؛ ادامه ثبت داده درمانی مشمول کنترل رضایت است.",
        category="consent",
        severity="warning",
        entity_type="case",
        entity_id=str(consent.case_id),
    )
    db.commit()
    return {
        "id": str(consent.id),
        "status": consent.status,
        "revoked_at": consent.revoked_at.isoformat() if consent.revoked_at else None,
        "revoke_reason": consent.revoke_reason,
        "consent_date": consent.consent_date.isoformat() if consent.consent_date else date.today().isoformat(),
    }
