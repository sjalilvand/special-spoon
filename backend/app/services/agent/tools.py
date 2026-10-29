"""فاز ۵۳ - رجیستری ابزارهای عامل (الگوی Tool Registry سند dsh).

هر ابزار:
- یک تابع پایتونی با امضای ``(db, actor, args) -> dict``؛
- شِمای پارامتر (JSON-Schema سبک) برای معرفی به مدل؛
- برچسب فارسی + سیاست دسترسی: ``staff=True`` یعنی فقط نقش‌های مجاز کارکنان؛
- «فقط‌خواندنی» — هیچ ابزاری داده می‌نویسد یا تغییر نمی‌دهد.

ابزارهای کاربر عادی فقط دادهٔ خودِ کاربر را برمی‌گردانند (data_scope=own
به‌صورت ساختاری تضمین شده چون کوئری‌ها با actor.id فیلتر می‌شوند).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.branch import Branch, BranchStatus
from app.models.catalog import Service, ServiceStatus
from app.models.case import Case, CaseStatus
from app.models.payment import Order
from app.models.topics import ServiceTopic
from app.models.user import User
from app.models.wallet import Wallet

STAFF_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "COUNSELOR", "TECHNICAL_SUPERVISOR")

STATUS_FA = {
    "pending": "در انتظار پرداخت",
    "paid": "پرداخت‌شده",
    "cancelled": "لغو‌شده",
    "failed": "ناموفق",
    "scheduled": "رزروشده",
    "done": "انجام‌شده",
    "no_show": "عدم حضور",
    "new": "جدید",
    "awaiting_assignment": "در انتظار ارجاع",
    "active": "فعال",
    "suspended": "معلق",
    "closed": "بسته",
    "archived": "بایگانی",
}


@dataclass
class Tool:
    """یک ابزار عامل — الگوی typed tool در dsh."""

    name: str
    title: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., dict]
    staff_only: bool = False
    staff_roles: tuple[str, ...] = STAFF_ROLES


def _fmt_money(v) -> str:
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return str(v)


# ----------------------------------------------------------------- ابزارهای عمومی (کاربر)
def tool_search_services(db: Session, actor: User, args: dict) -> dict:
    """جست‌وجوی خدمات فعال سامانه با کلیدواژه."""
    q = (args.get("query") or "").strip()
    limit = min(int(args.get("limit") or 8), 15)
    stmt = select(Service).where(Service.status == ServiceStatus.ACTIVE)
    if q:
        stmt = stmt.where(Service.title.ilike(f"%{q}%"))
    rows = db.scalars(stmt.order_by(Service.title).limit(limit)).all()
    return {
        "count": len(rows),
        "services": [
            {
                "title": s.title,
                "code": s.code,
                "duration_minutes": s.duration_minutes,
                "session_type": {"in_person": "حضوری", "online": "آنلاین", "phone": "تلفنی"}.get(s.session_type, s.session_type),
            }
            for s in rows
        ],
    }


def tool_list_branches(db: Session, actor: User, args: dict) -> dict:
    """فهرست شعب منتشرشده (با فیلتر اختیاری شهر)."""
    city = (args.get("city") or "").strip()
    stmt = select(Branch).where(Branch.status == BranchStatus.PUBLISHED)
    if city:
        stmt = stmt.where(Branch.city.ilike(f"%{city}%"))
    rows = db.scalars(stmt.order_by(Branch.name).limit(15)).all()
    return {
        "count": len(rows),
        "branches": [
            {
                "name": b.name,
                "city": b.city,
                "address": b.address,
                "phone": b.phone,
            }
            for b in rows
        ],
    }


def tool_my_orders(db: Session, actor: User, args: dict) -> dict:
    """خلاصهٔ سفارش‌های خودِ کاربر (فقط دادهٔ خودش)."""
    limit = min(int(args.get("limit") or 10), 20)
    rows = db.scalars(
        select(Order)
        .where(Order.owner_user_id == actor.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "count": len(rows),
        "orders": [
            {
                "order_number": o.order_number,
                "title": o.title,
                "status": STATUS_FA.get(o.status, o.status),
                "payable_amount": _fmt_money(o.payable_amount),
                "created_at": o.created_at.strftime("%Y-%m-%d") if o.created_at else None,
            }
            for o in rows
        ],
    }


def tool_my_appointments(db: Session, actor: User, args: dict) -> dict:
    """نوبت‌های آیندهٔ خودِ کاربر از طریق سفارش‌های متصل به نوبت."""
    now = datetime.now(timezone.utc)
    appt_ids = db.scalars(
        select(Order.appointment_id).where(
            Order.owner_user_id == actor.id, Order.appointment_id.isnot(None)
        )
    ).all()
    if not appt_ids:
        return {"count": 0, "appointments": [], "note": "نوبتی برای شما یافت نشد"}
    rows = db.scalars(
        select(Appointment).where(
            Appointment.id.in_(appt_ids),
            Appointment.scheduled_at >= now,
        ).order_by(Appointment.scheduled_at).limit(10)
    ).all()
    return {
        "count": len(rows),
        "appointments": [
            {
                "scheduled_at": a.scheduled_at.strftime("%Y-%m-%d %H:%M") if a.scheduled_at else None,
                "status": STATUS_FA.get(a.status, a.status),
            }
            for a in rows
        ],
    }


def tool_wallet_balance(db: Session, actor: User, args: dict) -> dict:
    """مانده کیف پول خودِ کاربر."""
    w = db.scalar(select(Wallet).where(Wallet.user_id == actor.id))
    if w is None:
        return {"balance": "0", "currency": "IRR", "note": "کیف پولی برای شما ساخته نشده است"}
    return {"balance": _fmt_money(w.balance), "currency": w.currency}


def tool_service_topics(db: Session, actor: User, args: dict) -> dict:
    """دسته‌بندی موضوعی خدمات (کاتالوگ عمومی)."""
    rows = db.execute(
        select(Service.title, ServiceTopic.topic_id)
        .join(ServiceTopic, ServiceTopic.service_id == Service.id)
        .where(Service.status == ServiceStatus.ACTIVE)
        .limit(60)
    ).all()
    topics: dict[str, list[str]] = {}
    for title, topic_id in rows:
        topics.setdefault(str(topic_id), []).append(title)
    return {"topics": [{"topic_id": k, "services": v[:6]} for k, v in list(topics.items())[:12]]}


# ----------------------------------------------------------------- ابزارهای کارکنان
def tool_cases_summary(db: Session, actor: User, args: dict) -> dict:
    """خلاصهٔ آماری پرونده‌ها بر اساس وضعیت (فقط کارکنان) — بدون محتوای بالینی."""
    rows = db.execute(
        select(Case.status, func.count()).group_by(Case.status)
    ).all()
    items = [{"status": STATUS_FA.get(s, s), "count": int(c)} for s, c in rows]
    return {"summary": items, "total": sum(i["count"] for i in items)}


def tool_no_show_risk(db: Session, actor: User, args: dict) -> dict:
    """ریسک عدم‌حضور نوبت‌های آینده (فقط کارکنان؛ همان منطق B27 قاعده‌محور)."""
    days = min(int(args.get("days_ahead") or 7), 30)
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=days)
    upcoming = db.scalars(
        select(Appointment).where(
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.scheduled_at >= now,
            Appointment.scheduled_at <= until,
        ).order_by(Appointment.scheduled_at).limit(200)
    ).all()
    high = 0
    for a in upcoming:
        prev = db.scalar(
            select(func.count()).select_from(Appointment).where(
                Appointment.case_id == a.case_id,
                Appointment.status == AppointmentStatus.NO_SHOW,
            )
        ) or 0
        if 10 + 25 * int(prev) >= 60:
            high += 1
    return {
        "window_days": days,
        "upcoming_appointments": len(upcoming),
        "high_risk_count": high,
        "note": "امتیاز قاعده‌محور (۱۰ پایه + ۲۵ به‌ازای هر عدم‌حضور قبلی؛ سقف ۹۵)؛ بالای ۶۰ = ریسک بالا",
    }


def tool_upcoming_appointments_staff(db: Session, actor: User, args: dict) -> dict:
    """نوبت‌های آیندهٔ کل سامانه (فقط کارکنان؛ بدون دادهٔ بالینی)."""
    days = min(int(args.get("days_ahead") or 7), 30)
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(Appointment).where(
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.scheduled_at >= now,
            Appointment.scheduled_at <= now + timedelta(days=days),
        ).order_by(Appointment.scheduled_at).limit(15)
    ).all()
    return {
        "count": len(rows),
        "appointments": [
            {
                "scheduled_at": a.scheduled_at.strftime("%Y-%m-%d %H:%M") if a.scheduled_at else None,
                "status": STATUS_FA.get(a.status, a.status),
            }
            for a in rows
        ],
    }


# ----------------------------------------------------------------- رجیستری
@dataclass
class ToolRegistry:
    """رجیستری ابزارها — الگوی ctx.tools در dsh؛ افزودن ابزار = ثبت ردیف جدید."""

    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def catalog(self) -> list[dict]:
        """متادیتای عمومی برای UI (بدون جزئیات داخلی)."""
        return [
            {"name": t.name, "title": t.title, "description": t.description, "staff_only": t.staff_only}
            for t in self.tools.values()
        ]


def build_registry() -> ToolRegistry:
    """ساخت رجیستری پیش‌فرض فاز ۵۳."""
    reg = ToolRegistry()
    reg.register(Tool(
        name="search_services",
        title="جست‌وجوی خدمات",
        description="جست‌وجوی خدمات فعال سامانه با کلیدواژه (نام خدمت)",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "کلیدواژه نام خدمت"},
                "limit": {"type": "integer", "description": "حداکثر تعداد (پیش‌فرض ۸)"},
            },
            "required": [],
        },
        func=tool_search_services,
    ))
    reg.register(Tool(
        name="list_branches",
        title="فهرست شعب",
        description="شعب منتشرشده سامانه با فیلتر اختیاری شهر",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string", "description": "نام شهر برای فیلتر"}},
            "required": [],
        },
        func=tool_list_branches,
    ))
    reg.register(Tool(
        name="my_orders",
        title="سفارش‌های من",
        description="خلاصهٔ سفارش‌های اخیر خودِ کاربر (شماره، وضعیت، مبلغ)",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "حداکثر تعداد (پیش‌فرض ۱۰)"}},
            "required": [],
        },
        func=tool_my_orders,
    ))
    reg.register(Tool(
        name="my_appointments",
        title="نوبت‌های من",
        description="نوبت‌های آیندهٔ خودِ کاربر",
        parameters={"type": "object", "properties": {}, "required": []},
        func=tool_my_appointments,
    ))
    reg.register(Tool(
        name="wallet_balance",
        title="مانده کیف پول",
        description="مانده کیف پول خودِ کاربر",
        parameters={"type": "object", "properties": {}, "required": []},
        func=tool_wallet_balance,
    ))
    reg.register(Tool(
        name="service_topics",
        title="دسته‌بندی خدمات",
        description="گروه‌بندی موضوعی خدمات فعال سامانه",
        parameters={"type": "object", "properties": {}, "required": []},
        func=tool_service_topics,
    ))
    reg.register(Tool(
        name="cases_summary",
        title="خلاصهٔ پرونده‌ها",
        description="تعداد پرونده‌ها بر اساس وضعیت (ابزار کارکنان؛ بدون محتوای بالینی)",
        parameters={"type": "object", "properties": {}, "required": []},
        func=tool_cases_summary,
        staff_only=True,
    ))
    reg.register(Tool(
        name="no_show_risk",
        title="ریسک عدم حضور",
        description="شمار نوبت‌های پرریسک عدم‌حضور در روزهای پیش‌رو (ابزار کارکنان)",
        parameters={
            "type": "object",
            "properties": {"days_ahead": {"type": "integer", "description": "افق روزها (پیش‌فرض ۷)"}},
            "required": [],
        },
        func=tool_no_show_risk,
        staff_only=True,
    ))
    reg.register(Tool(
        name="upcoming_appointments_staff",
        title="نوبت‌های پیش‌رو سامانه",
        description="نوبت‌های آیندهٔ کل سامانه برای برنامه‌ریزی پذیرش (ابزار کارکنان)",
        parameters={
            "type": "object",
            "properties": {"days_ahead": {"type": "integer", "description": "افق روزها (پیش‌فرض ۷)"}},
            "required": [],
        },
        func=tool_upcoming_appointments_staff,
        staff_only=True,
    ))
    return reg


def staff_allowed(user: User, tool: Tool) -> bool:
    """بررسی سیاست دسترسی ابزار — defense in depth (داخل اجرا هم چک می‌شود)."""
    if not tool.staff_only:
        return True
    return bool({r.code for r in user.roles}.intersection(set(tool.staff_roles)))
