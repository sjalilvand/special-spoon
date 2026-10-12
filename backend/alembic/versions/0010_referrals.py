"""phase 13 - referrals + consultation request conversion links

Revision ID: 0010_referrals
Revises: 0009_coop_clinical
Create Date: 2024-12-10 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_referrals"
down_revision = "0009_coop_clinical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "referrals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="initiated"),
        sa.Column("to_counselor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("counselors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("to_service_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("to_center_name", sa.String(300), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("referral_date", sa.Date(), nullable=False),
        sa.Column("outcome_date", sa.Date(), nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("handled_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("direction IN ('internal','cross_center','external')", name="ck_referrals_direction"),
        sa.CheckConstraint("status IN ('initiated','accepted','completed','rejected','cancelled')", name="ck_referrals_status"),
    )
    op.create_index("ix_referrals_case_id", "referrals", ["case_id"])
    op.create_index("ix_referrals_status", "referrals", ["status"])

    op.add_column(
        "consultation_requests",
        sa.Column("applicant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applicants.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "consultation_requests",
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consultation_requests", "case_id")
    op.drop_column("consultation_requests", "applicant_id")
    op.drop_index("ix_referrals_status", table_name="referrals")
    op.drop_index("ix_referrals_case_id", table_name="referrals")
    op.drop_table("referrals")
