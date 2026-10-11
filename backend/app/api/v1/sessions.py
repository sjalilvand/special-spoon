import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.appointment import (
    Appointment,
    AppointmentStatus,
    Session,
    SessionNoteRevision,
    SessionNoteStatus,
)
from app.models.case import Case, CaseStatus
from app.models.people import Counselor
from app.models.user import User
from app.schemas.schedule import SessionCreate, SessionNoteUpdate
from app.services.audit import record_audit

router = APIRouter(tags=["sessions"])

# بند ۶.۴: هدف، خلاصه وضعیت، مداخله، پاسخ مراجع، تکلیف، پیگیری و یادداشت
NOTE_FIELDS = ("goal", "status_summary", "intervention", "client_response", "homework", "follow_up", "note")


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def _clinical_access(actor, case) -> None:
    """محتوای جلسه بالینی است - فقط مشاور تخصیصی یا مسئول فنی؛ سایر نقش‌ها 404 (بند ۳.۲)."""
    roles = _roles(actor)
    if "TECHNICAL_SUPERVISOR" in roles:
        return
    if "COUNSELOR" in roles:
        c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if c is not None and case.primary_counselor_id == c.id:
            return
    raise HTTPException(status_code=404, detail="پرونده یافت نشد")


def _assigned_counselor(actor, case) -> None:
    if "COUNSELOR" not in _roles(actor):
        raise HTTPException(status_code=403, detail="ثبت جلسه فقط با نقش مشاور و تخصیص جاری مجاز است")
    c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
    if c is None or case.primary_counselor_id != c.id:
        raise HTTPException(status_code=403, detail="این پرونده به شما تخصیص نیافته است")


def _clean_content(raw: dict | None) -> dict:
    out: dict[str, str] = {}
    for k in NOTE_FIELDS:
        v = (raw or {}).get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()[:2000]
    return out


def _session_out(db, s: Session) -> dict:
    c = db.get(Counselor, s.counselor_id)
    revs = db.scalars(
        select(SessionNoteRevision)
        .where(SessionNoteRevision.session_id == s.id)
        .order_by(SessionNoteRevision.version)
    ).all()
    latest = revs[-1] if revs else None
    author = db.get(User, latest.author_user_id) if latest and latest.author_user_id else None
    return {
        "id": str(s.id),
        "case_id": str(s.case_id),
        "session_number": s.session_number,
        "occurred_at": s.occurred_at.isoformat(),
        "appointment_id": str(s.appointment_id) if s.appointment_id else None,
        "counselor_name": (f"{c.first_name} {c.last_name}" if c else None),
        "note_status": latest.status if latest else "draft",
        "note_version": latest.version if latest else 0,
        "content": (latest.content or {}) if latest else {},
        "author_name": author.display_name if author else None,
        "can_edit_note": bool(latest and latest.status == SessionNoteStatus.DRAFT),
        "updated_at": latest.updated_at.isoformat() if latest else None,
    }


def _get_case_or_404(db, case_id) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    return case


def _latest_revision(db, session_id) -> SessionNoteRevision | None:
    return db.scalar(
        select(SessionNoteRevision)
        .where(SessionNoteRevision.session_id == session_id)
        .order_by(SessionNoteRevision.version.desc())
        .limit(1)
    )


@router.get("/cases/{case_id}/sessions")
def list_case_sessions(case_id: uuid.UUID, db=Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = _get_case_or_404(db, case_id)
    _clinical_access(actor, case)
    items = db.scalars(
        select(Session).where(Session.case_id == case.id).order_by(Session.session_number.desc())
    ).all()
    return {"items": [_session_out(db, s) for s in items]}


@router.post("/cases/{case_id}/sessions", status_code=201)
def create_session(case_id: uuid.UUID, payload: SessionCreate, db=Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = _get_case_or_404(db, case_id)
    if case.status in (CaseStatus.CLOSED, CaseStatus.ARCHIVED):
        raise HTTPException(status_code=409, detail="برای پرونده بسته یا بایگانی نمی‌توان جلسه ثبت کرد")
    _assigned_counselor(actor, case)

    appointment = None
    if payload.appointment_id is not None:
        appointment = db.get(Appointment, payload.appointment_id)
        if appointment is None or appointment.case_id != case.id:
            raise HTTPException(status_code=422, detail="نوبت انتخابی به این پرونده تعلق ندارد")
        if appointment.status == AppointmentStatus.CANCELLED:
            raise HTTPException(status_code=409, detail="نوبت لغوشده قابل اتصال به جلسه نیست")

    last_no = db.scalar(select(func.max(Session.session_number)).where(Session.case_id == case.id)) or 0
    s = Session(
        case_id=case.id,
        appointment_id=appointment.id if appointment is not None else None,
        counselor_id=case.primary_counselor_id,
        occurred_at=payload.occurred_at,
        session_number=int(last_no) + 1,
        created_by=actor.id,
    )
    db.add(s)
    db.flush()
    db.add(SessionNoteRevision(
        session_id=s.id, version=1,
        content=_clean_content(payload.content),
        status=SessionNoteStatus.DRAFT,
        author_user_id=actor.id,
    ))
    # اتصال جلسه به نوبت → نوبت «انجام‌شده» می‌شود (بند ۶.۴)
    if appointment is not None and appointment.status != AppointmentStatus.DONE:
        appointment.status = AppointmentStatus.DONE
    db.commit()
    record_audit(db, action="session.created", actor_user_id=actor.id,
                 entity_type="session", entity_id=str(s.id),
                 detail={"session_number": s.session_number})
    return _session_out(db, s)


@router.post("/sessions/{session_id}/note")
def save_note(session_id: uuid.UUID, payload: SessionNoteUpdate, db=Depends(get_db), actor=Depends(get_current_user)) -> dict:
    s = db.get(Session, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد")
    case = _get_case_or_404(db, s.case_id)
    _clinical_access(actor, case)
    latest = _latest_revision(db, s.id)
    if latest is None:
        raise HTTPException(status_code=404, detail="یادداشت یافت نشد")
    if latest.status != SessionNoteStatus.DRAFT:
        raise HTTPException(status_code=409, detail="یادداشت نهایی بی‌ردپا تغییر نمی‌کند؛ نسخه جدید بسازید")
    if latest.author_user_id != actor.id:
        raise HTTPException(status_code=403, detail="فقط نویسنده یادداشت می‌تواند پیش‌نویس را ویرایش کند")
    if payload.expected_version is not None and payload.expected_version != latest.version:
        raise HTTPException(status_code=409, detail="این یادداشت توسط کاربر دیگری تغییر کرده است؛ صفحه را بازخوانی کنید")
    latest.content = _clean_content(payload.content)
    db.commit()
    record_audit(db, action="session.note_updated", actor_user_id=actor.id,
                 entity_type="session", entity_id=str(s.id),
                 detail={"note_version": latest.version})
    return _session_out(db, s)


@router.post("/sessions/{session_id}/note/finalize")
def finalize_note(session_id: uuid.UUID, db=Depends(get_db), actor=Depends(get_current_user)) -> dict:
    s = db.get(Session, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد")
    case = _get_case_or_404(db, s.case_id)
    _clinical_access(actor, case)
    latest = _latest_revision(db, s.id)
    if latest is None:
        raise HTTPException(status_code=404, detail="یادداشت یافت نشد")
    if latest.status != SessionNoteStatus.DRAFT:
        raise HTTPException(status_code=409, detail="این یادداشت قبلاً نهایی شده است")
    if latest.author_user_id != actor.id:
        raise HTTPException(status_code=403, detail="فقط نویسنده یادداشت می‌تواند آن را نهایی کند")
    content = latest.content or {}
    if not any(content.get(k) for k in ("status_summary", "intervention", "note")):
        raise HTTPException(status_code=422, detail="برای نهایی‌سازی، حداقل یکی از «خلاصه وضعیت»، «مداخله» یا «یادداشت» باید ثبت شده باشد")
    latest.status = SessionNoteStatus.FINAL
    db.commit()
    record_audit(db, action="session.note_finalized", actor_user_id=actor.id,
                 entity_type="session", entity_id=str(s.id),
                 detail={"note_version": latest.version})
    return _session_out(db, s)


@router.post("/sessions/{session_id}/note/revisions", status_code=201)
def create_note_revision(session_id: uuid.UUID, db=Depends(get_db), actor=Depends(get_current_user)) -> dict:
    s = db.get(Session, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد")
    case = _get_case_or_404(db, s.case_id)
    _clinical_access(actor, case)
    latest = _latest_revision(db, s.id)
    if latest is None:
        raise HTTPException(status_code=404, detail="یادداشت یافت نشد")
    if latest.status == SessionNoteStatus.DRAFT:
        raise HTTPException(status_code=409, detail="ابتدا پیش‌نویس جاری یادداشت را نهایی کنید")
    rev = SessionNoteRevision(
        session_id=s.id,
        version=latest.version + 1,
        content=dict(latest.content or {}),
        status=SessionNoteStatus.DRAFT,
        author_user_id=actor.id,
    )
    db.add(rev)
    db.commit()
    record_audit(db, action="session.note_revision_created", actor_user_id=actor.id,
                 entity_type="session", entity_id=str(s.id),
                 detail={"note_version": rev.version})
    return _session_out(db, s)
