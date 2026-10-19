"""phase 28 - B05/B06/B07: counselor credentials, services & versioned tariffs

Revision ID: 0017_phase28_services_tariffs
Revises: 0016_phase27_email_dpo
Create Date: 2024-12-20 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_phase28_services_tariffs"
down_revision = "0016_phase27_email_dpo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- B05: مدارک و صلاحیت مشاوران ---
    op.create_table(
        "counselor_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("counselor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("counselors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False, server_default="license"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("license_number", sa.String(100), nullable=True),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("file_path", sa.String(255), nullable=True),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("verification_status IN ('pending','approved','rejected')",
                           name="ck_counselor_credentials_status"),
        sa.CheckConstraint("expires_at IS NULL OR issued_at IS NULL OR expires_at >= issued_at",
                           name="ck_counselor_credentials_range"),
    )
    op.create_index("ix_counselor_credentials_counselor", "counselor_credentials", ["counselor_id"])
    op.create_index("ix_counselor_credentials_status", "counselor_credentials", ["verification_status"])

    # --- B06: تخصص‌ها و خدمات ---
    op.create_table(
        "specialties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("specialty_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("specialties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(50), nullable=True, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("session_type", sa.String(20), nullable=False, server_default="in_person"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("duration_minutes > 0", name="ck_services_duration_positive"),
        sa.CheckConstraint("session_type IN ('in_person','online','phone')",
                           name="ck_services_session_type"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_services_status"),
    )
    op.create_index("ix_services_specialty_id", "services", ["specialty_id"])

    # --- B07: تعرفه نسخه‌دار ---
    op.create_table(
        "tariff_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_tariff_amount_nonneg"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_tariff_range"),
    )
    op.create_index("ix_tariff_versions_service_from", "tariff_versions", ["service_id", "valid_from"])

    # --- B06/B07: ستون‌های خدمت و snapshot قیمت روی نوبت‌ها ---
    op.add_column("appointments",
                  sa.Column("service_id", postgresql.UUID(as_uuid=True),
                            sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("appointments",
                  sa.Column("tariff_version_id", postgresql.UUID(as_uuid=True),
                            sa.ForeignKey("tariff_versions.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("appointments", sa.Column("price_amount", sa.Numeric(16, 2), nullable=True))
    op.add_column("appointments", sa.Column("price_currency", sa.String(3), nullable=True))
    op.create_index("ix_appointments_service_id", "appointments", ["service_id"])

    # --- B06: خدمت انتخابی درخواست مشاوره عمومی ---
    op.add_column("consultation_requests",
                  sa.Column("service_id", postgresql.UUID(as_uuid=True),
                            sa.ForeignKey("services.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("consultation_requests", "service_id")
    op.drop_index("ix_appointments_service_id", table_name="appointments")
    op.drop_column("appointments", "price_currency")
    op.drop_column("appointments", "price_amount")
    op.drop_column("appointments", "tariff_version_id")
    op.drop_column("appointments", "service_id")
    op.drop_index("ix_tariff_versions_service_from", table_name="tariff_versions")
    op.drop_table("tariff_versions")
    op.drop_index("ix_services_specialty_id", table_name="services")
    op.drop_table("services")
    op.drop_table("specialties")
    op.drop_index("ix_counselor_credentials_status", table_name="counselor_credentials")
    op.drop_index("ix_counselor_credentials_counselor", table_name="counselor_credentials")
    op.drop_table("counselor_credentials")
