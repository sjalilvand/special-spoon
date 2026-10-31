"""فاز ۶۵ - ستون کلینک محل خدمت برای پروندهٔ مشاور.

Revision ID: 0041_counselor_clinic
Revises: 0041_rose_clinics_map
Create Date: 2026-10-31

هم‌راستا با «انتقال مشخصات کامل کاربر» در ورود یکپارچه (SSO) رز هاب:
توکن رز هاب حالا علاوه بر کد ملی و موبایل، ``province``/``provinceCode``
و ``clinic`` را هم حمل می‌کند. ستون ``counselors.clinic`` مقدار claim
``clinic`` (کلینکی که مشاور در آن خدمت می‌کند) را نگه می‌دارد.
"""
import sqlalchemy as sa
from alembic import op

revision = "0042_counselor_clinic"
down_revision = "0041_rose_clinics_map"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("counselors", sa.Column("clinic", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("counselors", "clinic")
