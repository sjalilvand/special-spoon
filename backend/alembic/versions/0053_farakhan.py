"""فاز ۸۸ — فراخوان همکاری: پورت فرم مرجع Samaneh-IT-rose/farakhan در سامانه.

سه جدول جدید (idempotent — همه با بررسی وجود ساخته می‌شوند):
- ``farakhan_locations``: استان‌ها و شهرستان‌های ایران (seed از
  ``app.data.farakhan_locations`` — ۳۱ استان، ۴۸۴ شهرستان؛ منبع مرکز آمار)
- ``farakhan_submissions``: ثبت‌نام‌های فراخوان همکاری (کد پیگیری یکتا)
- ``farakhan_files``: پیوند فایل‌های آپلودی به ثبت‌نام (محتوا در files/objstore)

+ seed سطح دسترسی منوی «فراخوان همکاری» در ماتریس منوها (idempotent،
  ON CONFLICT DO NOTHING — مثل الگوی مایگریشن 0046).
"""

from alembic import op
import sqlalchemy as sa

revision = "0053_farakhan"
down_revision = "0052_org_flow_tokens"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    insp = sa.inspect(bind)
    return insp.has_table(table)


def upgrade() -> None:
    bind = op.get_bind()

    # ── farakhan_locations ──
    if not _has_table(bind, "farakhan_locations"):
        op.create_table(
            "farakhan_locations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("province_name", sa.String(length=80), nullable=False, index=True),
            sa.Column("county_name", sa.String(length=80), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    # seed استان/شهرستان‌ها — idempotent (فقط شمارش ردیف‌های غایب درج می‌شود)
    from app.data.farakhan_locations import FARAKHAN_LOCATIONS

    locations_tbl = sa.table(
        "farakhan_locations",
        sa.column("province_name", sa.String),
        sa.column("county_name", sa.String),
    )
    existing = {
        (row[0], row[1])
        for row in bind.execute(
            sa.text("SELECT province_name, county_name FROM farakhan_locations")
        ).fetchall()
    }
    rows: list[dict] = []
    for province, counties in FARAKHAN_LOCATIONS:
        if (province, None) not in existing:
            rows.append({"province_name": province, "county_name": None})
        for county in counties:
            if (province, county) not in existing:
                rows.append({"province_name": province, "county_name": county})
    if rows:
        op.bulk_insert(locations_tbl, rows)

    # ── farakhan_submissions ──
    if not _has_table(bind, "farakhan_submissions"):
        pg_uuid = sa.dialects.postgresql.UUID(as_uuid=True)
        op.create_table(
            "farakhan_submissions",
            sa.Column("id", pg_uuid, primary_key=True),
            sa.Column("tracking_code", sa.String(length=32), nullable=False),
            sa.Column("first_name", sa.String(length=100), nullable=False),
            sa.Column("last_name", sa.String(length=100), nullable=False),
            sa.Column("national_code", sa.String(length=10), nullable=False),
            sa.Column("gender", sa.String(length=10), nullable=False),
            sa.Column("birth_date_jalali", sa.String(length=10), nullable=False),
            sa.Column("birth_date_gregorian", sa.String(length=10), nullable=True),
            sa.Column("military_status", sa.String(length=40), nullable=True),
            sa.Column("education_degree", sa.String(length=30), nullable=False),
            sa.Column("education_field", sa.String(length=120), nullable=False),
            sa.Column("license_status", sa.String(length=20), nullable=False),
            sa.Column("license_number", sa.String(length=50), nullable=True),
            sa.Column("license_description", sa.Text(), nullable=True),
            sa.Column("center_ownership", sa.String(length=20), nullable=False),
            sa.Column("province_name", sa.String(length=80), nullable=False),
            sa.Column("county_name", sa.String(length=80), nullable=False),
            sa.Column("phone", sa.String(length=15), nullable=False),
            sa.Column("mobile_number", sa.String(length=15), nullable=True),
            sa.Column("postal_code", sa.String(length=10), nullable=True),
            sa.Column("address", sa.String(length=500), nullable=True),
            sa.Column("individual_rooms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("group_rooms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("child_rooms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("counselors_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("has_waiting_space", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("accepts_company_pattern", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("has_accessibility", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
            sa.Column("review_note", sa.String(length=500), nullable=True),
            sa.Column("reviewed_by", pg_uuid, nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("submit_ip", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "status IN ('new','reviewed','accepted','rejected')",
                name="ck_farakhan_status",
            ),
            sa.CheckConstraint("gender IN ('male','female')", name="ck_farakhan_gender"),
            sa.CheckConstraint(
                "education_degree IN ('bachelor','master','phd')",
                name="ck_farakhan_degree",
            ),
            sa.CheckConstraint(
                "license_status IN ('valid','in_progress','none')",
                name="ck_farakhan_license_status",
            ),
            sa.CheckConstraint(
                "center_ownership IN ('owned','rented','other')",
                name="ck_farakhan_ownership",
            ),
            sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_farakhan_submissions_tracking", "farakhan_submissions", ["tracking_code"], unique=True)
        op.create_index("ix_farakhan_submissions_national", "farakhan_submissions", ["national_code"])
        op.create_index("ix_farakhan_submissions_status", "farakhan_submissions", ["status"])

    # ── farakhan_files ──
    if not _has_table(bind, "farakhan_files"):
        pg_uuid = sa.dialects.postgresql.UUID(as_uuid=True)
        op.create_table(
            "farakhan_files",
            sa.Column("id", pg_uuid, primary_key=True),
            sa.Column("submission_id", pg_uuid, nullable=False),
            sa.Column("file_id", pg_uuid, nullable=False),
            sa.Column("field_key", sa.String(length=40), nullable=False),
            sa.Column("original_name", sa.String(length=255), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["submission_id"], ["farakhan_submissions.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="RESTRICT"),
        )
        op.create_index("ix_farakhan_files_submission", "farakhan_files", ["submission_id"])
        op.create_index("ix_farakhan_files_file", "farakhan_files", ["file_id"])

    # ── seed دسترسی منوی «فراخوان همکاری» (الگوی 0046) ──
    from app.core.menu_registry import MENU_SEED

    for role, key, level in MENU_SEED:
        if key != "farakhan":
            continue
        bind.execute(
            sa.text(
                "INSERT INTO role_menu_permissions (role_code, menu_key, level) "
                "VALUES (:r, :m, :l) ON CONFLICT (role_code, menu_key) DO NOTHING"
            ),
            {"r": role, "m": key, "l": level},
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "farakhan_files"):
        op.drop_table("farakhan_files")
    if _has_table(bind, "farakhan_submissions"):
        op.drop_table("farakhan_submissions")
    if _has_table(bind, "farakhan_locations"):
        op.drop_table("farakhan_locations")
    bind.execute(
        sa.text("DELETE FROM role_menu_permissions WHERE menu_key = 'farakhan'")
    )
