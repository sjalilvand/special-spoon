"""فاز ۵۵ - پنل پذیرش/مدیر برای مشاهدهٔ گفتگوهای عمومی و امتیازها

Revision ID: 0033_public_chat_monitor
Revises: 0032_public_chat
Create Date: 2026-10-29

- دسترسی جدید ``chat.public_monitor`` در کاتالوگ RBAC (بخش «گفتگو») —
  مشاهدهٔ گفتگوهای عمومی سایت، هویت گوینده (کاربر/مهمان/IP)، متن پرسش‌ها
  و امتیاز/نظری که کاربر برای گفتگو ثبت کرده است؛
- اعطای پیش‌فرض به نقش‌های ORG_MANAGER (مدیر) و RECEPTION (پذیرش) و
  SYSTEM_ADMIN — idempotent؛ پس از این، ماتریس گرافیکی پنل ملاک است؛
- ستون‌های پیگیری پذیرش روی public_chat_sessions:
    staff_note        → یادداشت پذیرش/مدیر روی هر گفتگو (تماس گرفتیم و…)؛
    handled_by_user_id → آخرین همکارِ رسیدگی‌کننده؛
    handled_at        → زمان آخرین رسیدگی.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0033_public_chat_monitor"
down_revision = "0032_public_chat"
branch_labels = None
depends_on = None

PERM_CODE = "chat.public_monitor"
PERM_SECTION = "گفتگو"
PERM_TITLE = "مشاهدهٔ گفتگوهای عمومی سایت و امتیازها"
PERM_SORT = 3
# پذیرش/مدیر باید بلافاصله پنل را ببینند؛ SYSTEM_ADMIN ذاتی دسترسی کامل دارد
# ولی ردیفش در ماتریس ثبت می‌شود تا نمایش یکدست بماند.
DEFAULT_ROLES = ("ORG_MANAGER", "RECEPTION", "SYSTEM_ADMIN")


def upgrade() -> None:
    # --- ستون‌های پیگیری پذیرش ---
    op.add_column(
        "public_chat_sessions",
        sa.Column("staff_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "public_chat_sessions",
        sa.Column(
            "handled_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "public_chat_sessions",
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- seed دسترسی جدید + اعطای پیش‌فرض (idempotent) ---
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO permissions (code, section, title, sort) "
            "VALUES (:c, :s, :t, :o) ON CONFLICT (code) DO NOTHING"
        ),
        {"c": PERM_CODE, "s": PERM_SECTION, "t": PERM_TITLE, "o": PERM_SORT},
    )
    for role_code in DEFAULT_ROLES:
        conn.execute(
            sa.text(
                "INSERT INTO roles (code, title, data_scope) "
                "VALUES (:r, :t, 'all') ON CONFLICT (code) DO NOTHING"
            ),
            {"r": role_code, "t": role_code},
        )
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_code, permission_code) "
                "VALUES (:r, :c) ON CONFLICT DO NOTHING"
            ),
            {"r": role_code, "c": PERM_CODE},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code = :c"),
        {"c": PERM_CODE},
    )
    conn.execute(
        sa.text("DELETE FROM permissions WHERE code = :c"),
        {"c": PERM_CODE},
    )
    op.drop_column("public_chat_sessions", "handled_at")
    op.drop_column("public_chat_sessions", "handled_by_user_id")
    op.drop_column("public_chat_sessions", "staff_note")
