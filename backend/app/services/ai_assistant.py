"""فاز ۳۵ - B25/B26/B27 سند جامع: دستیار هوشمند — تصمیم D07 (پلاگین‌پذیر).

تصمیم D07 (همان الگوی D02/D03):
- سرویس AI آداپتور قابل‌جایگزین با config است؛ پیش‌فرض «rule» —
  قاعده‌محور، قطعی، بدون کلید و بدون هزینه (پاسخ از دانش ثابت سامانه:
  خدمات/رزرو/سفارش/ساعات/شعب)؛
- «llm» فقط با تنظیم AI_API_KEY فعال می‌شود؛ در نبود کلید به‌جای شکست
  به rule سقوط می‌کند (fail-soft مثل D03)؛ کلید سرویس هرگز به کلاینت
  و به لاگ نمی‌رود؛
- پاسخ دستیار همیشه با دیسکلیمر همراه است: «جایگزین مشاوره حرفه‌ای
  نیست»؛ دامنه پاسخ محدود به اطلاعات عمومی سامانه است (بدون داده
  بالینی)؛ هر تعامل در ai_chat_logs ثبت می‌شود؛
- سقف نرخ: حداکثر RATE_LIMIT پیام در دقیقه برای هر کاربر (in-process).

B26 پیشنهادگر خدمات: قاعده‌محور و قطعی — پیشنهاد خدمات فعالِ هم‌دسته
(B32 service_topics) بر پایه آخرین سفارش/نوبت کاربر؛ بدون مدل بیرونی.
B27 ریسک عدم‌حضور: امتیاز قاعده‌محور برای نوبت‌های آینده — ۱۰ پایه +
۲۵ به‌ازای هر عدم‌حضور قبلی همان کاربر (سقف ۹۵)؛ عوامل در خروجی شفاف است.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import AiChatLog
from app.models.appointment import Appointment, AppointmentStatus
from app.models.catalog import Service, ServiceStatus
from app.models.payment import Order
from app.models.topics import ServiceTopic

RATE_LIMIT_PER_MINUTE = 30

_DISCLAIMER = "این پاسخ جایگزین مشاوره حرفه‌ای نیست؛ برای تصمیم بالینی با مشاور خود تماس بگیرید."

_KNOWLEDGE: list[tuple[tuple[str, ...], str]] = [
    (("رزرو", "نوبت", "وقت", "appointment"), "برای رزرو نوبت از صفحه «رزرو آنلاین» استفاده کنید: خدمت را انتخاب کنید، زمان آزاد را ببینید و پس از ثبت، نوبت برای ۱۵ دقیقه نگهداشت موقت می‌شود و با تأیید نهایی می‌شود."),
    (("سفارش", "پرداخت", "پول", "فاکتور", "order"), "سفارش شما از snapshot قیمت ساخته می‌شود و پس از پرداخت موفق فاکتور با شماره یکتا صادر می‌شود؛ وضعیت سفارش‌ها در صفحه «سفارش و پرداخت» قابل پیگیری است."),
    (("ساعت", "کار", "باز", "تعطیل"), "ساعات کاری مراکز شنبه تا پنجشنبه ۸ تا ۲۰ است؛ ساعت دقیق هر شعبه در صفحه «شعب» مشخص شده است."),
    (("شعبه", "آدرس", "مرکز", "کجا"), "فهرست شعب با شهر و خدمات هر شعبه در صفحه «شعب» و نقشه شعب (نزدیک‌ترین به شما) در صفحه «نقشه شعب» موجود است."),
    (("کیف پول", "اعتبار", "شارژ", "wallet"), "کیف پول را می‌توانید از صفحه «کیف پول» شارژ کنید؛ استردادها به کیف پول شما بازمی‌گردند و مانده همیشه با قفل ردیفی محافظت می‌شود."),
    (("گواهی", "certificate", "دوره", "آزمون"), "گواهی‌های شما پس از قبولی در آزمون یا تکمیل دوره با شماره یکتا صادر می‌شود؛ اعتبارسنجی شماره گواهی در صفحه عمومی «اعتبارسنجی گواهی» است."),
    (("سلام", "درود", "خسته", "وقت بخیر"), "سلام! درباره رزرو نوبت، خدمات، سفارش و پرداخت یا شعب می‌توانم راهنمایی کنم."),
]

_FALLBACK = (
    "این پرسش خارج از دامنه من است. من فقط درباره اطلاعات عمومی سامانه "
    "(رزرو نوبت، خدمات، سفارش و پرداخت، شعب و ساعات کاری، کیف پول و گواهی‌ها) راهنمایی می‌کنم؛ "
    "برای موارد تخصصی با پشتیبانی تیکت بزنید."
)


@dataclass
class ChatResult:
    response: str
    provider: str
    disclaimer: str
    latency_ms: int


def configured_ai_provider(s=None) -> str:
    """D07: نام سرویس پیکربندی‌شده (پیش‌فرض rule)."""
    s = s or get_settings()
    return (getattr(s, "ai_provider", "rule") or "rule").strip().lower()


def active_ai_provider(s=None) -> str:
    """سرویس فعال واقعی — llm فقط با کلید؛ نبود کلید → fallback به rule (fail-soft)."""
    s = s or get_settings()
    provider = configured_ai_provider(s)
    if provider == "llm" and not getattr(s, "ai_api_key", ""):
        return "rule"
    if provider not in ("rule", "llm"):
        return "rule"
    return provider


def ai_config_out(s=None) -> dict:
    """متادیتای عمومی — بدون کلید (شفافیت D07 مثل D03)."""
    s = s or get_settings()
    configured = configured_ai_provider(s)
    active = active_ai_provider(s)
    return {
        "configured_provider": configured,
        "active_provider": active,
        "fallback_applied": configured != active,
        "rate_limit_per_minute": RATE_LIMIT_PER_MINUTE,
        "disclaimer": _DISCLAIMER,
    }


# ---------------------------------------------------------------- rate limit
_rate_bucket: dict[uuid.UUID, deque[float]] = defaultdict(deque)


def check_rate_limit(user_id: uuid.UUID) -> bool:
    """True = مجاز؛ False = سقف پر شده (۴۲۹). پنجره ۶۰ ثانیه in-process."""
    now = time.monotonic()
    bucket = _rate_bucket[user_id]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        return False
    bucket.append(now)
    return True


# ---------------------------------------------------------------- adapters
def _rule_answer(message: str) -> str:
    text = (message or "").strip()
    for keywords, answer in _KNOWLEDGE:
        if any(k in text for k in keywords):
            return answer
    return _FALLBACK


def _llm_answer(message: str) -> str | None:
    """آداپتور LLM — فقط با کلید؛ هر خطا None برمی‌گرداند (fail-soft → rule)."""
    s = get_settings()
    if not getattr(s, "ai_api_key", ""):
        return None
    # در این مخزن اتصال سرویس بیرونی عمداً فعال نیست (بدهی ADR-02 صف کار)؛
    # آداپتور آماده است: پیاده‌سازی تماس با SDK در تولید همین‌جا قرار می‌گیرد.
    return None


def chat(db: Session, user_id: uuid.UUID | None, message: str) -> ChatResult:
    """پاسخ دستیار + ثبت لاگ (بدون کلید، بدون داده بالینی)."""
    started = time.monotonic()
    provider = active_ai_provider()
    answer = None
    if provider == "llm":
        answer = _llm_answer(message)
        if answer is None:
            provider = "rule"
    if answer is None:
        answer = _rule_answer(message)
    latency = int((time.monotonic() - started) * 1000)
    db.add(
        AiChatLog(
            user_id=user_id,
            provider=provider,
            message=(message or "")[:2000],
            response=answer[:4000],
            latency_ms=latency,
        )
    )
    db.commit()
    return ChatResult(response=answer, provider=provider, disclaimer=_DISCLAIMER, latency_ms=latency)


# ---------------------------------------------------------------- B26 پیشنهادگر
def recommend_services(db: Session, user_id: uuid.UUID, limit: int = 5) -> list[dict]:
    """پیشنهاد قطعی: خدمات فعالِ هم‌دستهِ آخرین خدمت سفارش‌شده کاربر (B32×B10)."""
    last_service_id = db.scalar(
        select(Order.service_id)
        .where(Order.owner_user_id == user_id, Order.service_id.isnot(None))
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    if last_service_id is None:
        return []
    topic_ids = db.scalars(
        select(ServiceTopic.topic_id).where(ServiceTopic.service_id == last_service_id)
    ).all()
    if not topic_ids:
        return []
    rows = db.execute(
        select(Service, ServiceTopic.topic_id)
        .join(ServiceTopic, ServiceTopic.service_id == Service.id)
        .where(
            ServiceTopic.topic_id.in_(topic_ids),
            Service.id != last_service_id,
            Service.status == ServiceStatus.ACTIVE,
        )
        .limit(limit)
    ).all()
    out = []
    seen: set[uuid.UUID] = set()
    for svc, topic_id in rows:
        if svc.id in seen:
            continue
        seen.add(svc.id)
        out.append({"service_id": str(svc.id), "title": svc.title, "topic_id": str(topic_id)})
    return out


# ---------------------------------------------------------------- B27 ریسک عدم‌حضور
def no_show_risk(db: Session, *, days_ahead: int = 7) -> dict:
    """امتیاز ریسک عدم‌حضور نوبت‌های آینده — قاعده‌محور و شفاف:
    پایه ۱۰ + ۲۵×تعداد عدم‌حضور قبلی همان کاربر (سقف ۹۵)."""
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=days_ahead)
    appts = db.scalars(
        select(Appointment)
        .where(
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.scheduled_at >= now,
            Appointment.scheduled_at <= until,
        )
        .order_by(Appointment.scheduled_at)
        .limit(200)
    ).all()
    items = []
    for a in appts:
        prev_no_show = db.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.case_id == a.case_id,
                Appointment.status == AppointmentStatus.NO_SHOW,
            )
        ) or 0
        prev_no_show = int(prev_no_show)
        score = min(95, 10 + 25 * prev_no_show)
        items.append(
            {
                "appointment_id": str(a.id),
                "case_id": str(a.case_id) if a.case_id else None,
                "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
                "previous_no_shows": prev_no_show,
                "risk_score": score,
                "risk_level": "بالا" if score >= 60 else "متوسط" if score >= 35 else "کم",
                "factors": ["تاریخچه عدم‌حضور" if prev_no_show else "بدون سابقه عدم‌حضور"],
            }
        )
    items.sort(key=lambda x: (-x["risk_score"], x["scheduled_at"] or ""))
    return {
        "window_days": days_ahead,
        "count": len(items),
        "items": items,
        "note": "امتیاز قاعده‌محور و قطعی است (D07: پیش‌فرض بدون مدل بیرونی)؛ صرفاً اولویت‌بندی پیگیری است",
    }
