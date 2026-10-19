"""phase 29 - B10/B11/B31: orders & payments & invoices + clinics & branches

Revision ID: 0018_phase29_payments_branches
Revises: 0017_phase28_services_tariffs
Create Date: 2026-10-19 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_phase29_payments_branches"
down_revision = "0017_phase28_services_tariffs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- B31: مراکز مشاوره و شعب ---
    op.create_table(
        "clinics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("logo_path", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("website", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clinics.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("province", sa.String(80), nullable=True),
        sa.Column("city", sa.String(80), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("working_hours", postgresql.JSONB(), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_branches_status"),
        sa.CheckConstraint("latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
                           name="ck_branches_lat_range"),
        sa.CheckConstraint("longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
                           name="ck_branches_lon_range"),
    )
    op.create_index("ix_branches_clinic", "branches", ["clinic_id"])
    op.create_index("ix_branches_status", "branches", ["status"])
    op.create_index("ix_branches_city", "branches", ["city"])

    op.create_table(
        "branch_service_offerings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("branch_id", "service_id", name="uq_branch_service"),
    )
    op.create_index("ix_branch_offerings_branch", "branch_service_offerings", ["branch_id"])
    op.create_index("ix_branch_offerings_service", "branch_service_offerings", ["service_id"])

    # --- B10: سفارش و پرداخت ---
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_number", sa.String(40), nullable=False, unique=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, unique=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("tariff_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tariff_versions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("discount_amount", sa.Numeric(16, 2), nullable=True),
        sa.Column("payable_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending','paid','cancelled','failed')", name="ck_orders_status"),
        sa.CheckConstraint("amount >= 0", name="ck_orders_amount_nonneg"),
        sa.CheckConstraint("discount_amount IS NULL OR discount_amount >= 0", name="ck_orders_discount_nonneg"),
        sa.CheckConstraint("payable_amount >= 0", name="ck_orders_payable_nonneg"),
    )
    op.create_index("ix_orders_owner", "orders", ["owner_user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_appointment", "orders", ["appointment_id"])

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("gateway", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="initiated"),
        sa.Column("authority", sa.String(120), nullable=False, unique=True),
        sa.Column("gateway_ref", sa.String(120), nullable=True),
        sa.Column("card_mask", sa.String(30), nullable=True),
        sa.Column("fail_reason", sa.String(300), nullable=True),
        sa.Column("verify_payload", postgresql.JSONB(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('initiated','success','failed')", name="ck_payments_status"),
        sa.CheckConstraint("amount >= 0", name="ck_payments_amount_nonneg"),
    )
    op.create_index("ix_payments_order", "payments", ["order_id"])

    # --- B11: فاکتور ---
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_number", sa.String(40), nullable=False, unique=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("buyer_name", sa.String(200), nullable=True),
        sa.Column("buyer_national_id", sa.String(20), nullable=True),
        sa.Column("buyer_email", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="issued"),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('issued','void')", name="ck_invoices_status"),
        sa.CheckConstraint("total_amount >= 0", name="ck_invoices_total_nonneg"),
    )
    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(16, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_items_qty_positive"),
        sa.CheckConstraint("unit_amount >= 0", name="ck_invoice_items_unit_nonneg"),
    )
    op.create_index("ix_invoice_items_invoice", "invoice_items", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_items_invoice", table_name="invoice_items")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_index("ix_payments_order", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_orders_appointment", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_owner", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_branch_offerings_service", table_name="branch_service_offerings")
    op.drop_index("ix_branch_offerings_branch", table_name="branch_service_offerings")
    op.drop_table("branch_service_offerings")
    op.drop_index("ix_branches_city", table_name="branches")
    op.drop_index("ix_branches_status", table_name="branches")
    op.drop_index("ix_branches_clinic", table_name="branches")
    op.drop_table("branches")
    op.drop_table("clinics")
