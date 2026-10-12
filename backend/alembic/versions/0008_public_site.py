"""phase 10 - counselor photo + consultation requests (سایت عمومی)

Revision ID: 0008_public_site
Revises: 0007_recommendations
Create Date: 2024-12-08 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_public_site"
down_revision = "0007_recommendations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("counselors", sa.Column("photo_path", sa.String(255), nullable=True))
    op.create_table(
        "consultation_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("mobile", sa.String(20), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("preferred_slot", sa.String(30), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("handled_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('new','in_review','converted','archived')", name="ck_consult_status"),
    )
    op.create_index("ix_consultation_requests_status", "consultation_requests", ["status"])
    op.create_index("ix_consultation_requests_created_at", "consultation_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_consultation_requests_created_at", table_name="consultation_requests")
    op.drop_index("ix_consultation_requests_status", table_name="consultation_requests")
    op.drop_table("consultation_requests")
    op.drop_column("counselors", "photo_path")
