"""phase 14 - consultation follow-up (reception note, contact attempts, city, referral source)

Revision ID: 0011_followup
Revises: 0010_referrals
Create Date: 2024-12-11 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = "0011_followup"
down_revision = "0010_referrals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("consultation_requests", sa.Column("reception_note", sa.Text(), nullable=True))
    op.add_column("consultation_requests", sa.Column("contact_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("consultation_requests", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("consultation_requests", sa.Column("referral_source", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("consultation_requests", "referral_source")
    op.drop_column("consultation_requests", "city")
    op.drop_column("consultation_requests", "contact_attempts")
    op.drop_column("consultation_requests", "reception_note")
