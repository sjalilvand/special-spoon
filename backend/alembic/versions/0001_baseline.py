"""baseline - اسکلت پایه

Revision ID: 0001_baseline
Revises:
Create Date: 2024-12-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # فاز ۱: بدون جدول. جداول بند ۱۱ سند در فازهای ۲ تا ۴ اضافه می‌شوند.
    pass


def downgrade() -> None:
    pass
