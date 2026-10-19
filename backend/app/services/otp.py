"""B02 سند جامع - کد یک‌بارمصرف (OTP) برای تأیید شماره موبایل.

نسخه lite (فاز ۲۶): کد در حالت توسعه (OTP_DEV_MODE=true) در پاسخ API و
لاگ نمایش داده می‌شود تا بدون درگاه پیامک (تصمیم D04) قابل تست باشد.
الزامات B02 که اینجا کنترل می‌شود:
- انقضای کد (OTP_CODE_TTL_SECONDS) و انقضای توکن اثبات تأیید
- سقف تلاش (OTP_MAX_ATTEMPTS) و سقف درخواست در بازه زمانی
- کد مصرف‌شده دوباره پذیرفته نمی‌شود

فاز ۳۶ (B28 + D04 تکمیلی): در فعال بودن سرویس پیامک با آداپتور کلیددار
(kavenegar/smsir)، کد به‌صورت مستقیم ارسال می‌شود؛ «کد خام هرگز در
پایگاه‌داده ذخیره نمی‌شود» و شکست ارسال جریان صدور کد را متوقف نمی‌کند
(ارسال در مسیر درخواست = بدهی مستند در ADR-02 صف کار).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.otp import OtpChallenge, OtpPurpose
from app.services.audit import record_audit

settings = get_settings()

_PEPPER = settings.auth_secret_key


def normalize_mobile(raw: str) -> str:
    """یکسان‌سازی شماره موبایل ایرانی به قالب 09XXXXXXXXX"""
    s = (raw or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = s.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    return s


def is_valid_mobile(m: str) -> bool:
    return len(m) == 11 and m.startswith("09") and m.isdigit()


def _hash_code(mobile: str, code: str) -> str:
    return hashlib.sha256(f"{_PEPPER}:{mobile}:{code}".encode()).hexdigest()


def _gen_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def request_otp(db: Session, mobile: str, purpose: str, ip: str | None = None) -> dict:
    """صدور کد جدید؛ چالش‌های قبلی مصرف‌نشده باطل می‌شوند.

    خروجی: {challenge, dev_code} — dev_code فقط در حالت توسعه.
    """
    now = datetime.now(timezone.utc)
    # سقف درخواست: حداکثر OTP_REQUEST_MAX چالش در OTP_REQUEST_WINDOW_SECONDS
    window_start = now - timedelta(seconds=settings.otp_request_window_seconds)
    count_recent = int(db.scalar(
        select(func.count()).select_from(OtpChallenge).where(
            OtpChallenge.mobile == mobile,
            OtpChallenge.purpose == purpose,
            OtpChallenge.created_at >= window_start,
        )
    ) or 0)
    if count_recent >= settings.otp_request_max:
        return {"challenge": None, "dev_code": None, "rate_limited": True}

    # باطل کردن چالش‌های معلق قبلی همان موبایل/هدف
    db.execute(
        update(OtpChallenge)
        .where(OtpChallenge.mobile == mobile, OtpChallenge.purpose == purpose,
               OtpChallenge.consumed_at.is_(None), OtpChallenge.expires_at > now)
        .values(consumed_at=now)
    )

    code = _gen_code()
    ch = OtpChallenge(
        mobile=mobile,
        purpose=purpose,
        code_hash=_hash_code(mobile, code),
        expires_at=now + timedelta(seconds=settings.otp_code_ttl_seconds),
        ip=ip,
    )
    db.add(ch)
    db.commit()

    dev_code = None
    if settings.otp_dev_mode:
        dev_code = code
        # الزام «نمایش در لاگ» از roadmap فاز ۲۶ - کد هرگز در audit ذخیره نمی‌شود
        print(f"[OTP-DEV] mobile={mobile} purpose={purpose} code={code}")
    _try_send_otp_sms(settings, mobile, code, purpose)
    record_audit(db, action="auth.otp_requested", detail={"purpose": purpose, "ip": ip})
    return {"challenge": ch, "dev_code": dev_code, "rate_limited": False}


def _try_send_otp_sms(settings, mobile: str, code: str, purpose: str) -> None:
    """B28 فاز ۳۶: ارسال مستقیم OTP با آداپتور کلیددار — بدون ذخیره کد در DB.

    فقط وقتی سرویس پیامک فعال است و آداپتور واقعی (کلیددار) فعال است؛ در
    حالت log توسعه/آزمون کد در پاسخ API (otp_dev_mode) نمایش داده می‌شود.
    شکست هرگز جریان اصلی را متوقف نمی‌کند.
    """
    try:
        from app.services.integrations import active_sms_provider, _send

        if not getattr(settings, "sms_enabled", False):
            return
        provider, fallback = active_sms_provider(settings)
        if fallback or provider == "log":
            return  # بدون آداپتور واقعی، ارسال پیامکی انجام نمی‌شود
        body = f"کد تأیید شما در سامانه Rosepsy: {code}\nاعتبار: {settings.otp_code_ttl_seconds // 60} دقیقه"
        _send(settings, provider, mobile, body)
    except Exception:
        pass


def verify_otp(db: Session, mobile: str, purpose: str, code: str, ip: str | None = None) -> dict:
    """بررسی کد؛ در موفقیت توکن اثبات یک‌بارمصرف برمی‌گرداند."""
    now = datetime.now(timezone.utc)
    ch = db.scalar(
        select(OtpChallenge).where(
            OtpChallenge.mobile == mobile,
            OtpChallenge.purpose == purpose,
            OtpChallenge.consumed_at.is_(None),
        ).order_by(OtpChallenge.created_at.desc())
    )
    invalid = {"ok": False, "reason": "invalid"}
    if ch is None or ch.expires_at <= now:
        return invalid
    if ch.attempts >= settings.otp_max_attempts:
        ch.consumed_at = now  # قفل چالش
        db.commit()
        return {"ok": False, "reason": "locked"}
    if not secrets.compare_digest(ch.code_hash, _hash_code(mobile, (code or "").strip())):
        ch.attempts += 1
        db.commit()
        record_audit(db, action="auth.otp_failed", detail={"purpose": purpose, "ip": ip})
        return {"ok": False, "reason": "invalid"}
    # موفقیت - مصرف یک‌باره کد + صدور توکن اثبات
    verify_token = secrets.token_urlsafe(24)
    ch.consumed_at = now
    ch.verify_token_hash = hashlib.sha256(verify_token.encode()).hexdigest()
    ch.verify_expires_at = now + timedelta(seconds=settings.otp_verify_token_seconds)
    db.commit()
    record_audit(db, action="auth.otp_verified", detail={"purpose": purpose, "ip": ip})
    return {"ok": True, "challenge": ch, "verify_token": verify_token}


def consume_verify_token(db: Session, token: str, mobile: str) -> bool:
    """اعتبارسنجی توکن اثبات تأیید موبایل - مصرف یک‌باره با حذف hash."""
    if not token:
        return False
    h = hashlib.sha256(token.strip().encode()).hexdigest()
    now = datetime.now(timezone.utc)
    ch = db.scalar(
        select(OtpChallenge).where(
            OtpChallenge.verify_token_hash == h,
            OtpChallenge.mobile == mobile,
        )
    )
    if ch is None:
        return False
    if ch.verify_expires_at is None or ch.verify_expires_at <= now:
        return False
    ch.verify_token_hash = None  # یک‌بارمصرف
    db.commit()
    return True


def count_active_holds_for_mobile(db: Session, mobile: str, now: datetime) -> int:
    from app.models.booking import SlotClaim, SlotClaimStatus
    return int(db.scalar(
        select(func.count()).select_from(SlotClaim).where(
            SlotClaim.mobile == mobile,
            SlotClaim.status == SlotClaimStatus.ACTIVE,
            SlotClaim.expires_at > now,
        )
    ) or 0)


def purpose_values() -> tuple[str, str]:
    return OtpPurpose.BOOKING, OtpPurpose.LOGIN
