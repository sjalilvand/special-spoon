"""فاز ۴۹ - B41/B42: فرایندهای سازمانی نسخه‌دار + مانیتورینگ وضعیت درخواست.

- تعریف فرایند جدید (کد/عنوان/شرح + XML استاندارد BPMN 2.0 نسخه ۱)؛
- افزودن نسخه جدید (شماره‌گذاری خودکار، تغییرات/چانج‌لاگ، انتشار اختیاری —
  انتشار، نسخه منتشرشده قبلی را بایگانی می‌کند تا «ثبت نسخه قبلی» حفظ شود)؛
- شروع نمونه اجرا برای یک موضوع (درخواست مشاوره/پرونده/متقاضی/دستی)؛
- ثبت گام‌ها و انتقال وضعیت نمونه (تکمیل/لغو/تعلیق/ادامه)؛
- مانیتورینگ: نمونه‌های یک موضوع با خط‌زمانی گام‌ها و گام فعال فعلی.

XML فقط ساختاری اعتبارسنجی می‌شود (well-formed + ریشه definitions + داشتن
حداقل یک فرایند) تا فایل‌های خروجی هر ابزار استاندارد BPMN پذیرفته شود.
"""
import uuid
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.process import (
    ProcessDefinition,
    ProcessInstance,
    ProcessInstanceEvent,
    ProcessVersion,
)
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(tags=["processes"])

# مدیریت فرایندها: مدیر سامانه/سازمان؛ اجرا: + پذیرش/مسئول فنی/مشاور
MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
RUN_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")
READ_ROLES = RUN_ROLES  # خواندن = همه نقش‌های داخلی ستاد
SUBJECT_TYPES = ("consultation_request", "case", "applicant", "manual")

STATUS_META = {
    "running": "در جریان",
    "suspended": "معلق",
    "completed": "تکمیل‌شده",
    "cancelled": "لغوشده",
}


def _roles(actor: User) -> set[str]:
    return {r.code for r in actor.roles}


def _require_read(actor: User) -> None:
    if not (_roles(actor) & set(READ_ROLES)):
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")


def _require_manage(actor: User) -> None:
    if not (_roles(actor) & set(MANAGE_ROLES)):
        raise HTTPException(status_code=403, detail="فقط مدیر سامانه/سازمان مجاز است")


def _require_run(actor: User) -> None:
    if not (_roles(actor) & set(RUN_ROLES)):
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")


# ------------------------------------------------------------ اعتبارسنجی XML
def validate_bpmn_xml(xml: str) -> dict:
    """اعتبارسنجی ساختاری BPMN 2.0 + استخراج نام فرایند اول."""
    if not xml or len(xml.strip()) < 40:
        raise HTTPException(status_code=422, detail="محتوای XML فرایند خالی یا خیلی کوتاه است")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise HTTPException(status_code=422, detail=f"XML نامعتبر است: {e}")
    tag = root.tag.rsplit("}", 1)[-1]
    if tag != "definitions":
        raise HTTPException(status_code=422, detail="ریشه XML باید <definitions> استاندارد BPMN باشد")
    process_name = None
    process_id = None
    for child in root.iter():
        ctag = child.tag.rsplit("}", 1)[-1]
        if ctag == "process":
            process_id = child.get("id") or process_id
            process_name = child.get("name") or process_name
            break
    if process_id is None and process_name is None:
        raise HTTPException(status_code=422, detail="XML فاقد عنصر <process> است")
    return {"process_name": process_name, "process_id": process_id}


# ------------------------------------------------------------ schemas
class ProcessCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    bpmn_xml: str
    changelog: str | None = Field(default=None, max_length=1000)
    publish: bool = True


class ProcessVersionCreate(BaseModel):
    bpmn_xml: str
    changelog: str | None = Field(default=None, max_length=1000)
    publish: bool = True


class ProcessUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class InstanceCreate(BaseModel):
    definition_id: uuid.UUID
    subject_type: str = Field(pattern="^(consultation_request|case|applicant|manual)$")
    subject_id: str = Field(min_length=1, max_length=64)
    subject_label: str | None = Field(default=None, max_length=200)
    subject_meta: dict | None = None
    note: str | None = Field(default=None, max_length=1000)


class EventCreate(BaseModel):
    element_id: str | None = Field(default=None, max_length=100)
    element_name: str = Field(min_length=1, max_length=200)
    element_type: str | None = Field(default=None, max_length=60)
    status: str = Field(default="done", pattern="^(done|active|pending|skipped|failed)$")
    note: str | None = Field(default=None, max_length=1000)


class TransitionCreate(BaseModel):
    action: str = Field(pattern="^(complete|cancel|suspend|resume)$")
    note: str | None = Field(default=None, max_length=1000)


# ------------------------------------------------------------ serializers
def _version_out(v: ProcessVersion, with_xml: bool = False) -> dict:
    data = {
        "id": str(v.id),
        "definition_id": str(v.definition_id),
        "version_number": v.version_number,
        "changelog": v.changelog,
        "status": v.status,
        "published_at": v.published_at.isoformat() if v.published_at else None,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }
    if with_xml:
        data["bpmn_xml"] = v.bpmn_xml
    return data


def _definition_out(db: Session, d: ProcessDefinition) -> dict:
    versions = db.scalars(
        select(ProcessVersion)
        .where(ProcessVersion.definition_id == d.id)
        .order_by(ProcessVersion.version_number.desc())
    ).all()
    published = next((v for v in versions if v.status == "published"), None)
    instances_count = db.scalar(
        select(func.count(ProcessInstance.id)).where(ProcessInstance.definition_id == d.id)
    ) or 0
    return {
        "id": str(d.id),
        "code": d.code,
        "title": d.title,
        "description": d.description,
        "is_active": d.is_active,
        "versions": [_version_out(v) for v in versions],
        "current_version": _version_out(published) if published else None,
        "instances_count": instances_count,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _instance_out(db: Session, i: ProcessInstance, with_events: bool = False) -> dict:
    d = db.get(ProcessDefinition, i.definition_id)
    v = db.get(ProcessVersion, i.version_id)
    data = {
        "id": str(i.id),
        "definition_id": str(i.definition_id),
        "definition_code": d.code if d else None,
        "definition_title": d.title if d else None,
        "version_number": v.version_number if v else None,
        "subject_type": i.subject_type,
        "subject_id": i.subject_id,
        "subject_label": i.subject_label,
        "subject_meta": i.subject_meta,
        "status": i.status,
        "status_label": STATUS_META.get(i.status, i.status),
        "current_element_id": i.current_element_id,
        "current_element_name": i.current_element_name,
        "note": i.note,
        "started_at": i.started_at.isoformat() if i.started_at else None,
        "finished_at": i.finished_at.isoformat() if i.finished_at else None,
    }
    if with_events:
        events = db.scalars(
            select(ProcessInstanceEvent)
            .where(ProcessInstanceEvent.instance_id == i.id)
            .order_by(ProcessInstanceEvent.occurred_at)
        ).all()
        data["events"] = [
            {
                "id": str(e.id),
                "element_id": e.element_id,
                "element_name": e.element_name,
                "element_type": e.element_type,
                "status": e.status,
                "note": e.note,
                "actor_id": str(e.actor_id) if e.actor_id else None,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in events
        ]
    return data


# ------------------------------------------------------------ فرایندها (تعریف + نسخه)
@router.get("/processes")
def list_processes(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    _require_read(actor)
    rows = db.scalars(select(ProcessDefinition).order_by(ProcessDefinition.code)).all()
    return {"items": [_definition_out(db, d) for d in rows]}


@router.post("/processes", status_code=201)
def create_process(
    payload: ProcessCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
):
    code = payload.code.strip().upper()
    if db.scalar(select(ProcessDefinition).where(ProcessDefinition.code == code)):
        raise HTTPException(status_code=409, detail="کد فرایند تکراری است")
    validate_bpmn_xml(payload.bpmn_xml)
    d = ProcessDefinition(
        code=code, title=payload.title.strip(), description=payload.description,
        created_by=actor.id,
    )
    db.add(d)
    db.flush()
    v = ProcessVersion(
        definition_id=d.id, version_number=1, bpmn_xml=payload.bpmn_xml,
        changelog=payload.changelog, status="published" if payload.publish else "draft",
        published_at=func.now() if payload.publish else None,
        created_by=actor.id,
    )
    db.add(v)
    db.commit()
    record_audit(db, action="process.created", actor_user_id=actor.id,
                 entity_type="process_definition", entity_id=str(d.id))
    return _definition_out(db, d)


@router.patch("/processes/{definition_id}")
def update_process(
    definition_id: uuid.UUID,
    payload: ProcessUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
):
    d = db.get(ProcessDefinition, definition_id)
    if d is None:
        raise HTTPException(status_code=404, detail="فرایند یافت نشد")
    if payload.title is not None:
        d.title = payload.title.strip()
    if payload.description is not None:
        d.description = payload.description
    if payload.is_active is not None:
        d.is_active = payload.is_active
    db.commit()
    record_audit(db, action="process.updated", actor_user_id=actor.id,
                 entity_type="process_definition", entity_id=str(d.id))
    return _definition_out(db, d)


@router.get("/processes/{definition_id}")
def get_process(
    definition_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    _require_read(actor)
    d = db.get(ProcessDefinition, definition_id)
    if d is None:
        raise HTTPException(status_code=404, detail="فرایند یافت نشد")
    return _definition_out(db, d)


@router.post("/processes/{definition_id}/versions", status_code=201)
def create_process_version(
    definition_id: uuid.UUID,
    payload: ProcessVersionCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
):
    """نسخه جدید: شماره‌گذاری خودکار = آخرین نسخه + ۱؛ «ثبت نسخه قبلی»
    چون هر نسخه ردیف خودش را دارد همیشه برقرار است."""
    d = db.get(ProcessDefinition, definition_id)
    if d is None:
        raise HTTPException(status_code=404, detail="فرایند یافت نشد")
    validate_bpmn_xml(payload.bpmn_xml)
    last = db.scalar(
        select(ProcessVersion)
        .where(ProcessVersion.definition_id == d.id)
        .order_by(ProcessVersion.version_number.desc())
        .limit(1)
    )
    next_no = (last.version_number if last else 0) + 1
    v = ProcessVersion(
        definition_id=d.id, version_number=next_no, bpmn_xml=payload.bpmn_xml,
        changelog=payload.changelog, created_by=actor.id,
    )
    if payload.publish:
        # بایگانی نسخه منتشرشده قبلی → فقط یک نسخه منتشرشده در هر زمان
        for prev in db.scalars(select(ProcessVersion).where(
                ProcessVersion.definition_id == d.id,
                ProcessVersion.status == "published")).all():
            prev.status = "archived"
        v.status = "published"
        v.published_at = func.now()
    else:
        v.status = "draft"
    db.add(v)
    db.commit()
    record_audit(db, action="process.version_created", actor_user_id=actor.id,
                 entity_type="process_version", entity_id=str(v.id),
                 detail={"version": next_no, "definition": d.code})
    return _version_out(v)


@router.get("/processes/versions/{version_id}")
def get_process_version(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    _require_read(actor)
    v = db.get(ProcessVersion, version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="نسخه فرایند یافت نشد")
    return _version_out(v, with_xml=True)


@router.post("/processes/versions/{version_id}/publish")
def publish_process_version(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
):
    v = db.get(ProcessVersion, version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="نسخه فرایند یافت نشد")
    for prev in db.scalars(select(ProcessVersion).where(
            ProcessVersion.definition_id == v.definition_id,
            ProcessVersion.status == "published",
            ProcessVersion.id != v.id)).all():
        prev.status = "archived"
    v.status = "published"
    v.published_at = func.now()
    db.commit()
    record_audit(db, action="process.version_published", actor_user_id=actor.id,
                 entity_type="process_version", entity_id=str(v.id))
    return _version_out(v)


@router.post("/processes/versions/{version_id}/archive")
def archive_process_version(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
):
    v = db.get(ProcessVersion, version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="نسخه فرایند یافت نشد")
    v.status = "archived"
    db.commit()
    record_audit(db, action="process.version_archived", actor_user_id=actor.id,
                 entity_type="process_version", entity_id=str(v.id))
    return _version_out(v)


# ------------------------------------------------------------ نمونه‌های اجرا + مانیتورینگ
@router.get("/process-instances")
def list_instances(
    subject_type: str | None = Query(default=None),
    subject_id: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None),
    definition_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    _require_read(actor)
    q = select(ProcessInstance)
    if subject_type:
        q = q.where(ProcessInstance.subject_type == subject_type)
    if subject_id:
        q = q.where(ProcessInstance.subject_id == subject_id)
    if status:
        q = q.where(ProcessInstance.status == status)
    if definition_id:
        q = q.where(ProcessInstance.definition_id == definition_id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(ProcessInstance.started_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    # فاز ۵۱: شکل قراردادی فهرست صفحه‌بندی‌شده v2 — {items, total, page, page_size}
    # (پاکت ADR-03 در این حالت items را به data و بقیه را به meta.pagination
    #  می‌برد؛ خروجی قبلی {"items", "meta"} نشانهٔ صفحه‌بندی سطح‌بالا نداشت،
    #  پاکت آن را نمی‌شکست و فرانت‌اند به‌جای آرایه یک شیء می‌گرفت — صفحهٔ سفید)
    return {
        "items": [_instance_out(db, i) for i in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/process-instances", status_code=201)
def start_instance(
    payload: InstanceCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*RUN_ROLES)),
):
    d = db.get(ProcessDefinition, payload.definition_id)
    if d is None or not d.is_active:
        raise HTTPException(status_code=404, detail="فرایند فعال یافت نشد")
    v = db.scalar(
        select(ProcessVersion)
        .where(ProcessVersion.definition_id == d.id, ProcessVersion.status == "published")
        .order_by(ProcessVersion.version_number.desc())
        .limit(1)
    )
    if v is None:
        raise HTTPException(status_code=422, detail="این فرایند نسخه منتشرشده ندارد")
    existing = db.scalar(
        select(ProcessInstance).where(
            ProcessInstance.definition_id == d.id,
            ProcessInstance.subject_type == payload.subject_type,
            ProcessInstance.subject_id == payload.subject_id,
            ProcessInstance.status.in_(("running", "suspended")),
        )
    )
    if existing:
        raise HTTPException(status_code=409,
                            detail="برای این موضوع، نمونه در جریانِ این فرایند وجود دارد")
    i = ProcessInstance(
        definition_id=d.id, version_id=v.id,
        subject_type=payload.subject_type, subject_id=payload.subject_id,
        subject_label=payload.subject_label, subject_meta=payload.subject_meta,
        note=payload.note, started_by=actor.id,
    )
    db.add(i)
    db.flush()
    db.add(ProcessInstanceEvent(
        instance_id=i.id, element_name="شروع فرایند", element_type="start",
        status="done", note=f"نسخه {v.version_number} فرایند «{d.title}»",
        actor_id=actor.id,
    ))
    db.commit()
    record_audit(db, action="process.instance_started", actor_user_id=actor.id,
                 entity_type="process_instance", entity_id=str(i.id),
                 detail={"definition": d.code, "subject": payload.subject_id})
    return _instance_out(db, i, with_events=True)


@router.get("/process-instances/{instance_id}")
def get_instance(
    instance_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    _require_read(actor)
    i = db.get(ProcessInstance, instance_id)
    if i is None:
        raise HTTPException(status_code=404, detail="نمونه فرایند یافت نشد")
    return _instance_out(db, i, with_events=True)


@router.post("/process-instances/{instance_id}/events", status_code=201)
def record_event(
    instance_id: uuid.UUID,
    payload: EventCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*RUN_ROLES)),
):
    i = db.get(ProcessInstance, instance_id)
    if i is None:
        raise HTTPException(status_code=404, detail="نمونه فرایند یافت نشد")
    if i.status in ("completed", "cancelled"):
        raise HTTPException(status_code=409, detail="نمونه پایان‌یافته است؛ ثبت گام مجاز نیست")
    e = ProcessInstanceEvent(
        instance_id=i.id, element_id=payload.element_id,
        element_name=payload.element_name, element_type=payload.element_type,
        status=payload.status, note=payload.note, actor_id=actor.id,
    )
    db.add(e)
    if payload.status in ("done", "active"):
        i.current_element_id = payload.element_id
        i.current_element_name = payload.element_name
    db.commit()
    record_audit(db, action="process.event_recorded", actor_user_id=actor.id,
                 entity_type="process_instance", entity_id=str(i.id),
                 detail={"element": payload.element_name, "status": payload.status})
    return _instance_out(db, i, with_events=True)


@router.post("/process-instances/{instance_id}/transition")
def transition_instance(
    instance_id: uuid.UUID,
    payload: TransitionCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*RUN_ROLES)),
):
    i = db.get(ProcessInstance, instance_id)
    if i is None:
        raise HTTPException(status_code=404, detail="نمونه فرایند یافت نشد")
    action = payload.action
    if action == "complete":
        if i.status == "cancelled":
            raise HTTPException(status_code=409, detail="نمونه لغوشده است")
        i.status = "completed"
        i.finished_at = func.now()
        db.add(ProcessInstanceEvent(instance_id=i.id, element_name="پایان فرایند",
                                    element_type="end", status="done",
                                    note=payload.note, actor_id=actor.id))
    elif action == "cancel":
        i.status = "cancelled"
        i.finished_at = func.now()
        db.add(ProcessInstanceEvent(instance_id=i.id, element_name="لغو فرایند",
                                    element_type="end", status="skipped",
                                    note=payload.note, actor_id=actor.id))
    elif action == "suspend":
        if i.status != "running":
            raise HTTPException(status_code=409, detail="فقط نمونه در جریان قابل تعلیق است")
        i.status = "suspended"
        db.add(ProcessInstanceEvent(instance_id=i.id, element_name="تعلیق فرایند",
                                    element_type="intermediate", status="pending",
                                    note=payload.note, actor_id=actor.id))
    elif action == "resume":
        if i.status != "suspended":
            raise HTTPException(status_code=409, detail="فقط نمونه معلق قابل ادامه است")
        i.status = "running"
        db.add(ProcessInstanceEvent(instance_id=i.id, element_name="ادامه فرایند",
                                    element_type="intermediate", status="active",
                                    note=payload.note, actor_id=actor.id))
    i.note = payload.note or i.note
    db.commit()
    record_audit(db, action=f"process.instance_{action}", actor_user_id=actor.id,
                 entity_type="process_instance", entity_id=str(i.id))
    return _instance_out(db, i, with_events=True)


# ------------------------------------------------------------ فاز ۵۹: دیاگرام BPMN زنده
# پارسر BPMN 2.0 + BPMNDI برای شبیه‌سازی بصری فرایند در مانیتورینگ:
# هر عنصر (رویداد/فعالیت/گیت‌وی) روی نمودار با وضعیت واقعی نمونه رنگ می‌شود.

_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
_DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
_DI_NS = "http://www.omg.org/spec/DD/20100524/DI"

# نوع‌های عنصر که فرانت آن‌ها را شکل‌دار رندر می‌کند
NODE_KINDS = {
    "startEvent": "start",
    "endEvent": "end",
    "task": "task",
    "userTask": "task",
    "serviceTask": "task",
    "manualTask": "task",
    "scriptTask": "task",
    "sendTask": "task",
    "receiveTask": "task",
    "businessRuleTask": "task",
    "callActivity": "subprocess",
    "subProcess": "subprocess",
    "exclusiveGateway": "gateway_exclusive",
    "parallelGateway": "gateway_parallel",
    "inclusiveGateway": "gateway_inclusive",
    "eventBasedGateway": "gateway_event",
    "complexGateway": "gateway_exclusive",
    "intermediateCatchEvent": "intermediate",
    "intermediateThrowEvent": "intermediate",
    "boundaryEvent": "intermediate",
}

GATEWAY_LABELS = {
    "gateway_exclusive": "گیت‌وی انحصاری (XOR)",
    "gateway_parallel": "گیت‌وی موازی (AND)",
    "gateway_inclusive": "گیت‌وی شمول (OR)",
    "gateway_event": "گیت‌وی رویدادمحور",
}


def parse_bpmn_diagram(xml: str) -> dict:
    """پارس XML استاندارد BPMN: گره‌ها + یال‌ها + مختصات BPMNDI.

    اگر XML مختصات DI نداشته باشد (XML دستی)، چیدمان خودکار لایه‌ای
    (بالا-به-پایین توپولوژیک با انشعاب افقی) ساخته می‌شود.
    """
    root = ET.fromstring(xml)

    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    # --- گره‌ها و یال‌ها از <process> ---
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for process in root.iter():
        if _local(process.tag) != "process":
            continue
        for el in process:
            tag = _local(el.tag)
            if tag == "sequenceFlow":
                edges.append({
                    "id": el.get("id") or "",
                    "source": el.get("sourceRef") or "",
                    "target": el.get("targetRef") or "",
                    "name": el.get("name") or None,
                    "waypoints": [],
                })
            elif tag in NODE_KINDS:
                nid = el.get("id")
                if not nid:
                    continue
                nodes[nid] = {
                    "id": nid,
                    "name": (el.get("name") or nid).strip(),
                    "kind": NODE_KINDS[tag],
                    "raw_type": tag,
                    "x": 0, "y": 0, "w": 0, "h": 0,
                }

    # --- مختصات از BPMNDI ---
    has_di = False
    for shape in root.iter(f"{{{_BPMNDI_NS}}}BPMNShape"):
        eid = shape.get("bpmnElement")
        if eid not in nodes:
            continue
        for child in shape.iter():
            if _local(child.tag) == "Bounds":
                nodes[eid]["x"] = float(child.get("x") or 0)
                nodes[eid]["y"] = float(child.get("y") or 0)
                nodes[eid]["w"] = float(child.get("width") or 0)
                nodes[eid]["h"] = float(child.get("height") or 0)
                has_di = True
    for edge_el in root.iter(f"{{{_BPMNDI_NS}}}BPMNEdge"):
        eid = edge_el.get("bpmnElement")
        for e in edges:
            if e["id"] == eid:
                pts = []
                for child in edge_el.iter():
                    if _local(child.tag) == "waypoint":
                        pts.append([float(child.get("x") or 0), float(child.get("y") or 0)])
                e["waypoints"] = pts

    # --- چیدمان خودکار برای گره‌های بدون مختصات ---
    missing = [n for n in nodes.values() if n["w"] == 0]
    if missing:
        has_di = _auto_layout(nodes, edges, missing) or has_di

    # محدودهٔ کل بوم
    if nodes:
        min_x = min(n["x"] for n in nodes.values())
        min_y = min(n["y"] for n in nodes.values())
        max_x = max(n["x"] + n["w"] for n in nodes.values())
        max_y = max(n["y"] + n["h"] for n in nodes.values())
        bounds = {"x": min_x - 40, "y": min_y - 40, "width": (max_x - min_x) + 80,
                  "height": (max_y - min_y) + 80}
    else:
        bounds = {"x": 0, "y": 0, "width": 800, "height": 400}
    return {"nodes": list(nodes.values()), "edges": edges, "bounds": bounds, "has_di": has_di}


def _auto_layout(nodes: dict, edges: list[dict], missing: list[dict]) -> bool:
    """چیدمان لایه‌ای ساده: عمق توپولوژیک = ردیف، ترتیب برادرها = ستون."""
    import math

    succ: dict[str, list[str]] = {}
    indeg: dict[str, int] = {nid: 0 for nid in nodes}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in nodes and t in nodes:
            succ.setdefault(s, []).append(t)
            indeg[t] = indeg.get(t, 0) + 1

    depth: dict[str, int] = {}

    def visit(nid: str, d: int, seen: set):
        if nid in seen or nid not in nodes:
            return
        seen.add(nid)
        if d > depth.get(nid, -1):
            depth[nid] = d
        for t in succ.get(nid, []):
            visit(t, d + 1, seen)

    roots = [nid for nid, dg in indeg.items() if dg == 0]
    for r in (roots or list(nodes.keys())[:1]):
        visit(r, 0, set())

    layers: dict[int, list[str]] = {}
    for nid, d in depth.items():
        layers.setdefault(d, []).append(nid)
    TW, TH, GX, GY = 160, 70, 60, 90
    for d, layer in sorted(layers.items()):
        row_w = len(layer) * (TW + GX)
        x0 = 40
        for k, nid in enumerate(sorted(layer)):
            n = nodes[nid]
            n["x"] = x0 + k * (TW + GX)
            n["y"] = 40 + d * (TH + GY)
            n["w"] = TW if n["kind"] not in ("start", "end") else 36
            n["h"] = TH if n["kind"] not in ("start", "end") else 36
    # یال‌های بدون waypoint: خط مستقیم مرکز-به-مرکز (فرانت خم می‌زند)
    for e in edges:
        if not e["waypoints"] and e["source"] in nodes and e["target"] in nodes:
            s, t = nodes[e["source"]], nodes[e["target"]]
            e["waypoints"] = [
                [s["x"] + s["w"] / 2, s["y"] + s["h"] / 2],
                [t["x"] + t["w"] / 2, t["y"] + t["h"] / 2],
            ]
    return True


def _element_states(events: list, instance: ProcessInstance) -> dict:
    """وضعیت هر عنصر از رخدادها + استنتاج گام‌های بعدی (pending).

    قواعد:
    - آخرین رخداد هر element_id ملاک است؛
    - گامِ فعال = current_element_id (یا رخداد active اخیر)؛
    - اگر نمونه completed باشد و رخداد end داشته باشیم، عنصر پایان done است؛
    - عناصر لایه‌های بعد از گام فعال که رخداد ندارند pending در نظر گرفته
      می‌شوند تا نمودار «فقط مسیر طی‌شده» را برجسته کند.
    """
    by_elem: dict[str, dict] = {}
    active_id = instance.current_element_id
    for e in events:
        eid = e.element_id
        if not eid:
            continue
        prev = by_elem.get(eid)
        # مقایسهٔ زمانی با datetime خام (خروجی ISO فقط برای نمایش)
        if (prev is None or e.occurred_at is None or prev["occurred_at"] is None
                or e.occurred_at >= prev["occurred_at"]):
            by_elem[eid] = {
                "status": e.status,
                "occurred_at": e.occurred_at,
                "note": e.note,
            }
    if active_id and by_elem.get(active_id, {}).get("status") != "active":
        by_elem.setdefault(active_id, {"status": "active", "occurred_at": None, "note": None})
        by_elem[active_id]["status"] = "active"
    # خروجی: زمان به ISO
    for v in by_elem.values():
        if v["occurred_at"] is not None:
            v["occurred_at"] = v["occurred_at"].isoformat()
    return by_elem


@router.get("/process-instances/{instance_id}/diagram")
def get_instance_diagram(
    instance_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """دیاگرام BPMN نمونه + وضعیت هر عنصر برای شبیه‌سازی بصری مانیتورینگ."""
    _require_read(actor)
    i = db.get(ProcessInstance, instance_id)
    if i is None:
        raise HTTPException(status_code=404, detail="نمونه فرایند یافت نشد")
    v = db.get(ProcessVersion, i.version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="نسخه فرایند یافت نشد")
    try:
        diagram = parse_bpmn_diagram(v.bpmn_xml)
    except ET.ParseError as e:
        raise HTTPException(status_code=422, detail=f"XML BPMN این نسخه قابل پارس نیست: {e}")
    events = db.scalars(
        select(ProcessInstanceEvent)
        .where(ProcessInstanceEvent.instance_id == i.id)
        .order_by(ProcessInstanceEvent.occurred_at)
    ).all()
    states = _element_states(events, i)
    # گره‌های بدون رخداد: pending مگر شروع/پایانِ نمونهٔ تمام‌شده
    for n in diagram["nodes"]:
        if n["id"] not in states:
            if i.status == "completed" and n["kind"] == "end":
                states[n["id"]] = {"status": "done", "occurred_at": None, "note": None}
            else:
                states[n["id"]] = {"status": "pending", "occurred_at": None, "note": None}
    # یال‌های طی‌شده: مبدأ done و مقصد done/active → highlighted
    flows = []
    for e in diagram["edges"]:
        s_state = states.get(e["source"], {}).get("status", "pending")
        t_state = states.get(e["target"], {}).get("status", "pending")
        passed = s_state in ("done", "skipped") and t_state in ("done", "active", "skipped")
        active = s_state == "done" and t_state == "active"
        flows.append({
            "id": e["id"], "source": e["source"], "target": e["target"],
            "name": e["name"], "waypoints": e["waypoints"],
            "passed": passed, "active": active,
        })
    return {
        "instance": _instance_out(db, i),
        "nodes": diagram["nodes"],
        "edges": flows,
        "bounds": diagram["bounds"],
        "states": states,
        "has_di": diagram["has_di"],
        "gateway_labels": GATEWAY_LABELS,
    }
