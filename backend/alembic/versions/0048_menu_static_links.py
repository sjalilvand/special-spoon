"""فاز ۸۲ — کلیددار شدن لینک‌های ایستا (راهنمای سامانه / گزارش پیشرفت پروژه)

تا فاز ۸۱ دو منوی «راهنمای سامانه» و «گزارش پیشرفت پروژه» (فایل‌های HTML ایستای
پنل) عمداً بیرون ماتریس دسترسی بودند و برای همه اجباری دیده می‌شدند. از این فاز
کلیدهای ``system-guide`` و ``project-progress`` به رجیستری منوها اضافه شدند و
در ماتریس «نقش‌ها و دسترسی‌ها» قابل مدیریت‌اند (دیدن/برداشتن برای هر نقش).

- این مایگریشن فقط پیش‌فرضِ «دیدن» را برای نقش‌های موجود درج می‌کند تا هیچ‌کس
  بعد از استقرار منویی را از دست ندهد (رفتار قبلی = دیده‌شدن برای همه).
- idempotent با ON CONFLICT DO NOTHING: تنظیم‌هایی که مدیر بعداً در ماتریس
  گرافیکی می‌کند هرگز با اجرای مجدد بازنویسی نمی‌شود (مایگریشن یک‌بار اجرا
  می‌شود، ولی همین تضمین برای محیط‌های بازپخش‌شده هم لازم است).
- نقش SYSTEM_ADMIN عمداً ردیفی ندارد — همیشه دسترسی کامل دارد (bypass).
"""

from alembic import op
import sqlalchemy as sa

revision = "0048_menu_static_links"
down_revision = "0047_org_branding"
branch_labels = None
depends_on = None

# کلیدهای جدید فاز ۸۲ (لینک‌های ایستای پنل)
NEW_MENU_KEYS = ("system-guide", "project-progress")


def upgrade() -> None:
    conn = op.get_bind()
    # همهٔ نقش‌های موجود (سیستمی + سفارشی) جزو گیرندهٔ پیش‌فرض — مثل رفتار قبلی
    # roles=["*"] — به‌جز SYSTEM_ADMIN که همیشه کامل است و ردیف نمی‌گیرد.
    role_codes = [
        r[0]
        for r in conn.execute(
            sa.text("SELECT code FROM roles WHERE code <> 'SYSTEM_ADMIN'")
        ).fetchall()
    ]
    for role_code in role_codes:
        for menu_key in NEW_MENU_KEYS:
            conn.execute(
                sa.text(
                    "INSERT INTO role_menu_permissions (role_code, menu_key, level) "
                    "VALUES (:r, :m, 'view') ON CONFLICT (role_code, menu_key) DO NOTHING"
                ),
                {"r": role_code, "m": menu_key},
            )


def downgrade() -> None:
    conn = op.get_bind()
    for menu_key in NEW_MENU_KEYS:
        conn.execute(
            sa.text("DELETE FROM role_menu_permissions WHERE menu_key = :m"),
            {"m": menu_key},
        )
