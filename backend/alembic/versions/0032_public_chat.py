"""فاز ۵۴ - چت آنلاین عمومی سایت: نشست‌های بازدیدکننده + پیام‌ها + بازخورد

Revision ID: 0032_public_chat
Revises: 0031_agent
Create Date: 2026-10-29

- public_chat_sessions: هویت لایه‌لایه — user_id (لاگین) / token مرورگر +
  IP (ناشناس) + visitor_name (نام معرفی‌شدهٔ اختیاری)؛ rating/comment =
  نظر کاربر دربارهٔ خودِ گفتگو؛
- public_chat_messages: پیام user/assistant + کارت اقدام (actions) و
  پاسخ پیشنهادی (quick_replies) برای هدایت بازدیدکننده به صفحهٔ مرتبط.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0032_public_chat"
down_revision = "0031_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visitor_name", sa.String(100), nullable=True),
        sa.Column("ip", sa.String(64), nullable=False, server_default="unknown"),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("first_page", sa.String(200), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="open"),
        sa.Column("rating", sa.SmallInteger(), nullable=True),
        sa.Column("rating_comment", sa.String(500), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("rating IS NULL OR (rating BETWEEN 1 AND 5)", name="ck_public_chat_rating"),
    )
    op.create_index("ix_public_chat_sessions_user", "public_chat_sessions", ["user_id"])
    op.create_index("ix_public_chat_sessions_ip", "public_chat_sessions", ["ip"])
    op.create_index("ix_public_chat_sessions_updated", "public_chat_sessions", ["updated_at"])
    op.create_table(
        "public_chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("public_chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("actions", JSONB(), nullable=True),
        sa.Column("quick_replies", JSONB(), nullable=True),
        sa.Column("intent", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_public_chat_messages_role"),
    )
    op.create_index("ix_public_chat_messages_session", "public_chat_messages", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_public_chat_messages_session", table_name="public_chat_messages")
    op.drop_table("public_chat_messages")
    op.drop_index("ix_public_chat_sessions_updated", table_name="public_chat_sessions")
    op.drop_index("ix_public_chat_sessions_ip", table_name="public_chat_sessions")
    op.drop_index("ix_public_chat_sessions_user", table_name="public_chat_sessions")
    op.drop_table("public_chat_sessions")
