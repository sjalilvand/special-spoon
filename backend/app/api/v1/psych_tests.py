"""فاز ۳۵ - B37 سند جامع: تست روان‌شناسی و تفسیر — تصمیم D08 (ناظر علمی).

قواعد پذیرش:
- ساخت/ویرایش ابزار، سؤال و بازه تفسیر: مدیر (SYSTEM_ADMIN/ORG_MANAGER)؛
- «انتشار ابزار علمی فقط با تأیید ناظر علمی»: draft → pending_review
  (ارسال برای بازبینی توسط مدیر) → published | rejected — فقط نقش
  TECHNICAL_SUPERVISOR می‌تواند review کند (مدیر ۴۰۳)؛ بازرسی با
  یادداشت و هویت ناظر ثبت می‌شود؛
- تأیید ابزار بدون سؤال یا بدون حداقل یک بازه تفسیر ممنوع (۴۲۲)؛
  ویرایش ابزار منتشرشده → بازگشت به draft (نسخه علمی باید دوباره
  تأیید شود)؛
- برگزاری فقط ابزار منتشرشده؛ پاسخ‌ها اندیس گزینه‌اند؛ نمره = جمع
  امتیاز گزینه‌ها؛ تفسیر از بازه‌های ثبت‌شده (اولین بازه شامل نمره)؛
  نتیجه snapshot می‌شود؛ فهرست عمومی فقط منتشرشده‌ها.
"""
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.psych_test import (
    PsychAttempt,
    PsychInterpretation,
    PsychQuestion,
    PsychStatus,
    PsychTest,
)
from app.models.topics import Topic
from app.models.user import User

router = APIRouter(tags=["psych-tests"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
VIEW_ROLES = (*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")
REVIEWER_ROLES = ("TECHNICAL_SUPERVISOR",)  # D08: ناظر علمی

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?$")


def _validate_slug(slug: str) -> str:
    s = slug.strip().lower()
    if not _SLUG_RE.match(s):
        raise HTTPException(
            status_code=422, detail="slug فقط حروف کوچک لاتین، عدد و خط تیره است"
        )
    return s


def _test_out(db: Session, t: PsychTest, *, with_counts: bool = True) -> dict:
    topic = db.get(Topic, t.topic_id) if t.topic_id else None
    reviewer = db.get(User, t.reviewed_by) if t.reviewed_by else None
    out = {
        "id": str(t.id),
        "slug": t.slug,
        "title": t.title,
        "description": t.description,
        "topic_id": str(t.topic_id) if t.topic_id else None,
        "topic_name": topic.name if topic else None,
        "status": t.status,
        "review_note": t.review_note,
        "reviewed_by": reviewer.display_name if reviewer else None,
        "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
    if with_counts:
        out["question_count"] = int(
            db.scalar(select(func.count()).select_from(PsychQuestion).where(PsychQuestion.test_id == t.id)) or 0
        )
        out["interpretation_count"] = int(
            db.scalar(select(func.count()).select_from(PsychInterpretation).where(PsychInterpretation.test_id == t.id)) or 0
        )
        out["attempt_count"] = int(
            db.scalar(select(func.count()).select_from(PsychAttempt).where(PsychAttempt.test_id == t.id)) or 0
        )
    return out


def _question_out(q: PsychQuestion) -> dict:
    return {
        "id": str(q.id),
        "test_id": str(q.test_id),
        "prompt": q.prompt,
        "options": q.options or [],
        "sort_order": q.sort_order,
    }


def _interp_out(i: PsychInterpretation) -> dict:
    return {
        "id": str(i.id),
        "test_id": str(i.test_id),
        "score_min": i.score_min,
        "score_max": i.score_max,
        "label": i.label,
        "guidance": i.guidance,
        "sort_order": i.sort_order,
    }


def _attempt_out(a: PsychAttempt) -> dict:
    return {
        "id": str(a.id),
        "test_id": str(a.test_id),
        "user_id": str(a.user_id),
        "score": int(a.score or 0),
        "interpretation_label": a.interpretation_label,
        "interpretation_guidance": a.interpretation_guidance,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ---------------------------------------------------------------- schemas
class PsychTestCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    topic_id: uuid.UUID | None = None


class PsychTestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    topic_id: uuid.UUID | None = None


class PsychReviewAction(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=1000)


class QuestionCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    options: list[dict] = Field(min_length=2, max_length=10)  # [{"label","score"}]
    sort_order: int = Field(default=0, ge=0)


class InterpretationCreate(BaseModel):
    score_min: int = Field(ge=0)
    score_max: int = Field(ge=0)
    label: str = Field(min_length=2, max_length=200)
    guidance: str | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0)


class AttemptCreate(BaseModel):
    answers: list[int] = Field(min_length=1)


# ---------------------------------------------------------------- admin
@router.get("/psych-tests")
def list_tests(
    include_unpublished: bool = Query(default=True),
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(PsychTest).order_by(PsychTest.created_at.desc()).limit(200)
    if not include_unpublished:
        q = q.where(PsychTest.status == PsychStatus.PUBLISHED)
    return {"items": [_test_out(db, t) for t in db.scalars(q).all()]}


@router.post("/psych-tests", status_code=201)
def create_test(
    payload: PsychTestCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    slug = _validate_slug(payload.slug)
    if db.scalars(select(PsychTest.id).where(PsychTest.slug == slug)).first() is not None:
        raise HTTPException(status_code=409, detail="این slug قبلاً استفاده شده است")
    if payload.topic_id is not None and db.get(Topic, payload.topic_id) is None:
        raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
    t = PsychTest(
        slug=slug,
        title=payload.title.strip(),
        description=payload.description,
        topic_id=payload.topic_id,
        status=PsychStatus.DRAFT,
        created_by=actor.id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _test_out(db, t)


@router.patch("/psych-tests/{test_id}")
def update_test(
    test_id: uuid.UUID,
    payload: PsychTestUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    if payload.title is not None:
        t.title = payload.title.strip()
    if payload.description is not None:
        t.description = payload.description
    if payload.topic_id is not None:
        if db.get(Topic, payload.topic_id) is None:
            raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
        t.topic_id = payload.topic_id
    # ویرایش محتوای علمی منتشرشده → بازگشت به پیش‌نویس (D08: دوباره باید تأیید شود)
    if t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()
    db.refresh(t)
    return _test_out(db, t)


@router.post("/psych-tests/{test_id}/submit-review")
def submit_for_review(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """ارسال برای بازبینی ناظر علمی (D08) — از draft یا rejected."""
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    if t.status not in (PsychStatus.DRAFT, PsychStatus.REJECTED):
        raise HTTPException(
            status_code=409, detail="فقط ابزار پیش‌نویس یا رد‌شده قابل ارسال برای بازبینی است"
        )
    questions = db.scalar(
        select(func.count()).select_from(PsychQuestion).where(PsychQuestion.test_id == test_id)
    ) or 0
    if int(questions) == 0:
        raise HTTPException(status_code=422, detail="ابزار بدون سؤال قابل ارسال برای بازبینی نیست")
    ranges = db.scalar(
        select(func.count()).select_from(PsychInterpretation).where(PsychInterpretation.test_id == test_id)
    ) or 0
    if int(ranges) == 0:
        raise HTTPException(status_code=422, detail="ابزار بدون بازه تفسیر قابل ارسال برای بازبینی نیست")
    t.status = PsychStatus.PENDING_REVIEW
    db.commit()
    db.refresh(t)
    return _test_out(db, t)


@router.post("/psych-tests/{test_id}/review")
def review_test(
    test_id: uuid.UUID,
    payload: PsychReviewAction,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*REVIEWER_ROLES)),
) -> dict:
    """تصمیم ناظر علمی (D08): تأیید → published؛ رد → rejected با یادداشت."""
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    if t.status != PsychStatus.PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="این ابزار در انتظار بازبینی نیست")
    if payload.approve:
        ranges = db.scalar(
            select(func.count()).select_from(PsychInterpretation).where(PsychInterpretation.test_id == test_id)
        ) or 0
        if int(ranges) == 0:
            raise HTTPException(status_code=422, detail="تأیید ابزار بدون بازه تفسیر ممنوع است")
        t.status = PsychStatus.PUBLISHED
    else:
        if not payload.note:
            raise HTTPException(status_code=422, detail="رد ابزار نیازمند یادداشت ناظر علمی است")
        t.status = PsychStatus.REJECTED
    t.review_note = payload.note
    t.reviewed_by = actor.id
    t.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(t)
    return _test_out(db, t)


@router.post("/psych-tests/{test_id}/questions", status_code=201)
def add_question(
    test_id: uuid.UUID,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    clean: list[dict] = []
    for idx, opt in enumerate(payload.options):
        label = str(opt.get("label", "")).strip()
        score = opt.get("score", 0)
        if not label:
            raise HTTPException(status_code=422, detail=f"برچسب گزینه {idx + 1} الزامی است")
        try:
            score = int(score)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"امتیاز گزینه {idx + 1} باید عدد باشد")
        if score < 0:
            raise HTTPException(status_code=422, detail=f"امتیاز گزینه {idx + 1} نمی‌تواند منفی باشد")
        clean.append({"label": label, "score": score})
    q = PsychQuestion(test_id=test_id, prompt=payload.prompt.strip(), options=clean,
                      sort_order=payload.sort_order)
    db.add(q)
    if t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()
    db.refresh(q)
    return _question_out(q)


@router.delete("/psych-tests/{test_id}/questions/{question_id}", status_code=204)
def delete_question(
    test_id: uuid.UUID,
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    q = db.get(PsychQuestion, question_id)
    if q is None or q.test_id != test_id:
        raise HTTPException(status_code=404, detail="سؤال یافت نشد")
    db.delete(q)
    t = db.get(PsychTest, test_id)
    if t and t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()


@router.get("/psych-tests/{test_id}/questions")
def list_questions(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    rows = db.scalars(
        select(PsychQuestion).where(PsychQuestion.test_id == test_id).order_by(PsychQuestion.sort_order)
    ).all()
    return {"items": [_question_out(q) for q in rows]}


@router.post("/psych-tests/{test_id}/interpretations", status_code=201)
def add_interpretation(
    test_id: uuid.UUID,
    payload: InterpretationCreate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    if payload.score_max < payload.score_min:
        raise HTTPException(status_code=422, detail="حد بالای بازه نمی‌تواند کمتر از حد پایین باشد")
    i = PsychInterpretation(
        test_id=test_id,
        score_min=payload.score_min,
        score_max=payload.score_max,
        label=payload.label.strip(),
        guidance=payload.guidance,
        sort_order=payload.sort_order,
    )
    db.add(i)
    if t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()
    db.refresh(i)
    return _interp_out(i)


@router.delete("/psych-tests/{test_id}/interpretations/{interp_id}", status_code=204)
def delete_interpretation(
    test_id: uuid.UUID,
    interp_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    i = db.get(PsychInterpretation, interp_id)
    if i is None or i.test_id != test_id:
        raise HTTPException(status_code=404, detail="بازه تفسیر یافت نشد")
    db.delete(i)
    t = db.get(PsychTest, test_id)
    if t and t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()


@router.get("/psych-tests/{test_id}/interpretations")
def list_interpretations(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    rows = db.scalars(
        select(PsychInterpretation)
        .where(PsychInterpretation.test_id == test_id)
        .order_by(PsychInterpretation.sort_order, PsychInterpretation.score_min)
    ).all()
    return {"items": [_interp_out(i) for i in rows]}


@router.get("/psych-tests/{test_id}/attempts")
def list_attempts(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    rows = db.scalars(
        select(PsychAttempt)
        .where(PsychAttempt.test_id == test_id)
        .order_by(PsychAttempt.created_at.desc())
        .limit(200)
    ).all()
    return {"items": [_attempt_out(a) for a in rows]}


# ---------------------------------------------------------------- عمومی و اجرا
@router.get("/public/psych-tests")
def public_tests(db: Session = Depends(get_db)) -> dict:
    """فقط ابزارهای منتشرشده (تأیید ناظر علمی — D08)."""
    rows = db.scalars(
        select(PsychTest)
        .where(PsychTest.status == PsychStatus.PUBLISHED)
        .order_by(PsychTest.created_at.desc())
    ).all()
    out = []
    for t in rows:
        topic = db.get(Topic, t.topic_id) if t.topic_id else None
        if topic is not None and not topic.is_active:
            continue
        qc = db.scalar(select(func.count()).select_from(PsychQuestion).where(PsychQuestion.test_id == t.id)) or 0
        out.append(
            {
                "id": str(t.id),
                "slug": t.slug,
                "title": t.title,
                "description": t.description,
                "topic_name": topic.name if topic else None,
                "question_count": int(qc),
            }
        )
    return {"items": out}


@router.get("/public/psych-tests/{slug}/paper")
def public_paper(slug: str, db: Session = Depends(get_db)) -> dict:
    """پرسش‌نامه ابزار منتشرشده — امتیاز گزینه‌ها هرگز به کلاینت نمی‌رود."""
    t = db.scalars(
        select(PsychTest).where(PsychTest.slug == slug, PsychTest.status == PsychStatus.PUBLISHED)
    ).first()
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار منتشرنشده است")
    questions = db.scalars(
        select(PsychQuestion).where(PsychQuestion.test_id == t.id).order_by(PsychQuestion.sort_order)
    ).all()
    return {
        "test": {"id": str(t.id), "slug": t.slug, "title": t.title, "description": t.description},
        "questions": [
            {
                "id": str(q.id),
                "prompt": q.prompt,
                "options": [o.get("label") for o in (q.options or [])],
                "sort_order": q.sort_order,
            }
            for q in questions
        ],
    }


@router.post("/public/psych-tests/{slug}/attempts", status_code=201)
def take_test(
    slug: str,
    payload: AttemptCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """اجرای تست — نمره‌دهی و تفسیر سمت سرور؛ snapshot نتیجه."""
    t = db.scalars(
        select(PsychTest).where(PsychTest.slug == slug, PsychTest.status == PsychStatus.PUBLISHED)
    ).first()
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار منتشرنشده است")
    questions = db.scalars(
        select(PsychQuestion).where(PsychQuestion.test_id == t.id).order_by(PsychQuestion.sort_order)
    ).all()
    if not questions:
        raise HTTPException(status_code=422, detail="ابزار بدون سؤال قابل برگزاری نیست")
    answers = payload.answers
    for a in answers:
        if not isinstance(a, int) or a < 0:
            raise HTTPException(status_code=422, detail="پاسخ‌ها باید اندیس گزینه باشند")
    for idx, q in enumerate(questions):
        if idx < len(answers) and answers[idx] >= len(q.options or []):
            raise HTTPException(status_code=422, detail="اندیس پاسخ خارج از محدوده گزینه‌هاست")
    score = 0
    for idx, q in enumerate(questions):
        if idx < len(answers):
            opts = q.options or []
            try:
                score += int(opts[answers[idx]].get("score", 0))
            except (IndexError, TypeError, ValueError):
                pass
    interp = db.scalars(
        select(PsychInterpretation)
        .where(
            PsychInterpretation.test_id == t.id,
            PsychInterpretation.score_min <= score,
            PsychInterpretation.score_max >= score,
        )
        .order_by(PsychInterpretation.sort_order, PsychInterpretation.score_min)
    ).first()
    if interp is None:
        raise HTTPException(
            status_code=422, detail="بازه تفسیر برای این نمره تعریف نشده است؛ با پشتیبانی تماس بگیرید"
        )
    a = PsychAttempt(
        test_id=t.id,
        user_id=actor.id,
        score=score,
        interpretation_label=interp.label,
        interpretation_guidance=interp.guidance,
        answers=answers,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return {
        "attempt": _attempt_out(a),
        "disclaimer": "این نتیجه ابزار غربالگری است و جایگزین ارزیابی بالینی مشاور نیست",
    }


@router.get("/my/psych-results")
def my_results(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    rows = db.scalars(
        select(PsychAttempt)
        .where(PsychAttempt.user_id == actor.id)
        .order_by(PsychAttempt.created_at.desc())
        .limit(100)
    ).all()
    out = []
    for a in rows:
        t = db.get(PsychTest, a.test_id)
        item = _attempt_out(a)
        item["test_title"] = t.title if t else None
        out.append(item)
    return {"items": out}
