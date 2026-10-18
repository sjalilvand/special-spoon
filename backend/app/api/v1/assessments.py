import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.forms import (
    FORM_REGISTRY, get_form_definition, get_form_meta, get_form_version,
    list_forms, validate_finalization,
)
from app.db.session import get_db
from app.services.case_access import counselor_can_access
from app.models.assessment import Assessment, AssessmentStatus, FormVersion, ReviewAction
from app.models.case import Case, CaseStatus
from app.models.people import Applicant, Counselor
from app.models.user import User
from app.schemas.assessment import AssessmentCreate, AssessmentUpdate, ReviewDecision
from app.services.audit import record_audit

router = APIRouter(tags=["assessments"])

CLINICAL_ROLES = ("COUNSELOR", "TECHNICAL_SUPERVISOR")

# فرم پیش‌فرض برای سازگاری با نسخه‌های قبلی (RS-PS-04-01)
DEFAULT_FORM_CODE = "RS-PS-04-01"


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def _get_form_version(db: Session, form_code: str) -> FormVersion:
    """ثبت نسخه فرم در پایگاه داده (بند ۶.۲) - ایجاد تنبل در نخستین استفاده.

    برای هر کد فرم، نسخه جاری ماژول تعریف آن فرم ثبت می‌شود؛ اگر قبلاً
    همان نسخه ثبت شده باشد، همان رکورد بازیافت می‌شود (نسخه‌داری حفظ می‌شود).
    """
    meta = get_form_meta(form_code)
    version = get_form_version(form_code)
    fv = db.scalar(
        select(FormVersion).where(FormVersion.form_code == form_code, FormVersion.version == version)
    )
    if fv is None:
        fv = FormVersion(
            form_code=form_code, version=version,
            definition=get_form_definition(form_code), is_published=True,
        )
        db.add(fv)
        db.commit()
        db.refresh(fv)
    return fv


def _clinical_access(db: Session, actor, case: Case) -> None:
    """مشاور تخصیص‌یافته یا مسئول فنی؛ سایر نقش‌ها 404 (بند ۳.۲)."""
    roles = _roles(actor)
    if "TECHNICAL_SUPERVISOR" in roles:
        return
    if "COUNSELOR" in roles:
        c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if c is not None and counselor_can_access(db, c.id, case):
            return
    raise HTTPException(status_code=404, detail="پرونده یافت نشد")


def _assigned_counselor(db: Session, actor, case: Case) -> Counselor:
    """ثبت ارزیابی فقط با نقش مشاور و تخصیص جاری (بند ۳.۲)."""
    if "COUNSELOR" not in _roles(actor):
        raise HTTPException(status_code=403, detail="ثبت ارزیابی فقط با نقش مشاور و تخصیص جاری مجاز است")
    c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
    if c is None or not counselor_can_access(db, c.id, case):
        raise HTTPException(status_code=403, detail="این پرونده به شما تخصیص نیافته است")
    return c


def _next_version_no(db: Session, case_id) -> int:
    last = db.scalar(select(func.max(Assessment.version_no)).where(Assessment.case_id == case_id)) or 0
    return int(last) + 1


def _assessment_detail(db: Session, a: Assessment) -> dict:
    case = db.get(Case, a.case_id)
    applicant = db.get(Applicant, case.applicant_id) if case else None
    fv = db.get(FormVersion, a.form_version_id)
    author = db.get(User, a.author_user_id) if a.author_user_id else None
    finalizer = db.get(User, a.finalized_by) if a.finalized_by else None
    actions = db.scalars(
        select(ReviewAction).where(ReviewAction.assessment_id == a.id).order_by(ReviewAction.created_at)
    ).all()
    out_actions = []
    for r in actions:
        rv = db.get(User, r.reviewer_user_id) if r.reviewer_user_id else None
        out_actions.append({
            "id": str(r.id),
            "decision": r.decision,
            "comment": r.comment,
            "reviewer_name": rv.display_name if rv else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    meta = FORM_REGISTRY.get(fv.form_code if fv else "")
    return {
        "id": str(a.id),
        "case_id": str(a.case_id),
        "case_number": case.case_number if case else None,
        "applicant_name": (f"{applicant.first_name} {applicant.last_name}" if applicant else None),
        "form_code": fv.form_code if fv else None,
        "form_title": meta.title if meta else None,
        "form_definition": (fv.definition if fv else None),
        "form_version": fv.version if fv else None,
        "status": a.status,
        "version_no": a.version_no,
        "row_version": a.row_version,
        "previous_version_id": str(a.previous_version_id) if a.previous_version_id else None,
        "author_user_id": str(a.author_user_id) if a.author_user_id else None,
        "author_name": author.display_name if author else None,
        "finalized_by_name": finalizer.display_name if finalizer else None,
        "finalized_at": a.finalized_at.isoformat() if a.finalized_at else None,
        "answers": a.answers or {},
        "review_actions": out_actions,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


# ---------- تعریف فرم‌ها ----------

@router.get("/forms")
def get_forms(_actor=Depends(require_roles(*CLINICAL_ROLES))) -> dict:
    """فهرست فرم‌های بالینی منتشرشده برای انتخاب هنگام ایجاد ارزیابی جدید."""
    return {"items": list_forms()}


@router.get("/forms/{form_code}")
def get_form(form_code: str, db: Session = Depends(get_db), _actor=Depends(require_roles(*CLINICAL_ROLES))) -> dict:
    meta = get_form_meta(form_code)  # 404 اگر فرم ثبت نشده باشد
    fv = _get_form_version(db, form_code)
    return {
        "code": fv.form_code,
        "title": meta.title,
        "description": meta.description,
        "usage": meta.usage,
        "version": fv.version,
        "definition": fv.definition,
    }


# ---------- لیست/ایجاد ----------

@router.get("/cases/{case_id}/assessments")
def list_case_assessments(case_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    _clinical_access(db, actor, case)
    items = db.scalars(
        select(Assessment).where(Assessment.case_id == case.id)
        .order_by(Assessment.version_no.desc(), Assessment.created_at.desc())
    ).all()
    out = []
    for a in items:
        author = db.get(User, a.author_user_id) if a.author_user_id else None
        fv = db.get(FormVersion, a.form_version_id)
        meta = FORM_REGISTRY.get(fv.form_code if fv else "")
        out.append({
            "id": str(a.id), "case_id": str(a.case_id),
            "case_number": case.case_number,
            "applicant_name": None,
            "form_code": fv.form_code if fv else None,
            "form_title": meta.title if meta else None,
            "version_no": a.version_no, "status": a.status,
            "author_name": author.display_name if author else None,
            "finalized_at": a.finalized_at.isoformat() if a.finalized_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        })
    return {"items": out}


@router.post("/cases/{case_id}/assessments", status_code=201)
def create_assessment(case_id: uuid.UUID, payload: AssessmentCreate, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    if case.status in (CaseStatus.CLOSED, CaseStatus.ARCHIVED):
        raise HTTPException(status_code=409, detail="برای پرونده بسته یا بایگانی نمی‌توان ارزیابی ثبت کرد")
    _assigned_counselor(db, actor, case)
    form_code = payload.form_code or DEFAULT_FORM_CODE
    fv = _get_form_version(db, form_code)
    a = Assessment(
        case_id=case.id, form_version_id=fv.id,
        answers=payload.answers or {},
        status=AssessmentStatus.DRAFT,
        version_no=_next_version_no(db, case.id),
        author_user_id=actor.id,
    )
    db.add(a)
    db.commit()
    record_audit(db, action="assessment.created", actor_user_id=actor.id,
                 entity_type="assessment", entity_id=str(a.id))
    return _assessment_detail(db, a)


# ---------- جزئیات / ویرایش پیش‌نویس ----------

@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="ارزیابی یافت نشد")
    case = db.get(Case, a.case_id)
    _clinical_access(db, actor, case)
    # بند ۱۴: ثبت مشاهده بالینی
    record_audit(db, action="assessment.viewed", actor_user_id=actor.id,
                 entity_type="assessment", entity_id=str(a.id))
    return _assessment_detail(db, a)


@router.patch("/assessments/{assessment_id}")
def update_assessment(assessment_id: uuid.UUID, payload: AssessmentUpdate, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="ارزیابی یافت نشد")
    case = db.get(Case, a.case_id)
    _clinical_access(db, actor, case)
    if a.author_user_id != actor.id:
        raise HTTPException(status_code=403, detail="فقط نویسنده ارزیابی می‌تواند پیش‌نویس را ویرایش کند")
    if a.status not in (AssessmentStatus.DRAFT, AssessmentStatus.RETURNED):
        # بند ۶.۲: فرم نهایی بی‌ردپا تغییر نمی‌کند
        raise HTTPException(status_code=409, detail="فرم نهایی بی‌ردپا تغییر نمی‌کند؛ برای اصلاح، نسخه جدید بسازید")
    if payload.expected_version is not None and payload.expected_version != a.row_version:
        raise HTTPException(status_code=409, detail="این ارزیابی توسط کاربر دیگری تغییر کرده است؛ صفحه را بازخوانی کنید")
    a.answers = payload.answers
    a.row_version += 1
    db.commit()
    record_audit(db, action="assessment.updated", actor_user_id=actor.id,
                 entity_type="assessment", entity_id=str(a.id))
    return _assessment_detail(db, a)


# ---------- گردش: نهایی‌سازی / تأیید / برگشت / نسخه اصلاحی ----------

@router.post("/assessments/{assessment_id}/finalize")
def finalize_assessment(assessment_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="ارزیابی یافت نشد")
    case = db.get(Case, a.case_id)
    _clinical_access(db, actor, case)
    if a.author_user_id != actor.id:
        raise HTTPException(status_code=403, detail="فقط نویسنده ارزیابی می‌تواند آن را نهایی کند")
    if a.status not in (AssessmentStatus.DRAFT, AssessmentStatus.RETURNED):
        raise HTTPException(status_code=409, detail="این ارزیابی در وضعیت قابل نهایی‌سازی نیست")
    fv = db.get(FormVersion, a.form_version_id)
    form_code = fv.form_code if fv else DEFAULT_FORM_CODE
    errors = validate_finalization(form_code, a.answers or {})
    if errors:
        raise HTTPException(status_code=422, detail={
            "message": "نهایی‌سازی با اطلاعات ناقص مجاز نیست (بند ۶.۲)",
            "errors": errors,
        })
    a.status = AssessmentStatus.PENDING_REVIEW
    a.finalized_by = actor.id
    a.finalized_at = datetime.now(timezone.utc)
    a.row_version += 1
    db.commit()
    record_audit(db, action="assessment.finalized", actor_user_id=actor.id,
                 entity_type="assessment", entity_id=str(a.id))
    return _assessment_detail(db, a)


@router.post("/assessments/{assessment_id}/approve")
def approve_assessment(assessment_id: uuid.UUID, payload: ReviewDecision, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    if "TECHNICAL_SUPERVISOR" not in _roles(actor):
        raise HTTPException(status_code=403, detail="تأیید فقط توسط مسئول فنی مجاز است")
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="ارزیابی یافت نشد")
    if a.status != AssessmentStatus.PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="فقط ارزیابی در انتظار بررسی قابل تأیید است")
    if a.author_user_id == actor.id:
        # بند ۷.۲: مسئول فنی فرم خود را به‌عنوان تأییدکننده مستقل تأیید نمی‌کند
        raise HTTPException(status_code=409, detail="مسئول فنی نمی‌تواند فرم تألیف خود را تأیید کند (بند ۷.۲)")
    a.status = AssessmentStatus.APPROVED
    a.row_version += 1
    db.add(ReviewAction(
        assessment_id=a.id, reviewer_user_id=actor.id,
        decision="approved", comment=(payload.comment or None),
    ))
    db.commit()
    record_audit(db, action="assessment.approved", actor_user_id=actor.id,
                 entity_type="assessment", entity_id=str(a.id))
    return _assessment_detail(db, a)


@router.post("/assessments/{assessment_id}/return")
def return_assessment(assessment_id: uuid.UUID, payload: ReviewDecision, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    if "TECHNICAL_SUPERVISOR" not in _roles(actor):
        raise HTTPException(status_code=403, detail="برگشت فقط توسط مسئول فنی مجاز است")
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="ارزیابی یافت نشد")
    if a.status != AssessmentStatus.PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="فقط ارزیابی در انتظار بررسی قابل برگشت است")
    comment = (payload.comment or "").strip()
    if len(comment) < 5:
        # بند ۷.۲: برگشت فرم برای اصلاح، توضیح الزامی دارد
        raise HTTPException(status_code=422, detail="ثبت توضیح برای برگشت الزامی است (بند ۷.۲)")
    a.status = AssessmentStatus.RETURNED
    a.row_version += 1
    db.add(ReviewAction(assessment_id=a.id, reviewer_user_id=actor.id, decision="returned", comment=comment))
    db.commit()
    record_audit(db, action="assessment.returned", actor_user_id=actor.id,
                 entity_type="assessment", entity_id=str(a.id))
    return _assessment_detail(db, a)


@router.post("/assessments/{assessment_id}/revisions", status_code=201)
def create_revision(assessment_id: uuid.UUID, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="ارزیابی یافت نشد")
    case = db.get(Case, a.case_id)
    _clinical_access(db, actor, case)
    if a.author_user_id != actor.id:
        raise HTTPException(status_code=403, detail="نسخه اصلاحی فقط توسط نویسنده ارزیابی ایجاد می‌شود")
    if a.status not in (AssessmentStatus.PENDING_REVIEW, AssessmentStatus.APPROVED, AssessmentStatus.FINALIZED):
        raise HTTPException(status_code=409, detail="اصلاح نسخه فقط برای فرم نهایی/در بررسی/تأییدشده مجاز است")
    # بند ۶.۲/۷.۲: اصلاح فرم نهایی، نسخه جدید با ارتباط به نسخه قبلی ایجاد می‌کند
    rev = Assessment(
        case_id=a.case_id, form_version_id=a.form_version_id,
        answers=dict(a.answers or {}),
        status=AssessmentStatus.DRAFT,
        version_no=_next_version_no(db, a.case_id),
        previous_version_id=a.id,
        author_user_id=actor.id,
    )
    db.add(rev)
    db.commit()
    record_audit(db, action="assessment.revision_created", actor_user_id=actor.id,
                 entity_type="assessment", entity_id=str(rev.id),
                 detail={"previous_assessment_id": str(a.id)})
    return _assessment_detail(db, rev)


# ---------- کارتابل‌ها (بند ۹.۱ و ۹.۴) ----------

# ثابت‌های کارتابل هشدار سطح ۳ (فرم مورد حاد RS-PS-08-01)
ACUTE_FORM_CODE = "RS-PS-08-01"
ACUTE_SEVERITY_KEY = "initial_assessment.severity"
ACUTE_SEVERITY_LABELS = {
    "level_1": "سطح ۱ (نیازمند پایش)",
    "level_2": "سطح ۲ (متوسط)",
    "level_3": "سطح ۳ (بالا)",
}
ACUTE_RISK_TYPE_LABELS = {
    "suicidal_ideation": "افکار خودکشی یا آسیب به خود",
    "suicide_attempt": "قصد یا اقدام به خودکشی",
    "harm_to_others": "آسیب به دیگران",
    "child_abuse": "کودک‌آزاری",
    "violence": "خشونت",
    "severe_crisis": "بحران شدید",
    "other": "سایر",
}


def _level3_condition():
    """شرط JSONB: سطح فوریت ۳ در پاسخ‌های فرم مورد حاد (کلیدهای تخت نقطه‌دار)."""
    return (
        FormVersion.form_code == ACUTE_FORM_CODE,
        Assessment.answers[ACUTE_SEVERITY_KEY].as_string() == "level_3",
    )


@router.get("/worklists/level3")
def level3_alert_worklist(db: Session = Depends(get_db), _actor=Depends(require_roles("TECHNICAL_SUPERVISOR"))) -> dict:
    """کارتابل هشدار سطح ۳ مسئول فنی — چرخه فرم مورد حاد را کامل می‌کند (فاز ۲۳).

    - items: فرم‌های RS-PS-08-01 نهایی‌شده با سطح فوریت ۳ که در انتظار بررسی
      (pending_review) هستند؛ قدیمی‌ترین هشدار اول تا هیچ موردی جا نماند.
    - total_level3: مجموع همه هشدارهای سطح ۳ ثبت‌شده (هر وضعیتی) برای نمایش در سربرگ.
    - خروجی شامل جزئیات فوری از پاسخ‌هاست: فرد در فرم، نوع خطر، اقدام فوری،
      مقصد و نتیجه ارجاع — بدون نیاز به باز کردن هر فرم.
    """
    rows = db.execute(
        select(Assessment, Case, Applicant, User, FormVersion)
        .join(Case, Assessment.case_id == Case.id)
        .join(Applicant, Case.applicant_id == Applicant.id)
        .outerjoin(User, Assessment.author_user_id == User.id)
        .join(FormVersion, Assessment.form_version_id == FormVersion.id)
        .where(*_level3_condition(), Assessment.status == AssessmentStatus.PENDING_REVIEW)
        .order_by(Assessment.finalized_at.asc())
        .limit(50)
    ).all()
    total_level3 = db.scalar(
        select(func.count())
        .select_from(Assessment)
        .join(FormVersion, Assessment.form_version_id == FormVersion.id)
        .where(*_level3_condition())
    ) or 0
    acute_meta = FORM_REGISTRY.get(ACUTE_FORM_CODE)
    items = []
    for a, c, ap, u, fv in rows:
        answers = a.answers or {}
        risk = answers.get("initial_assessment.risk_types")
        items.append({
            "id": str(a.id),
            "case_id": str(c.id),
            "case_number": c.case_number,
            "applicant_name": f"{ap.first_name} {ap.last_name}",
            "form_code": fv.form_code,
            "form_title": acute_meta.title if acute_meta else None,
            "status": a.status,
            "version_no": a.version_no,
            "author_name": u.display_name if u else None,
            "finalized_at": a.finalized_at.isoformat() if a.finalized_at else None,
            "severity_label": ACUTE_SEVERITY_LABELS.get(answers.get(ACUTE_SEVERITY_KEY), answers.get(ACUTE_SEVERITY_KEY)),
            "person_name": answers.get("person_info.full_name"),
            "person_phone": answers.get("person_info.phone"),
            "risk_types": [ACUTE_RISK_TYPE_LABELS.get(v, v) for v in risk] if isinstance(risk, list) else [],
            "immediate_action": answers.get("initial_assessment.immediate_action"),
            "referral_destination": answers.get("referral_info.referral_destination"),
            "referral_result": answers.get("referral_info.referral_result"),
        })
    return {"items": items, "total_level3": int(total_level3)}


@router.get("/worklists/supervisor")
def supervisor_worklist(db: Session = Depends(get_db), _actor=Depends(require_roles("TECHNICAL_SUPERVISOR"))) -> dict:
    rows = db.execute(
        select(Assessment, Case, Applicant, User)
        .join(Case, Assessment.case_id == Case.id)
        .join(Applicant, Case.applicant_id == Applicant.id)
        .outerjoin(User, Assessment.author_user_id == User.id)
        .where(Assessment.status == AssessmentStatus.PENDING_REVIEW)
        .order_by(Assessment.finalized_at)
        .limit(50)
    ).all()
    items = []
    for a, c, ap, u in rows:
        fv = db.get(FormVersion, a.form_version_id)
        meta = FORM_REGISTRY.get(fv.form_code if fv else "")
        items.append({
            "id": str(a.id), "case_id": str(c.id), "case_number": c.case_number,
            "applicant_name": f"{ap.first_name} {ap.last_name}",
            "form_code": fv.form_code if fv else None,
            "form_title": meta.title if meta else None,
            "version_no": a.version_no, "status": a.status,
            "author_name": u.display_name if u else None,
            "finalized_at": a.finalized_at.isoformat() if a.finalized_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        })
    return {"items": items}


@router.get("/worklists/counselor")
def counselor_worklist(db: Session = Depends(get_db), actor=Depends(require_roles("COUNSELOR"))) -> dict:
    c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
    if c is None:
        return {"items": []}
    rows = db.execute(
        select(Assessment, Case, Applicant, User)
        .join(Case, Assessment.case_id == Case.id)
        .join(Applicant, Case.applicant_id == Applicant.id)
        .outerjoin(User, Assessment.author_user_id == User.id)
        .where(
            Case.primary_counselor_id == c.id,
            Assessment.status.in_((AssessmentStatus.DRAFT, AssessmentStatus.RETURNED)),
        )
        .order_by(Assessment.updated_at.desc())
        .limit(50)
    ).all()
    items = []
    for a, cs, ap, u in rows:
        fv = db.get(FormVersion, a.form_version_id)
        meta = FORM_REGISTRY.get(fv.form_code if fv else "")
        items.append({
            "id": str(a.id), "case_id": str(cs.id), "case_number": cs.case_number,
            "applicant_name": f"{ap.first_name} {ap.last_name}",
            "form_code": fv.form_code if fv else None,
            "form_title": meta.title if meta else None,
            "version_no": a.version_no, "status": a.status,
            "author_name": u.display_name if u else None,
            "finalized_at": a.finalized_at.isoformat() if a.finalized_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        })
    return {"items": items}
