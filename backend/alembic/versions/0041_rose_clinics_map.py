"""فاز ۶۶ - نقشهٔ کلینیک‌های شرکت رز + اتصال مشاور به شعبه.

Revision ID: 0041_rose_clinics_map
Revises: 0040_provinces_counselor_fields
Create Date: 2026-10-31

- ستون‌های جدید ``branches``: province_code (کلید خارجی به provinces.code)،
  manager_name / manager_phone (مدیر کلینیک)، exec_name / exec_phone
  (مسئول اجرایی) و map_url (لینک مسیریابی نشان) — مشخصات استخراج‌شده از
  صفحهٔ رسمی کلینیک‌های شرکت رز؛
- ستون جدید ``counselors.branch_id``: اتصال مشاور به شعبهٔ استان خود برای
  نمایش «مشاوران این کلینیک» روی نقشهٔ عمومی سایت.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0041_rose_clinics_map"
down_revision = "0040_provinces_counselor_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("branches", sa.Column("manager_name", sa.String(120), nullable=True))
    op.add_column("branches", sa.Column("manager_phone", sa.String(30), nullable=True))
    op.add_column("branches", sa.Column("exec_name", sa.String(120), nullable=True))
    op.add_column("branches", sa.Column("exec_phone", sa.String(30), nullable=True))
    op.add_column("branches", sa.Column("map_url", sa.String(300), nullable=True))
    op.add_column("branches", sa.Column("province_code", sa.String(2), nullable=True))
    op.create_index("ix_branches_province_code", "branches", ["province_code"])
    op.create_foreign_key(
        "fk_branches_province_code", "branches", "provinces",
        ["province_code"], ["code"], ondelete="SET NULL",
    )

    op.add_column(
        "counselors",
        sa.Column("branch_id", pg.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_counselors_branch_id", "counselors", ["branch_id"])
    op.create_foreign_key(
        "fk_counselors_branch_id", "counselors", "branches",
        ["branch_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_counselors_branch_id", "counselors", type_="foreignkey")
    op.drop_index("ix_counselors_branch_id", table_name="counselors")
    op.drop_column("counselors", "branch_id")
    op.drop_constraint("fk_branches_province_code", "branches", type_="foreignkey")
    op.drop_index("ix_branches_province_code", table_name="branches")
    op.drop_column("branches", "province_code")
    op.drop_column("branches", "map_url")
    op.drop_column("branches", "exec_phone")
    op.drop_column("branches", "exec_name")
    op.drop_column("branches", "manager_phone")
    op.drop_column("branches", "manager_name")
