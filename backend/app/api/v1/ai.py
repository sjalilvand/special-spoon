"""فاز ۳۵ - B25/B26/B27 سند جامع: دستیار هوشمند — تصمیم D07 (پلاگین‌پذیر).

- GET /ai/config: متادیتای شفاف سرویس (سرویس فعال، fallback، سقف نرخ،
  دیسکلیمر) — «کلید سرویس هرگز به کلاینت نمی‌رود»؛
- POST /ai/chat: پاسخ در دامنه اطلاعات عمومی سامانه + دیسکلیمر؛ سقف
  نرخ per user (۴۲۹)؛ هر تعامل در ai_chat_logs ثبت می‌شود (بدون کلید)؛
- GET /ai/recommendations (B26): پیشنهاد قطعی خدمات هم‌دسته بر پایه
  آخرین سفارش کاربر (B32×B10) — بدون مدل بیرونی؛
- GET /ai/no-show-risk (B27): امتیاز قاعده‌محور عدم‌حضور نوبت‌های
  آینده با عوامل شفاف — فقط کارکنان.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.user import User
from app.services import ai_assistant as ai

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
