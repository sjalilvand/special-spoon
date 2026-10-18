"""phase 25 - B12/B38 notifications + B41 consent versions + B39 secure files

Revision ID: 0014_phase25_governance
Revises: 0013_public_booking
Create Date: 2026-10-19 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_phase25_governance"
down_revision = "0013_public_booking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- B12/B38: مرکز اعلان ----------
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(30), nullable=False, server_default="system"),
        sa.Column("event_code", sa.String(60), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.String(500), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("entity_type", sa.String(60), nullable=True),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("severity IN ('info','warning','critical')", name="ck_notifications_severity"),
        sa.CheckConstraint("read_at IS NULL OR read_at >= created_at", name="ck_notifications_read_time"),
    )
    op.create_index("ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])
    op.create_index("ix_notifications_category", "notifications", ["category"])
    op.create_index("ix_notifications_event_code", "notifications", ["event_code"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    # ---------- B41: نسخه‌های متن رضایت‌نامه ----------
    op.create_table(
        "consent_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("kind", sa.String(30), nullable=False, server_default="treatment"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('treatment','psych_test','data_share','marketing')",
            name="ck_consent_versions_kind",
        ),
        sa.UniqueConstraint("kind", "version", name="uq_consent_versions_kind_version"),
    )

    # توسعه جدول consents موجود (B41)
    op.add_column("consents", sa.Column("kind", sa.String(30), nullable=False, server_default="treatment"))
    op.add_column("consents", sa.Column(
        "consent_version_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("consent_versions.id", ondelete="SET NULL"), nullable=True))
    op.add_column("consents", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("consents", sa.Column(
        "revoked_by", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("consents", sa.Column("revoke_reason", sa.String(500), nullable=True))
    op.create_check_constraint("ck_consents_kind", "consents",
                               "kind IN ('treatment','psych_test','data_share','marketing')")

    # ---------- B39: فایل امن ----------
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("context", sa.String(40), nullable=False, server_default="case_document"),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(120), nullable=False),
        sa.Column("sensitivity", sa.String(20), nullable=False, server_default="confidential"),
        sa.Column("scan_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "scan_status IN ('pending','clean','quarantined','failed')",
            name="ck_files_scan_status",
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_files_size"),
        sa.UniqueConstraint("storage_key", name="uq_files_storage_key"),
    )
    op.create_index("ix_files_case_id", "files", ["case_id"])
    op.create_index("ix_files_scan_status", "files", ["scan_status"])
    op.create_index("ix_files_context", "files", ["context"])

    op.create_table(
        "file_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scanner", sa.String(60), nullable=False, server_default="builtin-stub"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("detail", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_file_scans_file_id", "file_scans", ["file_id"])


def downgrade() -> None:
    op.drop_table("file_scans")
    op.drop_index("ix_files_context", table_name="files")
    op.drop_index("ix_files_scan_status", table_name="files")
    op.drop_index("ix_files_case_id", table_name="files")
    op.drop_table("files")
    op.drop_constraint("ck_consents_kind", "consents", type_="check")
    op.drop_column("consents", "revoke_reason")
    op.drop_column("consents", "revoked_by")
    op.drop_column("consents", "revoked_at")
    op.drop_column("consents", "consent_version_id")
    op.drop_column("consents", "kind")
    op.drop_table("consent_versions")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_event_code", table_name="notifications")
    op.drop_index("ix_notifications_category", table_name="notifications")
    op.drop_index("ix_notifications_recipient_user_id", table_name="notifications")
    op.drop_table("notifications")
