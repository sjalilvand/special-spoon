"""phase 12 - co-counselors + independent diagnoses/treatment plans

Revision ID: 0009_coop_clinical
Revises: 0008_public_site
Create Date: 2024-12-09 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_coop_clinical"
down_revision = "0008_public_site"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_assignments",
        sa.Column("role_in_case", sa.String(20), nullable=False, server_default="primary"),
    )
    op.create_table(
        "diagnoses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("comorbid", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('confirmed','probable','under_review','none')", name="ck_diagnoses_status"),
    )
    op.create_index("ix_diagnoses_case_id", "diagnoses", ["case_id"])

    op.create_table(
        "treatment_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("approach", sa.String(50), nullable=True),
        sa.Column("approach_note", sa.String(200), nullable=True),
        sa.Column("protocol_name", sa.String(200), nullable=True),
        sa.Column("sessions_count", sa.Integer(), nullable=True),
        sa.Column("session_interval", sa.String(50), nullable=True),
        sa.Column("interventions", sa.Text(), nullable=True),
        sa.Column("external_referral", sa.String(500), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','active','archived')", name="ck_treatment_plans_status"),
    )
    op.create_index("ix_treatment_plans_case_id", "treatment_plans", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_treatment_plans_case_id", table_name="treatment_plans")
    op.drop_table("treatment_plans")
    op.drop_index("ix_diagnoses_case_id", table_name="diagnoses")
    op.drop_table("diagnoses")
    op.drop_column("case_assignments", "role_in_case")
