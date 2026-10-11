import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.case import Case, CaseStatus
from app.models.people import Counselor
from app.models.recommendation import Recommendation
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(tags=["recommendations"])


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def _clinical_access(db: Session, actor, case: Case) -> None:
    """توصیه‌ها بخشی از محتوای بالینی‌اند - مشاور تخصیصی یا مسئول فنی (بند ۳.۲)."""
    roles = _roles(actor)
    if "TECHNICAL_SUPERVISOR" in roles:
        return
    if "COUNSELOR" in roles:
        c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if c is not None and case.primary_counselor_id == c.id:
            return
    raise HTTPException(status_code=404, detail="پرونده یافت نشد")


def _assigned_counselor(db: Session, actor, case: Case) -> None:
    if "COUNSELOR" not in _roles(actor):
        raise HTTPException(status_code=403, detail="ثبت توصیه فقط با نقش مشاور و تخصیص جاری مجاز است")
    c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
    if c is None or case.primary_counselor_id != c.id:
        raise HTTPException(status_code=403, detail="این پرونده به شما تخصیص نیافته است")


class RecommendationCreate(BaseModel):
    content: str = Field(min_length=3, max_length=2000)


def _out(db: Session, r: Recommendation) -> dict:
    publisher = db.get(User, r.published_by) if r.published_by else None
    return {
        "id": str(r.id),
        "case_id": str(r.case_id),
        "content": r.content,
        "is_published": r.is_published,
        "published_at": r.published_at.isoformat() if r.published_at else None,
        "published_by_name": publisher.display_name if publisher else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/cases/{case_id}/recommendations")
def list_recommendations(case_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    _clinical_access(db, actor, case)
    items = db.scalars(
        select(Recommendation).where(Recommendation.case_id == case.id).order_by(Recommendation.created_at.desc())
    ).all()
    return {"items": [_out(db, r) for r in items]}


@router.post("/cases/{case_id}/recommendations", status_code=201)
def create_recommendation(case_id: uuid.UUID, payload: RecommendationCreate, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    if case.status in (CaseStatus.CLOSED, CaseStatus.ARCHIVED):
        raise HTTPException(status_code=409, detail="برای پرونده بسته یا بایگانی نمی‌توان توصیه ثبت کرد")
    _assigned_counselor(db, actor, case)
    r = Recommendation(case_id=case.id, content=payload.content.strip(), created_by=actor.id)
    db.add(r)
    db.commit()
    record_audit(db, action="recommendation.created", actor_user_id=actor.id,
                 entity_type="recommendation", entity_id=str(r.id))
    return _out(db, r)


@router.post("/recommendations/{recommendation_id}/publish")
def publish_recommendation(recommendation_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    r = db.get(Recommendation, recommendation_id)
    if r is None:
        raise HTTPException(status_code=404, detail="توصیه یافت نشد")
    case = db.get(Case, r.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    _assigned_counselor(db, actor, case)
    if r.is_published:
        raise HTTPException(status_code=409, detail="این توصیه قبلاً منتشر شده است")
    r.is_published = True
    r.published_by = actor.id
    r.published_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, action="recommendation.published", actor_user_id=actor.id,
                 entity_type="recommendation", entity_id=str(r.id))
    return _out(db, r)
