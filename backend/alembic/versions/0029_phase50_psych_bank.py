"""phase 50 - psych test bank expansion (راز زندگی ۲۲ آزمون + عکس سؤال + مشخصات اولیه)

Revision ID: 0029_phase50_psych_bank
Revises: 0028_phase49_processes
Create Date: 2026-10-21 10:00:00

فاز ۵۰: تکمیل بانک آزمون مطابق مرجع ۲۲ آزمون —
- psych_tests: code (کد مرجع مثل MMPI-SF-370)، age_range (محدوده سنی)،
  estimated_minutes (مدت تخمینی)، accent_color (رنگ کارت)، sort_order
  (ترتیب نمایش کاتالوگ)؛ همه nullable/پیش‌فرض‌دار — سازگار با داده فعلی؛
- psych_questions: image_path — مسیر نسبی عکس سؤال در uploads/psych_images
  (آزمون‌های تصویری مثل ریون)؛
- psych_attempts: demographics — مشخصات اولیه برگزارکننده (جنسیت/سن/
  تحصیلات/وضعیت تأهل) مطابق فرم «مشخصات اولیه» مرجع، JSONB nullable.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0029_phase50_psych_bank"
down_revision = "0028_phase49_processes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("psych_tests", sa.Column("code", sa.String(60), nullable=True))
    op.add_column("psych_tests", sa.Column("age_range", sa.String(120), nullable=True))
    op.add_column("psych_tests", sa.Column("estimated_minutes", sa.Integer(), nullable=True))
    op.add_column("psych_tests", sa.Column("accent_color", sa.String(20), nullable=True))
    op.add_column(
        "psych_tests",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("psych_questions", sa.Column("image_path", sa.String(300), nullable=True))
    op.add_column("psych_attempts", sa.Column("demographics", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("psych_attempts", "demographics")
    op.drop_column("psych_questions", "image_path")
    op.drop_column("psych_tests", "sort_order")
    op.drop_column("psych_tests", "accent_color")
    op.drop_column("psych_tests", "estimated_minutes")
    op.drop_column("psych_tests", "age_range")
    op.drop_column("psych_tests", "code")
