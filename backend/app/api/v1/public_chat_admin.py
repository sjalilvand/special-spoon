"""فاز ۵۵ - پنل پذیرش/مدیر: مشاهدهٔ گفتگوهای عمومی سایت و امتیازها.

پرسش کاربر: «چه کسی چه پرسیده و چه امتیازی داده؟»

- GET  /public-chat/admin/stats               کارت‌های آماری (تعداد/میانگین امتیاز/توزیع/نیت‌ها)
- GET  /public-chat/admin/sessions            فهرست نشست‌ها با فیلتر جست‌وجو/وضعیت/امتیاز/بازه
- GET  /public-chat/admin/sessions/{id}/messages   ترنسکریپت کامل گفتگو
- PUT  /public-chat/admin/sessions/{id}       یادداشت پذیرش + بستن/بازکردن گفتگو

همهٔ روت‌ها با ``require_perm("chat.public_monitor")`` محافظت می‌شوند؛
SYSTEM_ADMIN به‌صورت ذاتی دسترسی کامل دارد.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.db.session import get_db
from app.models.public_chat import CONTENT_MAX_LEN, PublicChatMessage, PublicChatSession
from app.models.user import User
from app.services import public_chat as engine
from app.services.audit import record_audit

router = APIRouter(prefix="/public-chat/admin", tags=["public-chat-admin"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
PREVIEW_LEN = 120


def _preview(text: str | None, limit: int = PREVIEW_LEN) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _session_row(db: Session, s: PublicChatSession, user: User | None,
                 first_q: str | None, last_msg: PublicChatMessage | None) -> dict:
    """خلاصهٔ یک نشست برای جدول پنل — «چه کسی چه پرسیده» در یک نگاه."""
    if user is not None:
        display_name = user.username
        who = "user"
    elif s.visitor_name:
        display_name = s.visitor_name
        who = "guest"
    else:
        display_name = "مهمان"
        who = "guest"
    return {
        "id": str(s.id),
        "who": who,
        "display_name": display_name,
        "username": user.username if user else None,
        "visitor_name": s.visitor_name,
        "is_registered": s.user_id is not None,
        "ip": s.ip,
        "user_agent": s.user_agent,
        "first_page": s.first_page,
        "status": s.status,
        "rating": s.rating,
        "rating_comment": s.rating_comment,
        "staff_note": s.staff_note,
        "handled_by": None,
        "handled_at": s.handled_at.isoformat() if s.handled_at else None,
        "message_count": s.message_count,
        "first_question": _preview(first_q),
        "last_message": _preview(last_msg.content) if last_msg else None,
        "last_role": last_msg.role if last_msg else None,
        "last_message_at": last_msg.created_at.isoformat() if last_msg else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _load_users(db: Session, sessions: list[PublicChatSession]) -> dict[str, User]:
    ids = {s.user_id for s in sessions if s.user_id}
    if not ids:
        return {}
    rows = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {str(u.id): u for u in rows}


def _load_message_edges(db: Session, session_ids: list[uuid.UUID]) -> dict[str, tuple[str | None, PublicChatMessage | None]]:
    """اولین پرسش کاربر + آخرین پیام هر نشست — با یک کوئری (بدون N+1)."""
    if not session_ids:
        return {}
    rows = db.scalars(
        select(PublicChatMessage)
        .where(PublicChatMessage.session_id.in_(session_ids))
        .order_by(PublicChatMessage.session_id, PublicChatMessage.created_at, PublicChatMessage.id)
    ).all()
    out: dict[str, tuple[str | None, PublicChatMessage | None]] = {}
    for r in rows:
        key = str(r.session_id)
        first_q, last = out.get(key, (None, None))
        if first_q is None and r.role == "user":
            first_q = r.content
        out[key] = (first_q, r)
    return out


@router.get("/stats")
def stats(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_perm("chat.public_monitor")),
) -> dict:
    """کارت‌های آماری پنل — نگاه کلی بدون باز کردن تک‌تک گفتگوها."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)

    total = db.scalar(select(func.count()).select_from(PublicChatSession)) or 0
    last7 = db.scalar(
        select(func.count()).select_from(PublicChatSession).where(PublicChatSession.created_at >= week_ago)
    ) or 0
    today = db.scalar(
        select(func.count()).select_from(PublicChatSession).where(PublicChatSession.created_at >= day_ago)
    ) or 0
    open_count = db.scalar(
        select(func.count()).select_from(PublicChatSession).where(PublicChatSession.status == "open")
    ) or 0
    rated = db.scalar(
        select(func.count()).select_from(PublicChatSession).where(PublicChatSession.rating.isnot(None))
    ) or 0
    avg = db.query(func.avg(PublicChatSession.rating)).filter(
        PublicChatSession.rating.isnot(None)
    ).scalar()

    dist_raw = db.execute(
        select(PublicChatSession.rating, func.count())
        .where(PublicChatSession.rating.isnot(None))
        .group_by(PublicChatSession.rating)
    ).all()
    distribution = {str(k): v for k, v in dist_raw}

    intents_raw = db.execute(
        select(PublicChatMessage.intent, func.count())
        .where(PublicChatMessage.role == "assistant", PublicChatMessage.intent.isnot(None))
        .group_by(PublicChatMessage.intent)
        .order_by(func.count().desc())
        .limit(8)
    ).all()

    return {
        "total": int(total),
        "last_7d": int(last7),
        "today": int(today),
        "open": int(open_count),
        "rated": int(rated),
        "avg_rating": round(float(avg), 2) if avg is not None else None,
        "distribution": distribution,
        "top_intents": [{"intent": k, "count": int(v)} for k, v in intents_raw],
    }


@router.get("/sessions")
def list_sessions(
    q: str = "",
    status: str = "",
    rating: str = "",   # "" | rated | unrated | 1..5
    days: int = 0,      # 0 = همه؛ 1/7/30 = بازهٔ اخیر
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_perm("chat.public_monitor")),
) -> dict:
    """فهرست نشست‌های گفتگوی عمومی — هویت + پرسش اول + امتیاز در یک نگاه."""
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    stmt = select(PublicChatSession, User).outerjoin(User, PublicChatSession.user_id == User.id)

    if status in ("open", "closed"):
        stmt = stmt.where(PublicChatSession.status == status)
    if rating == "rated":
        stmt = stmt.where(PublicChatSession.rating.isnot(None))
    elif rating == "unrated":
        stmt = stmt.where(PublicChatSession.rating.is_(None))
    elif rating in ("1", "2", "3", "4", "5"):
        stmt = stmt.where(PublicChatSession.rating == int(rating))
    if days and days > 0:
        stmt = stmt.where(PublicChatSession.created_at >= datetime.now(timezone.utc) - timedelta(days=days))
    if q.strip():
        needle = f"%{q.strip()}%"
        # جست‌وجو در هویت (نام کاربری/نام معرفی‌شده/IP) + پرسش‌های داخل گفتگو
        msg_ids = select(PublicChatMessage.session_id).where(PublicChatMessage.content.ilike(needle))
        stmt = stmt.where(
            or_(
                PublicChatSession.visitor_name.ilike(needle),
                PublicChatSession.ip.ilike(needle),
                PublicChatSession.rating_comment.ilike(needle),
                PublicChatSession.first_page.ilike(needle),
                PublicChatSession.staff_note.ilike(needle),
                User.username.ilike(needle),
                PublicChatSession.id.in_(msg_ids),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    rows = db.execute(
        stmt.order_by(PublicChatSession.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    sessions = [r[0] for r in rows]
    users = {str(u.id): u for r in rows if (u := r[1])}
    edges = _load_message_edges(db, [s.id for s in sessions])

    items = []
    for s in sessions:
        first_q, last_msg = edges.get(str(s.id), (None, None))
        items.append(_session_row(db, s, users.get(str(s.user_id)) if s.user_id else None, first_q, last_msg))

    return {"items": items, "total": int(total), "page": page, "page_size": page_size}


@router.get("/sessions/{session_id}/messages")
def session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("chat.public_monitor")),
) -> dict:
    """ترنسکریپت کامل گفتگو + خلاصهٔ هویت/امتیاز برای سربرگ دیالوگ."""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="شناسهٔ نشست نامعتبر است")
    s = db.get(PublicChatSession, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد")
    user = db.get(User, s.user_id) if s.user_id else None
    handled_by = db.get(User, s.handled_by_user_id) if s.handled_by_user_id else None

    row = _session_row(db, s, user, None, None)
    row["handled_by"] = handled_by.display_name or handled_by.username if handled_by else None
    # پرسش اول برای سربرگ دیالوگ
    first_user = db.scalar(
        select(PublicChatMessage)
        .where(PublicChatMessage.session_id == s.id, PublicChatMessage.role == "user")
        .order_by(PublicChatMessage.created_at, PublicChatMessage.id)
        .limit(1)
    )
    row["first_question"] = first_user.content if first_user else None

    return {"session": row, "messages": engine.session_messages(db, s)}


class SessionUpdate(BaseModel):
    staff_note: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(open|closed)$")


@router.put("/sessions/{session_id}")
def update_session(
    session_id: str,
    payload: SessionUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("chat.public_monitor")),
) -> dict:
    """ثبت یادداشت پذیرش/مدیر و بستن/بازکردن گفتگو (پیگیری پذیرش)."""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="شناسهٔ نشست نامعتبر است")
    s = db.get(PublicChatSession, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد")

    changed: dict = {}
    if payload.staff_note is not None:
        s.staff_note = payload.staff_note.strip()[:2000] or None
        changed["staff_note"] = bool(s.staff_note)
    if payload.status is not None and payload.status != s.status:
        s.status = payload.status
        changed["status"] = payload.status
    if changed:
        s.handled_by_user_id = actor.id
        s.handled_at = datetime.now(timezone.utc)
        db.commit()
        record_audit(
            db, action="public_chat.session_handled", actor_user_id=actor.id,
            entity_type="public_chat_session", entity_id=str(s.id), detail=changed,
        )
    return {"status": "ok", "session_status": s.status, "staff_note": s.staff_note}


# ------------------------------------------------------------------ فاز ۵۶ - پاسخ زندهٔ اپراتور
class OperatorReply(BaseModel):
    content: str = Field(min_length=1, max_length=CONTENT_MAX_LEN)


@router.post("/sessions/{session_id}/reply", status_code=201)
def reply_to_session(
    session_id: str,
    payload: OperatorReply,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("chat.public_reply")),
) -> dict:
    """پاسخ زندهٔ پذیرش/مدیر — مستقیم در ویجت عمومی بازدیدکننده نمایش داده می‌شود.
    تا ۱۵ دقیقه پس از پاسخ اپراتور، دستیار خودکار پیام خودکار نمی‌فرستد."""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="شناسهٔ نشست نامعتبر است")
    s = db.get(PublicChatSession, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد")
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="متن پیام خالی است")

    sender = (actor.display_name or actor.username or "پذیرش").strip()
    msg = engine.operator_reply(db, s, content, sender)
    if s.status != "open":
        # پاسخ اپراتور به گفتگوی بسته، آن را برای ادامهٔ مکالمه باز می‌کند
        s.status = "open"
        db.commit()
    record_audit(
        db, action="public_chat.operator_reply", actor_user_id=actor.id,
        entity_type="public_chat_session", entity_id=str(s.id),
    )
    return {"message": engine.message_out(msg)}
