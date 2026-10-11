"""phase 4 - cases, case_assignments, consents + case number sequence (بند ۶ و ۷ سند)

Revision ID: 0004_cases
Revises: 0003_people
Create Date: 2024-12-04 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_cases"
down_revision = "0003_people"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # شماره پرونده با Sequence - الگوی MAX+1 ممنوع (بند ۶.۱)
    op.execute("CREATE SEQUENCE IF NOT EXISTS case_number_seq START WITH 1 INCREMENT BY 1")

    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_number", sa.String(30), nullable=False),
        sa.Column("applicant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applicants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("acceptance_date", sa.Date(), nullable=False),
        sa.Column("service_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_type", sa.String(100), nullable=True),
        sa.Column("primary_counselor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("counselors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(30), nullable=False, server_default="awaiting_assignment"),
        sa.Column("consent_status", sa.String(20), nullable=False, server_default="none"),
        sa.Column("close_reason", sa.String(500), nullable=True),
        sa.Column("close_date", sa.Date(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('new','awaiting_assignment','active','suspended','closed','archived')", name="ck_cases_status"),
        sa.CheckConstraint("consent_status IN ('none','granted','revoked')", name="ck_cases_consent_status"),
        sa.CheckConstraint("priority IN ('low','normal','high')", name="ck_cases_priority"),
    )
    op.create_index("ix_cases_case_number", "cases", ["case_number"], unique=True)
    op.create_index("ix_cases_applicant_id", "cases", ["applicant_id"])
    op.create_index("ix_cases_status", "cases", ["status"])

    op.create_table(
        "case_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("counselor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("counselors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("end_reason", sa.String(500), nullable=True),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_case_assignments_case_id", "case_assignments", ["case_id"])
    op.create_index("ix_case_assignments_counselor_id", "case_assignments", ["counselor_id"])

    op.create_table(
        "consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("consent_date", sa.Date(), nullable=False),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('granted','revoked')", name="ck_consents_status"),
        sa.CheckConstraint("version >= 1", name="ck_consents_version"),
        sa.UniqueConstraint("case_id", "version", name="uq_consents_case_version"),
    )
    op.create_index("ix_consents_case_id", "consents", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_consents_case_id", table_name="consents")
    op.drop_table("consents")
    op.drop_index("ix_case_assignments_counselor_id", table_name="case_assignments")
    op.drop_index("ix_case_assignments_case_id", table_name="case_assignments")
    op.drop_table("case_assignments")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_applicant_id", table_name="cases")
    op.drop_index("ix_cases_case_number", table_name="cases")
    op.drop_table("cases")
    op.execute("DROP SEQUENCE IF EXISTS case_number_seq")
