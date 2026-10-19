"""فاز ۳۵ - B23 سند جامع: نظرسنجی، شکایت و تیکت پشتیبانی.

قواعد پذیرش:
- نظرسنجی پس از جلسه: هر جلسه حداکثر یک‌بار (uq → ۴۰۹)؛ امتیاز ۱..۵
  (۴۲۲)؛ گزارش میانگین/توزیع فقط برای مدیران/سرپرستان؛
- شکایت: ثبت توسط کاربر احراز‌هویت (کارکنان می‌توانند به‌نام کاربر
  دیگر ثبت کنند)؛ چرخه new → in_review → resolved/rejected فقط با
  مدیران؛ کاربر عادی فقط شکایت خودش را می‌بیند؛ تغییر وضعیت‌های
  نامعتبر ۴۲۲؛ بازبینی شکایت بررسی‌شده مجاز است (بروزرسانی یادداشت)؛
- تیکت: نخ پیام؛ پاسخ کارکنان → answered؛ پاسخ مالک → open؛ بستن
  توسط مالک یا کارکنان؛ «تیکت دیگران برای کاربر عادی ۴۰۳ است»؛
  تیکت بسته پیام جدید قبول نمی‌کند (۴۰۹).
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.appointment import Session
from app.models.support import (
    Complaint,
    ComplaintStatus,
    SessionSurvey,
    Ticket,
    TicketMessage,
    TicketStatus,
)
from app.models.user import User

router = APIRouter(tags=["support"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
STAFF_ROLES = (*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")
VIEW_ROLES = (*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "RECEPTION")


def _is_staff(u: User) -> bool:
    return any(r.code in STAFF_ROLES for r in u.roles)


# ---------------------------------------------------------------- نظرسنجی
class SurveyCreate(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
    respondent_user_id: uuid.UUID | None = None


@router.post("/sessions/{session_id}/survey", status_code=201)
def submit_session_survey(
    session_id: uuid.UUID,
    payload: SurveyCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """نظرسنجی رضایت پس از جلسه — کارکنان یا مالک پرونده؛ یک‌بارمصرف."""
    s = db.get(Session, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد")
    dup = db.scalars(
        select(SessionSurvey).where(SessionSurvey.session_id == session_id)
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="برای این جلسه قبلاً نظرسنجی ثبت شده است")
    respondent = payload.respondent_user_id if payload.respondent_user_id else actor.id
    if not _is_staff(actor) and respondent != actor.id:
        raise HTTPException(status_code=403, detail="ثبت نظرسنجی به‌نام دیگران فقط برای کارکنان مجاز است")
    if db.get(User, respondent) is None:
        raise HTTPException(status_code=404, detail="کاربر پاسخ‌دهنده یافت نشد")
    sv = SessionSurvey(
        session_id=session_id,
        respondent_user_id=respondent,
        score=payload.score,
        comment=payload.comment,
    )
    db.add(sv)
    db.commit()
    db.refresh(sv)
    return {
        "id": str(sv.id),
        "session_id": str(sv.session_id),
        "score": sv.score,
        "comment": sv.comment,
        "created_at": sv.created_at.isoformat() if sv.created_at else None,
    }


@router.get("/reports/survey-summary")
def survey_summary(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    """گزارش رضایت: تعداد، میانگین، توزیع ۱..۵، آخرین نظرات."""
    total = db.scalar(select(func.count()).select_from(SessionSurvey)) or 0
    avg = db.scalar(select(func.coalesce(func.avg(SessionSurvey.score), 0))) or 0
    distribution = {}
    for score in range(1, 6):
        distribution[str(score)] = int(
            db.scalar(
                select(func.count()).select_from(SessionSurvey).where(SessionSurvey.score == score)
            )
            or 0
        )
    recent = db.scalars(
        select(SessionSurvey)
        .where(SessionSurvey.comment.isnot(None))
        .order_by(SessionSurvey.created_at.desc())
        .limit(10)
    ).all()
    return {
        "total": int(total),
        "average": round(float(avg), 2),
        "distribution": distribution,
        "recent_comments": [
            {"score": r.score, "comment": r.comment, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in recent
        ],
    }


# ---------------------------------------------------------------- شکایت
class ComplaintCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=5, max_length=20_000)
    complainant_user_id: uuid.UUID | None = None


class ComplaintReview(BaseModel):
    status: str
    resolution_note: str | None = Field(default=None, max_length=2000)


def _complaint_out(c: Complaint) -> dict:
    return {
        "id": str(c.id),
        "complainant_user_id": str(c.complainant_user_id),
        "subject": c.subject,
        "body": c.body,
        "status": c.status,
        "resolution_note": c.resolution_note,
        "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.post("/complaints", status_code=201)
def create_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    complainant = payload.complainant_user_id or actor.id
    if not _is_staff(actor) and complainant != actor.id:
        raise HTTPException(status_code=403, detail="ثبت شکایت به‌نام دیگران فقط برای کارکنان مجاز است")
    if db.get(User, complainant) is None:
        raise HTTPException(status_code=404, detail="کاربر شاکی یافت نشد")
    c = Complaint(
        complainant_user_id=complainant,
        subject=payload.subject.strip(),
        body=payload.body,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _complaint_out(c)


@router.get("/complaints")
def list_complaints(
    status: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    q = select(Complaint).order_by(Complaint.created_at.desc()).limit(200)
    if _is_staff(actor):
        if status:
            if status not in ComplaintStatus.ALL:
                raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
            q = q.where(Complaint.status == status)
    else:
        q = q.where(Complaint.complainant_user_id == actor.id)
    return {"items": [_complaint_out(c) for c in db.scalars(q).all()]}


@router.patch("/complaints/{complaint_id}/review")
def review_complaint(
    complaint_id: uuid.UUID,
    payload: ComplaintReview,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """بررسی شکایت — فقط مدیران؛ گذار وضعیت محافظت‌شده."""
    c = db.get(Complaint, complaint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="شکایت یافت نشد")
    if payload.status not in ComplaintStatus.ALL or payload.status == ComplaintStatus.NEW:
        raise HTTPException(
            status_code=422, detail="وضعیت بررسی باید in_review، resolved یا rejected باشد"
        )
    if c.status in (ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED) and payload.status not in (
        ComplaintStatus.RESOLVED,
        ComplaintStatus.REJECTED,
    ):
        raise HTTPException(status_code=409, detail="شکایت بسته‌شده به جریان بررسی برنمی‌گردد")
    c.status = payload.status
    c.resolution_note = payload.resolution_note if payload.resolution_note is not None else c.resolution_note
    c.reviewed_by = actor.id
    c.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(c)
    return _complaint_out(c)


# ---------------------------------------------------------------- تیکت
class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=3, max_length=20_000)
    priority: str = Field(default="normal")
    user_id: uuid.UUID | None = None


class TicketMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)


def _ticket_out(db: Session, t: Ticket, *, with_messages: bool = False) -> dict:
    out = {
        "id": str(t.id),
        "user_id": str(t.user_id),
        "subject": t.subject,
        "status": t.status,
        "priority": t.priority,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "messages_count": int(
            db.scalar(select(func.count()).select_from(TicketMessage).where(TicketMessage.ticket_id == t.id))
            or 0
        ),
    }
    if with_messages:
        msgs = db.scalars(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == t.id)
            .order_by(TicketMessage.created_at)
        ).all()
        out["messages"] = [
            {
                "id": str(m.id),
                "sender_user_id": str(m.sender_user_id),
                "body": m.body,
                "is_staff": m.is_staff,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ]
    return out


@router.post("/tickets", status_code=201)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    if payload.priority not in ("normal", "high"):
        raise HTTPException(status_code=422, detail="اولویت باید normal یا high باشد")
    owner = payload.user_id or actor.id
    if not _is_staff(actor) and owner != actor.id:
        raise HTTPException(status_code=403, detail="ثبت تیکت به‌نام دیگران فقط برای کارکنان مجاز است")
    if db.get(User, owner) is None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    t = Ticket(user_id=owner, subject=payload.subject.strip(), priority=payload.priority)
    db.add(t)
    db.flush()
    db.add(TicketMessage(ticket_id=t.id, sender_user_id=actor.id, body=payload.body,
                         is_staff=_is_staff(actor)))
    db.commit()
    db.refresh(t)
    return _ticket_out(db, t)


@router.get("/tickets")
def list_tickets(
    status: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    q = select(Ticket).order_by(Ticket.created_at.desc()).limit(200)
    if _is_staff(actor):
        if status:
            if status not in TicketStatus.ALL:
                raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
            q = q.where(Ticket.status == status)
    else:
        q = q.where(Ticket.user_id == actor.id)
    return {"items": [_ticket_out(db, t) for t in db.scalars(q).all()]}


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد")
    if t.user_id != actor.id and not _is_staff(actor):
        raise HTTPException(status_code=403, detail="تیکت دیگران برای شما قابل مشاهده نیست")
    return _ticket_out(db, t, with_messages=True)


@router.post("/tickets/{ticket_id}/messages", status_code=201)
def add_ticket_message(
    ticket_id: uuid.UUID,
    payload: TicketMessageCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد")
    if t.user_id != actor.id and not _is_staff(actor):
        raise HTTPException(status_code=403, detail="ثبت پیام در تیکت دیگران مجاز نیست")
    if t.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=409, detail="تیکت بسته‌شده پیام جدید قبول نمی‌کند")
    staff = _is_staff(actor)
    db.add(TicketMessage(ticket_id=t.id, sender_user_id=actor.id, body=payload.body, is_staff=staff))
    # چرخه: پاسخ کارکنان → answered؛ پاسخ مالک → open
    t.status = TicketStatus.ANSWERED if staff else TicketStatus.OPEN
    db.commit()
    db.refresh(t)
    return _ticket_out(db, t, with_messages=True)


@router.post("/tickets/{ticket_id}/close")
def close_ticket(
    ticket_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد")
    if t.user_id != actor.id and not _is_staff(actor):
        raise HTTPException(status_code=403, detail="بستن تیکت دیگران مجاز نیست")
    if t.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=409, detail="تیکت قبلاً بسته شده است")
    t.status = TicketStatus.CLOSED
    t.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(t)
    return _ticket_out(db, t)
