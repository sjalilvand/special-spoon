"""فاز ۳۴ - B33/B34/B35/B36 سند جامع: محتوا، دوره، آزمون و گواهی.

قواعد پذیرش کلیدی:
- B33: slug یکتا (۴۰۹)؛ انتشار صریح (draft → published)؛ «محتوای
  منتشرشده زیر دسته غیرفعال در صفحات عمومی نشان داده نمی‌شود».
- B34: دوره رایگان ثبت‌نام فوری فعال؛ دوره پولی سفارش kind='course'
  با snapshot قیمت می‌سازد و پس از پرداخت موفق فعال می‌شود (B10)؛
  ظرفیت پر ۴۰۹؛ ثبت‌نام تکراری ۴۰۹.
- B35: «پاسخ صحیح سؤال‌ها هرگز به کلاینت نمی‌رود»؛ نمره‌دهی سمت سرور؛
  تلاش بیش از سقف ۴۰۹؛ آزمون دوره‌ای نیازمند ثبت‌نام فعال؛ آزمون
  پولی نیازمند سفارش پرداخت‌شده kind='exam'.
- B36: گواهی پس از قبولی خودکار (idempotent) و پس از تکمیل دوره با
  اقدام مدیر؛ شماره یکتای جلالی؛ verify عمومی؛ ابطال با پرچم.
"""
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.learning import (
    AttemptStatus,
    Certificate,
    Content,
    Course,
    CourseEnrollment,
    CourseSession,
    EnrollmentStatus,
    Exam,
    ExamAttempt,
    ExamQuestion,
    PublishStatus,
)
from app.models.payment import Order, OrderStatus
from app.models.topics import Topic
from app.models.user import User
from app.services import learning as learn
from app.services import payments as pay

router = APIRouter(tags=["learning"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
VIEW_ROLES = (*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION")

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?$")


# ---------------------------------------------------------------- helpers
def _validate_slug(slug: str) -> str:
    s = slug.strip().lower()
    if not _SLUG_RE.match(s):
        raise HTTPException(
            status_code=422, detail="slug فقط حروف کوچک لاتین، عدد و خط تیره است"
        )
    return s


def _user_display_name(db: Session, user_id: uuid.UUID) -> str | None:
    u = db.get(User, user_id)
    return u.display_name if u else None


def _content_out(c: Content, topic: Topic | None = None) -> dict:
    return {
        "id": str(c.id),
        "slug": c.slug,
        "title": c.title,
        "summary": c.summary,
        "body": c.body,
        "topic_id": str(c.topic_id) if c.topic_id else None,
        "topic_name": topic.name if topic else None,
        "status": c.status,
        "published_at": c.published_at.isoformat() if c.published_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _course_out(db: Session, c: Course, *, with_stats: bool = True) -> dict:
    topic = db.get(Topic, c.topic_id) if c.topic_id else None
    out = {
        "id": str(c.id),
        "slug": c.slug,
        "title": c.title,
        "summary": c.summary,
        "description": c.description,
        "topic_id": str(c.topic_id) if c.topic_id else None,
        "topic_name": topic.name if topic else None,
        "status": c.status,
        "price_amount": int(c.price_amount),
        "currency": c.currency,
        "is_free": int(c.price_amount) == 0,
        "capacity": c.capacity,
        "starts_at": c.starts_at.isoformat() if c.starts_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
    if with_stats:
        taken = db.scalar(
            select(func.count()).select_from(CourseEnrollment).where(
                CourseEnrollment.course_id == c.id,
                CourseEnrollment.status.in_(
                    (EnrollmentStatus.PENDING, EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)
                ),
            )
        ) or 0
        sessions = db.scalars(
            select(CourseSession).where(CourseSession.course_id == c.id).order_by(CourseSession.sort_order)
        ).all()
        out["enrolled_count"] = int(taken)
        out["remaining_capacity"] = (c.capacity - int(taken)) if c.capacity else None
        out["sessions"] = [
            {
                "id": str(s.id),
                "title": s.title,
                "session_date": s.session_date.isoformat(),
                "duration_minutes": s.duration_minutes,
                "sort_order": s.sort_order,
            }
            for s in sessions
        ]
    return out


def _exam_out(db: Session, e: Exam, *, with_question_count: bool = True) -> dict:
    topic = db.get(Topic, e.topic_id) if e.topic_id else None
    course = db.get(Course, e.course_id) if e.course_id else None
    out = {
        "id": str(e.id),
        "slug": e.slug,
        "title": e.title,
        "description": e.description,
        "topic_id": str(e.topic_id) if e.topic_id else None,
        "topic_name": topic.name if topic else None,
        "course_id": str(e.course_id) if e.course_id else None,
        "course_title": course.title if course else None,
        "status": e.status,
        "duration_minutes": e.duration_minutes,
        "pass_percent": e.pass_percent,
        "price_amount": int(e.price_amount),
        "currency": e.currency,
        "is_free": int(e.price_amount) == 0,
        "max_attempts": e.max_attempts,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
    if with_question_count:
        qc = db.scalar(
            select(func.count()).select_from(ExamQuestion).where(ExamQuestion.exam_id == e.id)
        )
        out["question_count"] = int(qc or 0)
    return out


def _question_out(q: ExamQuestion, *, include_answer: bool) -> dict:
    out = {
        "id": str(q.id),
        "exam_id": str(q.exam_id),
        "prompt": q.prompt,
        "options": q.options or [],
        "points": q.points,
        "sort_order": q.sort_order,
    }
    if include_answer:
        out["correct_index"] = q.correct_index
    return out


def _attempt_out(a: ExamAttempt) -> dict:
    return {
        "id": str(a.id),
        "exam_id": str(a.exam_id),
        "user_id": str(a.user_id),
        "status": a.status,
        "score_percent": float(a.score_percent) if a.score_percent is not None else None,
        "started_at": a.started_at.isoformat() if a.started_at else None,
        "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
    }


def _certificate_out(c: Certificate) -> dict:
    return {
        "id": str(c.id),
        "certificate_number": c.certificate_number,
        "user_id": str(c.user_id),
        "course_id": str(c.course_id) if c.course_id else None,
        "exam_id": str(c.exam_id) if c.exam_id else None,
        "title": c.title,
        "holder_name": c.holder_name,
        "revoked": c.revoked,
        "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        "revoke_reason": c.revoke_reason,
        "issued_at": c.issued_at.isoformat() if c.issued_at else None,
    }


def _create_learning_order(
    db: Session,
    *,
    kind: str,
    owner_user_id: uuid.UUID,
    amount: int,
    title: str,
    course_id: uuid.UUID | None = None,
    exam_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
) -> Order:
    """سفارش ثبت‌نام دوره / دسترسی آزمون — snapshot قیمت (B07)."""
    order = Order(
        order_number=pay.generate_order_number(db),
        owner_user_id=owner_user_id,
        title=title[:300],
        amount=amount,
        currency="IRR",
        payable_amount=amount,
        status=OrderStatus.PENDING,
        kind=kind,
        course_id=course_id,
        exam_id=exam_id,
        created_by=actor_id,
    )
    db.add(order)
    db.flush()
    return order


# ================================================================ B33 محتوا
class ContentCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=300)
    summary: str | None = Field(default=None, max_length=500)
    body: str = Field(default="", max_length=100_000)
    topic_id: uuid.UUID | None = None


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    summary: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=100_000)
    topic_id: uuid.UUID | None = None
    status: str | None = None


@router.get("/contents")
def list_contents(
    include_unpublished: bool = Query(default=True),
    topic_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(Content).order_by(Content.created_at.desc()).limit(200)
    if not include_unpublished:
        q = q.where(Content.status == PublishStatus.PUBLISHED)
    if topic_id is not None:
        q = q.where(Content.topic_id == topic_id)
    rows = db.scalars(q).all()
    out = []
    for c in rows:
        topic = db.get(Topic, c.topic_id) if c.topic_id else None
        out.append(_content_out(c, topic))
    return {"items": out}


@router.post("/contents", status_code=201)
def create_content(
    payload: ContentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    slug = _validate_slug(payload.slug)
    if db.scalars(select(Content.id).where(Content.slug == slug)).first() is not None:
        raise HTTPException(status_code=409, detail="این slug قبلاً استفاده شده است")
    topic = None
    if payload.topic_id is not None:
        topic = db.get(Topic, payload.topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
    c = Content(
        slug=slug,
        title=payload.title.strip(),
        summary=payload.summary,
        body=payload.body,
        topic_id=payload.topic_id,
        status=PublishStatus.DRAFT,
        author_id=actor.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _content_out(c, topic)


@router.patch("/contents/{content_id}")
def update_content(
    content_id: uuid.UUID,
    payload: ContentUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    c = db.get(Content, content_id)
    if c is None:
        raise HTTPException(status_code=404, detail="محتوا یافت نشد")
    if payload.status is not None:
        if payload.status not in PublishStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت باید draft یا published باشد")
        if payload.status == PublishStatus.PUBLISHED and c.status != PublishStatus.PUBLISHED:
            c.published_at = datetime.now(timezone.utc)
        c.status = payload.status
    for field in ("title", "summary", "body"):
        value = getattr(payload, field)
        if value is not None:
            setattr(c, field, value.strip() if isinstance(value, str) else value)
    if payload.topic_id is not None:
        if db.get(Topic, payload.topic_id) is None:
            raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
        c.topic_id = payload.topic_id
    db.commit()
    db.refresh(c)
    return _content_out(c, db.get(Topic, c.topic_id) if c.topic_id else None)


@router.delete("/contents/{content_id}", status_code=204)
def delete_content(
    content_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    c = db.get(Content, content_id)
    if c is None:
        raise HTTPException(status_code=404, detail="محتوا یافت نشد")
    db.delete(c)
    db.commit()


# ================================================================ B34 دوره
class CourseCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=300)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    topic_id: uuid.UUID | None = None
    price_amount: int = Field(default=0, ge=0)
    capacity: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    topic_id: uuid.UUID | None = None
    status: str | None = None
    price_amount: int | None = Field(default=None, ge=0)
    capacity: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None


class SessionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    session_date: datetime
    duration_minutes: int = Field(default=90, gt=0)
    sort_order: int = Field(default=0, ge=0)


class StaffEnroll(BaseModel):
    owner_user_id: uuid.UUID


class EnrollmentUpdate(BaseModel):
    status: str | None = None
    note: str | None = Field(default=None, max_length=500)


@router.get("/courses")
def list_courses(
    include_unpublished: bool = Query(default=True),
    topic_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(Course).order_by(Course.created_at.desc()).limit(200)
    if not include_unpublished:
        q = q.where(Course.status == PublishStatus.PUBLISHED)
    if topic_id is not None:
        q = q.where(Course.topic_id == topic_id)
    return {"items": [_course_out(db, c) for c in db.scalars(q).all()]}


@router.post("/courses", status_code=201)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    slug = _validate_slug(payload.slug)
    if db.scalars(select(Course.id).where(Course.slug == slug)).first() is not None:
        raise HTTPException(status_code=409, detail="این slug قبلاً استفاده شده است")
    if payload.topic_id is not None and db.get(Topic, payload.topic_id) is None:
        raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
    c = Course(
        slug=slug,
        title=payload.title.strip(),
        summary=payload.summary,
        description=payload.description,
        topic_id=payload.topic_id,
        price_amount=payload.price_amount,
        capacity=payload.capacity,
        starts_at=payload.starts_at,
        created_by=actor.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _course_out(db, c)


@router.patch("/courses/{course_id}")
def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    c = db.get(Course, course_id)
    if c is None:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")
    if payload.status is not None:
        if payload.status not in PublishStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت باید draft یا published باشد")
        c.status = payload.status
    for field in ("title", "summary", "description"):
        value = getattr(payload, field)
        if value is not None:
            setattr(c, field, value.strip() if isinstance(value, str) else value)
    if payload.topic_id is not None:
        if db.get(Topic, payload.topic_id) is None:
            raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
        c.topic_id = payload.topic_id
    if payload.price_amount is not None:
        c.price_amount = payload.price_amount
    if payload.capacity is not None:
        c.capacity = payload.capacity
    if payload.starts_at is not None:
        c.starts_at = payload.starts_at
    db.commit()
    db.refresh(c)
    return _course_out(db, c)


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    c = db.get(Course, course_id)
    if c is None:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")
    used = db.scalar(
        select(func.count()).select_from(CourseEnrollment).where(CourseEnrollment.course_id == course_id)
    )
    if (used or 0) > 0:
        raise HTTPException(
            status_code=409, detail="دوره ثبت‌نام دارد؛ حذف ممنوع است (تاریخچه حفظ می‌شود)"
        )
    sessions = db.scalar(
        select(func.count()).select_from(CourseSession).where(CourseSession.course_id == course_id)
    )
    if (sessions or 0) > 0:
        raise HTTPException(status_code=409, detail="دوره جلسه ثبت‌شده دارد؛ ابتدا جلسات را حذف کنید")
    db.delete(c)
    db.commit()


@router.post("/courses/{course_id}/sessions", status_code=201)
def create_session(
    course_id: uuid.UUID,
    payload: SessionCreate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    c = db.get(Course, course_id)
    if c is None:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")
    s = CourseSession(
        course_id=course_id,
        title=payload.title.strip(),
        session_date=payload.session_date,
        duration_minutes=payload.duration_minutes,
        sort_order=payload.sort_order,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return {
        "id": str(s.id),
        "course_id": str(s.course_id),
        "title": s.title,
        "session_date": s.session_date.isoformat(),
        "duration_minutes": s.duration_minutes,
        "sort_order": s.sort_order,
    }


@router.delete("/courses/{course_id}/sessions/{session_id}", status_code=204)
def delete_session(
    course_id: uuid.UUID,
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    s = db.get(CourseSession, session_id)
    if s is None or s.course_id != course_id:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد")
    db.delete(s)
    db.commit()


@router.get("/courses/{course_id}/enrollments")
def list_enrollments(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    c = db.get(Course, course_id)
    if c is None:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")
    rows = db.scalars(
        select(CourseEnrollment)
        .where(CourseEnrollment.course_id == course_id)
        .order_by(CourseEnrollment.created_at.desc())
    ).all()
    items = []
    for e in rows:
        u = db.get(User, e.user_id)
        order = db.get(Order, e.order_id) if e.order_id else None
        items.append(
            {
                "id": str(e.id),
                "course_id": str(e.course_id),
                "user_id": str(e.user_id),
                "username": u.username if u else None,
                "display_name": u.display_name if u else None,
                "status": e.status,
                "order_id": str(e.order_id) if e.order_id else None,
                "order_number": order.order_number if order else None,
                "order_status": order.status if order else None,
                "activated_at": e.activated_at.isoformat() if e.activated_at else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
        )
    return {"items": items}


@router.patch("/enrollments/{enrollment_id}")
def update_enrollment(
    enrollment_id: uuid.UUID,
    payload: EnrollmentUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    e = db.get(CourseEnrollment, enrollment_id)
    if e is None:
        raise HTTPException(status_code=404, detail="ثبت‌نام یافت نشد")
    if payload.status is not None:
        if payload.status not in EnrollmentStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت ثبت‌نام نامعتبر است")
        e.status = payload.status
        if payload.status == EnrollmentStatus.ACTIVE and e.activated_at is None:
            from app.services.learning import utcnow

            e.activated_at = utcnow()
        if payload.status == EnrollmentStatus.COMPLETED:
            # فاز ۳۴ - B36: تکمیل دوره → صدور خودکار گواهی دوره (idempotent)
            course = db.get(Course, e.course_id)
            learn.issue_certificate(
                db,
                user_id=e.user_id,
                title=f"گواهی تکمیل دوره «{course.title}»",
                holder_name=_user_display_name(db, e.user_id),
                course_id=e.course_id,
                actor_id=actor.id,
                commit=False,
            )
    if payload.note is not None:
        e.note = payload.note
    db.commit()
    certs = db.scalars(
        select(Certificate).where(Certificate.course_id == e.course_id, Certificate.user_id == e.user_id)
    ).all()
    out = {
        "id": str(e.id),
        "course_id": str(e.course_id),
        "user_id": str(e.user_id),
        "status": e.status,
        "activated_at": e.activated_at.isoformat() if e.activated_at else None,
        "note": e.note,
        "certificates": [_certificate_out(c) for c in certs],
    }
    return out


def _enroll_user(db: Session, course: Course, user_id: uuid.UUID, actor_id: uuid.UUID | None) -> dict:
    """موتور ثبت‌نام مشترک (خودکاربر / مدیر) — رایگان: فعال فوری؛
    پولی: سفارش kind='course' + pending تا پرداخت."""
    if course.status != PublishStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="دوره منتشر نشده است")
    existing = db.scalars(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course.id, CourseEnrollment.user_id == user_id
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="کاربر قبلاً در این دوره ثبت‌نام کرده است")
    if course.capacity is not None:
        taken = db.scalar(
            select(func.count()).select_from(CourseEnrollment).where(
                CourseEnrollment.course_id == course.id,
                CourseEnrollment.status.in_(
                    (EnrollmentStatus.PENDING, EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)
                ),
            )
        ) or 0
        if int(taken) >= course.capacity:
            raise HTTPException(status_code=409, detail="ظرفیت دوره تکمیل است")
    order = None
    status = EnrollmentStatus.PENDING
    if int(course.price_amount) == 0:
        status = EnrollmentStatus.ACTIVE
    else:
        order = _create_learning_order(
            db,
            kind="course",
            owner_user_id=user_id,
            amount=int(course.price_amount),
            title=f"ثبت‌نام دوره «{course.title}»",
            course_id=course.id,
            actor_id=actor_id,
        )
    enr = CourseEnrollment(
        course_id=course.id,
        user_id=user_id,
        status=status,
        order_id=order.id if order else None,
        activated_at=datetime.now(timezone.utc) if status == EnrollmentStatus.ACTIVE else None,
    )
    db.add(enr)
    db.commit()
    db.refresh(enr)
    return {
        "enrollment": {
            "id": str(enr.id),
            "course_id": str(enr.course_id),
            "user_id": str(enr.user_id),
            "status": enr.status,
            "order_id": str(enr.order_id) if enr.order_id else None,
            "activated_at": enr.activated_at.isoformat() if enr.activated_at else None,
        },
        "order": (
            {
                "id": str(order.id),
                "order_number": order.order_number,
                "amount": float(order.amount),
                "payable_amount": float(order.payable_amount),
                "status": order.status,
                "kind": order.kind,
            }
            if order
            else None
        ),
    }


# ================================================================ B35 آزمون
class ExamCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    topic_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    duration_minutes: int = Field(default=30, gt=0)
    pass_percent: int = Field(default=60, ge=0, le=100)
    price_amount: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=1, ge=1)


class ExamUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    topic_id: uuid.UUID | None = None
    status: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    pass_percent: int | None = Field(default=None, ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1)


class QuestionCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int = Field(ge=0)
    points: int = Field(default=1, ge=1)
    sort_order: int = Field(default=0, ge=0)


class QuestionUpdate(BaseModel):
    prompt: str | None = Field(default=None, min_length=3, max_length=1000)
    options: list[str] | None = Field(default=None, min_length=2, max_length=6)
    correct_index: int | None = Field(default=None, ge=0)
    points: int | None = Field(default=None, ge=1)
    sort_order: int | None = Field(default=None, ge=0)


class AttemptSubmit(BaseModel):
    answers: list[int] = Field(default_factory=list)


@router.get("/exams")
def list_exams(
    include_unpublished: bool = Query(default=True),
    topic_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(Exam).order_by(Exam.created_at.desc()).limit(200)
    if not include_unpublished:
        q = q.where(Exam.status == PublishStatus.PUBLISHED)
    if topic_id is not None:
        q = q.where(Exam.topic_id == topic_id)
    return {"items": [_exam_out(db, e) for e in db.scalars(q).all()]}


@router.post("/exams", status_code=201)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    slug = _validate_slug(payload.slug)
    if db.scalars(select(Exam.id).where(Exam.slug == slug)).first() is not None:
        raise HTTPException(status_code=409, detail="این slug قبلاً استفاده شده است")
    if payload.topic_id is not None and db.get(Topic, payload.topic_id) is None:
        raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
    if payload.course_id is not None and db.get(Course, payload.course_id) is None:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")
    e = Exam(
        slug=slug,
        title=payload.title.strip(),
        description=payload.description,
        topic_id=payload.topic_id,
        course_id=payload.course_id,
        duration_minutes=payload.duration_minutes,
        pass_percent=payload.pass_percent,
        price_amount=payload.price_amount,
        max_attempts=payload.max_attempts,
        created_by=actor.id,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _exam_out(db, e)


@router.patch("/exams/{exam_id}")
def update_exam(
    exam_id: uuid.UUID,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    e = db.get(Exam, exam_id)
    if e is None:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
    if payload.status is not None:
        if payload.status not in PublishStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت باید draft یا published باشد")
        e.status = payload.status
    if payload.title is not None:
        e.title = payload.title.strip()
    if payload.description is not None:
        e.description = payload.description
    if payload.topic_id is not None:
        if db.get(Topic, payload.topic_id) is None:
            raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
        e.topic_id = payload.topic_id
    if payload.duration_minutes is not None:
        e.duration_minutes = payload.duration_minutes
    if payload.pass_percent is not None:
        e.pass_percent = payload.pass_percent
    if payload.max_attempts is not None:
        e.max_attempts = payload.max_attempts
    db.commit()
    db.refresh(e)
    return _exam_out(db, e)


@router.delete("/exams/{exam_id}", status_code=204)
def delete_exam(
    exam_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    e = db.get(Exam, exam_id)
    if e is None:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
    used = db.scalar(
        select(func.count()).select_from(ExamAttempt).where(ExamAttempt.exam_id == exam_id)
    )
    if (used or 0) > 0:
        raise HTTPException(status_code=409, detail="آزمون تلاش ثبت‌شده دارد؛ حذف ممنوع است")
    db.delete(e)
    db.commit()


@router.post("/exams/{exam_id}/questions", status_code=201)
def create_question(
    exam_id: uuid.UUID,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    e = db.get(Exam, exam_id)
    if e is None:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
    if len(payload.options) < 2 or len(payload.options) > 6:
        raise HTTPException(status_code=422, detail="تعداد گزینه‌ها باید ۲ تا ۶ باشد")
    if payload.correct_index >= len(payload.options):
        raise HTTPException(status_code=422, detail="اندیس پاسخ صحیح خارج از محدوده گزینه‌هاست")
    q = ExamQuestion(
        exam_id=exam_id,
        prompt=payload.prompt.strip(),
        options=payload.options,
        correct_index=payload.correct_index,
        points=payload.points,
        sort_order=payload.sort_order,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return _question_out(q, include_answer=True)


@router.patch("/exams/{exam_id}/questions/{question_id}")
def update_question(
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    q = db.get(ExamQuestion, question_id)
    if q is None or q.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="سؤال یافت نشد")
    if payload.options is not None:
        if len(payload.options) < 2 or len(payload.options) > 6:
            raise HTTPException(status_code=422, detail="تعداد گزینه‌ها باید ۲ تا ۶ باشد")
        q.options = payload.options
    if payload.correct_index is not None:
        opts = q.options or []
        if payload.correct_index >= len(opts):
            raise HTTPException(status_code=422, detail="اندیس پاسخ صحیح خارج از محدوده گزینه‌هاست")
        q.correct_index = payload.correct_index
    if payload.prompt is not None:
        q.prompt = payload.prompt.strip()
    if payload.points is not None:
        q.points = payload.points
    if payload.sort_order is not None:
        q.sort_order = payload.sort_order
    db.commit()
    db.refresh(q)
    return _question_out(q, include_answer=True)


@router.delete("/exams/{exam_id}/questions/{question_id}", status_code=204)
def delete_question(
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    q = db.get(ExamQuestion, question_id)
    if q is None or q.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="سؤال یافت نشد")
    db.delete(q)
    db.commit()


@router.get("/exams/{exam_id}/questions")
def list_questions(
    exam_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    """فهرست سؤال‌ها برای کارکنان — با پاسخ صحیح (هرگز عمومی نیست)."""
    e = db.get(Exam, exam_id)
    if e is None:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
    rows = db.scalars(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id).order_by(ExamQuestion.sort_order)
    ).all()
    return {"items": [_question_out(q, include_answer=True) for q in rows]}


@router.get("/exams/{exam_id}/attempts")
def list_attempts(
    exam_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    e = db.get(Exam, exam_id)
    if e is None:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
    rows = db.scalars(
        select(ExamAttempt).where(ExamAttempt.exam_id == exam_id).order_by(ExamAttempt.started_at.desc())
    ).all()
    return {"items": [_attempt_out(a) for a in rows]}


def _ensure_exam_access(db: Session, exam: Exam, user: User) -> None:
    """دسترسی برگزاری: آزمون دوره‌ای ← ثبت‌نام فعال؛ آزمون پولی ← سفارش
    پرداخت‌شده kind='exam'؛ آزمون رایگان مستقل ← همه."""
    if exam.status != PublishStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="آزمون منتشر نشده است")
    if exam.course_id is not None:
        enr = db.scalars(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == exam.course_id,
                CourseEnrollment.user_id == user.id,
                CourseEnrollment.status.in_((EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)),
            )
        ).first()
        if enr is None:
            raise HTTPException(
                status_code=403, detail="برای این آزمون باید در دوره ثبت‌نام فعال داشته باشید"
            )
        return
    if int(exam.price_amount) > 0:
        paid = db.scalars(
            select(Order).where(
                Order.exam_id == exam.id,
                Order.owner_user_id == user.id,
                Order.status == OrderStatus.PAID,
            )
        ).first()
        if paid is None:
            raise HTTPException(status_code=403, detail="برای این آزمون ابتدا هزینه را پرداخت کنید")


@router.post("/exams/{exam_id}/attempts", status_code=201)
def start_attempt(
    exam_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """شروع تلاش — سؤال‌ها بدون پاسخ صحیح برمی‌گردند؛ تلاش نیمه‌کاره
    ادامه می‌یابد (resumed)؛ قبولی قبلی یا سقف تلاش → ۴۰۹."""
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
    _ensure_exam_access(db, exam, actor)
    passed = db.scalars(
        select(ExamAttempt).where(
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.user_id == actor.id,
            ExamAttempt.status == AttemptStatus.PASSED,
        )
    ).first()
    if passed is not None:
        raise HTTPException(status_code=409, detail="کاربر قبلاً در این آزمون قبول شده است")
    used = db.scalar(
        select(func.count()).select_from(ExamAttempt).where(
            ExamAttempt.exam_id == exam_id, ExamAttempt.user_id == actor.id
        )
    ) or 0
    resumed = False
    attempt = db.scalars(
        select(ExamAttempt).where(
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.user_id == actor.id,
            ExamAttempt.status == AttemptStatus.IN_PROGRESS,
        )
    ).first()
    if attempt is not None:
        resumed = True
    else:
        if int(used) >= exam.max_attempts:
            raise HTTPException(
                status_code=409, detail=f"سقف تلاش‌های مجاز ({exam.max_attempts}) تکمیل شده است"
            )
        attempt = ExamAttempt(exam_id=exam_id, user_id=actor.id)
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
    questions = db.scalars(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id).order_by(ExamQuestion.sort_order)
    ).all()
    if not questions:
        raise HTTPException(status_code=422, detail="آزمون بدون سؤال قابل برگزاری نیست")
    return {
        "attempt": _attempt_out(attempt),
        "resumed": resumed,
        "exam": {"id": str(exam.id), "title": exam.title, "duration_minutes": exam.duration_minutes},
        "questions": [_question_out(q, include_answer=False) for q in questions],
    }


@router.post("/exams/attempts/{attempt_id}/submit")
def submit_attempt(
    attempt_id: uuid.UUID,
    payload: AttemptSubmit,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """ثبت و نمره‌دهی سمت سرور؛ قبولی → صدور خودکار گواهی (B36، idempotent)."""
    attempt = db.get(ExamAttempt, attempt_id)
    if attempt is None or attempt.user_id != actor.id:
        raise HTTPException(status_code=404, detail="تلاش یافت نشد")
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="این تلاش قبلاً ثبت شده است")
    questions = db.scalars(
        select(ExamQuestion)
        .where(ExamQuestion.exam_id == attempt.exam_id)
        .order_by(ExamQuestion.sort_order)
    ).all()
    answers = payload.answers
    for a in answers:
        if not isinstance(a, int) or a < 0:
            raise HTTPException(status_code=422, detail="پاسخ‌ها باید اندیس گزینه باشند")
    for idx, q in enumerate(questions):
        if idx < len(answers) and answers[idx] >= len(q.options or []):
            raise HTTPException(status_code=422, detail="اندیس پاسخ خارج از محدوده گزینه‌هاست")
    try:
        score, passed = learn.grade_attempt(db, attempt, answers)
    except learn.LearningError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    attempt.answers = answers
    attempt.score_percent = score
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.status = AttemptStatus.PASSED if passed else AttemptStatus.FAILED
    cert = learn.maybe_issue_exam_certificate(db, attempt, passed=passed, actor_id=actor.id)
    db.commit()
    db.refresh(attempt)
    out = {"attempt": _attempt_out(attempt), "passed": passed, "score_percent": score}
    if cert is not None:
        out["certificate"] = _certificate_out(cert)
    return out


@router.get("/exams/attempts/{attempt_id}")
def get_attempt(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    attempt = db.get(ExamAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="تلاش یافت نشد")
    is_staff = any(r.code in VIEW_ROLES for r in actor.roles)
    if attempt.user_id != actor.id and not is_staff:
        raise HTTPException(status_code=403, detail="دسترسی به این تلاش مجاز نیست")
    return _attempt_out(attempt)


# ================================================================ B36 گواهی
class CertificateIssue(BaseModel):
    user_id: uuid.UUID
    title: str = Field(min_length=2, max_length=300)
    course_id: uuid.UUID | None = None
    exam_id: uuid.UUID | None = None


class CertificateRevoke(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.get("/certificates")
def list_certificates(
    user_id: uuid.UUID | None = None,
    revoked: bool | None = None,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(Certificate).order_by(Certificate.created_at.desc()).limit(200)
    if user_id is not None:
        q = q.where(Certificate.user_id == user_id)
    if revoked is not None:
        q = q.where(Certificate.revoked.is_(revoked))
    return {"items": [_certificate_out(c) for c in db.scalars(q).all()]}


@router.post("/certificates/issue", status_code=201)
def issue_certificate(
    payload: CertificateIssue,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    if payload.course_id is None and payload.exam_id is None:
        raise HTTPException(status_code=422, detail="course_id یا exam_id لازم است")
    if payload.course_id is not None and db.get(Course, payload.course_id) is None:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")
    if payload.exam_id is not None and db.get(Exam, payload.exam_id) is None:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
    if db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    existing = learn.find_certificate(
        db, user_id=payload.user_id, exam_id=payload.exam_id, course_id=payload.course_id
    )
    if existing is not None:
        return {"certificate": _certificate_out(existing), "already_existed": True}
    cert = learn.issue_certificate(
        db,
        user_id=payload.user_id,
        title=payload.title.strip(),
        holder_name=_user_display_name(db, payload.user_id),
        course_id=payload.course_id,
        exam_id=payload.exam_id,
        actor_id=actor.id,
    )
    return {"certificate": _certificate_out(cert), "already_existed": False}


@router.post("/certificates/{certificate_id}/revoke")
def revoke_certificate(
    certificate_id: uuid.UUID,
    payload: CertificateRevoke,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    c = db.get(Certificate, certificate_id)
    if c is None:
        raise HTTPException(status_code=404, detail="گواهی یافت نشد")
    if c.revoked:
        raise HTTPException(status_code=409, detail="این گواهی قبلاً باطل شده است")
    c.revoked = True
    c.revoked_at = datetime.now(timezone.utc)
    c.revoke_reason = payload.reason
    db.commit()
    db.refresh(c)
    return _certificate_out(c)


@router.get("/my/certificates")
def my_certificates(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    rows = db.scalars(
        select(Certificate)
        .where(Certificate.user_id == actor.id)
        .order_by(Certificate.created_at.desc())
    ).all()
    return {"items": [_certificate_out(c) for c in rows]}


# ================================================================ عمومی
@router.get("/public/contents")
def public_contents(
    topic_id: uuid.UUID | None = None,
    topic_slug: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """«دسته غیرفعال در صفحات عمومی نشان داده نشود» — محتوای منتشرشده
    زیر دسته غیرفعال هم عمومی نیست."""
    q = (
        select(Content)
        .join(Topic, Topic.id == Content.topic_id, isouter=True)
        .where(Content.status == PublishStatus.PUBLISHED)
        .order_by(Content.published_at.desc().nullslast(), Content.created_at.desc())
    )
    if topic_id is not None:
        q = q.where(Content.topic_id == topic_id)
    if topic_slug:
        q = q.where(Topic.slug == topic_slug)
    rows = db.scalars(q).all()
    out = []
    for c in rows:
        topic = db.get(Topic, c.topic_id) if c.topic_id else None
        if topic is not None and not topic.is_active:
            continue
        out.append(_content_out(c, topic))
    return {"items": out}


@router.get("/public/contents/{slug}")
def public_content_detail(slug: str, db: Session = Depends(get_db)) -> dict:
    c = db.scalars(
        select(Content).where(Content.slug == slug, Content.status == PublishStatus.PUBLISHED)
    ).first()
    if c is None:
        raise HTTPException(status_code=404, detail="محتوا یافت نشد")
    topic = db.get(Topic, c.topic_id) if c.topic_id else None
    if topic is not None and not topic.is_active:
        raise HTTPException(status_code=404, detail="محتوا یافت نشد")
    return _content_out(c, topic)


@router.get("/public/courses")
def public_courses(
    topic_id: uuid.UUID | None = None,
    topic_slug: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    q = (
        select(Course)
        .join(Topic, Topic.id == Course.topic_id, isouter=True)
        .where(Course.status == PublishStatus.PUBLISHED)
        .order_by(Course.created_at.desc())
    )
    if topic_id is not None:
        q = q.where(Course.topic_id == topic_id)
    if topic_slug:
        q = q.where(Topic.slug == topic_slug)
    rows = db.scalars(q).all()
    out = []
    for c in rows:
        topic = db.get(Topic, c.topic_id) if c.topic_id else None
        if topic is not None and not topic.is_active:
            continue
        out.append(_course_out(db, c))
    return {"items": out}


@router.get("/public/courses/{slug}")
def public_course_detail(slug: str, db: Session = Depends(get_db)) -> dict:
    c = db.scalars(
        select(Course).where(Course.slug == slug, Course.status == PublishStatus.PUBLISHED)
    ).first()
    if c is None:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")
    topic = db.get(Topic, c.topic_id) if c.topic_id else None
    if topic is not None and not topic.is_active:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")
    return _course_out(db, c)


@router.post("/public/courses/{slug}/enroll")
def public_enroll(
    slug: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """ثبت‌نام خودکاربر — رایگان: فعال فوری؛ پولی: سفارش (پرداخت با جریان B10)."""
    c = db.scalars(
        select(Course).where(Course.slug == slug, Course.status == PublishStatus.PUBLISHED)
    ).first()
    if c is None:
        raise HTTPException(status_code=404, detail="دوره منتشر نشده است")
    return _enroll_user(db, c, actor.id, actor.id)


@router.post("/public/exams/{slug}/purchase")
def public_exam_purchase(
    slug: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """خرید دسترسی آزمون پولی — سفارش kind='exam' با snapshot قیمت."""
    e = db.scalars(
        select(Exam).where(Exam.slug == slug, Exam.status == PublishStatus.PUBLISHED)
    ).first()
    if e is None:
        raise HTTPException(status_code=404, detail="آزمون منتشر نشده است")
    if int(e.price_amount) == 0:
        raise HTTPException(status_code=422, detail="این آزمون رایگان است")
    paid = db.scalars(
        select(Order).where(
            Order.exam_id == e.id, Order.owner_user_id == actor.id, Order.status == OrderStatus.PAID
        )
    ).first()
    if paid is not None:
        raise HTTPException(status_code=409, detail="دسترسی این آزمون قبلاً خریداری شده است")
    order = _create_learning_order(
        db,
        kind="exam",
        owner_user_id=actor.id,
        amount=int(e.price_amount),
        title=f"دسترسی آزمون «{e.title}»",
        exam_id=e.id,
        actor_id=actor.id,
    )
    db.commit()
    db.refresh(order)
    return {
        "order": {
            "id": str(order.id),
            "order_number": order.order_number,
            "amount": float(order.amount),
            "payable_amount": float(order.payable_amount),
            "status": order.status,
            "kind": order.kind,
        }
    }


@router.get("/public/exams")
def public_exams(
    topic_id: uuid.UUID | None = None,
    topic_slug: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    q = (
        select(Exam)
        .join(Topic, Topic.id == Exam.topic_id, isouter=True)
        .where(Exam.status == PublishStatus.PUBLISHED)
        .order_by(Exam.created_at.desc())
    )
    if topic_id is not None:
        q = q.where(Exam.topic_id == topic_id)
    if topic_slug:
        q = q.where(Topic.slug == topic_slug)
    rows = db.scalars(q).all()
    out = []
    for e in rows:
        topic = db.get(Topic, e.topic_id) if e.topic_id else None
        if topic is not None and not topic.is_active:
            continue
        out.append(_exam_out(db, e, with_question_count=False))
    return {"items": out}


@router.get("/public/certificates/verify")
def public_certificate_verify(
    number: str = Query(min_length=4, max_length=40),
    db: Session = Depends(get_db),
) -> dict:
    """اعتبارسنجی عمومی گواهی با شماره یکتا."""
    c = db.scalars(
        select(Certificate).where(Certificate.certificate_number == number.strip().upper())
    ).first()
    if c is None:
        raise HTTPException(status_code=404, detail="گواهی با این شماره یافت نشد")
    return {
        "valid": not c.revoked,
        "certificate_number": c.certificate_number,
        "title": c.title,
        "holder_name": c.holder_name,
        "issued_at": c.issued_at.isoformat() if c.issued_at else None,
        "revoked": c.revoked,
        "revoke_reason": c.revoke_reason if c.revoked else None,
    }
