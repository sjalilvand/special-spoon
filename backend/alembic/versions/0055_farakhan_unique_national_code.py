"""فاز ۹۳ — فراخوان همکاری: جلوگیری از ثبت‌نام تکراری با یک کد ملی.

خواستهٔ صاحب سامانه: «مشخص‌کنندهٔ تکرار بودن کد ملی در صورت وجود».
- endpoint عمومی GET /farakhan/check-national-code برای نشان زندهٔ فرم
- وارسی پیش از ذخیره در POST /farakhan/submissions با پیام فارسی اختصاصی
- ایندکس یکتای جزئی ``ux_farakhan_nc_active`` روی national_code فقط برای
  ثبت‌نام‌های «فعال» (status <> 'rejected') به‌عنوان پشتیبانِ هم‌زمانی:
  دو درخواستِ هم‌زمان با یک کد ملی هر دو از وارسی پیش از ذخیره می‌گذرند و
  همین ایندکس دومی را در سطح پایگاه‌داده رد می‌کند.
- ثبت‌نامِ «ردشده» مستثنا است تا متقاضیِ ردشده بتواند دوباره ثبت‌نام کند
  (جریان کاری جذب نیرو؛ endpoint حذف رکورد وجود ندارد).

ایندکس idempotent با IF NOT EXISTS (الگوی مایگریشن‌های 0050+).
اگر پیش از اعمال، رکورد فعالِ تکراری با یک کد ملی موجود باشد، ارتقا با پیام
روشن فارسی متوقف می‌شود تا دادهٔ تکراری نخست رسیدگی شود (حذف/رد کردن در پنل).
"""

from alembic import op
import sqlalchemy as sa

revision = "0055_farakhan_unique_national_code"
down_revision = "0054_case_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dup = bind.execute(sa.text(
        "SELECT national_code, COUNT(*) AS c FROM farakhan_submissions "
        "WHERE status <> 'rejected' GROUP BY national_code "
        "HAVING COUNT(*) > 1 ORDER BY c DESC LIMIT 1"
    )).first()
    if dup is not None:
        raise RuntimeError(
            f"فاز ۹۳: ساخت ایندکس یکتای کد ملی ممکن نیست — ثبت‌نام‌های فعالِ تکراری با "
            f"کد ملی «{dup[0]}» ({dup[1]} رکورد) موجود است؛ ابتدا در پنل فراخوان "
            "رسیدگی کنید (یکی را رد کنید و بعد ارتقا را دوباره اجرا کنید)."
        )
    op.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_farakhan_nc_active '
        "ON farakhan_submissions (national_code) WHERE status <> 'rejected'"
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ux_farakhan_nc_active')
