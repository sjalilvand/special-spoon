"""فاز ۶۴ - جدول پایهٔ استان‌ها (کد رسمی ۰۱..۳۱) + فیلدهای پروندهٔ مشاور.

Revision ID: 0040_provinces_counselor_fields
Revises: 0039_psych_scales
Create Date: 2026-10-30

- جدول ``provinces``: پایهٔ استان‌های ایران با کد رسمی دو رقمی؛ دادهٔ پایه
  در همین مهاجرت درج می‌شود (۳۱ استان با مرکز و کد تلفن) تا روی هر نصبی
  موجود باشد (هم‌راستا با الگوی مهاجرت 0030 برای مجوزها)؛
- ستون‌های جدید ``counselors``: province_code (کلید خارجی به provinces.code)،
  professional_rank (رتبه حرفه‌ای)، contract_number (شماره قرارداد)،
  sheba_number (شماره شبا) و detailed_code (کد تفضیلی شخص) — مطابق ستون‌های
  فایل ورود مشاوران شرکت رز.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0040_provinces_counselor_fields"
down_revision = "0039_psych_scales"
branch_labels = None
depends_on = None

# (کد، استان، مرکز، کد تلفن) — نسخهٔ منجمد برای مهاجرت (کپی از models/location.py)
PROVINCES: list[tuple[str, str, str, str]] = [
    ("01", "آذربایجان شرقی", "تبریز", "041"),
    ("02", "آذربایجان غربی", "ارومیه", "044"),
    ("03", "اردبیل", "اردبیل", "045"),
    ("04", "اصفهان", "اصفهان", "031"),
    ("05", "البرز", "کرج", "026"),
    ("06", "ایلام", "ایلام", "084"),
    ("07", "بوشهر", "بوشهر", "077"),
    ("08", "تهران", "تهران", "021"),
    ("09", "چهارمحال و بختیاری", "شهرکرد", "038"),
    ("10", "خراسان جنوبی", "بیرجند", "056"),
    ("11", "خراسان رضوی", "مشهد", "051"),
    ("12", "خراسان شمالی", "بجنورد", "058"),
    ("13", "خوزستان", "اهواز", "061"),
    ("14", "زنجان", "زنجان", "024"),
    ("15", "سمنان", "سمنان", "023"),
    ("16", "سیستان و بلوچستان", "زاهدان", "054"),
    ("17", "فارس", "شیراز", "071"),
    ("18", "قزوین", "قزوین", "028"),
    ("19", "قم", "قم", "025"),
    ("20", "کردستان", "سنندج", "087"),
    ("21", "کرمان", "کرمان", "034"),
    ("22", "کرمانشاه", "کرمانشاه", "083"),
    ("23", "کهگیلویه و بویراحمد", "یاسوج", "074"),
    ("24", "گلستان", "گرگان", "017"),
    ("25", "گیلان", "رشت", "013"),
    ("26", "لرستان", "خرم‌آباد", "066"),
    ("27", "مازندران", "ساری", "011"),
    ("28", "مرکزی", "اراک", "086"),
    ("29", "هرمزگان", "بندرعباس", "076"),
    ("30", "همدان", "همدان", "081"),
    ("31", "یزد", "یزد", "035"),
]

provinces_tbl = sa.table(
    "provinces",
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("capital", sa.String),
    sa.column("area_code", sa.String),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
    op.create_table(
        "provinces",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(2), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("capital", sa.String(80), nullable=True),
        sa.Column("area_code", sa.String(5), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_provinces_code", "provinces", ["code"], unique=True)
    op.create_index("ix_provinces_name", "provinces", ["name"], unique=True)
    op.bulk_insert(
        provinces_tbl,
        [
            {"code": c, "name": n, "capital": cap, "area_code": ac, "is_active": True}
            for c, n, cap, ac in PROVINCES
        ],
    )

    op.add_column("counselors", sa.Column("province_code", sa.String(2), nullable=True))
    op.add_column("counselors", sa.Column("professional_rank", sa.String(100), nullable=True))
    op.add_column("counselors", sa.Column("contract_number", sa.String(100), nullable=True))
    op.add_column("counselors", sa.Column("sheba_number", sa.String(34), nullable=True))
    op.add_column("counselors", sa.Column("detailed_code", sa.String(50), nullable=True))
    op.create_index("ix_counselors_province_code", "counselors", ["province_code"])
    op.create_foreign_key(
        "fk_counselors_province_code", "counselors", "provinces",
        ["province_code"], ["code"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_counselors_province_code", "counselors", type_="foreignkey")
    op.drop_index("ix_counselors_province_code", table_name="counselors")
    op.drop_column("counselors", "detailed_code")
    op.drop_column("counselors", "sheba_number")
    op.drop_column("counselors", "contract_number")
    op.drop_column("counselors", "professional_rank")
    op.drop_column("counselors", "province_code")
    op.drop_index("ix_provinces_name", table_name="provinces")
    op.drop_index("ix_provinces_code", table_name="provinces")
    op.drop_table("provinces")
