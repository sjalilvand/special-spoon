"""phase 49 - processes: versioned organizational processes + request monitoring (B41/B42)

Revision ID: 0028_phase49_processes
Revises: 0027_phase47_psych_subscale
Create Date: 2026-10-21 10:00:00

فاز ۴۹: تعریف فرایند جدید + ثبت نسخه‌های قبلی + مانیتورینگ وضعیت درخواست
در فرایند. چهار جدول: process_definitions / process_versions (XML استاندارد
BPMN 2.0 با شماره نسخه) / process_instances (نمونه اجرا روی یک موضوع:
درخواست، پرونده، متقاضی یا دستی) / process_instance_events (خط‌زمانی گام‌ها).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0028_phase49_processes"
down_revision = "0027_phase47_psych_subscale"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "process_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(code) >= 2", name="ck_process_definitions_code"),
    )
    op.create_table(
        "process_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("definition_id", UUID(as_uuid=True),
                  sa.ForeignKey("process_definitions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("bpmn_xml", sa.Text(), nullable=False),
        sa.Column("changelog", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("definition_id", "version_number", name="uq_process_version_number"),
        sa.CheckConstraint("status IN ('draft','published','archived')", name="ck_process_versions_status"),
    )
    op.create_index("ix_process_versions_definition", "process_versions", ["definition_id"])
    op.create_table(
        "process_instances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("definition_id", UUID(as_uuid=True),
                  sa.ForeignKey("process_definitions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_id", UUID(as_uuid=True),
                  sa.ForeignKey("process_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subject_type", sa.String(50), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("subject_label", sa.String(200), nullable=True),
        sa.Column("subject_meta", JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("current_element_id", sa.String(100), nullable=True),
        sa.Column("current_element_name", sa.String(200), nullable=True),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("started_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','suspended','completed','cancelled')",
            name="ck_process_instances_status",
        ),
    )
    op.create_index("ix_process_instances_subject", "process_instances", ["subject_type", "subject_id"])
    op.create_index("ix_process_instances_definition", "process_instances", ["definition_id"])
    op.create_index("ix_process_instances_status", "process_instances", ["status"])
    op.create_table(
        "process_instance_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("instance_id", UUID(as_uuid=True),
                  sa.ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("element_id", sa.String(100), nullable=True),
        sa.Column("element_name", sa.String(200), nullable=False),
        sa.Column("element_type", sa.String(60), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="done"),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('done','active','pending','skipped','failed')",
            name="ck_process_instance_events_status",
        ),
    )
    op.create_index("ix_process_instance_events_instance", "process_instance_events", ["instance_id"])


def downgrade() -> None:
    op.drop_table("process_instance_events")
    op.drop_table("process_instances")
    op.drop_table("process_versions")
    op.drop_table("process_definitions")
