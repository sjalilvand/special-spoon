"""فاز ۸۶ — آکادمی رز: ویترین عمومی دوره‌ها + سبد خرید + درگاه بانکی + پخش ویدیو.

قواعد کلیدی (سند فاز ۸۶):
- «ویدیوی جلسه هرگز در خروجی عمومی نمی‌رود» — فقط از endpoint
  ``GET /academy/videos/{session_id}`` و فقط برای واجد شرط:
  جلسهٔ رایگان (is_free) یا ثبت‌نام فعال/تکمیل‌شده با احتساب
  انتشار پلکانی (release_after_days روز پس از فعال‌سازی ثبت‌نام).
- «قیمت لحظه خرید snapshot می‌شود» (B07) — ردیف‌های
  ``academy_order_items`` قیمت هر دوره را در لحظه checkout قفل می‌کنند.
- «سبد = یک سفارش، یک پرداخت» — چند دورهٔ پولی در یک سفارش kind='course'
  جمع می‌شوند و پس از verify موفق، همهٔ ثبت‌نام‌های pending همان سفارش
  فعال می‌شوند (اثر جانبی B10؛ بدون فاکتور مضاعف).
- دورهٔ رایگان (price=0) در همان checkout بلافاصله فعال می‌شود.
- ورود کاربر سایت با OTP پیامکی (purpose='academy')؛ حساب خودکار
  username=موبایل (همان الگوی رزرو عمومی فاز ۶۹)؛ توکن دسترسی ۳۰ روز.
- درگاه: همان معماری پلاگین‌پذیر D02 (شبیه‌ساز پیش‌فرض، زرین‌پال در تولید).
"""

import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token
from app.models.learning import (
    AcademyOrderItem,
    AcademyWatchProgress,
    Course,
    CourseEnrollment,
    CourseSession,
    EnrollmentStatus,
    PublishStatus,
)
from app.models.payment import Order, OrderStatus, Payment
from app.models.topics import Topic
from app.models.user import User, UserStatus
from app.services import otp as otp_service
from app.services import payments as pay

router = APIRouter(prefix="/academy", tags=["academy"])

ACADEMY_OTP_PURPOSE = "academy"
SITE_TOKEN_MINUTES = 60 * 24 * 30  # نشست سایت: ۳۰ روز

# محدودسازی نرخ درخواست کد OTP از هر IP (همان الگوی رزرو عمومی)
_academy_otp_ip: dict[str, list[float]] = {}
_OTP_RATE = 10
_OTP_WINDOW = 3600.0


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _otp_rate_ok(ip: str) -> bool:
    now = time.monotonic()
    lst = [t for t in _academy_otp_ip.get(ip, []) if now - t < _OTP_WINDOW]
    if len(lst) >= _OTP_RATE:
        _academy_otp_ip[ip] = lst
        return False
    lst.append(now)
    _academy_otp_ip[ip] = lst
    return True


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- serializers
def _episode_meta(s: CourseSession, *, for_public: bool = True) -> dict:
    """متادیتای جلسه برای خروجی عمومی — video_url هرگز برنمی‌گردد."""
    out = {
        "id": str(s.id),
        "title": s.title,
        "description": s.description,
        "duration_minutes": s.duration_minutes,
        "sort_order": s.sort_order,
        "is_free": bool(s.is_free),
        "release_after_days": int(s.release_after_days or 0),
        "has_video": bool(s.video_url),
        "session_date": s.session_date.isoformat() if s.session_date else None,
    }
    if not for_public:
        out["video_url"] = s.video_url  # فقط خروجی پنل/مالک مجاز
    return out


def _course_public_out(db: Session, c: Course, *, detail: bool = False) -> dict:
    topic = db.get(Topic, c.topic_id) if c.topic_id else None
    sessions = db.scalars(
        select(CourseSession)
        .where(CourseSession.course_id == c.id)
        .order_by(CourseSession.sort_order, CourseSession.created_at)
    ).all()
    free_count = sum(1 for s in sessions if s.is_free)
    total_minutes = sum(s.duration_minutes or 0 for s in sessions)
    out = {
        "id": str(c.id),
        "slug": c.slug,
        "title": c.title,
        "summary": c.summary,
        "topic_name": topic.name if topic else None,
        "price_amount": int(c.price_amount),
        "currency": c.currency,
        "is_free": int(c.price_amount) == 0,
        "cover_image_url": c.cover_image_url,
        "episodes_count": len(sessions),
        "free_episodes_count": free_count,
        "total_minutes": total_minutes,
    }
    if detail:
        out["description"] = c.description
        out["trailer_url"] = c.trailer_url
        out["episodes"] = [_episode_meta(s) for s in sessions]
        out["starts_at"] = c.starts_at.isoformat() if c.starts_at else None
    return out


def _active_topic_ids(db: Session) -> set:
    return set(db.scalars(select(Topic.id).where(Topic.is_active.is_(True))).all())


def _public_courses_query(db: Session):
    """دوره‌های منتشرشدهٔ عمومی؛ دورهٔ زیر دستهٔ غیرفعال عمومی نیست (B33)."""
    return (
        select(Course)
        .outerjoin(Topic, Topic.id == Course.topic_id)
        .where(
            Course.status == PublishStatus.PUBLISHED,
            (Course.topic_id.is_(None)) | (Topic.is_active.is_(True)),
        )
    )


# ---------------------------------------------------------------- ویترین عمومی
@router.get("/courses")
def academy_courses(
    topic: str | None = Query(default=None, max_length=120),
    db: Session = Depends(get_db),
) -> dict:
    q = _public_courses_query(db).order_by(Course.created_at.desc()).limit(100)
    items = db.scalars(q).all()
    if topic:
        items = [c for c in items if (c.topic_id and (t := db.get(Topic, c.topic_id)) and t.slug == topic)]
    return {"items": [_course_public_out(db, c) for c in items]}


@router.get("/courses/{slug}")
def academy_course_detail(slug: str, db: Session = Depends(get_db)) -> dict:
    c = db.scalars(_public_courses_query(db).where(Course.slug == slug)).first()
    if c is None:
        raise HTTPException(status_code=404, detail="دوره یافت نشد یا منتشر نشده است")
    return _course_public_out(db, c, detail=True)


# ---------------------------------------------------------------- ورود با OTP
class AcademyOtpRequest(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)


class AcademyOtpVerify(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    full_name: str | None = Field(default=None, max_length=200)


@router.post("/auth/request-code")
def academy_request_code(payload: AcademyOtpRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = _client_ip(request)
    if not _otp_rate_ok(ip):
        raise HTTPException(status_code=429, detail="تعداد درخواست کد زیاد است؛ کمی بعد تلاش کنید")
    mobile = otp_service.normalize_mobile(payload.mobile)
    if not otp_service.is_valid_mobile(mobile):
        raise HTTPException(status_code=422, detail="شماره موبایل معتبر نیست (نمونه: 09121234567)")
    res = otp_service.request_otp(db, mobile, ACADEMY_OTP_PURPOSE, ip=ip)
    if res.get("rate_limited"):
        raise HTTPException(status_code=429, detail="تعداد درخواست کد زیاد است؛ کمی بعد دوباره تلاش کنید")
    out: dict = {"status": "sent", "expires_in": otp_service.settings.otp_code_ttl_seconds}
    if res.get("dev_code") is not None:
        out["dev_code"] = res["dev_code"]
        out["dev_notice"] = res.get("dev_notice") or "حالت توسعه: کد به‌جای پیامک در پاسخ نمایش داده می‌شود"
    return out


def _get_or_create_academy_user(db: Session, mobile: str, full_name: str | None) -> User:
    u = db.scalars(select(User).where(User.username == mobile)).first()
    if u is not None:
        if full_name and not (u.display_name or "").strip():
            u.display_name = full_name.strip()[:200]
            db.commit()
            db.refresh(u)
        return u
    u = User(
        username=mobile,
        display_name=(full_name or mobile).strip()[:200] or mobile,
        mobile=mobile,
        password_hash=None,
        status=UserStatus.ACTIVE,
    )
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        u = db.scalars(select(User).where(User.username == mobile)).first()
        if u is None:
            raise HTTPException(status_code=500, detail="ساخت حساب کاربری ناموفق بود")
        db.refresh(u)
    return u


@router.post("/auth/verify")
def academy_verify_code(payload: AcademyOtpVerify, request: Request, db: Session = Depends(get_db)) -> dict:
    mobile = otp_service.normalize_mobile(payload.mobile)
    if not otp_service.is_valid_mobile(mobile):
        raise HTTPException(status_code=422, detail="شماره موبایل معتبر نیست")
    res = otp_service.verify_otp(db, mobile, ACADEMY_OTP_PURPOSE, payload.code, ip=_client_ip(request))
    if res.get("reason") == "locked":
        raise HTTPException(status_code=429, detail="تلاش‌های ناموفق زیاد است؛ کد جدید درخواست کنید")
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail="کد وارد شده نادرست یا منقضی است")
    user = _get_or_create_academy_user(db, mobile, payload.full_name)
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="حساب غیرفعال است")
    token = create_access_token(
        user_id=str(user.id), auth_version=user.auth_version, expires_minutes=SITE_TOKEN_MINUTES
    )
    return {
        "access_token": token,
        "user": {"id": str(user.id), "display_name": user.display_name, "mobile": user.mobile},
    }


# ---------------------------------------------------------------- دوره‌های من
def _my_enrollment(db: Session, course_id, user_id) -> CourseEnrollment | None:
    return db.scalars(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course_id, CourseEnrollment.user_id == user_id
        )
    ).first()


def _my_courses_out(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(CourseEnrollment, Course)
        .join(Course, Course.id == CourseEnrollment.course_id)
        .where(CourseEnrollment.user_id == user.id)
        .order_by(CourseEnrollment.created_at.desc())
    ).all()
    items = []
    for enr, c in rows:
        order = db.get(Order, enr.order_id) if enr.order_id else None
        sessions = db.scalars(
            select(CourseSession).where(CourseSession.course_id == c.id)
        ).all()
        watched = db.scalar(
            select(func.count()).select_from(AcademyWatchProgress).where(
                AcademyWatchProgress.user_id == user.id,
                AcademyWatchProgress.course_id == c.id,
                AcademyWatchProgress.watched.is_(True),
            )
        ) or 0
        items.append(
            {
                "enrollment_id": str(enr.id),
                "status": enr.status,
                "activated_at": enr.activated_at.isoformat() if enr.activated_at else None,
                "course": {
                    "id": str(c.id),
                    "slug": c.slug,
                    "title": c.title,
                    "summary": c.summary,
                    "cover_image_url": c.cover_image_url,
                    "price_amount": int(c.price_amount),
                    "is_free": int(c.price_amount) == 0,
                    "episodes_count": len(sessions),
                },
                "watched_count": int(watched),
                "order": (
                    {
                        "id": str(order.id),
                        "order_number": order.order_number,
                        "status": order.status,
                        "payable_amount": int(order.payable_amount),
                    }
                    if order
                    else None
                ),
            }
        )
    return items


@router.get("/me")
def academy_me(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return {
        "user": {"id": str(user.id), "display_name": user.display_name, "mobile": user.mobile},
        "courses": _my_courses_out(db, user),
    }


@router.get("/me/courses/{course_id}")
def academy_my_course(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    c = db.get(Course, course_id)
    if c is None or c.status != PublishStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="دوره یافت نشد")
    enr = _my_enrollment(db, c.id, user.id)
    if enr is None:
        raise HTTPException(status_code=403, detail="در این دوره ثبت‌نام نکرده‌اید")
    sessions = db.scalars(
        select(CourseSession)
        .where(CourseSession.course_id == c.id)
        .order_by(CourseSession.sort_order, CourseSession.created_at)
    ).all()
    watched_ids = set(
        db.scalars(
            select(AcademyWatchProgress.session_id).where(
                AcademyWatchProgress.user_id == user.id,
                AcademyWatchProgress.course_id == c.id,
                AcademyWatchProgress.watched.is_(True),
            )
        ).all()
    )
    base = _course_public_out(db, c, detail=False)
    base["description"] = c.description
    base["trailer_url"] = c.trailer_url
    base["enrollment_status"] = enr.status
    base["activated_at"] = enr.activated_at.isoformat() if enr.activated_at else None
    episodes = []
    for s in sessions:
        meta = _episode_meta(s, for_public=False)
        meta["video_url"] = None  # آدرس واقعی فقط از /videos/{id}
        meta["watched"] = s.id in watched_ids
        meta["access"] = _episode_access(enr, s)
        episodes.append(meta)
    base["episodes"] = episodes
    return base


# ---------------------------------------------------------------- سبد خرید
class CheckoutCreate(BaseModel):
    course_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


def _capacity_taken(db: Session, course_id) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(CourseEnrollment).where(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.status.in_(
                    (EnrollmentStatus.PENDING, EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)
                ),
            )
        )
        or 0
    )


@router.post("/checkout")
def academy_checkout(
    payload: CheckoutCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # حذف تکراری با حفظ ترتیب
    seen: set = set()
    ids = [i for i in payload.course_ids if not (i in seen or seen.add(i))]

    paid_courses: list[Course] = []
    free_enrolled: list[dict] = []
    for cid in ids:
        c = db.get(Course, cid)
        if c is None or c.status != PublishStatus.PUBLISHED:
            raise HTTPException(status_code=404, detail="یکی از دوره‌ها یافت نشد یا منتشر نشده است")
        enr = _my_enrollment(db, c.id, user.id)
        if enr is not None and enr.status in (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED):
            raise HTTPException(status_code=409, detail=f"قبلاً در «{c.title}» ثبت‌نام کرده‌اید")
        if enr is not None and enr.status == EnrollmentStatus.PENDING:
            raise HTTPException(
                status_code=409,
                detail=f"ثبت‌نام «{c.title}» در انتظار پرداخت است؛ از «دوره‌های من» پرداخت را کامل کنید",
            )
        if c.capacity is not None and _capacity_taken(db, c.id) >= c.capacity:
            raise HTTPException(status_code=409, detail=f"ظرفیت دوره «{c.title}» تکمیل است")
        if int(c.price_amount) == 0:
            db.add(
                CourseEnrollment(
                    course_id=c.id, user_id=user.id, status=EnrollmentStatus.ACTIVE,
                    activated_at=_now(),
                )
            )
            free_enrolled.append({"course_id": str(c.id), "title": c.title, "status": EnrollmentStatus.ACTIVE})
        else:
            paid_courses.append(c)

    order_dict = None
    if paid_courses:
        total = sum(int(c.price_amount) for c in paid_courses)
        title = (
            f"ثبت‌نام دوره «{paid_courses[0].title}»"
            if len(paid_courses) == 1
            else f"خرید آکادمی رز ({len(paid_courses)} دوره)"
        )
        order = Order(
            order_number=pay.generate_order_number(db),
            owner_user_id=user.id,
            title=title[:300],
            amount=total,
            currency="IRR",
            payable_amount=total,
            status=OrderStatus.PENDING,
            kind="course",
        )
        db.add(order)
        db.flush()
        for c in paid_courses:
            db.add(
                AcademyOrderItem(
                    order_id=order.id, course_id=c.id,
                    title=c.title[:300], price_amount=int(c.price_amount), currency="IRR",
                )
            )
            db.add(
                CourseEnrollment(
                    course_id=c.id, user_id=user.id,
                    status=EnrollmentStatus.PENDING, order_id=order.id,
                )
            )
        order_dict = {
            "id": str(order.id),
            "order_number": order.order_number,
            "amount": total,
            "payable_amount": total,
            "status": OrderStatus.PENDING,
            "courses": [{"id": str(c.id), "title": c.title, "price": int(c.price_amount)} for c in paid_courses],
        }
    db.commit()
    return {"order": order_dict, "enrolled_free": free_enrolled}


@router.post("/orders/{order_id}/pay")
def academy_pay_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    order = db.get(Order, order_id)
    if order is None or order.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    if order.kind != "course":
        raise HTTPException(status_code=422, detail="این سفارش از نوع خرید دوره نیست")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail="سفارش در وضعیت قابل پرداخت نیست" if order.status != OrderStatus.PAID
            else "این سفارش قبلاً پرداخت شده است",
        )
    try:
        init = pay.initiate_payment(db, order, gateway=pay.public_default_gateway())
    except pay.GatewayError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "redirect_url": init.redirect_url,
        "authority": init.payment.authority,
        "gateway": init.payment.gateway,
        "order_number": order.order_number,
        "amount": int(order.payable_amount),
        "currency": order.currency,
    }


@router.get("/orders/{order_id}")
def academy_order_status(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    order = db.get(Order, order_id)
    if order is None or order.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    items = db.scalars(
        select(AcademyOrderItem).where(AcademyOrderItem.order_id == order.id)
    ).all()
    payment = db.scalars(
        select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at.desc())
    ).first()
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "status": order.status,
        "kind": order.kind,
        "amount": int(order.amount),
        "payable_amount": int(order.payable_amount),
        "currency": order.currency,
        "items": [
            {"course_id": str(i.course_id), "title": i.title, "price_amount": int(i.price_amount)}
            for i in items
        ],
        "payment": (
            {
                "gateway": payment.gateway,
                "status": payment.status,
                "fail_reason": payment.fail_reason,
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            }
            if payment
            else None
        ),
    }


# ---------------------------------------------------------------- ویدیو و دسترسی
def _episode_access(enr: CourseEnrollment | None, s: CourseSession) -> str:
    """وضعیت دسترسی جلسه برای نمایش UI: free | locked | coming_soon | ready."""
    if s.is_free:
        return "free"
    if enr is None or enr.status not in (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED):
        return "locked"
    days = int(s.release_after_days or 0)
    if days <= 0 or enr.activated_at is None:
        return "ready"
    unlock_at = enr.activated_at + timedelta(days=days)
    return "ready" if _now() >= unlock_at else "coming_soon"


@router.get("/videos/{session_id}")
def academy_video_access(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    s = db.get(CourseSession, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد")
    course = db.get(Course, s.course_id)
    if course is None or course.status != PublishStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="دوره منتشر نشده است")
    if not s.video_url:
        raise HTTPException(status_code=404, detail="ویدیویی برای این جلسه ثبت نشده است")
    enr = _my_enrollment(db, s.course_id, user.id)
    access = _episode_access(enr, s)
    if access == "locked":
        raise HTTPException(status_code=403, detail="این جلسه پس از خرید دوره باز می‌شود")
    if access == "coming_soon":
        raise HTTPException(status_code=403, detail="این جلسه هنوز آزاد نشده است (انتشار پلکانی)")
    url = s.video_url
    kind = "mp4" if url.lower().split("?")[0].endswith((".mp4", ".webm", ".m3u8")) else "embed"
    return {"kind": kind, "url": url, "session_id": str(s.id), "title": s.title}


class WatchUpdate(BaseModel):
    watched: bool = True


@router.post("/videos/{session_id}/watched")
def academy_mark_watched(
    session_id: uuid.UUID,
    payload: WatchUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    s = db.get(CourseSession, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد")
    enr = _my_enrollment(db, s.course_id, user.id)
    if enr is None or enr.status not in (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED):
        raise HTTPException(status_code=403, detail="در این دوره ثبت‌نام فعال ندارید")
    row = db.scalars(
        select(AcademyWatchProgress).where(
            AcademyWatchProgress.user_id == user.id, AcademyWatchProgress.session_id == s.id
        )
    ).first()
    if row is None:
        row = AcademyWatchProgress(user_id=user.id, course_id=s.course_id, session_id=s.id)
        db.add(row)
    row.watched = bool(payload.watched)
    row.updated_at = _now()
    db.commit()
    return {"session_id": str(s.id), "watched": row.watched}
