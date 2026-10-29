"""فاز ۵۶ - اتصال زندهٔ پذیرش به گفتگوی عمومی (پاسخ‌دهی اپراتور)

Revision ID: 0034_public_chat_operator
Revises: 0033_public_chat_monitor
Create Date: 2026-10-29

- نقش جدید پیام: ``operator`` (اپراتور پذیرش/مدیر از پنل) در کنار
  ``user`` (بازدیدکننده) و ``assistant`` (دستیار قاعده‌محور)؛
- ستون ``sender_name``: نام نمایشی فرستنده برای پیام اپراتور (نام کاربری
  پنل)؛ برای پیام‌های user/assistant خالی می‌ماند؛
- دسترسی جدید ``chat.public_reply`` (بخش «گفتگو») — پاسخ‌دهی زندهٔ پذیرش
  در گفتگوی عمومی؛ پیش‌فرض: RECEPTION / ORG_MANAGER / SYSTEM_ADMIN.
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_public_chat_operator"
down_revision = "0033_public_chat_monitor"
branch_labels = None
depends_on = None

PERM_CODE = "chat.public_reply"
PERM_SECTION = "گفتگو"
PERM_TITLE = "پاسخ‌دهی زندهٔ پذیرش در گفتگوی عمومی"
PERM_SORT = 4
DEFAULT_ROLES = ("ORG_MANAGER", "RECEPTION", "SYSTEM_ADMIN")


def upgrade() -> None:
    # --- نقش پیام اپراتور: بازسازی constraint ---
    op.drop_constraint("ck_public_chat_messages_role", "public_chat_messages", type_="check")
    op.create_check_constraint(
        "ck_public_chat_messages_role",
        "public_chat_messages",
        "role IN ('user','assistant','operator')",
    )

    # --- نام نمایشی فرستنده (اپراتور) ---
    op.add_column(
        "public_chat_messages",
        sa.Column("sender_name", sa.String(120), nullable=True),
    )

    # --- seed دسترسی پاسخ‌دهی (idempotent) ---
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
    op.drop_column("public_chat_messages", "sender_name")
    op.drop_constraint("ck_public_chat_messages_role", "public_chat_messages", type_="check")
    op.create_check_constraint(
        "ck_public_chat_messages_role",
        "public_chat_messages",
        "role IN ('user','assistant')",
    )
