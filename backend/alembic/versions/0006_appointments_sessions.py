"""phase 6 - appointments, sessions, session_note_revisions (بند ۶.۴ و ۹.۱ سند)

Revision ID: 0006_schedule
Revises: 0005_assessments
Create Date: 2024-12-06 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_schedule"
down_revision = "0005_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("counselor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("counselors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('scheduled','done','cancelled','no_show')", name="ck_appointments_status"),
    )
    op.create_index("ix_appointments_case_id", "appointments", ["case_id"])
    op.create_index("ix_appointments_counselor_id", "appointments", ["counselor_id"])
    op.create_index("ix_appointments_scheduled_at", "appointments", ["scheduled_at"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("counselor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("counselors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_case_id", "sessions", ["case_id"])

    op.create_table(
        "session_note_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','final')", name="ck_session_note_status"),
        sa.UniqueConstraint("session_id", "version", name="uq_session_note_version"),
    )
    op.create_index("ix_session_note_revisions_session_id", "session_note_revisions", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_session_note_revisions_session_id", table_name="session_note_revisions")
    op.drop_table("session_note_revisions")
    op.drop_index("ix_sessions_case_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_appointments_scheduled_at", table_name="appointments")
    op.drop_index("ix_appointments_counselor_id", table_name="appointments")
    op.drop_index("ix_appointments_case_id", table_name="appointments")
    op.drop_table("appointments")
