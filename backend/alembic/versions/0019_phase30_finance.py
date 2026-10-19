"""phase 30 - B18/B19/B20: wallet & discount codes & refunds

Revision ID: 0019_phase30_finance
Revises: 0018_phase29_payments_branches
Create Date: 2026-10-19 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_phase30_finance"
down_revision = "0018_phase29_payments_branches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- B19: کد تخفیف ---
    op.create_table(
        "discounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="amount"),
        sa.Column("value", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("max_uses_per_user", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("min_order_amount", sa.Numeric(16, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('amount','percent')", name="ck_discounts_kind"),
        sa.CheckConstraint("value > 0", name="ck_discounts_value_positive"),
        sa.CheckConstraint("kind != 'percent' OR value <= 100", name="ck_discounts_percent_max"),
        sa.CheckConstraint("expires_at IS NULL OR starts_at IS NULL OR expires_at >= starts_at",
                           name="ck_discounts_range"),
        sa.CheckConstraint("min_order_amount IS NULL OR min_order_amount >= 0",
                           name="ck_discounts_min_nonneg"),
    )
    op.create_table(
        "discount_redemptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("discount_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("discounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount_applied", sa.Numeric(16, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("order_id", name="uq_discount_redemption_order"),
    )
    op.create_index("ix_discount_redemptions_discount", "discount_redemptions", ["discount_id"])
    op.create_index("ix_discount_redemptions_user", "discount_redemptions", ["user_id"])

    # --- ستون‌های جدید سفارش (B18/B19/B20) ---
    op.add_column("orders", sa.Column("kind", sa.String(20), nullable=False, server_default="service"))
    op.add_column("orders", sa.Column("discount_id", postgresql.UUID(as_uuid=True),
                                      sa.ForeignKey("discounts.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("orders", sa.Column("refunded_amount", sa.Numeric(16, 2), nullable=False, server_default="0"))
    op.create_check_constraint("ck_orders_kind", "orders", "kind IN ('service','topup')")
    op.create_check_constraint("ck_orders_refunded_nonneg", "orders", "refunded_amount >= 0")

    # --- B20: استرداد (پیش از کیف پول، به‌خاطر FK از wallet_entries) ---
    op.create_table(
        "refund_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending','approved','rejected','executed')",
                           name="ck_refund_requests_status"),
        sa.CheckConstraint("amount > 0", name="ck_refund_requests_amount_positive"),
    )
    op.create_index("ix_refund_requests_order", "refund_requests", ["order_id"])
    op.create_index("ix_refund_requests_status", "refund_requests", ["status"])

    op.create_table(
        "refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("refund_request_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("refund_requests.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("gateway", sa.String(30), nullable=True),
        sa.Column("gateway_ref", sa.String(120), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("executed_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_refunds_amount_positive"),
    )
    op.create_index("ix_refunds_order", "refunds", ["order_id"])

    # --- B18: کیف پول ---
    op.create_table(
        "wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("balance", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("balance >= 0", name="ck_wallets_balance_nonneg"),
    )
    op.create_table(
        "wallet_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("refund_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("refunds.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("direction IN ('credit','debit')", name="ck_wallet_entries_direction"),
        sa.CheckConstraint("reason IN ('topup','payment','refund','adjustment')",
                           name="ck_wallet_entries_reason"),
        sa.CheckConstraint("amount > 0", name="ck_wallet_entries_amount_positive"),
    )
    op.create_index("ix_wallet_entries_wallet", "wallet_entries", ["wallet_id"])
    op.create_index("ix_wallet_entries_created", "wallet_entries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_wallet_entries_created", table_name="wallet_entries")
    op.drop_index("ix_wallet_entries_wallet", table_name="wallet_entries")
    op.drop_table("wallet_entries")
    op.drop_table("wallets")
    op.drop_index("ix_refunds_order", table_name="refunds")
    op.drop_table("refunds")
    op.drop_index("ix_refund_requests_status", table_name="refund_requests")
    op.drop_index("ix_refund_requests_order", table_name="refund_requests")
    op.drop_table("refund_requests")
    op.drop_constraint("ck_orders_refunded_nonneg", "orders", type_="check")
    op.drop_constraint("ck_orders_kind", "orders", type_="check")
    op.drop_column("orders", "refunded_amount")
    op.drop_column("orders", "discount_id")
    op.drop_column("orders", "kind")
    op.drop_index("ix_discount_redemptions_user", table_name="discount_redemptions")
    op.drop_index("ix_discount_redemptions_discount", table_name="discount_redemptions")
    op.drop_table("discount_redemptions")
    op.drop_table("discounts")
