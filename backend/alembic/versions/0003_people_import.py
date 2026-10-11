"""phase 3 - org units, service locations, counselors, applicants, imports (بند ۱۱ سند)

Revision ID: 0003_people
Revises: 0002_auth
Create Date: 2024-12-03 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_people"
down_revision = "0002_auth"
branch_labels = None
depends_on = None


def _uuid_pk():
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False)


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def upgrade() -> None:
    op.create_table(
        "organization_units",
        _uuid_pk(),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
    )
    op.create_index("ix_organization_units_code", "organization_units", ["code"], unique=True)

    op.create_table(
        "service_locations",
        _uuid_pk(),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
    )
    op.create_index("ix_service_locations_code", "service_locations", ["code"], unique=True)

    op.create_table(
        "user_scopes",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_user_scopes_user_id", "user_scopes", ["user_id"], unique=True)

    op.create_table(
        "counselors",
        _uuid_pk(),
        sa.Column("counselor_code", sa.String(50), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("national_id", sa.String(20), nullable=True),
        sa.Column("professional_title", sa.String(200), nullable=True),
        sa.Column("degree", sa.String(100), nullable=True),
        sa.Column("specialty", sa.String(100), nullable=True),
        sa.Column("license_number", sa.String(100), nullable=True),
        sa.Column("license_expiry_date", sa.Date(), nullable=True),
        sa.Column("license_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("work_mobile", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("service_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active','inactive','suspended')", name="ck_counselors_status"),
    )
    op.create_index("ix_counselors_counselor_code", "counselors", ["counselor_code"], unique=True)
    op.create_index("ix_counselors_national_id", "counselors", ["national_id"], unique=True)
    op.create_index("ix_counselors_user_id", "counselors", ["user_id"], unique=True)

    op.create_table(
        "applicants",
        _uuid_pk(),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column("employee_code", sa.String(50), nullable=True),
        sa.Column("national_id", sa.String(20), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("marital_status", sa.String(50), nullable=True),
        sa.Column("education", sa.String(100), nullable=True),
        sa.Column("occupation", sa.String(100), nullable=True),
        sa.Column("mobile", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("province_code", sa.String(50), nullable=True),
        sa.Column("county_code", sa.String(50), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("referral_source", sa.String(200), nullable=True),
        sa.Column("referral_description", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("record_source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active','inactive','archived')", name="ck_applicants_status"),
        sa.CheckConstraint("record_source IN ('manual','excel')", name="ck_applicants_source"),
    )
    op.create_index("ix_applicants_external_id", "applicants", ["external_id"], unique=True)
    op.create_index("ix_applicants_employee_code", "applicants", ["employee_code"], unique=True)
    op.create_index("ix_applicants_national_id", "applicants", ["national_id"], unique=True)
    op.create_index("ix_applicants_user_id", "applicants", ["user_id"], unique=True)

    op.create_table(
        "import_jobs",
        _uuid_pk(),
        sa.Column("import_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="preview"),
        sa.Column("importer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("import_type IN ('users','counselors','applicants')", name="ck_import_jobs_type"),
        sa.CheckConstraint("status IN ('preview','committed','failed')", name="ck_import_jobs_status"),
    )

    op.create_table(
        "import_rows",
        _uuid_pk(),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="valid"),
        sa.Column("error_text", sa.String(1000), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("existing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("will_update", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_import_rows_job_id", "import_rows", ["job_id"])


def downgrade() -> None:
    op.drop_table("import_rows")
    op.drop_table("import_jobs")
    op.drop_index("ix_applicants_user_id", table_name="applicants")
    op.drop_index("ix_applicants_national_id", table_name="applicants")
    op.drop_index("ix_applicants_employee_code", table_name="applicants")
    op.drop_index("ix_applicants_external_id", table_name="applicants")
    op.drop_table("applicants")
    op.drop_index("ix_counselors_user_id", table_name="counselors")
    op.drop_index("ix_counselors_national_id", table_name="counselors")
    op.drop_index("ix_counselors_counselor_code", table_name="counselors")
    op.drop_table("counselors")
    op.drop_index("ix_user_scopes_user_id", table_name="user_scopes")
    op.drop_table("user_scopes")
    op.drop_index("ix_service_locations_code", table_name="service_locations")
    op.drop_table("service_locations")
    op.drop_index("ix_organization_units_code", table_name="organization_units")
    op.drop_table("organization_units")
