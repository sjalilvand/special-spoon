"""phase 47 - psych tests subscale support (B37)

Revision ID: 0027_phase47_psych_subscale
Revises: 0026_phase42_idempotency
Create Date: 2026-10-21 09:00:00

فاز ۴۷: زیرمقیاس ابزارهای روان‌شناسی — ستون subscale روی سؤال (نام
زیرمقیاس مثل «اضطراب») و subscale_scores روی اجرا (ریزنمره snapshot) تا
ابزارهای چندبُعدی (DASS-21، گلاسر، گاردنر، شاین، هوش هیجانی) بتوانند
علاوه بر نمره کل، ریزنمره هر بعد را هم نمایش دهند. هر دو ستون nullable —
سازگار کامل با داده‌های فعلی.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0027_phase47_psych_subscale"
down_revision = "0026_phase42_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "psych_questions",
        sa.Column("subscale", sa.String(100), nullable=True),
    )
    op.add_column(
        "psych_attempts",
        sa.Column("subscale_scores", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("psych_attempts", "subscale_scores")
    op.drop_column("psych_questions", "subscale")
