"""فاز ۶۲ - دامنه آزمون قرارداد سازمان (کدام آزمون‌ها برای سازمان باز باشد).

Revision ID: 0038_contract_tests
Revises: 0037_form_builder_calls
Create Date: 2026-10-30

- جدول ``contract_tests`` (قرارداد × آزمون روان‌شناسی)؛ بدون ردیف برای یک
  قرارداد = همه آزمون‌ها باز؛ با ردیف = فقط همان آزمون‌ها؛
- «آزمون‌های باز سازمان» از قرارداد فعال مشتق و در خروجی سازمان‌ها عرضه می‌شود.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0038_contract_tests"
down_revision = "0037_form_builder_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_tests",
        # server_default برای درج‌های مستقیم SQL (درس فاز ۶۱)
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "contract_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "test_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("psych_tests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("contract_id", "test_id", name="uq_contract_test"),
    )
    op.create_index("ix_contract_tests_contract", "contract_tests", ["contract_id"])
    op.create_index("ix_contract_tests_test", "contract_tests", ["test_id"])


def downgrade() -> None:
    op.drop_table("contract_tests")
