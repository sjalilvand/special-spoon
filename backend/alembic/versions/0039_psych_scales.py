"""فاز ۶۳ - گزارش تحلیلی چندلایه نتایج آزمون (مدل مرجع ای‌سنج).

Revision ID: 0039_psych_scales
Revises: 0038_contract_tests
Create Date: 2026-10-30

- جدول ``psych_scales``: مقیاس‌های هر ابزار با سلسله‌مراتب اختیاری
  (بعد/محور ← زیرمقیاس/وجه)، بازه‌های سطح (JSONB) و متن تفسیر هر سطح؛
- ستون ``result_payload`` روی ``psych_attempts``: snapshot ساخت‌یافتهٔ
  گزارش (نمرهٔ هر مقیاس، درصد، سطح غالب، متن تفسیر) تا گزارش مشابه
  نتیجهٔ بقیهٔ فیلدها مستقل از تغییر بعدی مقیاس‌ها بماند.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0039_psych_scales"
down_revision = "0038_contract_tests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "psych_scales",
        # server_default برای درج‌های مستقیم SQL (درس فاز ۶۱)
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "test_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("psych_tests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("psych_scales.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # نام‌های زیرمقیاس سؤال‌ها که به این مقیاس شمارش می‌شوند
        sa.Column("match_names", pg.JSONB(), nullable=True),
        # بازه‌های تفسیر سطح: [{"min":0,"max":10,"label":"کم","text":"...","guidance":"..."}]
        sa.Column("levels", pg.JSONB(), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        # higher_worse | higher_better | balanced — برای رنگ‌بندی سطح‌ها
        sa.Column("direction", sa.String(20), server_default="balanced", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("test_id", "key", name="uq_psych_scale_key"),
    )
    op.create_index("ix_psych_scales_test", "psych_scales", ["test_id"])
    op.create_index("ix_psych_scales_parent", "psych_scales", ["parent_id"])

    op.add_column("psych_attempts", sa.Column("result_payload", pg.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("psych_attempts", "result_payload")
    op.drop_table("psych_scales")
