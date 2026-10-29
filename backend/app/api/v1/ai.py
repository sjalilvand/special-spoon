"""فاز ۳۵ - B25/B26/B27 سند جامع: دستیار هوشمند — تصمیم D07 (پلاگین‌پذیر).
فاز ۵۳ - عامل هوشمند (الگوی deepseek-harness): حلقهٔ عامل + ابزار + نشست.

- GET /ai/config: متادیتای شفاف سرویس (سرویس فعال، fallback، سقف نرخ،
  دیسکلیمر) — «کلید سرویس هرگز به کلاینت نمی‌رود»؛
- POST /ai/chat: پاسخ در دامنه اطلاعات عمومی سامانه + دیسکلیمر؛ سقف
  نرخ per user (۴۲۹)؛ هر تعامل در ai_chat_logs ثبت می‌شود (بدون کلید)؛
- فاز ۵۳ (عامل):
  - POST /ai/agent/chat: یک Turn حلقهٔ عامل — مدل با ابزارهای مجاز همان
    کاربر؛ نبود کلید → همان پاسخ قاعده‌محور (fail-soft)؛ هر گام ابزار در
    خروجی با traces شفاف می‌شود؛
  - GET /ai/agent/tools: کاتالوگ ابزارها برای UI؛
  - GET /ai/agent/sessions: نشست‌های کاربر؛
  - GET /ai/agent/sessions/{id}/messages: بازپخش نشست (فقط مالک)؛
  - DELETE /ai/agent/sessions/{id}: حذف نشست خود (آبشاری)؛
- GET /ai/recommendations (B26): پیشنهاد قطعی خدمات هم‌دسته بر پایه
  آخرین سفارش کاربر (B32×B10) — بدون مدل بیرونی؛
- GET /ai/no-show-risk (B27): امتیاز قاعده‌محور عدم‌حضور نوبت‌های
  آینده با عوامل شفاف — فقط کارکنان.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.agent import AgentMessage, AgentSession
from app.models.user import User
from app.services import ai_assistant as ai
from app.services.agent import engine as agent_engine
from app.services.agent import provider as agent_provider
from app.services.agent.tools import build_registry

router = APIRouter(tags=["ai"])


class ChatPayload(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.get("/ai/config")
def ai_config(_actor: User = Depends(get_current_user)) -> dict:
    """شفافیت D07 — بدون هیچ کلیدی در خروجی."""
    return ai.ai_config_out()


@router.post("/ai/chat")
def ai_chat(
    payload: ChatPayload,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    if not ai.check_rate_limit(actor.id):
        raise HTTPException(status_code=429, detail="سقف پیام‌های دستیار پر شد؛ کمی بعد تلاش کنید")
    result = ai.chat(db, actor.id, payload.message)
    return {
        "response": result.response,
        "provider": result.provider,
        "disclaimer": result.disclaimer,
        "latency_ms": result.latency_ms,
    }


@router.get("/ai/recommendations")
def ai_recommendations(
    limit: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """B26 — پیشنهادگر خدمات قاعده‌محور و قطعی."""
    items = ai.recommend_services(db, actor.id, limit)
    return {
        "items": items,
        "note": "پیشنهاد بر پایه دسته‌بندی موضوعی خدمات و آخرین سفارش شماست (قاعده‌محور)",
    }


@router.get("/ai/no-show-risk")
def ai_no_show_risk(
    days_ahead: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR")),
) -> dict:
    """B27 — ریسک عدم‌حضور نوبت‌های آینده (قاعده‌محور، عوامل شفاف)."""
    return ai.no_show_risk(db, days_ahead=days_ahead)


# ============================================================================
# فاز ۵۳ - عامل هوشمند (الگوی deepseek-harness: agent loop + tools + session)
# ============================================================================


class AgentChatPayload(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: uuid.UUID | None = None


@router.get("/ai/agent/config")
def agent_config(actor: User = Depends(get_current_user)) -> dict:
    """شفافیت عامل: سرویس فعال + کاتالوگ ابزارهای مجاز همان کاربر."""
    reg = build_registry()
    return {
        "llm_ready": agent_provider.is_enabled(),
        "agent_available": True,
        "tools": reg.catalog(),
        "disclaimer": ai.ai_config_out()["disclaimer"],
        "_actor_roles": [r.code for r in actor.roles],
    }


@router.post("/ai/agent/chat")
def agent_chat(
    payload: AgentChatPayload,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """یک Turn حلقهٔ عامل؛ نشست تازه در صورت نبود session_id ساخته می‌شود."""
    if not ai.check_rate_limit(actor.id):
        raise HTTPException(status_code=429, detail="سقف پیام‌های دستیار پر شد؛ کمی بعد تلاش کنید")
    if payload.session_id is not None:
        session = db.scalar(
            select(AgentSession).where(
                AgentSession.id == payload.session_id,
                AgentSession.user_id == actor.id,
            )
        )
        if session is None:
            raise HTTPException(status_code=404, detail="نشست یافت نشد")
    else:
        session = AgentSession(
            user_id=actor.id,
            title=(payload.message.strip()[:60] or "گفتگوی جدید"),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    result = agent_engine.run_turn(db, actor, session, payload.message)
    return {
        "session_id": str(session.id),
        "response": result.response,
        "provider": result.provider,
        "fallback_used": result.fallback_used,
        "steps": [
            {
                "tool_name": s.tool_name,
                "tool_title": s.tool_title,
                "args": s.args,
                "result": s.result,
            }
            for s in result.steps
        ],
        "disclaimer": result.disclaimer,
        "latency_ms": result.latency_ms,
    }


@router.get("/ai/agent/sessions")
def agent_sessions(
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """نشست‌های خودِ کاربر (عنوان + زمان به‌روزرسانی)."""
    q = select(AgentSession).where(AgentSession.user_id == actor.id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(AgentSession.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": str(s.id),
                "title": s.title,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in rows
        ],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


@router.get("/ai/agent/sessions/{session_id}/messages")
def agent_session_messages(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """بازپخش نشست (فقط مالک) — الگوی Session Replay در dsh."""
    session = db.scalar(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.user_id == actor.id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="نشست یافت نشد")
    rows = db.scalars(
        select(AgentMessage)
        .where(AgentMessage.session_id == session.id)
        .order_by(AgentMessage.created_at, AgentMessage.id)
        .limit(500)
    ).all()
    return {
        "session_id": str(session.id),
        "title": session.title,
        "items": [
            {
                "role": r.role,
                "content": r.content,
                "tool_name": r.tool_name,
                "tool_args": r.tool_args,
                "tool_result": r.tool_result,
                "provider": r.provider,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.delete("/ai/agent/sessions/{session_id}", status_code=204)
def agent_session_delete(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> None:
    """حذف نشست خودِ کاربر (پیام‌ها آبشاری حذف می‌شوند)."""
    session = db.scalar(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.user_id == actor.id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="نشست یافت نشد")
    db.delete(session)
    db.commit()
