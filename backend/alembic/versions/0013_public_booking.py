"""phase 21 - public booking (رزرو آنلاین نوبت از سایت عمومی)

Revision ID: 0013_public_booking
Revises: 0012_intake
Create Date: 2024-12-13 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_public_booking"
down_revision = "0012_intake"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consultation_requests",
        sa.Column("preferred_counselor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("counselors.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "consultation_requests",
        sa.Column("preferred_start_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_consult_requests_pref_counselor", "consultation_requests", ["preferred_counselor_id"])
    # فقط یک رزرو در انتظار برای هر (مشاور، اسلات) - بند ضد دوباره‌رزرو
    op.create_index(
        "uq_consult_requests_pending_slot",
        "consultation_requests",
        ["preferred_counselor_id", "preferred_start_at"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('new','in_review') AND preferred_counselor_id IS NOT NULL AND preferred_start_at IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_consult_requests_pending_slot", table_name="consultation_requests")
    op.drop_index("ix_consult_requests_pref_counselor", table_name="consultation_requests")
    op.drop_column("consultation_requests", "preferred_start_at")
    op.drop_column("consultation_requests", "preferred_counselor_id")