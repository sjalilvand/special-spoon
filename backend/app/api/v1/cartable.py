"""فاز ۵۹ - کارتابل شخصی هر حساب + مشاهدهٔ سطح دسترسی توسط مدیر.

هر شخص یک کارتابل دارد:
- نمای خودی (``/cartable/me``): هر کاربرِ فعال کارتابل خودش را می‌بیند —
  نقش‌ها، سطح دسترسی روی داده، دسترسی‌های مؤثر گروه‌بندی‌شده بر پایهٔ بخش،
  کارهای در جریان (نمونه‌های فرایند که آخرین گامشان را همین کاربر ثبت کرده)،
  آمار فعالیت و رخدادهای اخیر.
- نمای مدیریتی (``/cartable/users/{user_id}``): مدیر سامانه از صفحهٔ کاربران
  وارد کارتابل هر شخص می‌شود و دقیقاً همان نما را با نقطهٔ نظر آن کاربر
  می‌بیند (بدون امکان ویرایش — فقط مشاهده).

منبع داده‌ها (بدون جدول جدید):
- نقش‌ها/دسترسی‌ها: user_roles + role_permissions + کاتالوگ permissions
- کارهای در جریان: process_instances + آخرین process_instance_events کاربر
- فعالیت‌ها: audit_events (نمای مدیریتی/خودی فقط رخدادهای خود شخص)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.process import ProcessInstance, ProcessInstanceEvent
from app.models.rbac import DATA_SCOPE_TITLES, Permission
from app.models.user import Role, User
from app.services.audit import record_audit

router = APIRouter(prefix="/cartable", tags=["cartable"])

AUDIT_ACTION_LABELS = {
    "auth.login": "ورود به سامانه",
    "auth.login_failed": "ورود ناموفق",
    "user.created": "ایجاد حساب",
    "user.updated": "ویرایش حساب",
    "user.roles_changed": "تغییر نقش‌ها",
    "user.password_reset": "بازنشانی رمز",
    "role.updated": "ویرایش نقش",
    "role.created": "ایجاد نقش",
    "process.created": "تعریف فرایند",
    "process.instance_started": "شروع فرایند",
    "process.event_recorded": "ثبت گام فرایند",
    "process.instance_complete": "تکمیل فرایند",
    "process.instance_cancel": "لغو فرایند",
    "process.instance_suspend": "تعلیق فرایند",
    "process.instance_resume": "ادامه فرایند",
    "case.created": "تشکیل پرونده",
    "case.updated": "ویرایش پرونده",
    "consultation.created": "ثبت درخواست مشاوره",
    "order.created": "ثبت سفارش",
    "payment.confirmed": "تأیید پرداخت",
}


def _audit_label(action: str) -> str:
    if action in AUDIT_ACTION_LABELS:
        return AUDIT_ACTION_LABELS[action]
    base = action.split(".", 1)[0] if "." in action else action
    generic = {
        "process": "فرایند", "case": "پرونده", "chat": "گفتگو",
        "user": "حساب", "role": "نقش", "order": "سفارش", "wallet": "کیف پول",
        "org": "سازمان", "psych": "آزمون", "intake": "پذیرش", "file": "فایل",
        "accounting": "حسابداری", "learning": "آموزش", "support": "پشتیبانی",
    }
    return f"عملیات {generic.get(base, '')}".strip()


def _effective_permissions(user: User) -> set[str]:
    """اجتماع دسترسی‌های نقش‌های کاربر (SYSTEM_ADMIN = همه)."""
    perms: set[str] = set()
    for role in user.roles:
        if role.code == "SYSTEM_ADMIN":
            return {"*"}
        for p in getattr(role, "permissions", []):
            perms.add(p.code)
    return perms


def _permission_sections(db: Session, perms: set[str]) -> dict:
    """دسترسی‌های مؤثر گروه‌بندی‌شده بر پایهٔ بخش (نقشهٔ منو)."""
    if "*" in perms:
        rows = db.scalars(
            select(Permission).order_by(Permission.section, Permission.sort, Permission.code)
        ).all()
        codes = None  # همه
    else:
        if not perms:
            return {"sections": [], "total": 0, "wildcard": False}
        rows = db.scalars(
            select(Permission)
            .where(Permission.code.in_(perms))
            .order_by(Permission.section, Permission.sort, Permission.code)
        ).all()
        codes = perms
    order: list[str] = []
    by_section: dict[str, list[dict]] = {}
    for p in rows:
        if p.section not in by_section:
            by_section[p.section] = []
            order.append(p.section)
        by_section[p.section].append({"code": p.code, "title": p.title})
    unknown = sorted(codes - {p.code for p in rows}) if codes else []
    if unknown:
        order.append("سایر")
        by_section["سایر"] = [{"code": c, "title": c} for c in unknown]
    return {
        "sections": [
            {"section": s, "permissions": by_section[s], "count": len(by_section[s])}
            for s in order
        ],
        "total": len(rows) + len(unknown),
        "wildcard": "*" in perms,
    }


def _open_work(db: Session, user_id) -> list[dict]:
    """کارهای در جریان: نمونه‌های running/suspended که آخرین گام ثبت‌شده‌شان
    توسط همین کاربر است یا فرایند را او شروع کرده — کارتابل عملیاتی شخص."""
    last_event_sq = (
        select(
            ProcessInstanceEvent.instance_id,
            func.max(ProcessInstanceEvent.occurred_at).label("last_at"),
        )
        .group_by(ProcessInstanceEvent.instance_id)
        .subquery()
    )
    last_rows = db.execute(
        select(ProcessInstanceEvent.instance_id, ProcessInstanceEvent.actor_id)
        .join(
            last_event_sq,
            (ProcessInstanceEvent.instance_id == last_event_sq.c.instance_id)
            & (ProcessInstanceEvent.occurred_at == last_event_sq.c.last_at),
        )
    ).all()
    mine = {iid for iid, aid in last_rows if aid == user_id}
    started = set(db.scalars(
        select(ProcessInstance.id).where(ProcessInstance.started_by == user_id)
    ).all())
    target_ids = (mine | started) or {uuid.UUID(int=0)}
    rows = db.scalars(
        select(ProcessInstance)
        .where(
            ProcessInstance.id.in_(target_ids),
            ProcessInstance.status.in_(("running", "suspended")),
        )
        .order_by(desc(ProcessInstance.updated_at))
        .limit(20)
    ).all()
    from app.models.process import ProcessDefinition
    defs = {
        str(d.id): d
        for d in db.scalars(
            select(ProcessDefinition).where(
                ProcessDefinition.id.in_({r.definition_id for r in rows} or {uuid.UUID(int=0)})
            )
        ).all()
    }
    return [
        {
            "id": str(i.id),
            "definition_title": defs[str(i.definition_id)].title if str(i.definition_id) in defs else None,
            "definition_code": defs[str(i.definition_id)].code if str(i.definition_id) in defs else None,
            "subject_label": i.subject_label,
            "subject_type": i.subject_type,
            "status": i.status,
            "current_element_name": i.current_element_name,
            "current_element_id": i.current_element_id,
            "updated_at": i.updated_at.isoformat() if i.updated_at else None,
        }
        for i in rows
    ]


def _cartable_payload(db: Session, user: User, viewer: User) -> dict:
    perms = _effective_permissions(user)
    roles_out = [
        {
            "code": r.code,
            "title": r.title,
            "data_scope": r.data_scope,
            "data_scope_title": DATA_SCOPE_TITLES.get(r.data_scope, r.data_scope),
        }
        for r in sorted(user.roles, key=lambda x: x.code)
    ]
    stats = {
        "open_work": db.scalar(
            select(func.count(ProcessInstance.id)).where(
                ProcessInstance.started_by == user.id,
                ProcessInstance.status.in_(("running", "suspended")),
            )
        ) or 0,
        "recorded_steps": db.scalar(
            select(func.count(ProcessInstanceEvent.id)).where(
                ProcessInstanceEvent.actor_id == user.id
            )
        ) or 0,
        "audit_events": db.scalar(
            select(func.count(AuditEvent.id)).where(AuditEvent.actor_user_id == user.id)
        ) or 0,
    }
    recent = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.actor_user_id == user.id)
        .order_by(desc(AuditEvent.created_at))
        .limit(15)
    ).all()
    work = _open_work(db, user.id)
    return {
        "user": {
            "id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "mobile": user.mobile,
            "status": user.status,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "roles": roles_out,
        "permissions": _permission_sections(db, perms),
        "stats": stats,
        "open_work": work,
        "recent_activity": [
            {
                "id": str(a.id),
                "action": a.action,
                "action_label": _audit_label(a.action),
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "result": a.result,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in recent
        ],
        "viewer_is_admin": viewer.id != user.id,
    }


@router.get("/me")
def my_cartable(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """کارتابل شخصی کاربر جاری — همهٔ حساب‌های فعال."""
    return _cartable_payload(db, actor, actor)


@router.get("/users/{user_id}")
def user_cartable(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSTEM_ADMIN")),
):
    """کارتابل هر شخص از نقطهٔ نظر خودش — فقط مدیر سامانه (صفحهٔ کاربران)."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    payload = _cartable_payload(db, target, actor)
    record_audit(db, action="cartable.viewed", actor_user_id=actor.id,
                 entity_type="user", entity_id=str(user_id))
    return payload
