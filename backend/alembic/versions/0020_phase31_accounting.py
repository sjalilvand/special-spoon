"""phase 31 - B22: accounting coding, journal entries, settlements

Revision ID: 0020_phase31_accounting
Revises: 0019_phase30_finance
Create Date: 2026-10-19 00:00:00

قاعده سند: «سند متوازن و قابل ردیابی به رویداد مالی باشد» —
CHECKهای یک‌سمتی/مثبت روی ردیف‌ها + قید یکتایی (source_type, source_id)
برای اسناد خودکار + کدینگ پیش‌فرض (سرفصل‌های سیستمی).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020_phase31_accounting"
down_revision = "0019_phase30_finance"
branch_labels = None
depends_on = None


# کدینگ پیش‌فرض (سرفصل سیستمی) — سرویس accounting نیز ensure می‌کند
DEFAULT_ACCOUNTS = [
    ("1101", "حساب بانک", "asset"),
    ("1102", "درگاه‌های پرداخت - در جریان وصول", "asset"),
    ("1103", "حساب‌های تصفیه", "asset"),
    ("2101", "کیف پول کاربران", "liability"),
    ("2102", "استردادهای پرداختنی", "liability"),
    ("4101", "درآمد خدمات مشاوره", "revenue"),
    ("4102", "برگشت از فروش", "revenue"),
    ("4103", "سایر درآمدها (تعدیل)", "revenue"),
    ("5101", "هزینه کارمزد درگاه", "expense"),
    ("5102", "هزینه تخفیف", "expense"),
    ("5103", "هزینه جبران و تعدیل", "expense"),
]


def upgrade() -> None:
    # --- B22: کدینگ (سرفصل‌ها) ---
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("type IN ('asset','liability','equity','revenue','expense')",
                           name="ck_accounts_type"),
    )

    # --- B22: سند حسابداری دوطرفه ---
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_no", sa.String(40), nullable=False, unique=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reversal_of_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("is_reversal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_type", "source_id", name="uq_journal_source_event"),
        sa.CheckConstraint(
            "source_type IN ('payment','refund','wallet_adjustment','settlement','manual','reversal')",
            name="ck_journal_source_type",
        ),
    )
    op.create_index("ix_journal_entries_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_source", "journal_entries", ["source_type", "source_id"])
    op.create_index("ix_journal_entries_kind", "journal_entries", ["kind"])

    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("debit", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_lines_nonneg"),
        sa.CheckConstraint("(debit > 0) <> (credit > 0)", name="ck_journal_lines_one_side"),
    )
    op.create_index("ix_journal_lines_entry", "journal_lines", ["entry_id"])
    op.create_index("ix_journal_lines_account", "journal_lines", ["account_id"])

    # --- B22: تسویه دوره درگاه ---
    op.create_table(
        "settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("settlement_no", sa.String(40), nullable=False, unique=True),
        sa.Column("gateway", sa.String(30), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("payments_count", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("gross_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("fee_amount", sa.Numeric(16, 2), nullable=True),
        sa.Column("net_amount", sa.Numeric(16, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("settled_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','settled')", name="ck_settlements_status"),
        sa.CheckConstraint("gross_amount >= 0", name="ck_settlements_gross_nonneg"),
        sa.CheckConstraint("fee_amount IS NULL OR fee_amount >= 0", name="ck_settlements_fee_nonneg"),
        sa.CheckConstraint("period_start IS NULL OR period_end IS NULL OR period_end >= period_start",
                           name="ck_settlements_period"),
    )
    op.create_index("ix_settlements_gateway", "settlements", ["gateway"])
    op.create_index("ix_settlements_status", "settlements", ["status"])

    op.create_table(
        "settlement_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("settlement_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_settlement_items_settlement", "settlement_items", ["settlement_id"])

    # --- کدینگ پیش‌فرض ---
    for code, name, atype in DEFAULT_ACCOUNTS:
        op.execute(
            sa.text(
                "INSERT INTO accounts (id, code, name, type, is_active, is_system) "
                "VALUES (gen_random_uuid(), :code, :name, :type, true, true)"
            ).bindparams(code=code, name=name, type=atype)
        )


def downgrade() -> None:
    op.drop_index("ix_settlement_items_settlement", table_name="settlement_items")
    op.drop_table("settlement_items")
    op.drop_index("ix_settlements_status", table_name="settlements")
    op.drop_index("ix_settlements_gateway", table_name="settlements")
    op.drop_table("settlements")
    op.drop_index("ix_journal_lines_account", table_name="journal_lines")
    op.drop_index("ix_journal_lines_entry", table_name="journal_lines")
    op.drop_table("journal_lines")
    op.drop_index("ix_journal_entries_kind", table_name="journal_entries")
    op.drop_index("ix_journal_entries_source", table_name="journal_entries")
    op.drop_index("ix_journal_entries_date", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_table("accounts")
