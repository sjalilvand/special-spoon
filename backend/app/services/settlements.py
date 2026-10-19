"""فاز ۳۱ - B22 سند جامع: تسویه دوره‌ای دریافت‌های درگاه.

قواعد:
- تسویه فقط برای پرداخت‌های موفق درگاه واقعی/آزمون است؛ پرداخت از
  کیف پول (gateway='wallet') تسویه بیرونی ندارد (وجه داخلی جابه‌جا می‌شود).
- هر پرداخت حداکثر یک‌بار در یک تسویه می‌آید (uq روی payment_id) —
  «تسویه مضاعف ممنوع».
- پیش‌نویس → تسویه‌شده: با تسویه، سند متوازن (بانک + کارمزد | درگاه)
  در همان تراکنش ثبت می‌شود؛ وضعیت تکراری → خطا.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounting import Settlement, SettlementItem, SettlementStatus
from app.models.payment import Payment, PaymentStatus


class SettlementError(Exception):
    """خطای قابل نمایش کاربر."""


def next_settlement_number(db: Session) -> str:
    """شماره یکتای تسویه: SET-<سال شمسی>-<ترتیب ۶ رقمی>؛ مقاوم به تلاش هم‌زمان."""
    from sqlalchemy import text

    from app.core.dates import gregorian_to_jalali

    now = datetime.now(timezone.utc)
    jy, _, _ = gregorian_to_jalali(now.year, now.month, now.day)
    for _ in range(30):
        rows = db.execute(
            text("SELECT COUNT(*) FROM settlements WHERE settlement_no LIKE :pfx"),
            {"pfx": f"SET-{jy:04d}-%"},
        ).scalar() or 0
        candidate = f"SET-{jy:04d}-{rows + 1:06d}"
        if db.scalars(
            select(Settlement.id).where(Settlement.settlement_no == candidate)
        ).first() is None:
            return candidate
    raise SettlementError("تولید شماره تسویه ناموفق بود")


def create_draft(
    db: Session,
    *,
    gateway: str,
    period_start: date | None,
    period_end: date | None,
    actor=None,
    note: str | None = None,
) -> Settlement:
    """ساخت پیش‌نویس تسویه: پرداخت‌های موفق دوره که قبلاً تسویه نشده‌اند."""
    if gateway == "wallet":
        raise SettlementError("پرداخت از کیف پول تسویه بیرونی ندارد")
    if gateway not in ("sandbox", "zarinpal"):
        raise SettlementError("درگاه نامعتبر است")
    if period_start and period_end and period_end < period_start:
        raise SettlementError("بازه دوره نامعتبر است")

    settled_ids = select(SettlementItem.payment_id)
    q = (
        select(Payment)
        .where(Payment.status == PaymentStatus.SUCCESS, Payment.gateway == gateway)
        .where(Payment.id.not_in(settled_ids))
        .order_by(Payment.paid_at)
    )
    if period_start:
        end_of_day = datetime.combine(period_end or period_start, datetime.max.time()).replace(tzinfo=timezone.utc)
        q = q.where(Payment.paid_at >= datetime.combine(period_start, datetime.min.time()).replace(tzinfo=timezone.utc),
                    Payment.paid_at <= end_of_day)

    payments = db.scalars(q).all()
    if not payments:
        raise SettlementError("پرداخت تسویه‌نشده‌ای در این دوره/درگاه یافت نشد")

    gross = sum(int(Decimal(p.amount)) for p in payments)
    st = Settlement(
        settlement_no=next_settlement_number(db),
        gateway=gateway,
        period_start=period_start,
        period_end=period_end,
        payments_count=len(payments),
        gross_amount=gross,
        currency=payments[0].currency or "IRR",
        status=SettlementStatus.DRAFT,
        note=(note or "")[:300] or None,
        created_by=actor.id if actor else None,
    )
    db.add(st)
    db.flush()
    for p in payments:
        db.add(SettlementItem(settlement_id=st.id, payment_id=p.id, amount=Decimal(p.amount)))
    db.commit()
    db.refresh(st)
    return st


def settle(db: Session, st: Settlement, *, fee_amount: int, actor=None) -> Settlement:
    """اجرای تسویه: کارمزد → خالص بانکی + سند متوازن، اتمیک."""
    if st.status == SettlementStatus.SETTLED:
        raise SettlementError("این تسویه قبلاً اجرا شده است (اجرای تکراری ممنوع)")
    if fee_amount is None or fee_amount < 0:
        raise SettlementError("کارمزد نامعتبر است")
    gross = int(Decimal(st.gross_amount))
    if fee_amount > gross:
        raise SettlementError("کارمزد از مبلغ ناخالص تسویه بیشتر است")

    from app.services.accounting import entry_for_settlement

    st.fee_amount = Decimal(fee_amount)
    st.net_amount = Decimal(gross - fee_amount)
    entry = entry_for_settlement(db, st, commit=False)  # idempotent با (settlement, source_id)
    st.journal_entry_id = entry.id
    st.status = SettlementStatus.SETTLED
    st.settled_by = actor.id if actor else None
    st.settled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(st)
    return st


def settlement_out(db: Session, st: Settlement, with_items: bool = False) -> dict:
    from app.models.accounting import JournalEntry

    from app.services.accounting import entry_out

    journal_entry = db.get(JournalEntry, st.journal_entry_id) if st.journal_entry_id else None
    out = {
        "id": str(st.id),
        "settlement_no": st.settlement_no,
        "gateway": st.gateway,
        "period_start": st.period_start.isoformat() if st.period_start else None,
        "period_end": st.period_end.isoformat() if st.period_end else None,
        "payments_count": int(Decimal(st.payments_count or 0)),
        "gross_amount": float(Decimal(st.gross_amount or 0)),
        "fee_amount": float(Decimal(st.fee_amount)) if st.fee_amount is not None else None,
        "net_amount": float(Decimal(st.net_amount)) if st.net_amount is not None else None,
        "currency": st.currency,
        "status": st.status,
        "journal_entry_id": str(st.journal_entry_id) if st.journal_entry_id else None,
        "journal_entry": entry_out(journal_entry, db) if journal_entry else None,
        "note": st.note,
        "settled_at": st.settled_at.isoformat() if st.settled_at else None,
        "created_at": st.created_at.isoformat() if st.created_at else None,
    }
    if with_items:
        items = db.scalars(
            select(SettlementItem).where(SettlementItem.settlement_id == st.id)
        ).all()
        out["items"] = [
            {
                "payment_id": str(i.payment_id),
                "amount": float(Decimal(i.amount)),
            }
            for i in items
        ]
    return out
