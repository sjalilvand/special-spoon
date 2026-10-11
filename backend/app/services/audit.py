from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def record_audit(
    db: Session,
    *,
    action: str,
    actor_user_id: Any = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    result: str = "success",
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """ثبت رخداد در تراکنش مستقل - بدون متن بالینی یا رمز (بند ۱۴ سند)"""
    event = AuditEvent(
        action=action,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        result=result,
        detail=detail,
        ip=ip,
    )
    db.add(event)
    db.commit()
