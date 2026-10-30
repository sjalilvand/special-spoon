"""فاز ۶۴ - ورود گروهی مشاوران از فایل اکسل شرکت رز.

قالب ستون‌ها دقیقاً همان فایل «اسامی مشاورین» است:
    استان | نام و نام خانوادگی | مدرک تحصیلی | پروانه اشتغال | رتبه حرفه‌ای |
    شماره قرارداد | کد استانها | کد تفضیلی شخص | شماره شباء بانکی | کد ملی |
    شماره تماس

قواعد:
- کلید یکتایی ردیف «کد ملی» است؛ اگر مشاور با همین کد ملی موجود باشد،
  ردیف به‌روزرسانی می‌شود (وگرنه ایجاد)؛
- برای هر مشاورِ جدید یک حساب کاربری فعال ساخته می‌شود:
  نام کاربری = کد ملی، رمز عبور = شماره تماس (موبایل)، نقش = مشاور؛
- «کد استانها» باید در جدول پایهٔ استان‌ها (کد رسمی ۰۱..۳۱) موجود باشد؛
  اگر کد خالی باشد، نام استان به کد نگاشت می‌شود؛
- هیچ فرمولی در فایل پذیرفته نمی‌شود؛ سقف ۵۰۰۰ ردیف و ۵ مگابایت.
"""
import io
import re
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dates import normalize_digits
from app.core.security import hash_password
from app.models.location import IRAN_PROVINCE_SEED, Province
from app.models.people import Counselor
from app.models.user import Role, User, UserStatus
from app.services.audit import record_audit
from app.services.otp import is_valid_mobile, normalize_mobile

MAX_ROWS = 5000
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_LISTED_ERRORS = 200

# ترتیب و عنوان دقیق ستون‌های فایل مرجع
COLUMNS: list[str] = [
    "استان",
    "نام و نام خانوادگی",
    "مدرک تحصیلی",
    "پروانه اشتغال",
    "رتبه حرفه ای",
    "شماره قرارداد",
    "کد استانها",
    "کد تفضیلی شخص",
    "شماره شباء بانکی",
    "کد ملی",
    "شماره تماس",
]
# ستون‌هایی که باید «متن» بخوانند (حفظ صفر ابتدایی کد ملی/استان/شبا/تماس)
TEXT_COLUMNS = {"کد استانها", "کد ملی", "شماره تماس", "شماره شباء بانکی", "پروانه اشتغال", "شماره قرارداد", "کد تفضیلی شخص"}

REQUIRED_HEADERS = {"نام و نام خانوادگی", "کد ملی", "شماره تماس"}
RESOLVABLE = {"کد استانها", "استان"}  # حداقل یکی از این دو باید باشد

RULES = [
    "ردیف اول شیت «مشخصات مشاوره ها» عنوان ستون‌هاست؛ حذف یا جابه‌جا نشود.",
    "ستون‌های کد ملی، کد استان، شماره تماس و شبا باید قالب «متن» باشند تا صفر ابتدایی حفظ شود.",
    "کد ملی باید ۱۰ رقم و معتبر (رقم کنترل) باشد؛ کلید یکتایی ردیف‌ها همان کد ملی است.",
    "اگر مشاوری با کد ملی تکراری موجود باشد، اطلاعات او به‌روزرسانی می‌شود (ایجاد نشدن رکورد تکراری).",
    "کد استان باید از جدول پایهٔ استان‌ها باشد (شیت راهنما)؛ اگر خالی باشد از ستون «استان» استفاده می‌شود.",
    "شماره تماس باید موبایل ۱۱ رقمی با ۰۹ باشد؛ برای مشاورِ جدید، نام کاربری حساب = کد ملی و رمز عبور اولیه = همین شماره تماس است.",
    "شماره شبا (در صورت درج) باید با IR شروع شود و ۲۶ نویسه باشد.",
    "در سلول‌ها فرمول ننویسید؛ حداکثر ۵۰۰۰ ردیف و ۵ مگابایت.",
]

COLUMN_HELP: list[tuple[str, str, str]] = [
    ("استان", "اختیاری", "نام استان — اگر «کد استانها» خالی باشد ملاک است"),
    ("نام و نام خانوادگی", "الزامی", "نام و نام خانوادگی مشاور؛ کلمهٔ اول = نام"),
    ("مدرک تحصیلی", "اختیاری", "مثال: کارشناسی ارشد روان‌شناسی بالینی"),
    ("پروانه اشتغال", "اختیاری", "شماره پروانهٔ اشتغال به کار - قالب متن"),
    ("رتبه حرفه ای", "اختیاری", "رتبهٔ حرفه‌ای نظام روان‌شناسی (یک/دو/سه)"),
    ("شماره قرارداد", "اختیاری", "شماره قرارداد همکاری - قالب متن"),
    ("کد استانها", "شرطی", "کد رسمی استان ۰۱ تا ۳۱ (شیت راهنما)؛ حداقل این یا ستون «استان»"),
    ("کد تفضیلی شخص", "اختیاری", "کد تفضیلی/داخلی شخص در شرکت"),
    ("شماره شباء بانکی", "اختیاری", "IR + ۲۴ رقم (مجموعاً ۲۶ نویسه)"),
    ("کد ملی", "الزامی و یکتا", "کد ملی ۱۰ رقمی معتبر - کلید یکتایی ردیف"),
    ("شماره تماس", "الزامی", "موبایل ۱۱ رقمی با ۰۹ - رمز اولیهٔ حساب مشاور جدید"),
]

_PERSIAN_YK = str.maketrans({"ي": "ی", "ك": "ک", "\u200c": "", "‌": ""})
_WS = re.compile(r"\s+")


def normalize_header(value: Any) -> str:
    """یکسان‌سازی عنوان ستون: ارقام فارسی→انگلیسی، ي/ك، حذف نیم‌فاصله، فشرده‌سازی فاصله."""
    s = normalize_digits(str(value or "")).translate(_PERSIAN_YK)
    return _WS.sub(" ", s).strip()


def normalize_province_code(value: Any) -> str | None:
    """'8'، '08'، 8.0، '۰۸' → '08'؛ نامعتبر → None."""
    if value is None:
        return None
    s = normalize_digits(str(value)).strip()
    if s.endswith(".0"):
        s = s[:-2]
    s = s.strip()
    if not s.isdigit() or not (1 <= len(s) <= 2):
        return None
    return s.zfill(2)


def is_valid_national_id(nid: str) -> bool:
    """کد ملی ۱۰ رقمی ایرانی با رقم کنترل."""
    if not (len(nid) == 10 and nid.isdigit()):
        return False
    if len(set(nid)) == 1:  # ۰۰۰۰۰۰۰۰۰۰ و امثال آن
        return False
    check = int(nid[-1])
    s = sum(int(nid[i]) * (10 - i) for i in range(9)) % 11
    return check == s if s < 2 else check == 11 - s


def is_valid_sheba(value: str) -> bool:
    s = value.replace(" ", "").upper()
    return bool(re.fullmatch(r"IR\d{24}", s))


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


# ---------------- قالب اکسل ----------------

def build_template() -> bytes:
    """قالب ورود مشاوران: شیت «مشخصات مشاوره ها» (فقط سرستون) + شیت «راهنما»."""
    wb = Workbook()
    ws = wb.active
    ws.title = "مشخصات مشاوره ها"
    ws.sheet_view.rightToLeft = True
    ws.append(COLUMNS)
    bold = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="4472C4")
    for cell in ws[1]:
        cell.font = bold
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 24
    for idx, name in enumerate(COLUMNS, start=1):
        letter = get_column_letter(idx)
        ws.column_dimensions[letter].width = 20 if name != "نام و نام خانوادگی" else 28
        if name in TEXT_COLUMNS:
            for r in range(2, 300):
                ws.cell(row=r, column=idx).number_format = "@"

    guide = wb.create_sheet("راهنما")
    guide.sheet_view.rightToLeft = True
    guide.column_dimensions["A"].width = 24
    guide.column_dimensions["B"].width = 18
    guide.column_dimensions["C"].width = 95
    title = guide.cell(row=1, column=1, value="قالب ورود گروهی مشاوران — سامانه Rosepsy (فاز ۶۴)")
    title.font = Font(bold=True, size=13)
    guide.append([])
    guide.append(["قواعد کلی:"])
    for rule in RULES:
        guide.append(["", "", rule])
    guide.append([])
    guide.append(["ستون", "الزام", "توضیح"])
    for c in guide[guide.max_row]:
        c.font = Font(bold=True)
    for name, req, desc in COLUMN_HELP:
        guide.append([name, req, desc])
    guide.append([])
    guide.append(["نمونهٔ ردیف پرشده (فقط برای دیدن؛ در فایل اصلی درج نکنید):"])
    guide.append([
        "تهران", "نمونه تستی رضایی", "کارشناسی ارشد روان‌شناسی بالینی", "12345",
        "یک", "RZ-1403-001", "08", "D-1001", "IR000000000000000000000001",
        _example_national_id(), "09121234567",
    ])
    guide.append([])
    guide.append(["کد", "استان", "مرکز"])
    for c in guide[guide.max_row]:
        c.font = Font(bold=True)
    for code, name, cap, _ac in IRAN_PROVINCE_SEED:
        guide.append([code, name, cap])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _example_national_id() -> str:
    """کد ملی معتبر نمونه برای شیت راهنما (رقم کنترل محاسبه‌شده)."""
    base = "0012345678"
    s = sum(int(base[i]) * (10 - i) for i in range(9)) % 11
    check = s if s < 2 else 11 - s
    return base + str(check)


# ---------------- خواندن فایل ----------------

def parse_file(data: bytes) -> tuple[list[dict], str | None]:
    """بررسی سطح فایل + استخراج ردیف‌ها به‌صورت dict با کلیدهای انگلیسی."""
    if len(data) > MAX_FILE_SIZE:
        return [], "حجم فایل بیش از ۵ مگابایت است"
    if not data.startswith(b"PK"):
        return [], "فایل باید xlsx باشد"
    try:
        wb = load_workbook(io.BytesIO(data), data_only=False, read_only=False)
    except Exception:
        return [], "فایل قابل خواندن نیست؛ فقط xlsx معتبر است"
    if not (1 <= len(wb.sheetnames) <= 5):
        return [], "تعداد شیت‌های فایل مجاز نیست (حداکثر ۵ شیت)"
    ws = wb.worksheets[0]
    if ws.max_row and ws.max_row > MAX_ROWS + 1:
        return [], f"تعداد ردیف‌ها بیش از سقف {MAX_ROWS} است"

    headers: list[str] = []
    for cell in ws[1]:
        headers.append(normalize_header(cell.value) if cell.value is not None else "")
    present = {h for h in headers if h}
    missing = REQUIRED_HEADERS - present
    if missing:
        return [], "عنوان ستون‌های الزامی یافت نشد: " + "، ".join(sorted(missing)) + "؛ قالب نمونه را دانلود کنید"
    if not (present & RESOLVABLE):
        return [], "حداقل یکی از ستون‌های «کد استانها» یا «استان» باید موجود باشد"

    idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        if h in COLUMNS and h not in idx:
            idx[h] = i

    rows: list[dict] = []
    for r in range(2, (ws.max_row or 1) + 1):
        values: dict[str, Any] = {}
        has_formula = False
        formula_cols: list[str] = []
        empty = True
        for name, i in idx.items():
            cell = ws.cell(row=r, column=i + 1)
            v = cell.value
            if v is None or (isinstance(v, str) and not v.strip()):
                values[name] = None
                continue
            empty = False
            if cell.data_type == "f" or (isinstance(v, str) and v.startswith("=")):
                has_formula = True
                formula_cols.append(name)
                values[name] = None
                continue
            v = normalize_digits(str(v)).strip() if isinstance(v, (str, int, float)) else str(v).strip()
            values[name] = v or None
        if empty:
            continue
        rows.append({"row_number": r, "has_formula": has_formula,
                     "formula_cols": formula_cols, "values": values})
    return rows, None


# ---------------- اعتبارسنجی و درج/به‌روزرسانی ----------------

def _norm_province_name(s: str) -> str:
    return _WS.sub(" ", s.translate(_PERSIAN_YK)).strip()


def validate_and_upsert(db: Session, rows: list[dict], actor, upload_name: str | None = None) -> dict:
    """اعتبارسنجی ردیف‌ها + ایجاد/به‌روزرسانی مشاور و حساب کاربری."""
    counselor_role = db.get(Role, "COUNSELOR")
    errors: list[dict] = []
    created = updated = failed = 0
    seen_nids: set[str] = set()

    provinces_cache = {p.code: p for p in db.scalars(select(Province)).all()}
    name_to_code = {_norm_province_name(p.name): p.code for p in provinces_cache.values()}

    for row in rows:
        r = row["row_number"]
        v = row["values"]
        row_errors: list[str] = []
        if row["has_formula"]:
            row_errors.append("سلول فرمول در ستون‌های " + "، ".join(row["formula_cols"]) + " مجاز نیست")

        full_name = (v.get("نام و نام خانوادگی") or "").strip()
        nid = normalize_digits(v.get("کد ملی") or "").strip()
        phone_raw = v.get("شماره تماس")

        if not full_name:
            row_errors.append("«نام و نام خانوادگی» خالی است")
        if not nid:
            row_errors.append("«کد ملی» خالی است")
        elif not is_valid_national_id(nid):
            row_errors.append("کد ملی معتبر نیست (باید ۱۰ رقم با رقم کنترل درست باشد)")
        elif nid in seen_nids:
            row_errors.append("این کد ملی در ردیف‌های قبلی همین فایل آمده است (تکراری)")
        seen_nids.add(nid)

        mobile = normalize_mobile(phone_raw or "")
        if not is_valid_mobile(mobile):
            row_errors.append("«شماره تماس» باید موبایل ۱۱ رقمی با ۰۹ باشد (نمونه: 09121234567)")

        sheba_raw = (v.get("شماره شباء بانکی") or "").replace(" ", "")
        if sheba_raw and not is_valid_sheba(sheba_raw):
            row_errors.append("شماره شبا معتبر نیست (IR + ۲۴ رقم)")

        # استان
        province_code = None
        code_raw = normalize_province_code(v.get("کد استانها"))
        name_norm = _norm_province_name(v.get("استان") or "")
        if code_raw is not None and code_raw not in provinces_cache:
            row_errors.append(f"کد استان «{code_raw}» در جدول پایهٔ استان‌ها نیست (۰۱ تا ۳۱)")
        if v.get("استان") and name_norm not in name_to_code:
            row_errors.append(f"نام استان «{v.get('استان')}» در جدول پایه یافت نشد")
        if code_raw is None and not v.get("استان"):
            row_errors.append("کد استان یا نام استان باید درج شود")
        if code_raw in provinces_cache and name_norm in name_to_code and name_to_code[name_norm] != code_raw:
            row_errors.append(f"کد استان ({code_raw}) با نام استان درج‌شده همخوان نیست")
        if code_raw in provinces_cache:
            province_code = code_raw
        elif name_norm in name_to_code:
            province_code = name_to_code[name_norm]

        if row_errors:
            failed += 1
            errors.append({"row": r, "message": "؛ ".join(row_errors)})
            continue

        first_name, last_name = _split_name(full_name)
        degree = v.get("مدرک تحصیلی")
        license_number = v.get("پروانه اشتغال")
        professional_rank = v.get("رتبه حرفه ای")
        contract_number = v.get("شماره قرارداد")
        detailed_code = v.get("کد تفضیلی شخص")

        c = db.scalar(select(Counselor).where(Counselor.national_id == nid))
        if c is None:
            counselor_code = f"C-{nid}"
            if db.scalar(select(Counselor).where(Counselor.counselor_code == counselor_code)):
                failed += 1
                errors.append({"row": r, "message": f"کد مشاور «{counselor_code}» قبلاً برای شخص دیگری ثبت شده است"})
                continue
            u = User(
                username=nid,
                display_name=full_name,
                status=UserStatus.ACTIVE,
                must_change_password=False,
                mobile=mobile,
            )
            u.password_hash = hash_password(mobile)
            u.roles.append(counselor_role)
            db.add(u)
            db.flush()
            c = Counselor(
                counselor_code=counselor_code,
                first_name=first_name,
                last_name=last_name,
                national_id=nid,
                degree=degree,
                license_number=license_number,
                professional_rank=professional_rank,
                contract_number=contract_number,
                detailed_code=detailed_code,
                sheba_number=sheba_raw or None,
                province_code=province_code,
                work_mobile=mobile,
                status="active",
                user_id=u.id,
            )
            db.add(c)
            db.flush()
            created += 1
        else:
            c.first_name = first_name
            c.last_name = last_name
            c.degree = degree or c.degree
            c.license_number = license_number or c.license_number
            c.professional_rank = professional_rank or c.professional_rank
            c.contract_number = contract_number or c.contract_number
            c.detailed_code = detailed_code or c.detailed_code
            c.sheba_number = sheba_raw or c.sheba_number
            c.province_code = province_code or c.province_code
            c.work_mobile = mobile
            if c.user_id:
                u = db.get(User, c.user_id)
                if u is not None:
                    u.display_name = full_name
                    u.mobile = mobile
            updated += 1

    db.commit()
    record_audit(
        db,
        action="counselor.imported",
        actor_user_id=actor.id,
        detail={"file": upload_name or "", "created": created, "updated": updated, "failed": failed},
    )
    return {
        "total": len(rows),
        "created": created,
        "updated": updated,
        "failed": failed,
        "errors": errors[:MAX_LISTED_ERRORS],
    }
