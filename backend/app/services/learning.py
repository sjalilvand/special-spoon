"""فاز ۳۴ - B35/B36 سند جامع: نمره‌دهی آزمون و صدور گواهی.

قواعد:
- نمره‌دهی فقط سمت سرور انجام می‌شود؛ پاسخ صحیح سؤال‌ها هرگز از این
  ماژول به کلاینت نمی‌رود (خروجی سؤال عمومی correct_index ندارد)؛
- نمره = جمع امتیاز پاسخ‌های درست ÷ جمع امتیاز کل × ۱۰۰؛ قبولی اگر
  نمره ≥ pass_percent آزمون؛
- صدور گواهی idempotent است: برای هر (کاربر، آزمون) یا (کاربر، دوره)
  حداکثر یک گواهی معتبر وجود دارد؛ تلاش مجدد سند مضاعف نمی‌زند؛
- شماره گواهی یکتای جلالی: CERT-<سال شمسی>-<ترتیب ۶ رقمی>.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.learning import (
    AttemptStatus,
    Certificate,
    Exam,
    ExamAttempt,
    ExamQuestion,
)


class LearningError(Exception):
    """خطای قابل نمایش کاربر/مدیر در ماژول یادگیری."""


def next_certificate_number(db: Session) -> str:
    from app.core.dates import gregorian_to_jalali

    now = datetime.now(timezone.utc)
    jy, _, _ = gregorian_to_jalali(now.year, now.month, now.day)
    for _ in range(30):
        rows = db.execute(
            text("SELECT COUNT(*) FROM certificates WHERE certificate_number LIKE :pfx"),
            {"pfx": f"CERT-{jy:04d}-%"},
        ).scalar() or 0
        candidate = f"CERT-{jy:04d}-{rows + 1:06d}"
        if db.scalars(
            select(Certificate.id).where(Certificate.certificate_number == candidate)
        ).first() is None:
            return candidate
    raise LearningError("تولید شماره گواهی ناموفق بود")


def grade_attempt(db: Session, attempt: ExamAttempt, answers: list[int]) -> tuple[float, bool]:
    """نمره‌دهی سمت سرور؛ خروجی (نمره٪، قبولی)."""
    exam = db.get(Exam, attempt.exam_id)
    if exam is None:
        raise LearningError("آزمون یافت نشد")
    questions = db.scalars(
        select(ExamQuestion).where(ExamQuestion.exam_id == attempt.exam_id).order_by(ExamQuestion.sort_order)
    ).all()
    if not questions:
        raise LearningError("آزمون بدون سؤال قابل برگزاری نیست")
    total_points = sum(q.points for q in questions)
    earned = 0
    for idx, q in enumerate(questions):
        if idx < len(answers) and answers[idx] == q.correct_index:
            earned += q.points
    score = round(earned * 100.0 / total_points, 2) if total_points > 0 else 0.0
    return score, score >= exam.pass_percent


def find_certificate(db: Session, *, user_id: uuid.UUID, exam_id=None, course_id=None):
    """گواهی موجود کاربر برای آزمون/دوره — یا برای اطمینان از idempotency."""
    q = select(Certificate).where(Certificate.user_id == user_id)
    if exam_id is not None:
        q = q.where(Certificate.exam_id == exam_id)
    if course_id is not None:
        q = q.where(Certificate.course_id == course_id)
    return db.scalars(q.order_by(Certificate.created_at)).first()


def issue_certificate(
    db: Session,
    *,
    user_id: uuid.UUID,
    title: str,
    holder_name: str | None = None,
    course_id: uuid.UUID | None = None,
    exam_id: uuid.UUID | None = None,
    attempt_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    commit: bool = True,
) -> Certificate:
    """صدور گواهی (idempotent) — گواهی تکراری همان سند قبلی را برمی‌گرداند."""
    existing = find_certificate(db, user_id=user_id, exam_id=exam_id, course_id=course_id)
    if existing is not None:
        return existing
    cert = Certificate(
        certificate_number=next_certificate_number(db),
        user_id=user_id,
        course_id=course_id,
        exam_id=exam_id,
        attempt_id=attempt_id,
        title=title[:300],
        holder_name=(holder_name or "")[:200] or None,
        issued_by=actor_id,
    )
    db.add(cert)
    db.flush()
    if commit:
        db.commit()
        db.refresh(cert)
    return cert


def maybe_issue_exam_certificate(
    db: Session, attempt: ExamAttempt, *, passed: bool, actor_id: uuid.UUID | None = None
) -> Certificate | None:
    """پس از قبولی در آزمون، گواهی خودکار صادر می‌شود (B36)؛ داخل همان تراکنش."""
    if not passed or attempt.status != AttemptStatus.PASSED:
        return None
    exam = db.get(Exam, attempt.exam_id)
    if exam is None:
        return None
    return issue_certificate(
        db,
        user_id=attempt.user_id,
        title=f"گواهی قبولی آزمون «{exam.title}»",
        course_id=exam.course_id,
        exam_id=exam.id,
        attempt_id=attempt.id,
        actor_id=actor_id,
        commit=False,
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
