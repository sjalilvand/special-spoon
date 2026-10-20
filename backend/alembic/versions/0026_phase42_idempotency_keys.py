"""phase 42 - ADR-05 step 3: financial operations idempotency keys

Revision ID: 0026_phase42_idempotency
Revises: 0025_phase37_object_storage
Create Date: 2026-10-20 10:00:00

ADR-05 گام ۳: جدول idempotency_keys برای «دوبار-زدن دکمه پرداخت» روی شبکه
ناپایدار — تکرار همان کلید همان پاسخ قبلی را برمی‌گرداند (بدون ردیف دوم).
"""
from alembic import op
import sqlalchemy as sa

revision = "0026_phase42_idempotency"
down_revision = "0025_phase37_object_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_idempotency_keys_created_at", "idempotency_keys", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_created_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
