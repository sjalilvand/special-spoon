"""phase 33 - B32 + B21: topics, organizations/contracts, order share split

Revision ID: 0021_phase33_topics_orgs
Revises: 0020_phase31_accounting
Create Date: 2026-10-19 12:00:00

B32: دسته‌بندی موضوعی سلسله‌مراتبی + اتصال خدمت ↔ دسته
B21: سازمان/قرارداد/سهم پرداخت + تقسیم سهم روی سفارش (snapshot)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021_phase33_topics_orgs"
down_revision = "0020_phase31_accounting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- B32: دسته‌بندی موضوعی ---
    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("topics.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sort_order >= 0", name="ck_topics_sort_nonneg"),
    )
    op.create_index("ix_topics_parent", "topics", ["parent_id"])

    op.create_table(
        "service_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("service_id", "topic_id", name="uq_service_topic"),
    )
    op.create_index("ix_service_topics_service", "service_topics", ["service_id"])
    op.create_index("ix_service_topics_topic", "service_topics", ["topic_id"])

    # --- B21: سازمان‌ها و قراردادها ---
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("national_id", sa.String(20), nullable=True, unique=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("coverage_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("coverage_cap_amount", sa.Numeric(16, 2), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','active','terminated')", name="ck_contracts_status"),
        sa.CheckConstraint("coverage_percent > 0 AND coverage_percent <= 100",
                           name="ck_contracts_percent_range"),
        sa.CheckConstraint("coverage_cap_amount IS NULL OR coverage_cap_amount >= 0",
                           name="ck_contracts_cap_nonneg"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to >= valid_from",
                           name="ck_contracts_date_range"),
    )
    op.create_index("ix_contracts_org", "contracts", ["organization_id"])
    op.create_index("ix_contracts_status", "contracts", ["status"])

    op.create_table(
        "contract_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("contract_id", "service_id", name="uq_contract_service"),
    )
    op.create_index("ix_contract_services_contract", "contract_services", ["contract_id"])
    op.create_index("ix_contract_services_service", "contract_services", ["service_id"])

    # --- B21: سازمان متقاضی ---
    op.add_column(
        "applicants",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_applicants_organization", "applicants", "organizations",
        ["organization_id"], ["id"], ondelete="SET NULL",
    )

    # --- B21: تقسیم سهم روی سفارش (snapshot) ---
    op.add_column(
        "orders",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("coverage_percent", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("org_share_amount", sa.Numeric(16, 2), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("applicant_share_amount", sa.Numeric(16, 2), nullable=True),
    )
    op.create_foreign_key(
        "fk_orders_organization", "orders", "organizations",
        ["organization_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_orders_contract", "orders", "contracts",
        ["contract_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_orders_org_share_nonneg", "orders",
        "org_share_amount IS NULL OR org_share_amount >= 0",
    )
    op.create_index("ix_orders_organization", "orders", ["organization_id"])

    # --- B21 × B22: سرفصل دریافتنی از سازمان‌ها (idempotent) ---
    op.execute(
        sa.text(
            "INSERT INTO accounts (id, code, name, type, is_active, is_system) "
            "SELECT gen_random_uuid(), '1104', 'حساب‌های دریافتنی از سازمان‌ها', 'asset', true, true "
            "WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE code = '1104')"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_orders_organization", table_name="orders")
    op.drop_constraint("ck_orders_org_share_nonneg", "orders", type_="check")
    op.drop_constraint("fk_orders_contract", "orders", type_="foreignkey")
    op.drop_constraint("fk_orders_organization", "orders", type_="foreignkey")
    for col in ("applicant_share_amount", "org_share_amount", "coverage_percent",
                "contract_id", "organization_id"):
        op.drop_column("orders", col)
    op.drop_constraint("fk_applicants_organization", "applicants", type_="foreignkey")
    op.drop_column("applicants", "organization_id")
    op.drop_index("ix_contract_services_service", table_name="contract_services")
    op.drop_index("ix_contract_services_contract", table_name="contract_services")
    op.drop_table("contract_services")
    op.drop_index("ix_contracts_status", table_name="contracts")
    op.drop_index("ix_contracts_org", table_name="contracts")
    op.drop_table("contracts")
    op.drop_table("organizations")
    op.drop_index("ix_service_topics_topic", table_name="service_topics")
    op.drop_index("ix_service_topics_service", table_name="service_topics")
    op.drop_table("service_topics")
    op.drop_index("ix_topics_parent", table_name="topics")
    op.drop_table("topics")
