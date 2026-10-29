"""فاز ۶۱ - فرم‌ساز و نظرسنجی + تماس تلفنی مدیریت‌شده

Revision ID: 0037_form_builder_calls
Revises: 0036_jalali_date_repair
Create Date: 2026-10-30

- جدول ``form_templates`` (تعریف فرم توسط مدیر + JSONB فیلدها)؛
- جدول ``form_responses`` (پاسخ‌ها؛ قابل اتصال به تماس)؛
- جدول ``call_sessions`` (تماس تلفنی مدیریت‌شده با چرخهٔ ringing/ongoing/ended)؛
- دسترسی جدید ``forms.manage`` (بخش «فرم‌ها») → نقش‌های ORG_MANAGER و
  SYSTEM_ADMIN — idempotent؛ ماتریس گرافیکی پنل ملاک بعدی است؛
- سه فرم نمونهٔ پیش‌فرض (idempotent با ON CONFLICT DO NOTHING):
    1) نظرسنجی رضایت از تماس تلفنی — نظرسنجیِ پیش‌فرض پس از پایان تماس؛
    2) فرم پذیرش اولیهٔ مراجعان تلفنی (RS-PS-01-01)؛
    3) فرم ارزیابی و مدیریت مورد حاد/پرخطر (RS-PS-08-01).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0037_form_builder_calls"
down_revision = "0036_jalali_date_repair"
branch_labels = None
depends_on = None

PERM_CODE = "forms.manage"
PERM_SECTION = "فرم‌ها"
PERM_TITLE = "فرم‌ساز و مدیریت نظرسنجی‌ها"
PERM_SORT = 1
DEFAULT_ROLES = ("ORG_MANAGER", "SYSTEM_ADMIN")


SEED_FORMS = [
    {
        "code": "call-satisfaction-survey",
        "title": "نظرسنجی رضایت از تماس تلفنی",
        "description": "پس از پایان هر تماس تلفنی برای مراجع نمایش داده می‌شود.",
        "kind": "survey",
        "is_default_call_survey": True,
        "fields": [
            {"id": "f_quality", "type": "rating", "label": "کیفیت کلی مشاورهٔ تلفنی را چقدر ارزیابی می‌کنید؟", "required": True},
            {"id": "f_prof", "type": "radio", "label": "آیا مشاور رفتار حرفه‌ای و محترمانه داشت؟", "required": True, "options": ["بله", "نسبتاً", "خیر"]},
            {"id": "f_time", "type": "yesno", "label": "آیا تماس در زمان مناسب انجام شد؟", "required": True},
            {"id": "f_followup", "type": "yesno", "label": "آیا تمایل به تماس پیگیری دارید؟", "required": False},
            {"id": "f_note", "type": "textarea", "label": "نظرات و پیشنهادهای خود را بنویسید", "required": False, "help": "پاسخ شما محرمانه است."},
        ],
    },
    {
        "code": "phone-intake-form",
        "title": "فرم پذیرش اولیهٔ مراجعان تلفنی",
        "description": "مطابق فرم کاغذی RS-PS-01-01 مرکز.",
        "kind": "intake",
        "is_default_call_survey": False,
        "fields": [
            {"id": "f_name", "type": "text", "label": "نام و نام خانوادگی", "required": True},
            {"id": "f_age", "type": "number", "label": "سن", "required": True},
            {"id": "f_nid", "type": "text", "label": "کد ملی", "required": False},
            {"id": "f_phone", "type": "text", "label": "شماره تماس", "required": True},
            {"id": "f_province", "type": "text", "label": "استان", "required": True},
            {"id": "f_city", "type": "text", "label": "شهرستان", "required": False},
            {"id": "f_gender", "type": "radio", "label": "جنسیت", "required": True, "options": ["زن", "مرد"]},
            {"id": "f_reftype", "type": "select", "label": "نوع مراجع", "required": False, "options": ["مددجو آزاد", "معرفی‌شده", "سایر"]},
            {"id": "f_subject", "type": "checkbox", "label": "موضوع مراجعه", "required": True, "options": ["خانواده", "فردی", "ازدواج", "کودک و نوجوان", "تحصیلی", "بحران", "سایر"]},
            {"id": "f_desc", "type": "textarea", "label": "شرح مختصر مشکل و اقدامات انجام‌شده", "required": False},
            {"id": "f_counselor", "type": "text", "label": "نام مشاور", "required": False},
            {"id": "f_call_date", "type": "date", "label": "تاریخ تماس", "required": False},
        ],
    },
    {
        "code": "acute-case-form",
        "title": "فرم ارزیابی و مدیریت مورد حاد / پرخطر",
        "description": "مطابق فرم کاغذی RS-PS-08-01 مرکز.",
        "kind": "custom",
        "is_default_call_survey": False,
        "fields": [
            {"id": "h1", "type": "heading", "label": "اطلاعات فردی", "required": False},
            {"id": "f_name", "type": "text", "label": "نام و نام خانوادگی", "required": True},
            {"id": "f_age", "type": "number", "label": "سن", "required": True},
            {"id": "f_nid", "type": "text", "label": "کد ملی", "required": False},
            {"id": "f_phone", "type": "text", "label": "شماره تماس", "required": True},
            {"id": "f_province", "type": "text", "label": "استان", "required": False},
            {"id": "f_city", "type": "text", "label": "شهرستان", "required": False},
            {"id": "f_addr", "type": "textarea", "label": "آدرس", "required": False},
            {"id": "h2", "type": "heading", "label": "ارزیابی اولیه", "required": False},
            {"id": "f_case_code", "type": "text", "label": "کد مورد حاد", "required": False},
            {"id": "f_risk", "type": "checkbox", "label": "نوع خطر", "required": True, "options": ["افکار خودکشی یا آسیب به خود", "قصد یا اقدام به خودکشی", "آسیب به دیگران", "کودک‌آزاری", "خشونت", "بحران شدید", "سایر"]},
            {"id": "f_severity", "type": "radio", "label": "شدت و فوریت", "required": True, "options": ["سطح ۱ (نیازمند پایش)", "سطح ۲ (متوسط)", "سطح ۳ (بالا)"]},
            {"id": "f_danger_now", "type": "textarea", "label": "افکار یا رفتار خطرناک فعلی", "required": False},
            {"id": "f_history", "type": "textarea", "label": "سابقهٔ قبلی (اختلال روانپزشکی، بستری، اقدام به خودکشی)", "required": False},
            {"id": "f_riskfactors", "type": "textarea", "label": "عوامل خطر، برنامه، قصد یا دسترسی به وسیله", "required": False},
            {"id": "f_protective", "type": "textarea", "label": "عوامل محافظت‌کننده و حمایت در دسترس", "required": False},
            {"id": "f_action", "type": "textarea", "label": "اقدام فوری انجام‌شده", "required": False},
            {"id": "h3", "type": "heading", "label": "اطلاعات ارجاع", "required": False},
            {"id": "f_ref_resp", "type": "text", "label": "مسئول اطلاع‌رسانی یا ارجاع", "required": False},
            {"id": "f_ref_time", "type": "text", "label": "روز و ساعت ارجاع", "required": False},
            {"id": "f_ref_dest", "type": "text", "label": "مرجع ارجاع‌شده", "required": False},
            {"id": "f_ref_result", "type": "textarea", "label": "نتیجهٔ تماس و پذیرش مقصد", "required": False},
            {"id": "f_follow_resp", "type": "text", "label": "مسئول پیگیری", "required": False},
            {"id": "f_follow_time", "type": "text", "label": "زمان پیگیری", "required": False},
            {"id": "f_final", "type": "text", "label": "وضعیت نهایی", "required": False},
        ],
    },
]


def upgrade() -> None:
    op.create_table(
        "form_templates",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="custom"),
        sa.Column("fields", pg.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "is_default_call_survey", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_by",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('survey','intake','custom')", name="ck_form_templates_kind"),
    )

    op.create_table(
        "call_sessions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "caller_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "callee_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="ringing"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "survey_template_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("form_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("end_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('ringing','ongoing','ended','declined','cancelled')",
            name="ck_call_sessions_status",
        ),
    )
    op.create_index("ix_call_sessions_callee_status", "call_sessions", ["callee_id", "status"])
    op.create_index("ix_call_sessions_caller_status", "call_sessions", ["caller_id", "status"])

    op.create_table(
        "form_responses",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("form_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "respondent_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subject_user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "call_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("call_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("answers", pg.JSONB(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_form_responses_template", "form_responses", ["template_id"])
    op.create_index("ix_form_responses_respondent", "form_responses", ["respondent_id"])
    op.create_index("ix_form_responses_call", "form_responses", ["call_id"])

    # --- seed دسترسی جدید + اعطای پیش‌فرض (idempotent) ---
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO permissions (code, section, title, sort) "
            "VALUES (:c, :s, :t, :o) ON CONFLICT (code) DO NOTHING"
        ),
        {"c": PERM_CODE, "s": PERM_SECTION, "t": PERM_TITLE, "o": PERM_SORT},
    )
    for role in DEFAULT_ROLES:
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_code, permission_code) "
                "VALUES (:r, :c) ON CONFLICT (role_code, permission_code) DO NOTHING"
            ),
            {"r": role, "c": PERM_CODE},
        )

    # --- سه فرم نمونهٔ پیش‌فرض (idempotent) ---
    import json
    for form in SEED_FORMS:
        conn.execute(
            sa.text(
                "INSERT INTO form_templates (code, title, description, kind, fields, is_active, is_default_call_survey) "
                "VALUES (:code, :title, :desc, :kind, :fields, true, :dflt) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {
                "code": form["code"],
                "title": form["title"],
                "desc": form["description"],
                "kind": form["kind"],
                "fields": json.dumps(form["fields"], ensure_ascii=False),
                "dflt": form["is_default_call_survey"],
            },
        )


def downgrade() -> None:
    op.drop_table("form_responses")
    op.drop_table("call_sessions")
    op.drop_table("form_templates")
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_code = :c"), {"c": PERM_CODE})
    conn.execute(sa.text("DELETE FROM permissions WHERE code = :c"), {"c": PERM_CODE})
