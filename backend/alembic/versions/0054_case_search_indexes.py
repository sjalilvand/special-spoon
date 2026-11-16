"""فاز ۸۹ — ایندکس جست‌وجوی متقاضیان برای تشکیل پرونده در حجم بالا (حدود ۲ میلیون ردیف).

- ``ix_applicants_org_lastname`` روی (organization_id, last_name):
  فیلتر سازمان + مرتب‌سازی نام‌خانوادگی در انتخاب متقاضی، بدون full-scan/sort.
- ``ix_applicants_lastname`` روی (last_name):
  مرتب‌سازی پیش‌فرض گزینه‌ها (بدون فیلتر سازمان) را index-scan می‌کند.

idempotent با IF NOT EXISTS (الگوی مایگریشن‌های 0050+).
"""

from alembic import op

revision = "0054_case_search_indexes"
down_revision = "0053_farakhan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_applicants_org_lastname '
        'ON applicants (organization_id, last_name)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_applicants_lastname '
        'ON applicants (last_name)'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_applicants_lastname')
    op.execute('DROP INDEX IF EXISTS ix_applicants_org_lastname')
