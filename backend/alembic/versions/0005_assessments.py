"""phase 5 - form_versions, assessments, review_actions (بند ۶.۲ و ۷ سند)

Revision ID: 0005_assessments
Revises: 0004_cases
Create Date: 2024-12-05 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_assessments"
down_revision = "0004_cases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("form_code", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("form_code", "version", name="uq_form_versions_code_version"),
    )

    op.create_table(
        "assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("form_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("form_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("previous_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("finalized_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','finalized','pending_review','returned','approved')", name="ck_assessments_status"),
    )
    op.create_index("ix_assessments_case_id", "assessments", ["case_id"])
    op.create_index("ix_assessments_status", "assessments", ["status"])

    op.create_table(
        "review_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("decision IN ('approved','returned')", name="ck_review_actions_decision"),
    )
    op.create_index("ix_review_actions_assessment_id", "review_actions", ["assessment_id"])


def downgrade() -> None:
    op.drop_index("ix_review_actions_assessment_id", table_name="review_actions")
    op.drop_table("review_actions")
    op.drop_index("ix_assessments_status", table_name="assessments")
    op.drop_index("ix_assessments_case_id", table_name="assessments")
    op.drop_table("assessments")
    op.drop_table("form_versions")
