"""فاز ۸۴ — ویرایشگر وردپرسی‌وار صفحات عمومی سایت

دو تغییر:
- جدول ``site_page_content``: هر صفحهٔ عمومی (کلید page_key) یک ردیف با
  ``draft_content`` و ``published_content`` (JSONB). هیچ سندی منتشر نشده = سایت
  به متن‌های پیش‌فرض کد برمی‌گردد (fallback طبیعی اپ site) — یعنی مایگریشن
  هیچ چیزی را نمی‌شکند.
- ردیف ماتریس منو: ``ORG_MANAGER`` / ``site-content-editor`` / ``edit`` — سطح
  «ویرایش» چون endpointهای PUT/POST پشت دروازهٔ ماتریس‌اند. SYSTEM_ADMIN عمداً
  ردیفی ندارد (bypass همیشگی).

idempotent: ساخت جدول با بررسی وجود + INSERT ماتریس با ON CONFLICT DO NOTHING
تا تصمیم بعدی مدیر در ماتریس بازنویسی نشود.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0050_site_content_editor"
down_revision = "0049_menu_psych_builder"
branch_labels = None
depends_on = None

MENU_KEY = "site-content-editor"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("site_page_content"):
        op.create_table(
            "site_page_content",
            sa.Column("page_key", sa.String(length=64), primary_key=True),
            sa.Column("draft_content", JSONB(), nullable=True),
            sa.Column("published_content", JSONB(), nullable=True),
            sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=True,
            ),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_by", UUID(as_uuid=True), nullable=True),
        )
    bind.execute(
        sa.text(
            "INSERT INTO role_menu_permissions (role_code, menu_key, level) "
            "VALUES ('ORG_MANAGER', :m, 'edit') ON CONFLICT (role_code, menu_key) DO NOTHING"
        ),
        {"m": MENU_KEY},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM role_menu_permissions WHERE menu_key = :m"),
        {"m": MENU_KEY},
    )
    if sa.inspect(bind).has_table("site_page_content"):
        op.drop_table("site_page_content")
