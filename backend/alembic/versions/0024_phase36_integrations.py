"""phase 36 - B28: external integrations (pluggable SMS outbox)

Revision ID: 0024_phase36_integrations
Revises: 0023_phase35_support_psych_ai
Create Date: 2026-10-19 18:00:00

B28: صف خروجی پیامک (آداپتور پلاگین‌پذیر log/kavenegar/smsir — همان الگوی
D02/D03/D07)؛ ارسال غیرهمگام با صف DB تا پیش از صف کار اختصاصی (ADR-02).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024_phase36_integrations"
down_revision = "0023_phase35_support_psych_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient_mobile", sa.String(20), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False, server_default="notification"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False, server_default="log"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','sent','failed','disabled')",
                           name="ck_sms_outbox_status"),
        sa.CheckConstraint("provider IN ('log','kavenegar','smsir')",
                           name="ck_sms_outbox_provider"),
    )
    op.create_index("ix_sms_outbox_status", "sms_outbox", ["status"])
    op.create_index("ix_sms_outbox_created", "sms_outbox", ["created_at"])
    op.create_index("ix_sms_outbox_notification", "sms_outbox", ["notification_id"])


def downgrade() -> None:
    op.drop_table("sms_outbox")
