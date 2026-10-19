"""phase 37 - ADR-04: object storage (pluggable local|s3)

Revision ID: 0025_phase37_object_storage
Revises: 0024_phase36_integrations
Create Date: 2026-10-19 20:00:00

ADR-04: ستون files.storage پروایدر واقعیِ ذخیره هر فایل را ثبت می‌کند تا
مهاجرت تدریجی local→S3/MinIO ممکن باشد و دانلود همیشه از همان پروایدرِ
ردیف انجام شود (فایل‌های قدیمی local می‌مانند، فایل جدید طبق config).
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_phase37_object_storage"
down_revision = "0024_phase36_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column("storage", sa.String(20), nullable=False, server_default="local"),
    )
    op.create_check_constraint(
        "ck_files_storage", "files", "storage IN ('local','s3')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_files_storage", "files", type_="check")
    op.drop_column("files", "storage")
