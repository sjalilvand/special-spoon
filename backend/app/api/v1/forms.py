"""فاز ۶۱ - فرم‌ساز و نظرسنجی: API مدیریت فرم و ثبت پاسخ.

نقش‌ها:
- مدیریت (``forms.manage``): CRUD کامل فرم‌ها + مشاهدهٔ پاسخ‌ها؛
- همهٔ حساب‌های فعال: دریافت فرم برای تکمیل + ثبت پاسخ + فهرست
  «فرم‌های در انتظار من» (نظرسنجی‌های پس از تماس بی‌پاسخ).

اعتبارسنجی پاسخ‌ها بر اساس تعریف فیلدها انجام می‌شود (فیلد اجباری خالی → 422).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_perm
from app.db.session import get_db
from app.models.forms import FIELD_TYPES, FORM_KINDS, CallSession, FormResponse, FormTemplate
from app.models.user import User
from app.services.audit import record_audit

# توجه: پیشوند «form-templates» انتخاب شده تا با مسیر «/forms/{form_code}»
# مربوط به فرم‌های بالینی (assessments.py) تداخل مسیر رخ ندهد.
router = APIRouter(prefix="/form-templates", tags=["forms"])

FIELD_LABELS = {
    "text": "متن کوتاه",
    "textarea": "متن بلند",
    "number": "عدد",
    "date": "تاریخ",
    "select": "فهرست بسته",
    "radio": "چندگزینه‌ای",
    "checkbox": "چندانتخابی",
    "rating": "امتیاز ۱ تا ۵",
    "yesno": "بله/خیر",
    "heading": "سرصفحهٔ بخش",
}


def _validate_fields(fields: list[dict]) -> None:
    if not isinstance(fields, list):
        raise HTTPException(status_code=422, detail="فیلدها باید یک فهرست باشند")
    seen: set[str] = set()
    for f in fields:
        if not isinstance(f, dict):
            raise HTTPException(status_code=422, detail="ساختار فیلد نامعتبر است")
        ftype = str(f.get("type") or "")
        if ftype not in FIELD_TYPES:
            raise HTTPException(status_code=422, detail=f"نوع فیلد پشتیبانی نمی‌شود: {ftype or 'خالی'}")
        if ftype == "heading":
            continue
        if not str(f.get("label") or "").strip():
            raise HTTPException(status_code=422, detail="هر فیلد باید برچسب داشته باشد")
        fid = str(f.get("id") or "").strip()
        if not fid:
            raise HTTPException(status_code=422, detail="شناسهٔ فیلد لازم است")
        if fid in seen:
            raise HTTPException(status_code=422, detail=f"شناسهٔ فیلد تکراری است: {fid}")
        seen.add(fid)
        if ftype in ("select", "radio", "checkbox"):
            opts = f.get("options")
            if not isinstance(opts, list) or len([o for o in opts if str(o).strip()]) < 1:
                raise HTTPException(status_code=422, detail=f"فیلد «{f.get('label')}» باید حداقل یک گزینه داشته باشد")


def _template_out(t: FormTemplate, response_count: int | None = None) -> dict:
    out = {
        "id": str(t.id),
        "code": t.code,
        "title": t.title,
        "description": t.description,
        "kind": t.kind,
        "fields": t.fields or [],
        "is_active": t.is_active,
        "is_default_call_survey": t.is_default_call_survey,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
    if response_count is not None:
        out["response_count"] = response_count
    return out


def _get_template_or_404(db: Session, template_id: uuid.UUID) -> FormTemplate:
    t = db.get(FormTemplate, template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="فرم یافت نشد")
    return t


# ---------------------------------------------------------------------------
# مدیریت فرم‌ها (forms.manage)
# ---------------------------------------------------------------------------
class FormUpsertRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    code: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    kind: str = Field(default="custom")
    fields: list[dict] = Field(default_factory=list)
    is_active: bool = True
    is_default_call_survey: bool = False


@router.get("/admin")
def list_all_templates(
    kind: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("forms.manage")),
) -> dict:
    q = select(FormTemplate).order_by(FormTemplate.created_at.desc())
    if kind in FORM_KINDS:
        q = q.where(FormTemplate.kind == kind)
    rows = db.scalars(q).all()
    counts = dict(
        db.execute(
            select(FormResponse.template_id, func.count())
            .group_by(FormResponse.template_id)
        ).all()
    )
    return {
        "items": [
            _template_out(t, int(counts.get(t.id, 0)))
            for t in rows
        ]
    }


@router.post("/admin", status_code=201)
def create_template(
    payload: FormUpsertRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("forms.manage")),
) -> dict:
    if payload.kind not in FORM_KINDS:
        raise HTTPException(status_code=422, detail="نوع فرم نامعتبر است")
    _validate_fields(payload.fields)

    code = (payload.code or "").strip()
    if not code:
        # تولید کد از عنوان برای فارسی — اسلاگ سادهٔ لاتین یا کد تصادفی
        import re
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", payload.title).strip("-").lower()
        code = (slug[:60] or "form") + "-" + uuid.uuid4().hex[:6]
    if db.scalar(select(FormTemplate).where(FormTemplate.code == code)) is not None:
        raise HTTPException(status_code=409, detail="فرمی با این کد وجود دارد")

    t = FormTemplate(
        code=code,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        kind=payload.kind,
        fields=payload.fields,
        is_active=payload.is_active,
        is_default_call_survey=False,
        created_by_id=actor.id,
    )
    db.add(t)
    db.flush()
    if payload.is_default_call_survey and payload.kind == "survey":
        _set_default_call_survey(db, t)
    db.commit()
    record_audit(
        db, action="form.created", actor_user_id=actor.id,
        entity_type="form_template", entity_id=str(t.id),
        detail={"code": t.code, "title": t.title},
    )
    db.commit()
    return _template_out(t)


def _set_default_call_survey(db: Session, template: FormTemplate) -> None:
    """فقط یک نظرسنجی پیش‌فرض تماس وجود دارد."""
    from sqlalchemy import update, false as sa_false

    db.execute(
        update(FormTemplate)
        .where(FormTemplate.id != template.id)
        .values(is_default_call_survey=sa_false())
    )
    template.is_default_call_survey = True


@router.put("/admin/{template_id}")
def update_template(
    template_id: uuid.UUID,
    payload: FormUpsertRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("forms.manage")),
) -> dict:
    t = _get_template_or_404(db, template_id)
    if payload.kind not in FORM_KINDS:
        raise HTTPException(status_code=422, detail="نوع فرم نامعتبر است")
    _validate_fields(payload.fields)

    code = (payload.code or "").strip()
    if code and code != t.code:
        if db.scalar(select(FormTemplate).where(FormTemplate.code == code, FormTemplate.id != t.id)) is not None:
            raise HTTPException(status_code=409, detail="فرمی با این کد وجود دارد")
        t.code = code

    t.title = payload.title.strip()
    t.description = (payload.description or "").strip() or None
    t.kind = payload.kind
    t.fields = payload.fields
    t.is_active = payload.is_active

    if payload.is_default_call_survey:
        if payload.kind != "survey":
            raise HTTPException(status_code=422, detail="فقط فرم از نوع «نظرسنجی» می‌تواند پیش‌فرض تماس باشد")
        _set_default_call_survey(db, t)
    else:
        t.is_default_call_survey = False

    db.commit()
    record_audit(
        db, action="form.updated", actor_user_id=actor.id,
        entity_type="form_template", entity_id=str(t.id),
        detail={"code": t.code},
    )
    db.commit()
    return _template_out(t)


@router.delete("/admin/{template_id}")
def delete_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("forms.manage")),
) -> dict:
    t = _get_template_or_404(db, template_id)
    used = db.scalar(select(func.count()).select_from(FormResponse).where(FormResponse.template_id == t.id)) or 0
    if used:
        # حذف نهایی با پاسخ موجود ممنوع — فقط غیرفعال‌سازی
        t.is_active = False
        db.commit()
        raise HTTPException(
            status_code=409,
            detail=f"این فرم {used} پاسخ ثبت‌شده دارد؛ فرم غیرفعال شد (حذف نهایی ممکن نیست)",
        )
    db.delete(t)
    db.commit()
    record_audit(
        db, action="form.deleted", actor_user_id=actor.id,
        entity_type="form_template", entity_id=str(template_id),
    )
    db.commit()
    return {"ok": True}


@router.get("/admin/{template_id}/responses")
def list_responses(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("forms.manage")),
) -> dict:
    t = _get_template_or_404(db, template_id)
    rows = db.scalars(
        select(FormResponse).where(FormResponse.template_id == t.id)
        .order_by(FormResponse.submitted_at.desc()).limit(500)
    ).all()
    user_ids = {r.respondent_id for r in rows if r.respondent_id}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    call_ids = {r.call_id for r in rows if r.call_id}
    calls = {}
    if call_ids:
        calls = {c.id: c for c in db.scalars(select(CallSession).where(CallSession.id.in_(call_ids))).all()}
    items = []
    for r in rows:
        u = users.get(r.respondent_id)
        call = calls.get(r.call_id)
        items.append({
            "id": str(r.id),
            "respondent_id": str(r.respondent_id) if r.respondent_id else None,
            "respondent_name": u.display_name if u else None,
            "answers": r.answers or {},
            "call_id": str(r.call_id) if r.call_id else None,
            "call_duration_sec": call.duration_sec if call else None,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        })
    return {"template": _template_out(t), "items": items}


# ---------------------------------------------------------------------------
# سمت همهٔ کاربران: تکمیل فرم / نظرسنجی
# ---------------------------------------------------------------------------
@router.get("/mine")
def my_forms(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """فرم‌های من: نظرسنجی‌های در انتظار (پس از تماس) + تاریخچهٔ پاسخ‌های من."""
    # در انتظار: تماس‌های پایان‌یافته که من گیرنده‌ام و نظرسنجی دارند اما پاسخی ثبت نشده
    ended_calls = db.scalars(
        select(CallSession).where(
            CallSession.callee_id == actor.id,
            CallSession.status == "ended",
            CallSession.survey_template_id.is_not(None),
        ).order_by(CallSession.ended_at.desc()).limit(50)
    ).all()
    answered_call_ids = set(
        db.scalars(
            select(FormResponse.call_id).where(
                FormResponse.respondent_id == actor.id,
                FormResponse.call_id.is_not(None),
            )
        ).all()
    )
    pending = []
    for c in ended_calls:
        if c.id in answered_call_ids:
            continue
        t = db.get(FormTemplate, c.survey_template_id)
        if t is None or not t.is_active:
            continue
        caller = db.get(User, c.caller_id)
        pending.append({
            "call_id": str(c.id),
            "template": _template_out(t),
            "caller_name": caller.display_name if caller else None,
            "call_ended_at": c.ended_at.isoformat() if c.ended_at else None,
            "call_duration_sec": c.duration_sec,
        })

    my_responses = db.scalars(
        select(FormResponse).where(FormResponse.respondent_id == actor.id)
        .order_by(FormResponse.submitted_at.desc()).limit(100)
    ).all()
    tpl_ids = {r.template_id for r in my_responses}
    tpls = {t.id: t for t in db.scalars(select(FormTemplate).where(FormTemplate.id.in_(tpl_ids))).all()} if tpl_ids else {}
    history = []
    for r in my_responses:
        t = tpls.get(r.template_id)
        history.append({
            "id": str(r.id),
            "template_title": t.title if t else None,
            "template_id": str(r.template_id),
            "call_id": str(r.call_id) if r.call_id else None,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        })
    return {"pending": pending, "history": history}


@router.get("/public/{template_id}")
def get_template_for_fill(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """دریافت تعریف فرم برای تکمیل (فرم فعال)."""
    t = _get_template_or_404(db, template_id)
    if not t.is_active:
        raise HTTPException(status_code=409, detail="این فرم غیرفعال است")
    return _template_out(t)


class FormSubmitRequest(BaseModel):
    answers: dict = Field(default_factory=dict)
    call_id: str | None = Field(default=None, max_length=36)


def _validate_answers(template: FormTemplate, answers: dict) -> dict:
    """پاک‌سازی و اعتبارسنجی پاسخ‌ها بر اساس تعریف فیلدها."""
    if not isinstance(answers, dict):
        raise HTTPException(status_code=422, detail="پاسخ‌ها نامعتبر است")
    fields = [f for f in (template.fields or []) if f.get("type") != "heading"]
    clean: dict = {}
    for f in fields:
        fid = str(f.get("id"))
        val = answers.get(fid)
        ftype = f.get("type")
        required = bool(f.get("required"))
        if ftype == "checkbox":
            if not isinstance(val, list):
                val = [] if val is None else [val]
            val = [str(v) for v in val if str(v).strip()]
            if required and not val:
                raise HTTPException(status_code=422, detail=f"تکمیل «{f.get('label')}» الزامی است")
            clean[fid] = val
        elif ftype == "rating":
            try:
                iv = int(val) if val not in (None, "") else None
            except (TypeError, ValueError):
                iv = None
            if iv is not None and not (1 <= iv <= 5):
                iv = None
            if required and iv is None:
                raise HTTPException(status_code=422, detail=f"تکمیل «{f.get('label')}» الزامی است")
            clean[fid] = iv
        elif ftype == "number":
            if val in (None, ""):
                if required:
                    raise HTTPException(status_code=422, detail=f"تکمیل «{f.get('label')}» الزامی است")
                clean[fid] = None
                continue
            try:
                clean[fid] = float(val) if "." in str(val) else int(val)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"مقدار «{f.get('label')}» باید عدد باشد")
        else:
            sval = str(val).strip() if val not in (None, "") else ""
            if ftype in ("select", "radio") and sval:
                opts = [str(o) for o in (f.get("options") or [])]
                if sval not in opts:
                    raise HTTPException(status_code=422, detail=f"گزینهٔ انتخابی برای «{f.get('label')}» معتبر نیست")
            if ftype == "yesno" and sval and sval not in ("بله", "خیر"):
                sval = "بله" if sval.lower() in ("yes", "true", "1") else "خیر"
            if required and not sval:
                raise HTTPException(status_code=422, detail=f"تکمیل «{f.get('label')}» الزامی است")
            if sval:
                clean[fid] = sval[:4000]
    return clean


@router.post("/public/{template_id}/responses", status_code=201)
def submit_response(
    template_id: uuid.UUID,
    payload: FormSubmitRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    t = _get_template_or_404(db, template_id)
    if not t.is_active:
        raise HTTPException(status_code=409, detail="این فرم غیرفعال است؛ پاسخ پذیرفته نمی‌شود")
    clean = _validate_answers(t, payload.answers)

    call: CallSession | None = None
    if payload.call_id:
        try:
            call = db.get(CallSession, uuid.UUID(payload.call_id))
        except ValueError:
            call = None
        if call is None:
            raise HTTPException(status_code=404, detail="تماس یافت نشد")
        if call.callee_id != actor.id:
            raise HTTPException(status_code=403, detail="فقط گیرندهٔ تماس می‌تواند این نظرسنجی را تکمیل کند")
        dup = db.scalar(
            select(func.count()).select_from(FormResponse).where(
                FormResponse.call_id == call.id, FormResponse.respondent_id == actor.id
            )
        )
        if dup:
            raise HTTPException(status_code=409, detail="برای این تماس قبلاً نظرسنجی ثبت کرده‌اید")

    r = FormResponse(
        template_id=t.id,
        respondent_id=actor.id,
        subject_user_id=actor.id,
        call_id=call.id if call else None,
        answers=clean,
    )
    db.add(r)
    db.commit()
    record_audit(
        db, action="form.submitted", actor_user_id=actor.id,
        entity_type="form_template", entity_id=str(t.id),
        detail={"response": str(r.id), "call": str(call.id) if call else None},
    )
    db.commit()
    return {"ok": True, "id": str(r.id), "template_title": t.title}
