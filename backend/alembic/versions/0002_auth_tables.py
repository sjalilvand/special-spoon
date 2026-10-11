"""phase 2 - auth tables (بند ۱۱ سند)

Revision ID: 0002_auth
Revises: 0001_baseline
Create Date: 2024-12-02 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_auth"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

ROLE_ROWS = [
    ("SYSTEM_ADMIN", "مدیر سامانه"),
    ("ORG_MANAGER", "مدیر سازمان"),
    ("RECEPTION", "پذیرش"),
    ("COUNSELOR", "مشاور"),
    ("TECHNICAL_SUPERVISOR", "مسئول فنی"),
    ("APPLICANT", "متقاضی"),
]


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("mobile", sa.String(20), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_activation"),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending_activation','active','disabled')", name="ck_users_status"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_code", sa.String(50), sa.ForeignKey("roles.code", ondelete="RESTRICT"), primary_key=True),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(400), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auth_sessions_refresh_token_hash", "auth_sessions", ["refresh_token_hash"], unique=True)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    op.create_table(
        "activation_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_activation_tokens_token_hash", "activation_tokens", ["token_hash"], unique=True)

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("result", sa.String(20), nullable=False, server_default="success"),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    bind = op.get_bind()
    roles_table = sa.table("roles", sa.column("code", sa.String), sa.column("title", sa.String))
    for code, title in ROLE_ROWS:
        stmt = (
            postgresql.insert(roles_table)
            .values(code=code, title=title)
            .on_conflict_do_nothing(index_elements=["code"])
        )
        bind.execute(stmt)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("activation_tokens")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_refresh_token_hash", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("user_roles")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
