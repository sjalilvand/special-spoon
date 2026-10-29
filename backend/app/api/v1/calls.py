"""فاز ۶۱ - تماس تلفنی مدیریت‌شده در گفتگو + نظرسنجی پس از پایان تماس.

چرخهٔ تماس:
1) ``POST /calls/start``     — تماس‌گیرنده از گفتگو تماس می‌زند → status=ringing
   (WS: به گیرندهٔ event=incoming؛ پیام سیستمی در گفتگو)
2) ``POST /calls/{id}/answer``  — گیرنده پاسخ می‌دهد → status=ongoing
3) ``POST /calls/{id}/decline`` — گیرنده رد می‌کند → status=declined
4) ``POST /calls/{id}/end``     — هر طرف تماس را پایان می‌دهد → status=ended
   + مدت محاسبه + نظرسنجی پیش‌فرض به گیرنده تخصیص می‌یابد
   (WS: survey_pending + اعلان درون‌برنامه‌ای)

نکتهٔ واقع‌گرایانه: صدا در تماس تلفنی از بستر تلفن منتقل می‌شود (مرکز با
مراجع تلفنی حرف می‌زند)؛ سامانه چرخهٔ تماس، مدت، ثبت رخداد و نظرسنجی را
مدیریت می‌کند. اگر میکروفون مرورگر در دسترس باشد، طرفین می‌توانند پیام
صوتی هم بفرستند.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.chat import _broadcast_message, _member_ids, _require_membership, _utcnow
from app.db.session import get_db
from app.models.chat import Conversation, Message, MessageKind
from app.models.forms import CallSession, FormTemplate
from app.models.notification import Notification
from app.models.user import User, UserStatus
from app.services.audit import record_audit

router = APIRouter(prefix="/calls", tags=["calls"])


def _call_out(c: CallSession, uinfo: dict) -> dict:
    return {
        "id": str(c.id),
        "conversation_id": str(c.conversation_id) if c.conversation_id else None,
        "caller_id": str(c.caller_id),
        "caller_name": uinfo.get(c.caller_id).display_name if uinfo.get(c.caller_id) else None,
        "callee_id": str(c.callee_id),
        "callee_name": uinfo.get(c.callee_id).display_name if uinfo.get(c.callee_id) else None,
        "phone": c.phone,
        "status": c.status,
        "started_at": c.started_at.isoformat() if c.started_at else None,
        "answered_at": c.answered_at.isoformat() if c.answered_at else None,
        "ended_at": c.ended_at.isoformat() if c.ended_at else None,
        "duration_sec": c.duration_sec,
        "survey_template_id": str(c.survey_template_id) if c.survey_template_id else None,
    }


def _users_map(db: Session, *ids: uuid.UUID | None) -> dict:
    ids = [i for i in ids if i]
    rows = db.scalars(select(User).where(User.id.in_(set(ids)))).all() if ids else []
    return {u.id: u for u in rows}


def _default_call_survey(db: Session) -> FormTemplate | None:
    return db.scalars(
        select(FormTemplate).where(
            FormTemplate.is_default_call_survey.is_(True),
            FormTemplate.is_active.is_(True),
        )
    ).first()


def _system_message(db: Session, conv: Conversation, body: str) -> Message:
    msg = Message(conversation_id=conv.id, kind=MessageKind.SYSTEM, body=body, created_at=_utcnow())
    conv.last_message_at = msg.created_at
    db.add(msg)
    db.flush()
    return msg


class CallStartRequest(BaseModel):
    conversation_id: str = Field(min_length=36, max_length=36)
    phone: str | None = Field(default=None, max_length=30)


@router.post("/start", status_code=201)
async def start_call(
    payload: CallStartRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    try:
        conv_id = uuid.UUID(payload.conversation_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="شناسهٔ گفتگو نامعتبر است")
    _require_membership(db, conv_id, actor)
    conv = db.get(Conversation, conv_id)
    members = [m.user_id for m in conv.members if m.user_id != actor.id]
    if not members:
        raise HTTPException(status_code=422, detail="طرف مقابل برای تماس وجود ندارد")
    callee_id = members[0]  # گفتگوی دو نفره؛ در گروه نخستین عضو دیگر
    callee = db.get(User, callee_id)
    if callee is None or callee.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=404, detail="طرف مقابل فعال نیست")

    # تماس فعال تکراری؟
    existing = db.scalars(
        select(CallSession).where(
            CallSession.conversation_id == conv_id,
            CallSession.status.in_(("ringing", "ongoing")),
        )
    ).all()
    if existing:
        raise HTTPException(status_code=409, detail="یک تماس فعال در این گفتگو وجود دارد")

    call = CallSession(
        conversation_id=conv_id,
        caller_id=actor.id,
        callee_id=callee_id,
        phone=(payload.phone or "").strip() or callee.mobile,
        status="ringing",
        started_at=_utcnow(),
    )
    db.add(call)
    db.flush()

    sys_msg = _system_message(db, conv, f"📞 {actor.display_name} تماس تلفنی برقرار کرد…")
    db.commit()

    uinfo = _users_map(db, actor.id, callee_id)
    # زنده‌رسانی: پیام سیستمی + زنگ به گیرنده
    await _broadcast_message(db, sys_msg, conv)
    await _member_ids_push_call(db, conv_id, {
        "type": "call",
        "event": "incoming",
        "call": _call_out(call, uinfo),
    })
    record_audit(
        db, action="call.started", actor_user_id=actor.id,
        entity_type="call_session", entity_id=str(call.id),
        detail={"callee": str(callee_id), "conversation": str(conv_id)},
    )
    db.commit()
    return _call_out(call, uinfo)


async def _member_ids_push_call(db: Session, conv_id: uuid.UUID, payload: dict) -> None:
    from app.api.v1.chat import manager

    await manager.push_to_users(_member_ids(db, conv_id), payload)


@router.post("/{call_id}/answer")
async def answer_call(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    call = db.get(CallSession, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="تماس یافت نشد")
    if call.callee_id != actor.id:
        raise HTTPException(status_code=403, detail="فقط گیرندهٔ تماس می‌تواند پاسخ دهد")
    if call.status != "ringing":
        raise HTTPException(status_code=409, detail="این تماس در وضعیت زنگ‌خور نیست")
    call.status = "ongoing"
    call.answered_at = _utcnow()
    db.commit()

    uinfo = _users_map(db, call.caller_id, call.callee_id)
    payload = {"type": "call", "event": "answered", "call": _call_out(call, uinfo)}
    if call.conversation_id:
        await _member_ids_push_call(db, call.conversation_id, payload)
    return _call_out(call, uinfo)


@router.post("/{call_id}/decline")
async def decline_call(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    call = db.get(CallSession, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="تماس یافت نشد")
    if call.callee_id != actor.id:
        raise HTTPException(status_code=403, detail="فقط گیرندهٔ تماس می‌تواند رد کند")
    if call.status != "ringing":
        raise HTTPException(status_code=409, detail="این تماس در وضعیت زنگ‌خور نیست")
    call.status = "declined"
    call.ended_at = _utcnow()
    db.commit()

    uinfo = _users_map(db, call.caller_id, call.callee_id)
    payload = {"type": "call", "event": "declined", "call": _call_out(call, uinfo)}
    if call.conversation_id:
        await _member_ids_push_call(db, call.conversation_id, payload)
        conv = db.get(Conversation, call.conversation_id)
        sys_msg = _system_message(db, conv, "تماس پاسخ داده نشد")
        db.commit()
        await _broadcast_message(db, sys_msg, conv)
    return _call_out(call, uinfo)


@router.post("/{call_id}/cancel")
async def cancel_call(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    call = db.get(CallSession, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="تماس یافت نشد")
    if call.caller_id != actor.id:
        raise HTTPException(status_code=403, detail="فقط تماس‌گیرنده می‌تواند لغو کند")
    if call.status != "ringing":
        raise HTTPException(status_code=409, detail="این تماس در وضعیت زنگ‌خور نیست")
    call.status = "cancelled"
    call.ended_at = _utcnow()
    db.commit()

    uinfo = _users_map(db, call.caller_id, call.callee_id)
    payload = {"type": "call", "event": "cancelled", "call": _call_out(call, uinfo)}
    if call.conversation_id:
        await _member_ids_push_call(db, call.conversation_id, payload)
        conv = db.get(Conversation, call.conversation_id)
        sys_msg = _system_message(db, conv, "تماس لغو شد")
        db.commit()
        await _broadcast_message(db, sys_msg, conv)
    return _call_out(call, uinfo)


@router.post("/{call_id}/end")
async def end_call(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    call = db.get(CallSession, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="تماس یافت نشد")
    if actor.id not in (call.caller_id, call.callee_id):
        raise HTTPException(status_code=403, detail="به این تماس دسترسی ندارید")
    if call.status not in ("ringing", "ongoing"):
        raise HTTPException(status_code=409, detail="این تماس پایان یافته است")

    was_ongoing = call.status == "ongoing"
    call.status = "ended"
    call.ended_at = _utcnow()
    if call.answered_at:
        call.duration_sec = max(0, int((call.ended_at - call.answered_at).total_seconds()))
    elif was_ongoing:
        call.duration_sec = max(0, int((call.ended_at - call.started_at).total_seconds()))

    # تخصیص نظرسنجی پیش‌فرض به گیرندهٔ تماس
    survey = _default_call_survey(db)
    if survey is not None:
        call.survey_template_id = survey.id

    uinfo = _users_map(db, call.caller_id, call.callee_id)
    mins = call.duration_sec // 60
    secs = call.duration_sec % 60
    dur_txt = f"{mins}:{secs:02d}" if mins else f"{secs} ثانیه"
    survey_note = " — نظرسنجی برای شما فعال شد" if survey and call.callee_id else ""
    payload = {
        "type": "call",
        "event": "ended",
        "call": _call_out(call, uinfo),
        "survey_template_id": str(call.survey_template_id) if call.survey_template_id else None,
    }
    db.commit()

    if call.conversation_id:
        conv = db.get(Conversation, call.conversation_id)
        sys_msg = _system_message(db, conv, f"تماس پایان یافت — مدت: {dur_txt}{survey_note}")
        db.commit()
        await _broadcast_message(db, sys_msg, conv)
        await _member_ids_push_call(db, call.conversation_id, payload)

    # اعلان درون‌برنامه‌ای برای گیرنده (نظرسنجی پس از تماس)
    if survey is not None:
        db.add(Notification(
            recipient_user_id=call.callee_id,
            category="survey",
            event_code="call.survey_pending",
            title="نظرسنجی پس از تماس",
            body=f"نظرسنجی «{survey.title}» برای شما فعال شد؛ لطفاً تکمیل کنید.",
            entity_type="form_template",
            entity_id=str(survey.id),
        ))
        db.commit()
        from app.api.v1.chat import manager
        await manager.push_to_users(
            {call.callee_id},
            {
                "type": "call",
                "event": "survey_pending",
                "call": _call_out(call, uinfo),
                "template_id": str(call.survey_template_id),
                "template_title": survey.title,
            },
        )

    record_audit(
        db, action="call.ended", actor_user_id=actor.id,
        entity_type="call_session", entity_id=str(call.id),
        detail={"duration_sec": call.duration_sec, "survey": str(call.survey_template_id) if call.survey_template_id else None},
    )
    db.commit()
    return _call_out(call, uinfo)


@router.get("/active")
def active_call(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """تماس فعال من (برای بازسازی وضعیت پس از رفرش صفحه)."""
    call = db.scalars(
        select(CallSession).where(
            or_(CallSession.caller_id == actor.id, CallSession.callee_id == actor.id),
            CallSession.status.in_(("ringing", "ongoing")),
        ).order_by(CallSession.started_at.desc()).limit(1)
    ).first()
    if call is None:
        return {"call": None}
    uinfo = _users_map(db, call.caller_id, call.callee_id)
    return {"call": _call_out(call, uinfo)}


@router.get("/mine")
def my_calls(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    rows = db.scalars(
        select(CallSession).where(
            or_(CallSession.caller_id == actor.id, CallSession.callee_id == actor.id),
            CallSession.status.in_(("ended", "declined", "cancelled")),
        ).order_by(CallSession.started_at.desc()).limit(100)
    ).all()
    uinfo = _users_map(db, *[c.caller_id for c in rows] + [c.callee_id for c in rows])
    return {"items": [_call_out(c, uinfo) for c in rows]}
