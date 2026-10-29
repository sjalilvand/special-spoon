"""فاز ۵۹ - تعمیر داده‌های تاریخ: شمسیِ ذخیره‌شده به‌صورت میلادی (یک‌بار مصرف).

Revision ID: 0036_jalali_date_repair
Revises: 0035_org_programs
Create Date: 2026-10-30

پیشینهٔ باگ: کامپوننت ``JalaliDateField`` (فاز ۴۹) تاریخ انتخابی تقویم شمسی
(مثل ۱۴۰۴/۰۸/۰۸) را عیناً به‌صورت رشتهٔ ISO میلادی (``1404-08-08``) ذخیره
می‌کرد؛ یعنی تاریخ‌های پرسشنامهٔ پذیرش، متقاضیان، مدارک مشاوران و تعرفه‌ها
~۵۷۸ سال در آینده ثبت شده بودند.

راهکار: هر مقدار ``date`` با سال ≤ ۱۵۰۰ (محدودهٔ ناممکن میلادی در این سامانه،
محدودهٔ محتمل شمسی ۱۳۰۰–۱۵۰۰) با الگوریتم جلالی به میلادی واقعی تبدیل می‌شود.
ستون‌های هدف (فقط ستون‌هایی که از فرم‌های شمسی پر می‌شوند):
- applicants.birth_date
- counselors.license_expiry_date
- counselor_credentials.issued_at / expires_at
- intake_questionnaires.data  (کلیدهای *_date در JSONB)
"""
from alembic import op
import sqlalchemy as sa
import json
from datetime import date

revision = "0036_jalali_date_repair"
down_revision = "0035_org_programs"
branch_labels = None
depends_on = None

# سال‌های میلادیِ معتبر در این سامانه: ۱۹۰۰ به بعد؛ هرچه کمتر است = شمسیِ خطادار
MAX_GREGORIAN_YEAR = 1500

DATE_COLUMNS = [
    ("applicants", "birth_date"),
    ("counselors", "license_expiry_date"),
    ("counselor_credentials", "issued_at"),
    ("counselor_credentials", "expires_at"),
]

JSONB_TABLE = "intake_questionnaires"


def _jalali_to_gregorian(jy: int, jm: int, jd: int) -> sa.Date:
    """الگوریتم استاندارد جلالی (همسان با app.core.dates)."""
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    month_days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    for i, md in enumerate(month_days, start=1):
        if gd <= md:
            gm = i
            break
        gd -= md
    return date(gy, gm, gd)


def _needs_repair(value) -> bool:
    if value is None:
        return False
    year = getattr(value, "year", None)
    return year is not None and year <= MAX_GREGORIAN_YEAR


def upgrade() -> None:
    conn = op.get_bind()
    total = 0

    # --- ستون‌های date ساده ---
    for table, col in DATE_COLUMNS:
        rows = conn.execute(
            sa.text(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")
        ).fetchall()
        for row_id, value in rows:
            if _needs_repair(value):
                fixed = _jalali_to_gregorian(value.year, value.month, value.day)
                conn.execute(
                    sa.text(f"UPDATE {table} SET {col} = :v WHERE id = :i"),
                    {"v": fixed, "i": row_id},
                )
                total += 1

    # --- پرسشنامهٔ پذیرش: کلیدهای *_date در JSONB ---
    rows = conn.execute(
        sa.text(f"SELECT id, data FROM {JSONB_TABLE} WHERE data IS NOT NULL")
    ).fetchall()
    for row_id, data in rows:
        if not isinstance(data, dict):
            continue
        changed = False
        for key, val in list(data.items()):
            if not key.endswith("_date") or not isinstance(val, str):
                continue
            parts = val.strip().split("-")
            if len(parts) != 3:
                continue
            try:
                y, m, d = (int(p) for p in parts)
            except ValueError:
                continue
            if y <= MAX_GREGORIAN_YEAR and 1 <= m <= 12 and 1 <= d <= 31:
                fixed = _jalali_to_gregorian(y, m, d)
                data[key] = fixed.isoformat()
                changed = True
                total += 1
        if changed:
            conn.execute(
                sa.text(f"UPDATE {JSONB_TABLE} SET data = CAST(:j AS jsonb) WHERE id = :i"),
                {"j": json.dumps(data, ensure_ascii=False), "i": row_id},
            )

    # ثبت نتیجه در لاگ مایگریشن (قابل مشاهده در خروجی deploy)
    print(f"[0036] تاریخ‌های شمسیِ خطادار تعمیر شد: {total} مقدار")


def downgrade() -> None:
    # تعمیر داده برگشت‌پذیر نیست (اطلاعات اصلی از دست رفته است)
    pass
