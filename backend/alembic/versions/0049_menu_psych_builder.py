"""فاز ۸۳ج — منوی «فرم‌ساز آزمون‌ها» در گروه «سامانه و پشتیبانی»

فرم‌ساز گرافیکی ابزارهای آزمون (فاز ۸۳) فقط از پنجرهٔ «مدیریت سؤال و تفسیر» در
مرکز آزمون در دسترس بود و در فهرست ابزارها دیده نمی‌شد. از این فاز یک آیتم منوی
مستقل با کلید ``psych-form-builder`` به گروه «سامانه و پشتیبانی» اضافه شد که
لانچرِ انتخاب ابزار را باز می‌کند و از آنجا فرم‌ساز پنج‌تبی (با پیش‌نمایش زنده).

- فقط ``ORG_MANAGER`` پیش‌فرض «دیدن» می‌گیرد — همان نقش‌هایی که مسیر فرم‌ساز
  (ProtectedRoute) باز می‌کنند؛ SYSTEM_ADMIN عمداً ردیفی ندارد (bypass همیشگی).
- self_service=True در رجیستری: APIهای فرم‌ساز خودشان با require_roles
  محافظت می‌شوند؛ ماتریس فقط «نمایش منو» را کنترل می‌کند.
- idempotent با ON CONFLICT DO NOTHING: تصمیم بعدی مدیر در ماتریس بازنویسی
  نمی‌شود.
"""

from alembic import op
import sqlalchemy as sa

revision = "0049_menu_psych_builder"
down_revision = "0048_menu_static_links"
branch_labels = None
depends_on = None

MENU_KEY = "psych-form-builder"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO role_menu_permissions (role_code, menu_key, level) "
            "VALUES ('ORG_MANAGER', :m, 'view') ON CONFLICT (role_code, menu_key) DO NOTHING"
        ),
        {"m": MENU_KEY},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM role_menu_permissions WHERE menu_key = :m"),
        {"m": MENU_KEY},
    )
