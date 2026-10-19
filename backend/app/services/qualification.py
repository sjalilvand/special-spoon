"""فاز ۲۸ - B05 سند جامع: صلاحیت معتبر مشاور برای فهرست قابل رزرو.

قاعده پذیرش سند: «مشاور بدون صلاحیت معتبر در فهرست قابل رزرو قرار نگیرد».

مشاور «قابل رزرو» است وقتی:
1. وضعیت او فعال باشد، و
2. حداقل یکی از موارد برقرار باشد:
   - یک مدرک/مجوز «تأییدشده» داشته باشد که تاریخ انقضای آن نگذشته باشد، یا
   - مجوز پایه او (license_verified) تأیید شده و منقضی نشده باشد
     (سازگاری با داده‌های پیشین سامانه).
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import CounselorCredential, CredentialVerificationStatus
from app.models.people import Counselor


def has_valid_credential(db: Session, counselor_id, today: date | None = None) -> bool:
    """آیا حداقل یک مدرک تأییدشده و معتبر (منقضی‌نشده) برای مشاور وجود دارد؟"""
    today = today or date.today()
    q = select(CounselorCredential.expires_at).where(
        CounselorCredential.counselor_id == counselor_id,
        CounselorCredential.verification_status == CredentialVerificationStatus.APPROVED,
    )
    for expires_at in db.scalars(q):
        if expires_at is None or expires_at >= today:
            return True
    return False


def is_counselor_bookable(db: Session, counselor: Counselor, today: date | None = None) -> bool:
    """B05 - مرز ورود به چرخه رزرو عمومی (فهرست عمومی/اسلات/نگهداشت)."""
    today = today or date.today()
    if counselor is None or counselor.status != "active":
        return False
    if has_valid_credential(db, counselor.id, today):
        return True
    if counselor.license_verified and (
        counselor.license_expiry_date is None or counselor.license_expiry_date >= today
    ):
        return True
    return False


def bookable_counselors(db: Session, today: date | None = None) -> list[Counselor]:
    """فهرست مشاوران با صلاحیت معتبر برای نمایش عمومی."""
    today = today or date.today()
    items = db.scalars(select(Counselor).where(Counselor.status == "active")).all()
    return [c for c in items if is_counselor_bookable(db, c, today)]
