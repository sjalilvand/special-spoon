"""فاز ۳۳ - B32 سند جامع: دسته‌بندی موضوعی.

قواعد پذیرش:
- slug یکتا (۴۰۹ در تکرار)؛ فقط حروف کوچک لاتین، عدد و خط تیره؛
- والد باید فعال و غیرخودی باشد؛ انتقال دسته به فرزندِ خودش ممنوع (چرخه)؛
- دسته دارای خدمت یا فرزند حذف نمی‌شود (409) — ابتدا اتصال‌ها برداشته شوند؛
- «دسته غیرفعال در صفحات عمومی نشان داده نشود» — خروجی عمومی فقط فعال‌ها.
"""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalog import Service, ServiceStatus
from app.models.topics import ServiceTopic, Topic
from app.models.user import User

router = APIRouter(tags=["topics"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
VIEW_ROLES = (*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION")

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?$")


# ---------------------------------------------------------------- schemas
class TopicCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=120)
    parent_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0)


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    parent_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)


class TopicServicesUpdate(BaseModel):
    service_ids: list[uuid.UUID] = Field(default_factory=list)


# ---------------------------------------------------------------- helpers
def _topic_out(db: Session, t: Topic) -> dict:
    svc_rows = db.execute(
        select(ServiceTopic.service_id).where(ServiceTopic.topic_id == t.id)
    ).all()
    svc_ids = [str(sid) for (sid,) in svc_rows]
    svc_count = len(svc_ids)
    children = db.scalar(
        select(func.count()).select_from(Topic).where(Topic.parent_id == t.id)
    )
    parent = db.get(Topic, t.parent_id) if t.parent_id else None
    return {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "parent_id": str(t.parent_id) if t.parent_id else None,
        "parent_name": parent.name if parent else None,
        "description": t.description,
        "is_active": t.is_active,
        "sort_order": t.sort_order,
        "service_count": svc_count,
        "service_ids": svc_ids,
        "children_count": children or 0,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _validate_slug(slug: str) -> str:
    s = slug.strip().lower()
    if not _SLUG_RE.match(s):
        raise HTTPException(
            status_code=422, detail="slug فقط حروف کوچک لاتین، عدد و خط تیره است"
        )
    return s


def _ensure_no_cycle(topic: Topic, new_parent_id: uuid.UUID, db: Session) -> None:
    """دسته نمی‌تواند به خودش یا زیرمجموعه خودش منتقل شود (چرخه ممنوع)."""
    if new_parent_id == topic.id:
        raise HTTPException(status_code=422, detail="دسته نمی‌تواند والد خودش باشد")
    seen: set[uuid.UUID] = {topic.id}
    cursor = new_parent_id
    while cursor is not None:
        if cursor in seen:
            raise HTTPException(
                status_code=422, detail="انتقال دسته به زیرمجموعه خودش ممنوع است (چرخه)"
            )
        seen.add(cursor)
        parent = db.get(Topic, cursor)
        cursor = parent.parent_id if parent else None


def _set_topic_services(db: Session, topic: Topic, service_ids: list[uuid.UUID]) -> None:
    seen: set[uuid.UUID] = set()
    for sid in service_ids:
        if sid in seen:
            continue
        seen.add(sid)
        svc = db.get(Service, sid)
        if svc is None:
            raise HTTPException(status_code=404, detail=f"خدمت یافت نشد: {sid}")
        exists = db.scalars(
            select(ServiceTopic).where(
                ServiceTopic.topic_id == topic.id, ServiceTopic.service_id == sid
            )
        ).first()
        if exists is None:
            db.add(ServiceTopic(topic_id=topic.id, service_id=sid))


# ---------------------------------------------------------------- admin
@router.get("/topics")
def list_topics(
    include_inactive: bool = Query(default=True),
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(Topic).order_by(Topic.sort_order, Topic.name)
    if not include_inactive:
        q = q.where(Topic.is_active.is_(True))
    topics = db.scalars(q).all()
    return {"items": [_topic_out(db, t) for t in topics]}


@router.post("/topics", status_code=201)
def create_topic(
    payload: TopicCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    slug = _validate_slug(payload.slug)
    dup = db.scalars(select(Topic.id).where(Topic.slug == slug)).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="این slug قبلاً استفاده شده است")
    parent = None
    if payload.parent_id is not None:
        parent = db.get(Topic, payload.parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="دسته والد یافت نشد")
        if not parent.is_active:
            raise HTTPException(status_code=422, detail="دسته والد باید فعال باشد")
    topic = Topic(
        name=payload.name.strip(),
        slug=slug,
        parent_id=payload.parent_id,
        description=payload.description,
        sort_order=payload.sort_order,
        created_by=actor.id,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _topic_out(db, topic)


@router.patch("/topics/{topic_id}")
def update_topic(
    topic_id: uuid.UUID,
    payload: TopicUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="دسته یافت نشد")
    if payload.parent_id is not None and payload.parent_id != topic.parent_id:
        parent = db.get(Topic, payload.parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="دسته والد یافت نشد")
        if not parent.is_active:
            raise HTTPException(status_code=422, detail="دسته والد باید فعال باشد")
        _ensure_no_cycle(topic, payload.parent_id, db)
        topic.parent_id = payload.parent_id
    if payload.name is not None:
        topic.name = payload.name.strip()
    if payload.description is not None:
        topic.description = payload.description
    if payload.sort_order is not None:
        topic.sort_order = payload.sort_order
    if payload.is_active is not None:
        topic.is_active = payload.is_active
        if not topic.is_active:
            # غیرفعال‌سازی دسته والد فعال → فرزندان هم ناخواسته غیرقابل‌انتشار
            # می‌شوند؛ صریحاً مجاز ولی با پاسخ روشن (قاعده عمومی: فقط فعال‌ها)
            pass
    db.commit()
    db.refresh(topic)
    return _topic_out(db, topic)


@router.delete("/topics/{topic_id}", status_code=204)
def delete_topic(
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    """حذف فقط برای دسته بدون خدمت و بدون فرزند (قاعده: منع حذف دسته استفاده‌شده)."""
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="دسته یافت نشد")
    used = db.scalar(
        select(func.count()).select_from(ServiceTopic).where(ServiceTopic.topic_id == topic.id)
    )
    if (used or 0) > 0:
        raise HTTPException(
            status_code=409, detail="دسته به خدمت متصل است؛ ابتدا اتصال‌ها را بردارید"
        )
    children = db.scalar(
        select(func.count()).select_from(Topic).where(Topic.parent_id == topic.id)
    )
    if (children or 0) > 0:
        raise HTTPException(status_code=409, detail="دسته دارای زیر‌دسته است؛ ابتدا فرزندان را حذف کنید")
    db.delete(topic)
    db.commit()


@router.put("/topics/{topic_id}/services")
def set_topic_services(
    topic_id: uuid.UUID,
    payload: TopicServicesUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """تنظیم فهرست خدمات دسته (مجموعه جایگزین کامل می‌شود)."""
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="دسته یافت نشد")
    _set_topic_services(db, topic, payload.service_ids)
    keep = set(payload.service_ids)
    for row in db.scalars(
        select(ServiceTopic).where(ServiceTopic.topic_id == topic.id)
    ).all():
        if row.service_id not in keep:
            db.delete(row)
    db.commit()
    return _topic_out(db, topic)


# ---------------------------------------------------------------- public
@router.get("/public/topics")
def public_topics(db: Session = Depends(get_db)) -> dict:
    """«دسته غیرفعال در صفحات عمومی نشان داده نشود» + شمارش خدمات فعال."""
    topics = db.scalars(
        select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.sort_order, Topic.name)
    ).all()
    out = []
    for t in topics:
        svc_count = db.scalar(
            select(func.count())
            .select_from(ServiceTopic)
            .join(Service, Service.id == ServiceTopic.service_id)
            .where(ServiceTopic.topic_id == t.id, Service.status == ServiceStatus.ACTIVE)
        )
        out.append(
            {
                "id": str(t.id),
                "name": t.name,
                "slug": t.slug,
                "parent_id": str(t.parent_id) if t.parent_id else None,
                "description": t.description,
                "sort_order": t.sort_order,
                "active_service_count": svc_count or 0,
            }
        )
    return {"items": out}
