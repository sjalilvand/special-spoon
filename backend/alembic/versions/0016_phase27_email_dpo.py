"""phase 27 - email outbox (B12+) + DPO auditor role (B41+)

Revision ID: 0016_phase27_email_dpo
Revises: 0015_phase26_holds_otp
Create Date: 2024-12-15 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_phase27_email_dpo"
down_revision = "0015_phase26_holds_otp"
branch_labels = None
depends_on = None

DPO_ROLE = ("DPO", "حسابرس حفاظت داده (DPO)")


def upgrade() -> None:
    # --- B12+: صف خروجی ایمیل اعلان‌ها ---
    op.create_table(
        "email_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','sent','failed','disabled')",
                           name="ck_email_outbox_status"),
    )
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"])
    op.create_index("ix_email_outbox_created_at", "email_outbox", ["created_at"])
    op.create_index("ix_email_outbox_notification_id", "email_outbox", ["notification_id"])

    # --- B41+: نقش حسابرس حفاظت داده (DPO) ---
    roles_table = sa.table("roles", sa.column("code", sa.String), sa.column("title", sa.String))
    op.execute(
        postgresql.insert(roles_table)
        .values(code=DPO_ROLE[0], title=DPO_ROLE[1])
        .on_conflict_do_nothing(constraint="roles_pkey")
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_notification_id", table_name="email_outbox")
    op.drop_index("ix_email_outbox_created_at", table_name="email_outbox")
    op.drop_index("ix_email_outbox_status", table_name="email_outbox")
    op.drop_table("email_outbox")
    op.execute("DELETE FROM roles WHERE code = 'DPO'")
