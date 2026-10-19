"""phase 35 - B23 + B37 + B25-27: support (survey/complaint/ticket) + psych tests (D08) + AI (D07)

Revision ID: 0023_phase35_support_psych_ai
Revises: 0022_phase34_learning
Create Date: 2026-10-19 16:00:00

B23: نظرسنجی پس از جلسه + شکایت + تیکت پشتیبانی (نخ پیام)
B37: ابزار تست روان‌شناسی + سؤال + بازه تفسیر + اجرا (D08: انتشار فقط با تأیید ناظر علمی)
B25: لاگ تعامل دستیار هوشمند (D07)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0023_phase35_support_psych_ai"
down_revision = "0022_phase34_learning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- B23: نظرسنجی ---
    op.create_table(
        "session_surveys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("respondent_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_session_surveys_score"),
        sa.UniqueConstraint("session_id", name="uq_session_survey"),
    )
    op.create_index("ix_session_surveys_session", "session_surveys", ["session_id"])

    # --- B23: شکایت ---
    op.create_table(
        "complaints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("complainant_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("resolution_note", sa.String(2000), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('new','in_review','resolved','rejected')",
                           name="ck_complaints_status"),
    )
    op.create_index("ix_complaints_status", "complaints", ["status"])
    op.create_index("ix_complaints_user", "complaints", ["complainant_user_id"])

    # --- B23: تیکت ---
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('open','answered','closed')", name="ck_tickets_status"),
        sa.CheckConstraint("priority IN ('normal','high')", name="ck_tickets_priority"),
    )
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_user", "tickets", ["user_id"])

    op.create_table(
        "ticket_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ticket_messages_ticket", "ticket_messages", ["ticket_id"])

    # --- B37: ابزار تست روان‌شناسی ---
    op.create_table(
        "psych_tests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("review_note", sa.String(1000), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','pending_review','published','rejected')",
                           name="ck_psych_tests_status"),
    )
    op.create_index("ix_psych_tests_topic", "psych_tests", ["topic_id"])
    op.create_index("ix_psych_tests_status", "psych_tests", ["status"])

    op.create_table(
        "psych_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("psych_tests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prompt", sa.String(1000), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sort_order >= 0", name="ck_psych_questions_sort_nonneg"),
    )
    op.create_index("ix_psych_questions_test", "psych_questions", ["test_id"])

    op.create_table(
        "psych_interpretations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("psych_tests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("score_min", sa.Integer(), nullable=False),
        sa.Column("score_max", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("guidance", sa.String(1000), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("score_min <= score_max", name="ck_psych_interp_range"),
    )
    op.create_index("ix_psych_interp_test", "psych_interpretations", ["test_id"])

    op.create_table(
        "psych_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("psych_tests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("score", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("interpretation_label", sa.String(200), nullable=False),
        sa.Column("interpretation_guidance", sa.String(1000), nullable=True),
        sa.Column("answers", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("score >= 0", name="ck_psych_attempts_score_nonneg"),
    )
    op.create_index("ix_psych_attempts_test", "psych_attempts", ["test_id"])
    op.create_index("ix_psych_attempts_user", "psych_attempts", ["user_id"])

    # --- B25: لاگ دستیار (D07) ---
    op.create_table(
        "ai_chat_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(30), nullable=False, server_default="rule"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_chat_logs_user", "ai_chat_logs", ["user_id"])
    op.create_index("ix_ai_chat_logs_created", "ai_chat_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_chat_logs")
    op.drop_table("psych_attempts")
    op.drop_table("psych_interpretations")
    op.drop_table("psych_questions")
    op.drop_table("psych_tests")
    op.drop_table("ticket_messages")
    op.drop_table("tickets")
    op.drop_table("complaints")
    op.drop_table("session_surveys")
