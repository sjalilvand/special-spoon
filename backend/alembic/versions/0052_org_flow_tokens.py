"""فاز ۸۷ — جریان مشاورهٔ حضوری + توکن موقت کاربران + rebrand رز دکتر.

سه تغییر:
- ``users.token_hours``: عمر نشست کاربر بر حسب ساعت (NULL = دائمی — پیش‌فرض
  سامانه). کاربر موقت (مثلاً متقاضی آزمون سازمانی) بعد از ۱ تا ۲ ساعت از
  ورود، نشستش منقضی می‌شود و refresh هم دیگر آن را زنده نگه نمی‌دارد.
- ``users.serial_number``: شمارهٔ سریال اختیاری برای تفکیک کاربران در
  مدیریت کاربران (توکن با شمارهٔ سریال صادر می‌شود).
- ``consultation_requests.request_type``: نوع دریافت درخواست —
  ``online`` (رزرو سایت)، ``in_person`` (حضوری) و ``phone`` (تلفنی)؛
  NULL = ردیف‌های قدیمی (رفتار قبلی).

idempotent: همهٔ ستون‌ها با بررسی وجود اضافه می‌شوند؛ ایندکس سریال فقط
وقتی ساخته می‌شود که ستون تازه ساخته شده باشد (ستون‌های تکراری موجب
خطای ایندکس تکراری نمی‌شوند چون IF NOT EXISTS دارد).
"""

from alembic import op
import sqlalchemy as sa

revision = "0052_org_flow_tokens"
down_revision = "0051_academy_storefront"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()

    # ── users: توکن موقت + شمارهٔ سریال ──
    if not _has_column(bind, "users", "token_hours"):
        op.add_column("users", sa.Column("token_hours", sa.Integer(), nullable=True))
    if not _has_column(bind, "users", "serial_number"):
        op.add_column("users", sa.Column("serial_number", sa.String(length=50), nullable=True))
        op.create_index(
            "ix_users_serial_number", "users", ["serial_number"], unique=True,
            postgresql_where=sa.text("serial_number IS NOT NULL"),
        )

    # ── consultation_requests: نوع درخواست (حضوری/تلفنی/آنلاین) ──
    if not _has_column(bind, "consultation_requests", "request_type"):
        op.add_column(
            "consultation_requests",
            sa.Column("request_type", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "consultation_requests", "request_type"):
        op.drop_column("consultation_requests", "request_type")
    if _has_column(bind, "users", "serial_number"):
        op.drop_index("ix_users_serial_number", table_name="users")
        op.drop_column("users", "serial_number")
    if _has_column(bind, "users", "token_hours"):
        op.drop_column("users", "token_hours")
