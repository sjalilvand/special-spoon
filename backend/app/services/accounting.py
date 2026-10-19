"""فاز ۳۱ - B22 سند جامع: سرویس حسابداری — کدینگ، سند متوازن، ردیابی رویداد.

قواعد سند:
- «سند متوازن» — post_entry پیش از ثبت، توازن جمع بدهکار/بستانکار و
  یک‌سمتی هر ردیف را کنترل می‌کند؛ تخلف → AccountingError (422 در API).
- «قابل ردیابی به رویداد مالی» — اسناد خودکار با (source_type, source_id)
  ثبت می‌شوند و قید یکتایی پایگاه تکرار را ناممکن می‌کند؛ تابع‌های
  ensure_* ابتدا وجود سند را می‌کنند (idempotent کامل، سازگار با
  callback تکراری فاز ۲۹).
- backfill_financial_events — رویدادهای بدون سند (از فازهای پیش یا
  شکست تراکنش) را یک‌بارمصرف سند می‌زند؛ ابزار مغایرت‌گیری نیز هست.

کدینگ پیش‌فرض (سرفصل سیستمی):
  1101 بانک | 1102 درگاه در جریان وصول | 1103 تصفیه
  2101 کیف پول کاربران | 2102 استردادهای پرداختنی
  4101 درآمد خدمات | 4102 برگشت از فروش | 4103 سایر درآمد
  5101 کارمزد درگاه | 5102 هزینه تخفیف | 5103 جبران و تعدیل

نگاشت رویداد → سند:
  پرداخت درگاه (خدمت) : Dr 1102 خالص + Dr 5102 تخفیف  | Cr 4101 ناخالص
  پرداخت درگاه (شارژ) : Dr 1102                       | Cr 2101
  پرداخت کیف پول      : Dr 2101 خالص + Dr 5102 تخفیف  | Cr 4101 ناخالص
  استرداد به کیف پول  : Dr 4102                       | Cr 2101
  استرداد درگاهی      : Dr 4102                       | Cr 2102
  تعدیل + (شارژ)      : Dr 5103                       | Cr 2101
  تعدیل − (کسر)       : Dr 2101                       | Cr 4103
  تسویه دوره درگاه    : Dr 1101 خالص + Dr 5101 کارمزد | Cr 1102 ناخالص
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.accounting import (
    Account,
    AccountType,
    JournalEntry,
    JournalLine,
    JournalSource,
)
from app.models.payment import Order, Payment, PaymentStatus
from app.models.refund import Refund
from app.models.wallet import WalletEntry, WalletEntryReason

ACCOUNT_CODE = {
    "bank": "1101",
    "gateway_receivable": "1102",
    "clearing": "1103",
    "org_receivable": "1104",
    "wallet_liability": "2101",
    "refund_payable": "2102",
    "service_revenue": "4101",
    "sales_returns": "4102",
    "other_income": "4103",
    "gateway_fee": "5101",
    "discount_expense": "5102",
    "compensation_expense": "5103",
}

DEFAULT_ACCOUNTS = [
    ("1101", "حساب بانک", AccountType.ASSET),
    ("1102", "درگاه‌های پرداخت - در جریان وصول", AccountType.ASSET),
    ("1103", "حساب‌های تصفیه", AccountType.ASSET),
    ("1104", "حساب‌های دریافتنی از سازمان‌ها", AccountType.ASSET),
    ("2101", "کیف پول کاربران", AccountType.LIABILITY),
    ("2102", "استردادهای پرداختنی", AccountType.LIABILITY),
    ("4101", "درآمد خدمات مشاوره", AccountType.REVENUE),
    ("4102", "برگشت از فروش", AccountType.REVENUE),
    ("4103", "سایر درآمدها (تعدیل)", AccountType.REVENUE),
    ("5101", "هزینه کارمزد درگاه", AccountType.EXPENSE),
    ("5102", "هزینه تخفیف", AccountType.EXPENSE),
    ("5103", "هزینه جبران و تعدیل", AccountType.EXPENSE),
]

DEBIT_TYPES = (AccountType.ASSET, AccountType.EXPENSE)


class AccountingError(Exception):
    """خطای قابل نمایش کاربر/مدیر مالی."""


def _today() -> date:
    return datetime.now(timezone.utc).date()


def ensure_chart(db: Session) -> None:
    """کدینگ پیش‌فرض — idempotent؛ فقط کدهای غایب اضافه می‌شوند."""
    existing = {c for (c,) in db.execute(select(Account.code)).all()}
    for code, name, atype in DEFAULT_ACCOUNTS:
        if code not in existing:
            db.add(Account(code=code, name=name, type=atype, is_active=True, is_system=True))
    db.flush()


def account_by_code(db: Session, code: str) -> Account:
    acc = db.scalars(select(Account).where(Account.code == code)).first()
    if acc is None:
        ensure_chart(db)
        acc = db.scalars(select(Account).where(Account.code == code)).first()
    if acc is None:
        raise AccountingError(f"سرفصل با کد {code} یافت نشد")
    return acc


def next_entry_number(db: Session) -> str:
    """شماره یکتای سند: JE-<سال شمسی>-<ترتیب ۶ رقمی>؛ مقاوم به تلاش هم‌زمان."""
    from app.core.dates import gregorian_to_jalali

    now = datetime.now(timezone.utc)
    jy, _, _ = gregorian_to_jalali(now.year, now.month, now.day)
    for _ in range(30):
        rows = db.execute(
            text("SELECT COUNT(*) FROM journal_entries WHERE entry_no LIKE :pfx"),
            {"pfx": f"JE-{jy:04d}-%"},
        ).scalar() or 0
        candidate = f"JE-{jy:04d}-{rows + 1:06d}"
        if db.scalars(select(JournalEntry.id).where(JournalEntry.entry_no == candidate)).first() is None:
            return candidate
    raise AccountingError("تولید شماره سند ناموفق بود")


def _validate_lines(lines: list[dict]) -> None:
    """قاعده «سند متوازن» + یک‌سمتی و مثبت بودن مبالغ."""
    if not lines:
        raise AccountingError("سند بدون ردیف مجاز نیست")
    total_debit = Decimal(0)
    total_credit = Decimal(0)
    for ln in lines:
        debit = Decimal(ln.get("debit") or 0)
        credit = Decimal(ln.get("credit") or 0)
        if debit < 0 or credit < 0:
            raise AccountingError("مبالغ سند نمی‌توانند منفی باشند")
        if debit > 0 and credit > 0:
            raise AccountingError("هر ردیف فقط یک سمت (بدهکار یا بستانکار) می‌تواند داشته باشد")
        if debit == 0 and credit == 0:
            raise AccountingError("مبلغ هر ردیف باید مثبت باشد")
        if not ln.get("account_id"):
            raise AccountingError("سرفصل هر ردیف الزامی است")
        total_debit += debit
        total_credit += credit
    if total_debit != total_credit:
        raise AccountingError(
            f"سند متوازن نیست (بدهکار {int(total_debit):,} ≠ بستانکار {int(total_credit):,})"
        )


def post_entry(
    db: Session,
    *,
    lines: list[dict],
    description: str,
    kind: str,
    source_type: str,
    source_id: uuid.UUID | None = None,
    entry_date: date | None = None,
    created_by: uuid.UUID | None = None,
    commit: bool = True,
    is_reversal: bool = False,
    reversal_of_id: uuid.UUID | None = None,
) -> JournalEntry:
    """ثبت سند متوازن؛ برای رویداد سیستمی idempotent است (قید یکتایی)."""
    if source_type == JournalSource.MANUAL:
        existing = None
    elif source_id is not None:
        existing = db.scalars(
            select(JournalEntry).where(
                JournalEntry.source_type == source_type, JournalEntry.source_id == source_id
            )
        ).first()
        if existing is not None:
            return existing  # callback تکراری/فراخوانی مجدد → سند مضاعف ممنوع
    else:
        existing = None

    _validate_lines(lines)
    entry = JournalEntry(
        entry_no=next_entry_number(db),
        entry_date=entry_date or _today(),
        description=description[:500],
        kind=kind[:40],
        source_type=source_type,
        source_id=source_id,
        is_reversal=is_reversal,
        reversal_of_id=reversal_of_id,
        created_by=created_by,
    )
    db.add(entry)
    db.flush()
    for ln in lines:
        db.add(
            JournalLine(
                entry_id=entry.id,
                account_id=ln["account_id"],
                debit=Decimal(ln.get("debit") or 0),
                credit=Decimal(ln.get("credit") or 0),
                description=(ln.get("description") or None),
            )
        )
    if commit:
        db.commit()
        db.refresh(entry)
    return entry


def reverse_entry(
    db: Session, entry: JournalEntry, *, reason: str | None = None, actor=None, commit: bool = True
) -> JournalEntry:
    """ابطال با سند برگشتی آینه‌ای — اسناد ثبت‌شده تغییرناپذیرند."""
    if entry.is_reversal:
        raise AccountingError("سند برگشتی خودش قابل برگشت نیست")
    mirror = db.scalars(
        select(JournalEntry).where(
            JournalEntry.reversal_of_id == entry.id, JournalEntry.is_reversal.is_(True)
        )
    ).first()
    if mirror is not None:
        return mirror  # برگشت تکراری بی‌اثر
    lines = [
        {
            "account_id": ln.account_id,
            "debit": ln.credit,   # جای‌گشت سمت‌ها
            "credit": ln.debit,
            "description": ln.description,
        }
        for ln in entry.lines
    ]
    return post_entry(
        db,
        lines=lines,
        description=(reason or f"سند برگشتی سند {entry.entry_no}")[:500],
        kind=f"reversal:{entry.kind}"[:40],
        source_type=JournalSource.REVERSAL,
        source_id=None,
        created_by=actor.id if actor else None,
        commit=commit,
        is_reversal=True,
        reversal_of_id=entry.id,
    )


# ------------------------------------------------ auto-posting (B22 × B10/B18/B20)
def _order_lines_for_revenue(db: Session, order: Order, payable: int, kind: str) -> list[dict]:
    """ردیف‌های شناسایی درآمد با تفکیک تخفیف (B19) و سهم سازمان (B21، فاز ۳۳):
    ناخالص 4101، تخفیف 5102، سهم سازمان دریافتنی 1104."""
    discount = int(Decimal(order.discount_amount or 0))
    org_share = int(Decimal(getattr(order, "org_share_amount", 0) or 0))
    gross = int(Decimal(order.amount or 0))
    # ناخالص باید قابل بازسازی باشد: payable + discount + org_share (پوشش حالت‌های لبه)
    if gross < payable + discount + org_share:
        gross = payable + discount + org_share
    rev = account_by_code(db, ACCOUNT_CODE["service_revenue"])
    lines: list[dict] = []
    if kind == "wallet":
        lines.append({
            "account_id": account_by_code(db, ACCOUNT_CODE["wallet_liability"]).id,
            "debit": payable,
            "credit": 0,
            "description": f"پرداخت سفارش {order.order_number} از کیف پول",
        })
    else:
        lines.append({
            "account_id": account_by_code(db, ACCOUNT_CODE["gateway_receivable"]).id,
            "debit": payable,
            "credit": 0,
            "description": f"دریافت درگاه برای سفارش {order.order_number}",
        })
    if discount > 0:
        lines.append({
            "account_id": account_by_code(db, ACCOUNT_CODE["discount_expense"]).id,
            "debit": discount,
            "credit": 0,
            "description": f"هزینه تخفیف سفارش {order.order_number}",
        })
    if org_share > 0:
        # فاز ۳۳ - B21: سهم سازمان = مطالبه از سازمان (دارایی)، نه درآمد نقدی
        lines.append({
            "account_id": account_by_code(db, ACCOUNT_CODE["org_receivable"]).id,
            "debit": org_share,
            "credit": 0,
            "description": f"سهم سازمان سفارش {order.order_number} (قرارداد)",
        })
    lines.append({
        "account_id": rev.id,
        "debit": 0,
        "credit": gross,
        "description": f"درآمد خدمات - سفارش {order.order_number}",
    })
    return lines


def entry_for_payment(db: Session, payment: Payment, order: Order, *, commit: bool = False) -> JournalEntry | None:
    """سند خودکار پرداخت موفق — idempotent با (payment, source_id)."""
    if payment.status != PaymentStatus.SUCCESS:
        return None
    if order.kind == "topup":
        # شارژ کیف پول درآمد نیست؛ بدهی (اعتبار کاربر) شناخته می‌شود
        amount = int(Decimal(payment.amount))
        wallet = account_by_code(db, ACCOUNT_CODE["wallet_liability"])
        gw = account_by_code(db, ACCOUNT_CODE["gateway_receivable"])
        kind = "payment_topup" if payment.gateway != "wallet" else "payment_topup_wallet"
        lines = (
            [{"account_id": gw.id, "debit": amount, "credit": 0, "description": f"دریافت شارژ کیف پول {order.order_number}"}]
            if payment.gateway != "wallet"
            else [{"account_id": wallet.id, "debit": amount, "credit": 0, "description": f"شارژ کیف پول {order.order_number} از اعتبار"}]
        )
        lines.append({"account_id": wallet.id, "debit": 0, "credit": amount,
                      "description": f"اعتبار کیف پول کاربر - سفارش {order.order_number}"})
        return post_entry(
            db, lines=lines, description=f"شارژ کیف پول - سفارش {order.order_number}",
            kind=kind, source_type=JournalSource.PAYMENT, source_id=payment.id,
            entry_date=payment.paid_at.date() if payment.paid_at else None, commit=commit,
        )
    kind = "payment_wallet" if payment.gateway == "wallet" else "payment_gateway"
    return post_entry(
        db,
        lines=_order_lines_for_revenue(db, order, int(Decimal(payment.amount)), "wallet" if payment.gateway == "wallet" else "gateway"),
        description=f"پرداخت سفارش {order.order_number} ({'کیف پول' if payment.gateway == 'wallet' else 'درگاه ' + payment.gateway})",
        kind=kind,
        source_type=JournalSource.PAYMENT,
        source_id=payment.id,
        entry_date=payment.paid_at.date() if payment.paid_at else None,
        commit=commit,
    )


def entry_for_refund(db: Session, refund: Refund, *, commit: bool = False) -> JournalEntry | None:
    """سند خودکار استرداد اجراشده — برگشت از فروش (4102)."""
    amount = int(Decimal(refund.amount))
    returns_acc = account_by_code(db, ACCOUNT_CODE["sales_returns"])
    if refund.channel == "wallet":
        to_acc = account_by_code(db, ACCOUNT_CODE["wallet_liability"])
        kind = "refund_wallet"
        desc = f"استرداد به کیف پول - مبلغ {amount:,}"
    else:
        to_acc = account_by_code(db, ACCOUNT_CODE["refund_payable"])
        kind = "refund_gateway"
        desc = f"استرداد درگاهی ({refund.gateway or 'نامشخص'}) - مبلغ {amount:,}"
    return post_entry(
        db,
        lines=[
            {"account_id": returns_acc.id, "debit": amount, "credit": 0, "description": "برگشت از فروش"},
            {"account_id": to_acc.id, "debit": 0, "credit": amount, "description": desc},
        ],
        description=desc,
        kind=kind,
        source_type=JournalSource.REFUND,
        source_id=refund.id,
        entry_date=refund.executed_at.date() if refund.executed_at else None,
        commit=commit,
    )


def entry_for_wallet_adjustment(db: Session, entry: WalletEntry, *, commit: bool = False) -> JournalEntry | None:
    """سند خودکار تعدیل دستی مدیر — فقط ردیف‌های reason='adjustment'."""
    if entry.reason != WalletEntryReason.ADJUSTMENT:
        return None
    amount = int(Decimal(entry.amount))
    wallet = account_by_code(db, ACCOUNT_CODE["wallet_liability"])
    if entry.direction == "credit":
        lines = [
            {"account_id": account_by_code(db, ACCOUNT_CODE["compensation_expense"]).id,
             "debit": amount, "credit": 0, "description": "هزینه جبران/تعدیل کیف پول"},
            {"account_id": wallet.id, "debit": 0, "credit": amount, "description": "افزایش اعتبار کاربر"},
        ]
        side = "شارژ"
    else:
        lines = [
            {"account_id": wallet.id, "debit": amount, "credit": 0, "description": "کسر اعتبار کاربر"},
            {"account_id": account_by_code(db, ACCOUNT_CODE["other_income"]).id,
             "debit": 0, "credit": amount, "description": "صرفه تعدیل کیف پول"},
        ]
        side = "کسر"
    return post_entry(
        db,
        lines=lines,
        description=f"تعدیل کیف پول ({side}) - {entry.note or 'بدون یادداشت'}",
        kind="wallet_adjustment",
        source_type=JournalSource.WALLET_ADJUSTMENT,
        source_id=entry.id,
        commit=commit,
    )


def entry_for_settlement(db: Session, settlement, *, commit: bool = False) -> JournalEntry | None:
    """سند تسویه دوره: وصول بانکی خالص + کارمزد در برابر مطالبات درگاه."""
    gross = int(Decimal(settlement.gross_amount))
    fee = int(Decimal(settlement.fee_amount or 0))
    net = gross - fee
    bank = account_by_code(db, ACCOUNT_CODE["bank"])
    gw = account_by_code(db, ACCOUNT_CODE["gateway_receivable"])
    lines = [
        {"account_id": bank.id, "debit": net, "credit": 0,
         "description": f"واریز تسویه {settlement.settlement_no} به بانک"},
    ]
    if fee > 0:
        lines.append({
            "account_id": account_by_code(db, ACCOUNT_CODE["gateway_fee"]).id,
            "debit": fee, "credit": 0, "description": f"کارمزد درگاه {settlement.gateway}",
        })
    lines.append({"account_id": gw.id, "debit": 0, "credit": gross,
                  "description": f"تسویه مطالبات درگاه {settlement.gateway}"})
    return post_entry(
        db,
        lines=lines,
        description=f"تسویه دوره درگاه {settlement.gateway} - {settlement.settlement_no}",
        kind="settlement",
        source_type=JournalSource.SETTLEMENT,
        source_id=settlement.id,
        commit=commit,
    )


# ------------------------------------------------ backfill & گزارش
def backfill_financial_events(db: Session, *, actor=None, commit: bool = True) -> dict:
    """سند زدن رویدادهای مالی بدون سند (idempotent) — مغایرت‌گیری و مهاجرت."""
    ensure_chart(db)
    created = {"payments": 0, "refunds": 0, "wallet_adjustments": 0}

    payments = db.scalars(select(Payment).where(Payment.status == PaymentStatus.SUCCESS)).all()
    for p in payments:
        if db.scalars(
            select(JournalEntry.id).where(
                JournalEntry.source_type == JournalSource.PAYMENT, JournalEntry.source_id == p.id
            )
        ).first():
            continue
        order = db.get(Order, p.order_id)
        if order is None:
            continue
        if entry_for_payment(db, p, order, commit=False) is not None:
            created["payments"] += 1

    refunds = db.scalars(select(Refund)).all()
    for r in refunds:
        if db.scalars(
            select(JournalEntry.id).where(
                JournalEntry.source_type == JournalSource.REFUND, JournalEntry.source_id == r.id
            )
        ).first():
            continue
        if entry_for_refund(db, r, commit=False) is not None:
            created["refunds"] += 1

    adjustments = db.scalars(
        select(WalletEntry).where(WalletEntry.reason == WalletEntryReason.ADJUSTMENT)
    ).all()
    for w in adjustments:
        if db.scalars(
            select(JournalEntry.id).where(
                JournalEntry.source_type == JournalSource.WALLET_ADJUSTMENT,
                JournalEntry.source_id == w.id,
            )
        ).first():
            continue
        if entry_for_wallet_adjustment(db, w, commit=False) is not None:
            created["wallet_adjustments"] += 1

    if commit:
        db.commit()
    return created


def trial_balance(db: Session) -> dict:
    """تراز آزمایشی — مانده هر حساب + کنترل کل توازن دفتر."""
    rows = db.execute(
        select(
            JournalLine.account_id,
            func.sum(JournalLine.debit),
            func.sum(JournalLine.credit),
        ).group_by(JournalLine.account_id)
    ).all()
    by_acc = {r[0]: (Decimal(r[1] or 0), Decimal(r[2] or 0)) for r in rows}
    accounts = db.scalars(select(Account).order_by(Account.code)).all()
    items = []
    total_debit = Decimal(0)
    total_credit = Decimal(0)
    for acc in accounts:
        debit, credit = by_acc.get(acc.id, (Decimal(0), Decimal(0)))
        if debit == 0 and credit == 0:
            continue
        raw_balance = debit - credit
        typed_balance = raw_balance if acc.type in DEBIT_TYPES else -raw_balance
        items.append({
            "id": str(acc.id),
            "code": acc.code,
            "name": acc.name,
            "type": acc.type,
            "debit": float(debit),
            "credit": float(credit),
            "raw_balance": float(raw_balance),
            "balance": float(typed_balance),
            "is_active": acc.is_active,
        })
        total_debit += debit
        total_credit += credit
    return {
        "items": items,
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "is_balanced": total_debit == total_credit,
    }


def reconciliation(db: Session) -> dict:
    """مغایرت: پوشش سند رویدادهای مالی + توازن دفتر + تطبیق فروش (B24×B22)."""
    def _coverage(source_type: str) -> dict:
        if source_type == JournalSource.PAYMENT:
            total, amount = db.execute(
                select(func.count(), func.coalesce(func.sum(Payment.amount), 0))
                .where(Payment.status == PaymentStatus.SUCCESS)
            ).one()
        elif source_type == JournalSource.REFUND:
            total, amount = db.execute(
                select(func.count(), func.coalesce(func.sum(Refund.amount), 0))
            ).one()
        else:
            total, amount = db.execute(
                select(func.count(), func.coalesce(func.sum(WalletEntry.amount), 0))
                .where(WalletEntry.reason == WalletEntryReason.ADJUSTMENT)
            ).one()
        journaled = int(db.scalar(
            select(func.count()).select_from(JournalEntry).where(
                JournalEntry.source_type == source_type, JournalEntry.is_reversal.is_(False)
            )
        ) or 0)
        return {"total": int(total), "journaled": journaled, "uncovered": max(0, int(total) - journaled),
                "amount": float(amount)}

    payments_cov = _coverage(JournalSource.PAYMENT)
    refunds_cov = _coverage(JournalSource.REFUND)
    adjustments_cov = _coverage(JournalSource.WALLET_ADJUSTMENT)

    tb = trial_balance(db)

    # تطبیق فروش گزارش (سفارش‌های خدمت) با درآمد شناسایی‌شده در دفتر
    sales_net = db.execute(
        select(func.coalesce(func.sum(Order.payable_amount - Order.refunded_amount), 0))
        .where(Order.status == "paid", Order.kind == "service")
    ).scalar() or 0
    revenue_acc = db.scalars(select(Account).where(Account.code == ACCOUNT_CODE["service_revenue"])).first()
    returns_acc = db.scalars(select(Account).where(Account.code == ACCOUNT_CODE["sales_returns"])).first()
    discount_acc = db.scalars(select(Account).where(Account.code == ACCOUNT_CODE["discount_expense"])).first()
    revenue_amount = Decimal(0)
    returns_amount = Decimal(0)
    discount_amount = Decimal(0)
    if revenue_acc is not None:
        rows = db.execute(
            select(func.sum(JournalLine.credit), func.sum(JournalLine.debit))
            .where(JournalLine.account_id == revenue_acc.id, JournalLine.entry_id.in_(
                select(JournalEntry.id).where(JournalEntry.is_reversal.is_(False)))
            )
        ).one()
        revenue_amount = Decimal(rows[0] or 0) - Decimal(rows[1] or 0)
    if returns_acc is not None:
        rows = db.execute(
            select(func.sum(JournalLine.debit), func.sum(JournalLine.credit))
            .where(JournalLine.account_id == returns_acc.id, JournalLine.entry_id.in_(
                select(JournalEntry.id).where(JournalEntry.is_reversal.is_(False)))
            )
        ).one()
        returns_amount = Decimal(rows[0] or 0) - Decimal(rows[1] or 0)
    if discount_acc is not None:
        rows = db.execute(
            select(func.sum(JournalLine.debit), func.sum(JournalLine.credit))
            .where(JournalLine.account_id == discount_acc.id, JournalLine.entry_id.in_(
                select(JournalEntry.id).where(JournalEntry.is_reversal.is_(False)))
            )
        ).one()
        discount_amount = Decimal(rows[0] or 0) - Decimal(rows[1] or 0)
    # فروش گزارش (خالص پس از تخفیف/استرداد) = درآمد − برگشت از فروش − هزینه تخفیف
    journal_revenue = float(revenue_amount - returns_amount - discount_amount)
    diff = float(sales_net) - journal_revenue
    return {
        "events": {
            "payments": payments_cov,
            "refunds": refunds_cov,
            "wallet_adjustments": adjustments_cov,
        },
        "ledger": {
            "total_debit": tb["total_debit"],
            "total_credit": tb["total_credit"],
            "is_balanced": tb["is_balanced"],
        },
        "sales_reconciliation": {
            "sales_report_amount": float(sales_net),
            "journal_revenue_amount": journal_revenue,
            "difference": diff,
            "reconciled": abs(diff) < 0.01,
        },
    }


# ------------------------------------------------ serializers
def account_out(acc: Account, children: list | None = None) -> dict:
    out = {
        "id": str(acc.id),
        "code": acc.code,
        "name": acc.name,
        "type": acc.type,
        "parent_id": str(acc.parent_id) if acc.parent_id else None,
        "description": acc.description,
        "is_active": acc.is_active,
        "is_system": acc.is_system,
        "created_at": acc.created_at.isoformat() if acc.created_at else None,
    }
    if children is not None:
        out["children"] = children
    return out


def entry_out(entry: JournalEntry, db: Session | None = None) -> dict:
    lines = []
    for ln in entry.lines:
        acc = db.get(Account, ln.account_id) if db is not None else None
        lines.append({
            "id": str(ln.id),
            "account_id": str(ln.account_id),
            "account_code": acc.code if acc else None,
            "account_name": acc.name if acc else None,
            "debit": float(ln.debit),
            "credit": float(ln.credit),
            "description": ln.description,
        })
    return {
        "id": str(entry.id),
        "entry_no": entry.entry_no,
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
        "description": entry.description,
        "kind": entry.kind,
        "source_type": entry.source_type,
        "source_id": str(entry.source_id) if entry.source_id else None,
        "is_reversal": entry.is_reversal,
        "reversal_of_id": str(entry.reversal_of_id) if entry.reversal_of_id else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "lines": lines,
    }
