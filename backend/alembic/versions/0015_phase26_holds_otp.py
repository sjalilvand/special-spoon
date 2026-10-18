"""phase 26 - booking holds (B09) + otp challenges (B02)

Revision ID: 0015_phase26_holds_otp
Revises: 0014_phase25_governance
Create Date: 2024-12-14 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_phase26_holds_otp"
down_revision = "0014_phase25_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- B09: نگهداشت موقت اسلات ---
    op.create_table(
        "slot_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("counselor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("counselors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("hold_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("mobile", sa.String(15), nullable=True),
        sa.Column("consultation_request_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("consultation_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active','confirmed','released','expired')",
                           name="ck_slot_claims_status"),
    )
    op.create_index("ix_slot_claims_counselor_id", "slot_claims", ["counselor_id"])
    op.create_index("ix_slot_claims_status", "slot_claims", ["status"])
    op.create_index("ix_slot_claims_mobile", "slot_claims", ["mobile"])
    # فقط یک نگهداشت فعال برای هر (مشاور، اسلات) - منع تعارض B09
    op.create_index(
        "uq_slot_claims_active_slot",
        "slot_claims", ["counselor_id", "start_at"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # --- B02: چالش OTP ---
    op.create_table(
        "otp_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mobile", sa.String(15), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False, server_default="booking"),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verify_token_hash", sa.String(64), nullable=True),
        sa.Column("verify_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("purpose IN ('booking','login')", name="ck_otp_purpose"),
        sa.CheckConstraint("attempts >= 0", name="ck_otp_attempts"),
    )
    op.create_index("ix_otp_challenges_mobile", "otp_challenges", ["mobile"])
    op.create_index("ix_otp_challenges_created_at", "otp_challenges", ["created_at"])
    op.create_index("ix_otp_challenges_verify_token_hash", "otp_challenges", ["verify_token_hash"])


def downgrade() -> None:
    op.drop_table("otp_challenges")
    op.drop_index("uq_slot_claims_active_slot", table_name="slot_claims")
    op.drop_index("ix_slot_claims_mobile", table_name="slot_claims")
    op.drop_index("ix_slot_claims_status", table_name="slot_claims")
    op.drop_index("ix_slot_claims_counselor_id", table_name="slot_claims")
    op.drop_table("slot_claims")
