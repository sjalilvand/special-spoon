"""phase 20 - intake questionnaires (فرم XLSX درخواست مشاوره رز)

Revision ID: 0012_intake
Revises: 0011_followup
Create Date: 2024-12-12 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_intake"
down_revision = "0011_followup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intake_questionnaires",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("consultation_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consultation_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("filled_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','final')", name="ck_intake_status"),
        sa.UniqueConstraint("consultation_request_id", name="uq_intake_per_request"),
    )


def downgrade() -> None:
    op.drop_table("intake_questionnaires")
