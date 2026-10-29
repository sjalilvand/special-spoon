"""فاز ۵۲ - چت آنلاین داخلی: گفتگوی دو نفره + اتاق مشاورهٔ گروهی.

معماری:
- REST برای تاریخچه/ارسال/خوانده‌شدن/صوت — منبع حقیقت همیشه دیتابیس است
  (نگهداری دائمی پیام‌ها و صوت‌ها مطابق نیازمندی)؛
- WebSocket (``/api/v2/chat/ws``) فقط لایهٔ زنده‌رسانی است: پیام تازه،
  «در حال نوشتن…» و رسید خواندن؛ قطع WS به عملکرد آسیب نمی‌زند (fail-open
  مثل بند ۶ ADR-05) — فرانت به‌صورت دوره‌ای sync می‌کند؛
- پیام صوتی: آپلود multipart (ogg/webm؛ سقف ۵ مگابایت) → ذخیرهٔ bytea در
  messages.media_data → پخش از ``GET /chat/media/{message_id}`` با احراز
  عضویت؛
- دعوت به مشاوره: افزودن عضو به گفتگو (dm → group) با پیام سیستمی.

نکتهٔ مسیر: کلاینت‌های v2 همین روت‌ها را زیر /api/v2 می‌بینند (سوارشدن
دوبارهٔ روترها در main.py)؛ WebSocket نیز زیر همان پیشوند سرو می‌شود.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, WebSocket, WebSocketDisconnect,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import decode_access_token
from app.db.session import SessionLocal, get_db
from app.models.chat import (
    TEXT_MAX_LEN,
    VOICE_MAX_BYTES,
    Conversation,
    ConversationKind,
    ConversationMember,
    Message,
    MessageKind,
)
from app.models.user import User, UserStatus
from app.services.audit import record_audit

router = APIRouter(prefix="/chat", tags=["chat"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

# mime مجاز برای پیام صوتی (فاز ۶۱: بارگذاری فایل صوتی هم مسیر همین پایان‌گاه است)
VOICE_MIMES = ("audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/x-m4a", "audio/aac", "audio/3gpp")


# ---------------------------------------------------------------------------
# مدیر اتصال‌های زنده (در-فرایند؛ استقرار فعلی تک‌ورکر uvicorn است)
# ---------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[uuid.UUID, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._conns.setdefault(user_id, set()).add(ws)

    async def disconnect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._conns.get(user_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self._conns.pop(user_id, None)

    async def push_to_users(self, user_ids: set[uuid.UUID], payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False)
        async with self._lock:
            targets = [
                (ws, uid)
                for uid in user_ids
                for ws in list(self._conns.get(uid, ()))
            ]
        for ws, uid in targets:
            try:
                await ws.send_text(data)
            except Exception:
                await self.disconnect(uid, ws)


manager = ConnectionManager()


def _member_ids(db: Session, conversation_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        db.scalars(
            select(ConversationMember.user_id).where(
                ConversationMember.conversation_id == conversation_id
            )
        ).all()
    )


def _require_membership(db: Session, conversation_id: uuid.UUID, user: User) -> ConversationMember:
    m = db.get(ConversationMember, (conversation_id, user.id))
    if m is None:
        raise HTTPException(status_code=403, detail="به این گفتگو دسترسی ندارید")
    return m


def _conv_member_users(db: Session, convs: list[Conversation], me: User) -> dict:
    """شناسنامهٔ اعضا (batch) برای serialize لیست گفتگوها."""
    user_ids: set[uuid.UUID] = set()
    for c in convs:
        for m in c.members:
            user_ids.add(m.user_id)
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    uinfo = {u.id: u for u in users}

    # آخرین پیام هر گفتگو + شمارندهٔ نخوانده‌ها
    last_msgs: dict[uuid.UUID, Message | None] = {}
    unread: dict[uuid.UUID, int] = {}
    for c in convs:
        my = next((m for m in c.members if m.user_id == me.id), None)
        q = select(Message).where(Message.conversation_id == c.id)
        last = db.scalars(q.order_by(Message.created_at.desc()).limit(1)).first()
        last_msgs[c.id] = last
        if my is not None and my.last_read_message_id is not None:
            last_read = db.get(Message, my.last_read_message_id)
            if last_read is not None:
                unread[c.id] = db.scalar(
                    select(func.count()).select_from(Message).where(
                        Message.conversation_id == c.id,
                        Message.created_at > last_read.created_at,
                        Message.sender_id != me.id,
                    )
                ) or 0
            else:
                unread[c.id] = 0
        else:
            unread[c.id] = db.scalar(
                select(func.count()).select_from(Message).where(
                    Message.conversation_id == c.id,
                    Message.sender_id != me.id,
                )
            ) or 0
    return {"users": uinfo, "last": last_msgs, "unread": unread}


def _serialize_member(m: ConversationMember, uinfo: dict) -> dict:
    u = uinfo.get(m.user_id)
    return {
        "user_id": str(m.user_id),
        "username": u.username if u else None,
        "display_name": u.display_name if u else None,
        "roles": sorted(r.code for r in u.roles) if u else [],
    }


def _serialize_conversation(db: Session, c: Conversation, me: User, ctx: dict) -> dict:
    uinfo = ctx["users"]
    last = ctx["last"].get(c.id)
    others = [m for m in c.members if m.user_id != me.id]
    title = c.title or (
        "، ".join(u.display_name for u in (uinfo.get(m.user_id) for m in others) if u)
        or "گفتگو"
    )
    last_out = None
    if last is not None:
        sender = uinfo.get(last.sender_id)
        last_out = {
            "id": str(last.id),
            "kind": last.kind,
            "preview": (
                (last.body[:80] if last.body else "پیام صوتی")
                if last.kind != MessageKind.SYSTEM else (last.body or "")
            ),
            "sender_name": sender.display_name if sender else None,
            "created_at": last.created_at.isoformat(),
        }
    return {
        "id": str(c.id),
        "kind": c.kind,
        "title": title,
        "members": [_serialize_member(m, uinfo) for m in c.members],
        "unread": ctx["unread"].get(c.id, 0),
        "last_message": last_out,
        "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        "created_at": c.created_at.isoformat(),
    }


def _serialize_message(m: Message, uinfo: dict) -> dict:
    sender = uinfo.get(m.sender_id)
    out = {
        "id": str(m.id),
        "conversation_id": str(m.conversation_id),
        "kind": m.kind,
        "body": m.body,
        "sender_id": str(m.sender_id) if m.sender_id else None,
        "sender_name": sender.display_name if sender else "سامانه",
        "created_at": m.created_at.isoformat(),
    }
    if m.kind == MessageKind.VOICE:
        out["media"] = {
            "mime": m.media_mime,
            "bytes": m.media_bytes,
            "duration_ms": m.media_duration_ms,
            "url": f"/api/v2/chat/media/{m.id}",
        }
    return out


async def _broadcast_message(db: Session, msg: Message, conv: Conversation, exclude: set[uuid.UUID] | None = None) -> None:
    """ارسال پیام تازه به همهٔ اعضای متصل (زنده‌رسانی WS)."""
    targets = _member_ids(db, conv.id)
    if exclude:
        targets -= exclude
    uinfo_rows = db.scalars(select(User).where(User.id.in_(targets | {msg.sender_id}))).all() if targets else []
    uinfo = {u.id: u for u in uinfo_rows}
    payload = {
        "type": "message",
        "conversation_id": str(conv.id),
        "message": _serialize_message(msg, uinfo),
    }
    await manager.push_to_users(targets, payload)


class StartConversationRequest(BaseModel):
    peer_id: str = Field(min_length=36, max_length=36)


class TextMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=TEXT_MAX_LEN)


class InviteRequest(BaseModel):
    user_ids: list[str] = Field(min_length=1, max_length=10)
    note: str | None = Field(default=None, max_length=500)


class ReadRequest(BaseModel):
    message_id: str


@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    convs = db.scalars(
        select(Conversation)
        .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
        .where(ConversationMember.user_id == actor.id)
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
    ).all()
    ctx = _conv_member_users(db, convs, actor)
    return {"items": [_serialize_conversation(db, c, actor, ctx) for c in convs]}


@router.post("/conversations", status_code=201)
def start_conversation(
    payload: StartConversationRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """گفتگوی دو نفره (get-or-create) با یک کاربر دیگر."""
    try:
        peer_id = uuid.UUID(payload.peer_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="شناسهٔ مخاطب نامعتبر است")
    if peer_id == actor.id:
        raise HTTPException(status_code=422, detail="گفتگو با خودتان ممکن نیست")
    peer = db.get(User, peer_id)
    if peer is None or peer.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=404, detail="کاربر مخاطب یافت نشد یا فعال نیست")

    # get-or-create dm بر اساس اشتراک عضویت دو نفره
    convs = db.scalars(
        select(Conversation).where(
            Conversation.kind == ConversationKind.DM,
            Conversation.id.in_(
                select(ConversationMember.conversation_id).where(
                    ConversationMember.user_id == actor.id
                )
            ),
        )
    ).all()
    for c in convs:
        others = [m.user_id for m in c.members if m.user_id != actor.id]
        if others == [peer.id]:
            ctx = _conv_member_users(db, [c], actor)
            return _serialize_conversation(db, c, actor, ctx)

    conv = Conversation(kind=ConversationKind.DM, created_by_id=actor.id)
    db.add(conv)
    db.flush()
    db.add(ConversationMember(conversation_id=conv.id, user_id=actor.id))
    db.add(ConversationMember(conversation_id=conv.id, user_id=peer.id))
    sys_msg = Message(
        conversation_id=conv.id, kind=MessageKind.SYSTEM,
        body=f"گفتگو آغاز شد.",
    )
    db.add(sys_msg)
    db.commit()
    ctx = _conv_member_users(db, [conv], actor)
    return _serialize_conversation(db, conv, actor, ctx)


@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: uuid.UUID,
    before_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    _require_membership(db, conversation_id, actor)
    limit = max(1, min(limit, 100))
    q = select(Message).where(Message.conversation_id == conversation_id)
    if before_id:
        try:
            before = db.get(Message, uuid.UUID(before_id))
        except ValueError:
            before = None
        if before is not None:
            q = q.where(Message.created_at < before.created_at)
    rows = db.scalars(q.order_by(Message.created_at.desc()).limit(limit)).all()
    rows = list(reversed(rows))
    sender_ids = {m.sender_id for m in rows if m.sender_id is not None}
    uinfo = {u.id: u for u in db.scalars(select(User).where(User.id.in_(sender_ids))).all()} if sender_ids else {}
    return {"items": [_serialize_message(m, uinfo) for m in rows]}


@router.post("/conversations/{conversation_id}/messages")
async def send_text(
    conversation_id: uuid.UUID,
    payload: TextMessageRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    _require_membership(db, conversation_id, actor)
    conv = db.get(Conversation, conversation_id)
    msg = Message(
        conversation_id=conversation_id,
        sender_id=actor.id,
        kind=MessageKind.TEXT,
        body=payload.body.strip(),
        created_at=_utcnow(),
    )
    conv.last_message_at = msg.created_at
    db.add(msg)
    # ارسال‌کننده خودش را خوانده فرض می‌کنیم
    member = db.get(ConversationMember, (conversation_id, actor.id))
    if member:
        member.last_read_message_id = msg.id
    db.commit()
    await _broadcast_message(db, msg, conv)
    return _serialize_message(msg, {actor.id: actor})


@router.post("/conversations/{conversation_id}/voice")
async def send_voice(
    conversation_id: uuid.UUID,
    file: UploadFile = File(...),
    duration_ms: int = Form(default=0),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    _require_membership(db, conversation_id, actor)
    conv = db.get(Conversation, conversation_id)

    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in VOICE_MIMES:
        raise HTTPException(status_code=415, detail=f"فرمت صوتی پشتیبانی نمی‌شود ({mime})")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="فایل صوتی خالی است")
    if len(data) > VOICE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="حجم پیام صوتی بیش از ۵ مگابایت است")

    msg = Message(
        conversation_id=conversation_id,
        sender_id=actor.id,
        kind=MessageKind.VOICE,
        media_data=data,
        media_mime=mime,
        media_bytes=len(data),
        media_duration_ms=max(0, min(int(duration_ms or 0), 10 * 60 * 1000)),
        created_at=_utcnow(),
    )
    conv.last_message_at = msg.created_at
    db.add(msg)
    member = db.get(ConversationMember, (conversation_id, actor.id))
    if member:
        member.last_read_message_id = msg.id
    db.commit()
    await _broadcast_message(db, msg, conv)
    return _serialize_message(msg, {actor.id: actor})


@router.get("/media/{message_id}")
def get_media(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> Response:
    """پخش پیام صوتی — فقط اعضای گفتگو."""
    msg = db.get(Message, message_id)
    if msg is None or msg.kind != MessageKind.VOICE or msg.media_data is None:
        raise HTTPException(status_code=404, detail="رسانه یافت نشد")
    _require_membership(db, msg.conversation_id, actor)
    return Response(
        content=bytes(msg.media_data),
        media_type=msg.media_mime or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )


@router.post("/conversations/{conversation_id}/read")
async def mark_read(
    conversation_id: uuid.UUID,
    payload: ReadRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    _require_membership(db, conversation_id, actor)
    try:
        mid = uuid.UUID(payload.message_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="شناسهٔ پیام نامعتبر است")
    member = db.get(ConversationMember, (conversation_id, actor.id))
    if member is None:
        raise HTTPException(status_code=403, detail="به این گفتگو دسترسی ندارید")
    member.last_read_message_id = mid
    db.commit()
    await manager.push_to_users(
        _member_ids(db, conversation_id) - {actor.id},
        {"type": "read", "conversation_id": str(conversation_id), "user_id": str(actor.id), "message_id": payload.message_id},
    )
    return {"ok": True}


@router.post("/conversations/{conversation_id}/invite")
async def invite_to_conversation(
    conversation_id: uuid.UUID,
    payload: InviteRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """دعوت یک/چند نفر دیگر به گفتگو — گفتگوی دو نفره به «اتاق مشاوره» تبدیل می‌شود."""
    _require_membership(db, conversation_id, actor)
    conv = db.get(Conversation, conversation_id)

    added: list[User] = []
    for raw in payload.user_ids[:10]:
        try:
            uid = uuid.UUID(raw)
        except ValueError:
            raise HTTPException(status_code=422, detail="شناسهٔ کاربر نامعتبر است")
        target = db.get(User, uid)
        if target is None or target.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=404, detail="کاربر دعوت‌شده یافت نشد یا فعال نیست")
        existing = db.get(ConversationMember, (conversation_id, uid))
        if existing is None:
            db.add(ConversationMember(
                conversation_id=conversation_id, user_id=uid, invited_by_id=actor.id,
            ))
            added.append(target)
    if not added:
        raise HTTPException(status_code=409, detail="این کاربران از قبل عضو گفتگو هستند")

    # dm → گروه (اتاق مشاوره) پس از اولین دعوت
    was_dm = conv.kind == ConversationKind.DM
    conv.kind = ConversationKind.GROUP
    names = "، ".join(u.display_name for u in added)
    sys_body = f"{actor.display_name} {names} را به مشاوره دعوت کرد"
    if payload.note:
        sys_body += f" — {payload.note}"
    sys_msg = Message(
        conversation_id=conversation_id, kind=MessageKind.SYSTEM,
        body=sys_body, created_at=_utcnow(),
    )
    conv.last_message_at = sys_msg.created_at
    db.add(sys_msg)
    db.commit()

    # زنده‌رسانی: به اعضای قدیم (پیام) + به دعوت‌شدگان (تا لیست‌شان تازه شود)
    old_members = _member_ids(db, conversation_id) - {a.id for a in added}
    uinfo = {u.id: u for u in db.scalars(select(User).where(User.id.in_(old_members))).all()}
    await manager.push_to_users(old_members, {
        "type": "message",
        "conversation_id": str(conversation_id),
        "message": _serialize_message(sys_msg, uinfo),
    })
    await manager.push_to_users({a.id for a in added} | {actor.id}, {
        "type": "conversation-updated",
        "conversation_id": str(conversation_id),
    })
    ctx = _conv_member_users(db, [conv], actor)
    record_audit(
        db, action="chat.invited", actor_user_id=actor.id,
        entity_type="conversation", entity_id=str(conversation_id),
        detail={"added": [str(a.id) for a in added]},
    )
    return {
        "conversation": _serialize_conversation(db, conv, actor, ctx),
        "added": [{"id": str(a.id), "display_name": a.display_name} for a in added],
        "was_dm": was_dm,
    }


@router.get("/directory")
def chat_directory(
    search: str = "",
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """فهرست حساب‌های فعال برای شروع گفتگو/دعوت (بدون اطلاعات تماس خصوصی)."""
    q = select(User).where(User.status == UserStatus.ACTIVE, User.id != actor.id)
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(User.username.ilike(like), User.display_name.ilike(like)))
    rows = db.scalars(q.order_by(User.display_name).limit(50)).all()
    return {
        "items": [
            {
                "id": str(u.id),
                "username": u.username,
                "display_name": u.display_name,
                "roles": sorted(r.code for r in u.roles),
            }
            for u in rows
        ]
    }


# ---------------------------------------------------------------------------
# WebSocket زنده‌رسانی — ws://…/api/v2/chat/ws?token=<access_token>
# پیام‌های کلاینت: {"type":"typing","conversation_id":…}
# پیام‌های سرور:  message / read / typing / conversation-updated
# ---------------------------------------------------------------------------
def _ws_user(ws: WebSocket, db: Session) -> User | None:
    token = ws.query_params.get("token") or ""
    try:
        payload = decode_access_token(token)
    except Exception:
        return None
    try:
        user = db.get(User, uuid.UUID(payload["sub"]))
    except Exception:
        return None
    if user is None or user.status != UserStatus.ACTIVE:
        return None
    if payload.get("ver") != user.auth_version:
        return None
    return user


@router.websocket("/ws")
async def chat_ws(ws: WebSocket) -> None:
    db = SessionLocal()
    try:
        user = _ws_user(ws, db)
        if user is None:
            await ws.close(code=4401)
            return
        # فقط اعضای گفتگوهای موجود را ثبت می‌کنیم؛ هر اتصال شنوندهٔ خودش است
        await manager.connect(user.id, ws)
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    data = json.loads(raw)
                except ValueError:
                    continue
                mtype = data.get("type")
                if mtype == "typing":
                    try:
                        cid = uuid.UUID(str(data.get("conversation_id")))
                    except ValueError:
                        continue
                    member = db.get(ConversationMember, (cid, user.id))
                    if member is None:
                        continue
                    await manager.push_to_users(
                        _member_ids(db, cid) - {user.id},
                        {"type": "typing", "conversation_id": str(cid),
                         "user_id": str(user.id), "display_name": user.display_name},
                    )
                elif mtype == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(user.id, ws)
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass
    finally:
        db.close()
