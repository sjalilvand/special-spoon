"""phase 34 - B33-B36 + B21-plus: learning (content/course/exam/certificate) + org statements

Revision ID: 0022_phase34_learning
Revises: 0021_phase33_topics_orgs
Create Date: 2026-10-19 14:00:00

B33: محتوا روی دسته B32
B34: دوره + جلسات + ثبت‌نام (سفارش kind='course')
B35: آزمون + سؤال + تلاش (نمره‌دهی سمت سرور)
B36: گواهی با شماره جلالی یکتا
B21-plus: صورتحساب دوره‌ای سازمان + تسویه با سند ۱۱۰۴ (source_type='org_statement')
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022_phase34_learning"
down_revision = "0021_phase33_topics_orgs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- B33: محتوا ---
    op.create_table(
        "contents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_contents_status"),
    )
    op.create_index("ix_contents_topic", "contents", ["topic_id"])
    op.create_index("ix_contents_status", "contents", ["status"])

    # --- B34: دوره ---
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("price_amount", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_courses_status"),
        sa.CheckConstraint("price_amount >= 0", name="ck_courses_price_nonneg"),
        sa.CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_courses_capacity_positive"),
    )
    op.create_index("ix_courses_topic", "courses", ["topic_id"])
    op.create_index("ix_courses_status", "courses", ["status"])

    op.create_table(
        "course_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("session_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default=sa.text("90")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("duration_minutes > 0", name="ck_course_sessions_duration"),
        sa.CheckConstraint("sort_order >= 0", name="ck_course_sessions_sort_nonneg"),
    )
    op.create_index("ix_course_sessions_course", "course_sessions", ["course_id"])

    op.create_table(
        "course_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','active','completed','cancelled')",
            name="ck_course_enrollments_status",
        ),
        sa.UniqueConstraint("course_id", "user_id", name="uq_course_enrollment"),
    )
    op.create_index("ix_course_enrollments_course", "course_enrollments", ["course_id"])
    op.create_index("ix_course_enrollments_user", "course_enrollments", ["user_id"])

    # --- B35: آزمون ---
    op.create_table(
        "exams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("pass_percent", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("price_amount", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_exams_status"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_exams_duration_positive"),
        sa.CheckConstraint("pass_percent >= 0 AND pass_percent <= 100", name="ck_exams_pass_range"),
        sa.CheckConstraint("price_amount >= 0", name="ck_exams_price_nonneg"),
        sa.CheckConstraint("max_attempts > 0", name="ck_exams_attempts_positive"),
    )
    op.create_index("ix_exams_topic", "exams", ["topic_id"])
    op.create_index("ix_exams_course", "exams", ["course_id"])
    op.create_index("ix_exams_status", "exams", ["status"])

    op.create_table(
        "exam_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("exams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prompt", sa.String(1000), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("points > 0", name="ck_exam_questions_points_positive"),
        sa.CheckConstraint("sort_order >= 0", name="ck_exam_questions_sort_nonneg"),
    )
    op.create_index("ix_exam_questions_exam", "exam_questions", ["exam_id"])

    op.create_table(
        "exam_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("exams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("score_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("answers", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_progress','passed','failed')", name="ck_exam_attempts_status"
        ),
        sa.CheckConstraint(
            "score_percent IS NULL OR (score_percent >= 0 AND score_percent <= 100)",
            name="ck_exam_attempts_score_range",
        ),
    )
    op.create_index("ix_exam_attempts_exam", "exam_attempts", ["exam_id"])
    op.create_index("ix_exam_attempts_user", "exam_attempts", ["user_id"])

    # --- B36: گواهی ---
    op.create_table(
        "certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("certificate_number", sa.String(40), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("exams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("exam_attempts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("holder_name", sa.String(200), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(300), nullable=True),
        sa.Column("issued_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_certificates_user", "certificates", ["user_id"])
    op.create_index("ix_certificates_course", "certificates", ["course_id"])
    op.create_index("ix_certificates_exam", "certificates", ["exam_id"])

    # --- B21-plus: صورتحساب دوره‌ای سازمان ---
    op.create_table(
        "org_statements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("statement_no", sa.String(40), nullable=False, unique=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="issued"),
        sa.Column("orders_count", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("org_share_total", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("applicant_share_total", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("issued_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("settled_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('issued','settled')", name="ck_org_statements_status"),
        sa.CheckConstraint("period_to >= period_from", name="ck_org_statements_period"),
        sa.CheckConstraint("total_amount >= 0 AND org_share_total >= 0", name="ck_org_statements_amounts"),
    )
    op.create_index("ix_org_statements_org", "org_statements", ["organization_id"])
    op.create_index("ix_org_statements_status", "org_statements", ["status"])

    op.create_table(
        "org_statement_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("org_statements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("order_number", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("org_share_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("applicant_share_amount", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("coverage_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_org_statement_items_statement", "org_statement_items", ["statement_id"])

    # --- سفارش: kind جدید + پیوند دوره/آزمون ---
    op.add_column(
        "orders",
        sa.Column("course_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("courses.id", ondelete="RESTRICT"), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("exam_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("exams.id", ondelete="RESTRICT"), nullable=True),
    )
    op.drop_constraint("ck_orders_kind", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_kind", "orders", "kind IN ('service','topup','course','exam')"
    )
    # --- سند: رویداد جدید تسویه صورتحساب سازمان ---
    op.drop_constraint("ck_journal_source_type", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_source_type",
        "journal_entries",
        "source_type IN ('payment','refund','wallet_adjustment','settlement','org_statement','manual','reversal')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_journal_source_type", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_source_type",
        "journal_entries",
        "source_type IN ('payment','refund','wallet_adjustment','settlement','manual','reversal')",
    )
    op.drop_constraint("ck_orders_kind", "orders", type_="check")
    op.create_check_constraint("ck_orders_kind", "orders", "kind IN ('service','topup')")
    op.drop_column("orders", "exam_id")
    op.drop_column("orders", "course_id")
    op.drop_table("org_statement_items")
    op.drop_table("org_statements")
    op.drop_table("certificates")
    op.drop_table("exam_attempts")
    op.drop_table("exam_questions")
    op.drop_table("exams")
    op.drop_table("course_enrollments")
    op.drop_table("course_sessions")
    op.drop_table("courses")
    op.drop_table("contents")
