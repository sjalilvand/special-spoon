"""فاز ۸۶ — آکادمی رز: ویترین فروش دوره در سایت عمومی

چهار تغییر:
- ``courses``: ستون‌های ``cover_image_url`` و ``trailer_url`` (ویترین عمومی).
- ``course_sessions``: ستون‌های ``video_url`` (آدرس mp4/embed — هرگز در
  خروجی عمومی جزئیات نمی‌رود)، ``is_free`` (پیش‌نمایش رایگان) و
  ``release_after_days`` (انتشار پلکانی پس از خرید؛ ۰ = بلافاصله).
- جدول ``academy_order_items``: ردیف‌های سبد خرید — یک سفارش kind='course'
  می‌تواند چند دوره داشته باشد و با «یک» پرداخت درگاه تسویه شود.
- جدول ``academy_watch_progress``: وضعیت تماشای جلسه (mark as watched).
- حذف قید یکتایی ``order_id`` روی ``course_enrollments`` — با سبد خرید،
  چند ثبت‌نام به یک سفارش اشاره می‌کنند (قید یکتایی course+user پابرجاست).

idempotent: همهٔ عملیات با بررسی وجود (کولمن/قید/جدول) تکرارپذیرند.
"""

from alembic import op
import sqlalchemy as sa

revision = "0051_academy_storefront"
down_revision = "0050_site_content_editor"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()

    # ── courses: ویترین عمومی ──
    if not _has_column(bind, "courses", "cover_image_url"):
        op.add_column("courses", sa.Column("cover_image_url", sa.String(length=500), nullable=True))
    if not _has_column(bind, "courses", "trailer_url"):
        op.add_column("courses", sa.Column("trailer_url", sa.String(length=500), nullable=True))

    # ── course_sessions: ویدیو و کنترل آزادسازی ──
    if not _has_column(bind, "course_sessions", "video_url"):
        op.add_column("course_sessions", sa.Column("video_url", sa.String(length=500), nullable=True))
    if not _has_column(bind, "course_sessions", "is_free"):
        op.add_column(
            "course_sessions",
            sa.Column("is_free", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _has_column(bind, "course_sessions", "release_after_days"):
        op.add_column(
            "course_sessions",
            sa.Column("release_after_days", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _has_column(bind, "course_sessions", "description"):
        op.add_column("course_sessions", sa.Column("description", sa.String(length=1000), nullable=True))

    # ── academy_order_items ──
    if not sa.inspect(bind).has_table("academy_order_items"):
        op.create_table(
            "academy_order_items",
            sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "order_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("orders.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "course_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("courses.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("price_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="IRR"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("price_amount >= 0", name="ck_academy_order_items_price_nonneg"),
            sa.UniqueConstraint("order_id", "course_id", name="uq_academy_order_item"),
        )
        op.create_index("ix_academy_order_items_order", "academy_order_items", ["order_id"])
        op.create_index("ix_academy_order_items_course", "academy_order_items", ["course_id"])

    # ── academy_watch_progress ──
    if not sa.inspect(bind).has_table("academy_watch_progress"):
        op.create_table(
            "academy_watch_progress",
            sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "course_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("courses.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "session_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("course_sessions.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("watched", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "session_id", name="uq_academy_watch_progress"),
        )
        op.create_index("ix_academy_watch_progress_user", "academy_watch_progress", ["user_id"])
        op.create_index("ix_academy_watch_progress_course", "academy_watch_progress", ["course_id"])

    # ── سبد خرید: یک سفارش چند ثبت‌نام ──
    # هر قید یکتا روی ستون order_id (هر نامی که داشته باشد) حذف می‌شود؛
    # مهاجرت قدیمی unique=True را با نام خودکار مثل course_enrollments_order_id_key ساخته است.
    insp = sa.inspect(bind)
    for uq in insp.get_unique_constraints("course_enrollments"):
        cols = set(uq.get("column_names", []))
        if cols == {"order_id"}:
            op.drop_constraint(uq["name"], "course_enrollments", type_="unique")

    # ── OTP: هدف «academy» برای ورود خریدار آکادمی ──
    # (هر قید «purpose» قدیمی بدون academy حذف و با قید کامل بازسازى می‌شود)
    old_purposes = [
        c["name"]
        for c in insp.get_check_constraints("otp_challenges")
        if "purpose" in str(c["sqltext"]) and "academy" not in str(c["sqltext"])
    ]
    for name in old_purposes:
        op.drop_constraint(name, "otp_challenges", type_="check")
    if old_purposes:
        op.create_check_constraint(
            "ck_otp_purpose", "otp_challenges", "purpose IN ('booking','login','academy')"
        )


def downgrade() -> None:
    bind = op.get_bind()
    # بازگرداندن قید یکتایی فقط اگر دادهٔ مغایر وجود نداشته باشد
    dup = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM (SELECT order_id FROM course_enrollments "
            "WHERE order_id IS NOT NULL GROUP BY order_id HAVING COUNT(*) > 1) t"
        )
    ).scalar()
    if not dup:
        op.create_unique_constraint(
            "uq_course_enrollments_order_id", "course_enrollments", ["order_id"]
        )
    if sa.inspect(bind).has_table("academy_watch_progress"):
        op.drop_table("academy_watch_progress")
    if sa.inspect(bind).has_table("academy_order_items"):
        op.drop_table("academy_order_items")
    for table, col in (
        ("course_sessions", "description"),
        ("course_sessions", "release_after_days"),
        ("course_sessions", "is_free"),
        ("course_sessions", "video_url"),
        ("courses", "trailer_url"),
        ("courses", "cover_image_url"),
    ):
        if _has_column(bind, table, col):
            op.drop_column(table, col)
