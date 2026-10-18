"""B41+ فاز ۲۷ - گزارش انطباق برای نقش حسابرس حفاظت داده (DPO).

GET /api/v1/reports/dpo   گزارش تجمیعی رضایت، دسترسی، فایل و کانال ایمیل

اصول گزارش (بند ۱۵ سند):
- کاملاً تجمیعی؛ هیچ محتوای بالینی فردی یا داده شناسایی‌کننده در خروجی نیست.
- همه شمارش‌ها در بازه پرس‌وجو (پیش‌فرض ۳۰ روز) مگر صریحاً کل گفته شود.
- اجرای گزارش در audit ثبت می‌شود (بند ۱۴: عملیات حساس).
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.case import Consent
from app.models.consent import ConsentVersion
from app.models.email_outbox import EmailOutbox
from app.models.file import FileScan, StoredFile
from app.models.user import AuthSession, User, UserStatus
from app.services.audit import record_audit
from app.services.av_scan import scanner_status
from app.services.email_outbox import outbox_summary

router = APIRouter(tags=["compliance"])

DPO_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "DPO")

# اقدامات حساس audit که حسابرس باید روندشان را ببیند
_AUDIT_ACTIONS = (
    "auth.login", "auth.login_failed", "auth.password_changed",
    "assessment.viewed", "assessment.printed",
    "file.upload", "file.download_ticket", "file.rescan",
    "consent_version.published", "case.consent_recorded", "consent.revoked",
    "email.outbox_processed",
)


@router.get("/reports/dpo")
def dpo_compliance_report(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*DPO_ROLES)),
) -> dict:
    """گزارش انطباق رضایت/دسترسی برای حسابرس (B41+ فاز ۲۷)."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    # ---- ۱) انطباق رضایت (B41) ----
    consents_by_kind = {}
    for kind, status, count in db.execute(
        select(Consent.kind, Consent.status, func.count())
        .group_by(Consent.kind, Consent.status)
    ).all():
        bucket = consents_by_kind.setdefault(kind, {"granted_active": 0, "revoked": 0})
        bucket["granted_active" if status == "granted" else "revoked"] += int(count)

    grants_window = int(db.scalar(
        select(func.count()).select_from(Consent).where(Consent.created_at >= since)) or 0)
    revocations_window = int(db.scalar(
        select(func.count()).select_from(Consent)
        .where(Consent.revoked_at.is_not(None), Consent.revoked_at >= since)) or 0)
    orphan_grants = int(db.scalar(
        select(func.count()).select_from(Consent)
        .where(Consent.consent_version_id.is_(None))) or 0)

    versions_rows = db.execute(
        select(ConsentVersion.kind, func.count(), func.max(ConsentVersion.version))
        .group_by(ConsentVersion.kind)
    ).all()
    consent_versions = {
        kind: {"versions": int(cnt), "latest": int(latest)}
        for kind, cnt, latest in versions_rows
    }

    # ---- ۲) دسترسی و رخدادها (بند ۱۱/۱۴) ----
    audit_actions = {
        a: int(n) for a, n in db.execute(
            select(AuditEvent.action, func.count())
            .where(AuditEvent.created_at >= since)
            .group_by(AuditEvent.action)
            .order_by(func.count().desc())
        ).all()
    }
    tracked = {a: int(audit_actions.get(a, 0)) for a in _AUDIT_ACTIONS}
    login_failed = int(audit_actions.get("auth.login_failed", 0))
    distinct_actors = int(db.scalar(
        select(func.count(func.distinct(AuditEvent.actor_user_id)))
        .where(AuditEvent.created_at >= since)) or 0)

    # ---- ۳) امنیت فایل (B39/B39-plus) ----
    scan_status = {
        s: int(n) for s, n in db.execute(
            select(StoredFile.scan_status, func.count())
            .group_by(StoredFile.scan_status)
        ).all()
    }
    scanner_usage = {
        s: int(n) for s, n in db.execute(
            select(FileScan.scanner, func.count())
            .group_by(FileScan.scanner)
        ).all()
    }
    uploads_window = int(db.scalar(
        select(func.count()).select_from(StoredFile)
        .where(StoredFile.created_at >= since)) or 0)

    # ---- ۴) کانال ایمیل اعلان‌ها (B12+) ----
    outbox = outbox_summary(db)

    # ---- ۵) حساب‌ها و نگهداشت داده ----
    users_active = int(db.scalar(
        select(func.count()).select_from(User)
        .where(User.status == UserStatus.ACTIVE)) or 0)
    users_disabled = int(db.scalar(
        select(func.count()).select_from(User)
        .where(User.status == UserStatus.DISABLED)) or 0)
    users_pending = int(db.scalar(
        select(func.count()).select_from(User)
        .where(User.status == UserStatus.PENDING)) or 0)
    active_sessions = int(db.scalar(
        select(func.count()).select_from(AuthSession)
        .where(AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)) or 0)

    result = {
        "generated_at": now.isoformat(),
        "days": days,
        "generated_by": actor.display_name,
        "consents": {
            "by_kind": consents_by_kind,
            "grants_in_window": grants_window,
            "revocations_in_window": revocations_window,
            "grants_without_version": orphan_grants,
            "versions": consent_versions,
        },
        "access": {
            "distinct_actors": distinct_actors,
            "login_failed": login_failed,
            "tracked_actions": tracked,
            "actions_by_count": dict(list(audit_actions.items())[:15]),
        },
        "files": {
            "scan_status": scan_status,
            "scanner_usage": scanner_usage,
            "uploads_in_window": uploads_window,
            "scan_backends": scanner_status(),
        },
        "email_outbox": outbox,
        "accounts": {
            "users_active": users_active,
            "users_disabled": users_disabled,
            "users_pending": users_pending,
            "active_sessions": active_sessions,
        },
    }

    record_audit(
        db,
        action="report.dpo_generated",
        actor_user_id=actor.id,
        entity_type="report",
        detail={"days": days},
    )
    db.commit()
    return result
