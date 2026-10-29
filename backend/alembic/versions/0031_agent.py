"""فاز ۵۳ - عامل هوشمند: نشست‌های گفتگو و لاگ پیام‌ها (الگوی Session Log سند dsh)

Revision ID: 0031_agent
Revises: 0030_rbac_chat
Create Date: 2026-10-29

- agent_sessions: نشست گفتگو با عامل (عنوان خودکار از اولین پیام)؛
- agent_messages: لاگ append-only با نقش user/assistant/tool؛ برای پیام‌های
  tool، نام/آرگومان/خلاصهٔ نتیجه ذخیره می‌شود (بدون کلید سرویس و بدون دادهٔ
  بالینی — همان مرز امنیتی فاز ۳۵)؛ حذف نشست = حذف آبشاری پیام‌ها.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0031_agent"
down_revision = "0030_rbac_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False, server_default="گفتگوی جدید"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_sessions_updated", "agent_sessions", ["updated_at"])
    op.create_table(
        "agent_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("tool_name", sa.String(60), nullable=True),
        sa.Column("tool_args", JSONB(), nullable=True),
        sa.Column("tool_result", JSONB(), nullable=True),
        sa.Column("provider", sa.String(30), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user','assistant','tool')", name="ck_agent_messages_role"),
    )
    op.create_index("ix_agent_messages_session", "agent_messages", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_messages_session", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_agent_sessions_updated", table_name="agent_sessions")
    op.drop_table("agent_sessions")
