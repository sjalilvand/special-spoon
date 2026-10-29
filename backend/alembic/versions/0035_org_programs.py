"""فاز ۵۸ - پنل آزمون‌های سازمانی: برنامهٔ ارزیابی سازمان + آزمون‌های منتخب
+ اعضا + مشاوران پروژه + سوالات پرتکرار

Revision ID: 0035_org_programs
Revises: 0034_public_chat_operator
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0035_org_programs"
down_revision = "0034_public_chat_operator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_programs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("guide_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('draft','active','closed')", name="ck_org_programs_status"),
    )
    op.create_index("ix_org_programs_org", "org_programs", ["organization_id"])
    op.create_index("ix_org_programs_status", "org_programs", ["status"])

    op.create_table(
        "org_program_tests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("org_programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "test_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("psych_tests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("program_id", "test_id", name="uq_org_program_test"),
    )
    op.create_index("ix_org_program_tests_program", "org_program_tests", ["program_id"])
    op.create_index("ix_org_program_tests_test", "org_program_tests", ["test_id"])

    op.create_table(
        "org_program_members",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("org_programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("employee_code", sa.String(60), nullable=True),
        sa.Column("mobile", sa.String(30), nullable=True),
        sa.Column("unit", sa.String(120), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("program_id", "user_id", name="uq_org_program_member_user"),
    )
    op.create_index("ix_org_program_members_program", "org_program_members", ["program_id"])
    op.create_index("ix_org_program_members_user", "org_program_members", ["user_id"])

    op.create_table(
        "org_program_counselors",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("org_programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role_in_project", sa.String(80), nullable=False, server_default="مشاور"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("program_id", "user_id", name="uq_org_program_counselor"),
    )
    op.create_index("ix_org_program_counselors_program", "org_program_counselors", ["program_id"])

    op.create_table(
        "org_program_faqs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("org_programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sort_order >= 0", name="ck_org_program_faqs_sort_nonneg"),
    )
    op.create_index("ix_org_program_faqs_program", "org_program_faqs", ["program_id"])


def downgrade() -> None:
    op.drop_table("org_program_faqs")
    op.drop_table("org_program_counselors")
    op.drop_table("org_program_members")
    op.drop_table("org_program_tests")
    op.drop_table("org_programs")
