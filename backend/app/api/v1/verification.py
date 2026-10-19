"""فاز ۲۸ - B05 سند جامع: بازبینی صلاحیت مشاوران (verification-reviews).

صفحه سند: /verification-reviews - فهرست مدارک در انتظار تأیید و تصویب/رد
آن‌ها توسط مدیر سازمان / مسئول فنی. نتیجه بازبینی مستقیماً بر «قابل رزرو
بودن» مشاور در فهرست عمومی اثر می‌گذارد (قاعده B05).
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.catalog import CounselorCredential, CredentialVerificationStatus
from app.models.people import Counselor
from app.services.audit import record_audit

router = APIRouter(prefix="/verification-reviews", tags=["verification-reviews"])

REVIEW_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR")


class ReviewDecision(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=500)


def _cred_out(db: Session, c: CounselorCredential) -> dict:
    counselor = db.get(Counselor, c.counselor_id)
    return {
        "id": str(c.id),
        "counselor_id": str(c.counselor_id),
        "counselor_name": f"{counselor.first_name} {counselor.last_name}" if counselor else None,
        "counselor_code": counselor.counselor_code if counselor else None,
        "kind": c.kind,
        "title": c.title,
        "license_number": c.license_number,
        "issued_at": c.issued_at.isoformat() if c.issued_at else None,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "file_path": c.file_path,
        "verification_status": c.verification_status,
        "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
        "review_note": c.review_note,
    }


@router.get("")
def list_verification_reviews(
    status: str = Query(default="pending", max_length=20),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*REVIEW_ROLES)),
) -> dict:
    if status not in (CredentialVerificationStatus.PENDING, CredentialVerificationStatus.APPROVED,
                      CredentialVerificationStatus.REJECTED, "all"):
        raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
    q = select(CounselorCredential).order_by(CounselorCredential.created_at.desc())
    if status != "all":
        q = q.where(CounselorCredential.verification_status == status)
    items = db.scalars(q).all()
    return {"items": [_cred_out(db, c) for c in items], "total": len(items)}


@router.post("/{credential_id}")
def review_credential(
    credential_id: uuid.UUID,
    payload: ReviewDecision,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*REVIEW_ROLES)),
) -> dict:
    c = db.get(CounselorCredential, credential_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مدرک یافت نشد")
    if c.verification_status == CredentialVerificationStatus.APPROVED and payload.action == "approve":
        raise HTTPException(status_code=409, detail="این مدرک قبلاً تأیید شده است")
    c.verification_status = (
        CredentialVerificationStatus.APPROVED if payload.action == "approve"
        else CredentialVerificationStatus.REJECTED
    )
    c.reviewed_by = actor.id
    c.reviewed_at = datetime.now(timezone.utc)
    c.review_note = payload.note
    db.commit()
    record_audit(db, action="credential.reviewed", actor_user_id=actor.id,
                 entity_type="counselor_credential", entity_id=str(c.id),
                 detail={"decision": c.verification_status})
    return _cred_out(db, c)
