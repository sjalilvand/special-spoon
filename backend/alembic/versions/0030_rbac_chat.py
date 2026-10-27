"""فاز ۵۲ - مدیریت کاربران پیشرفته (RBAC گرافیکی) + چت آنلاین داخلی

Revision ID: 0030_rbac_chat
Revises: 0029_phase50_psych_bank
Create Date: 2026-10-27

الف) RBAC:
- permissions: کاتالوگ مرکزی دسترسی‌ها (کد + بخش + عنوان + ترتیب) — ماتریس
  گرافیکی «نقش‌ها و دسترسی‌ها» از همین کاتالوگ ساخته می‌شود؛
- role_permissions: پیوند نقش ↔ دسترسی؛ اثربخشی کاربر = اجتماع نقش‌هایش؛
- roles.data_scope: سطح دسترسی روی داده (all/own/assigned)؛
- seed کاتالوگ + مپ پیش‌فرض نقش‌های سیستمی (idempotent با ON CONFLICT DO NOTHING).

ب) چت:
- conversations / conversation_members / messages — گفتگوی دو نفره (dm) و
  اتاق مشاورهٔ گروهی (group) با پیام متنی/صوتی/سیستمی؛ صوت در media_data
  (bytea، سقف ۵ مگابایت در لایهٔ API) ذخیره می‌شود.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0030_rbac_chat"
down_revision = "0029_phase50_psych_bank"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# کاتالوگ دسترسی‌ها: (code, section, title, sort)
# section = عنوان بخش در ماتریس گرافیکی؛ هر بخش یک ردیف گروه‌بندی با تیک دارد
# ---------------------------------------------------------------------------
PERMISSIONS: list[tuple[str, str, str, int]] = [
    # داشبورد و گزارش‌ها
    ("dashboard.view", "داشبورد و گزارش‌ها", "مشاهده داشبورد عملیاتی", 1),
    ("dashboard.admin", "داشبورد و گزارش‌ها", "داشبورد مدیریتی", 2),
    ("reports.view", "داشبورد و گزارش‌ها", "گزارش‌ها و انطباق (DPO)", 3),
    # پرونده‌ها و مشاوره
    ("cases.view", "پرونده‌ها و مشاوره", "مشاهده پرونده‌ها", 1),
    ("cases.create", "پرونده‌ها و مشاوره", "ایجاد پرونده", 2),
    ("cases.edit", "پرونده‌ها و مشاوره", "ویرایش پرونده", 3),
    ("cases.delete", "پرونده‌ها و مشاوره", "حذف پرونده", 4),
    ("assessments.view", "پرونده‌ها و مشاوره", "مشاهده ارزیابی‌ها", 5),
    ("assessments.edit", "پرونده‌ها و مشاوره", "ثبت/ویرایش ارزیابی", 6),
    ("reviews.tech", "پرونده‌ها و مشاوره", "بررسی‌های فنی و نظارت", 7),
    ("worklist.view", "پرونده‌ها و مشاوره", "کارتابل مشاور", 8),
    # متقاضیان
    ("applicants.view", "متقاضیان", "مشاهده متقاضیان", 1),
    ("applicants.create", "متقاضیان", "ثبت متقاضی", 2),
    ("applicants.edit", "متقاضیان", "ویرایش متقاضی", 3),
    ("applicants.import", "متقاضیان", "ورود اکسل", 4),
    # کاربران و نقش‌ها
    ("users.view", "کاربران و نقش‌ها", "مشاهده کاربران", 1),
    ("users.create", "کاربران و نقش‌ها", "ایجاد کاربر", 2),
    ("users.edit", "کاربران و نقش‌ها", "ویرایش کاربر", 3),
    ("users.disable", "کاربران و نقش‌ها", "فعال/غیرفعال‌سازی", 4),
    ("users.reset_password", "کاربران و نقش‌ها", "بازنشانی رمز عبور", 5),
    ("roles.view", "کاربران و نقش‌ها", "مشاهده نقش‌ها و دسترسی‌ها", 6),
    ("roles.manage", "کاربران و نقش‌ها", "مدیریت نقش‌ها و ماتریس دسترسی", 7),
    ("audit.view", "کاربران و نقش‌ها", "رویدادهای حسابرسی", 8),
    # خدمات و شعب
    ("services.view", "خدمات و شعب", "مشاهده خدمات", 1),
    ("services.edit", "خدمات و شعب", "مدیریت خدمات", 2),
    ("branches.view", "خدمات و شعب", "مشاهده شعب", 3),
    ("branches.edit", "خدمات و شعب", "مدیریت شعب", 4),
    ("organizations.view", "خدمات و شعب", "مشاهده سازمان‌ها", 5),
    ("organizations.edit", "خدمات و شعب", "مدیریت سازمان‌ها", 6),
    ("topics.manage", "خدمات و شعب", "دسته‌بندی موضوعی", 7),
    # مالی
    ("orders.view", "مالی", "مشاهده سفارش‌ها", 1),
    ("orders.create", "مالی", "ثبت سفارش", 2),
    ("invoices.view", "مالی", "مشاهده فاکتورها", 3),
    ("accounting.view", "مالی", "مشاهده حسابداری", 4),
    ("accounting.edit", "مالی", "ثبت اسناد حسابداری", 5),
    ("refunds.view", "مالی", "مشاهده بازگشت وجه", 6),
    ("refunds.approve", "مالی", "تأیید بازگشت وجه", 7),
    # محتوا و آزمون
    ("learning.view", "محتوا و آزمون", "مشاهده محتوا و دوره‌ها", 1),
    ("learning.manage", "محتوا و آزمون", "مدیریت محتوا و دوره‌ها", 2),
    ("psych_tests.run", "محتوا و آزمون", "برگزاری آزمون روان‌شناسی", 3),
    ("psych_tests.manage", "محتوا و آزمون", "مدیریت بانک آزمون", 4),
    # پشتیبانی
    ("support.view", "پشتیبانی", "مشاهده تیکت‌ها", 1),
    ("support.reply", "پشتیبانی", "پاسخ به تیکت‌ها", 2),
    ("notifications.view", "پشتیبانی", "اعلان‌های من", 3),
    # یکپارچه‌سازی
    ("integrations.view", "یکپارچه‌سازی", "مشاهده یکپارچه‌سازی‌ها", 1),
    ("integrations.manage", "یکپارچه‌سازی", "مدیریت یکپارچه‌سازی‌ها", 2),
    # چت
    ("chat.use", "گفتگو", "استفاده از چت و مشاورهٔ آنلاین", 1),
    ("chat.moderate", "گفتگو", "مدیریت اتاق‌های گفتگو", 2),
]

# مپ پیش‌فرض نقش‌های سیستمی (فقط بار اول؛ پس از آن ماتریس گرافیکی ملاک است)
ROLE_DEFAULT_PERMS: dict[str, list[str]] = {
    "SYSTEM_ADMIN": ["*"],
    "ORG_MANAGER": [
        "dashboard.view", "dashboard.admin", "reports.view",
        "cases.view", "cases.create", "cases.edit", "assessments.view", "assessments.edit",
        "applicants.view", "applicants.create", "applicants.edit", "applicants.import",
        "users.view", "services.view", "services.edit",
        "branches.view", "branches.edit", "organizations.view", "organizations.edit", "topics.manage",
        "orders.view", "orders.create", "invoices.view", "accounting.view",
        "refunds.view", "learning.view", "learning.manage",
        "psych_tests.run", "psych_tests.manage",
        "support.view", "support.reply", "notifications.view", "chat.use",
    ],
    "RECEPTION": [
        "dashboard.view", "cases.view", "cases.create",
        "applicants.view", "applicants.create", "applicants.edit", "applicants.import",
        "services.view", "branches.view", "topics.manage",
        "orders.view", "orders.create", "invoices.view",
        "learning.view", "psych_tests.run",
        "support.view", "support.reply", "notifications.view", "chat.use",
    ],
    "COUNSELOR": [
        "dashboard.view", "cases.view", "assessments.view", "assessments.edit", "worklist.view",
        "services.view", "topics.manage", "learning.view", "psych_tests.run",
        "support.view", "notifications.view", "chat.use",
    ],
    "TECHNICAL_SUPERVISOR": [
        "dashboard.view", "reports.view", "cases.view", "assessments.view", "reviews.tech",
        "services.view", "learning.view", "learning.manage",
        "psych_tests.run", "psych_tests.manage",
        "support.view", "notifications.view", "chat.use",
    ],
    "APPLICANT": [
        "support.view", "notifications.view", "psych_tests.run", "chat.use",
    ],
    "DPO": [
        "dashboard.view", "reports.view", "audit.view", "chat.use",
    ],
}

ROLE_DEFAULT_DATA_SCOPE: dict[str, str] = {
    "SYSTEM_ADMIN": "all",
    "ORG_MANAGER": "all",
    "RECEPTION": "all",
    "COUNSELOR": "assigned",
    "TECHNICAL_SUPERVISOR": "assigned",
    "APPLICANT": "own",
    "DPO": "all",
}


def upgrade() -> None:
    # --- RBAC ---
    op.create_table(
        "permissions",
        sa.Column("code", sa.String(100), primary_key=True),
        sa.Column("section", sa.String(100), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_code", sa.String(50), sa.ForeignKey("roles.code", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_code", sa.String(100), sa.ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True),
    )
    op.add_column(
        "roles",
        sa.Column("data_scope", sa.String(20), nullable=False, server_default="all"),
    )

    # --- چت ---
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False, server_default="dm"),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.CheckConstraint("kind IN ('dm','group')", name="ck_conversations_kind"),
    )
    op.create_table(
        "conversation_members",
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("invited_by_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_read_message_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sender_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(10), nullable=False, server_default="text"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("media_data", sa.LargeBinary(), nullable=True),
        sa.Column("media_mime", sa.String(80), nullable=True),
        sa.Column("media_bytes", sa.BigInteger(), nullable=True),
        sa.Column("media_duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.CheckConstraint("kind IN ('text','voice','system')", name="ck_messages_kind"),
    )
    op.create_index("ix_messages_conv_created", "messages", ["conversation_id", "created_at"])

    # --- seed کاتالوگ + مپ پیش‌فرض (idempotent) ---
    conn = op.get_bind()
    for code, section, title, sort in PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, section, title, sort) "
                "VALUES (:c, :s, :t, :o) ON CONFLICT (code) DO NOTHING"
            ),
            {"c": code, "s": section, "t": title, "o": sort},
        )
    for role_code, perms in ROLE_DEFAULT_PERMS.items():
        scope = ROLE_DEFAULT_DATA_SCOPE.get(role_code, "all")
        conn.execute(
            sa.text(
                "UPDATE roles SET data_scope = :s WHERE code = :r "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions WHERE role_code = :r)"
            ),
            {"s": scope, "r": role_code},
        )
        # نقش SYSTEM_ADMIN همیشه '*'؛ برای بقیه مپ واقعی
        actual = [p for p in PERMISSIONS if p[0] in perms] if "*" not in perms else PERMISSIONS
        for code, _s, _t, _o in actual:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_code, permission_code) "
                    "VALUES (:r, :c) ON CONFLICT DO NOTHING"
                ),
                {"r": role_code, "c": code},
            )


def downgrade() -> None:
    op.drop_index("ix_messages_conv_created", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversation_members")
    op.drop_table("conversations")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_column("roles", "data_scope")
