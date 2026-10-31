"""فاز ۶۶ - درج کلینیک‌های شرکت رز و جایگزینی فهرست مشاوران (idempotent).

اجرا (در محیط backend):  python seed_rose_data.py

منابع داده (نسخهٔ منجمد در مخزن):
- backend/rose_seed/clinics.json     — ۳۱ کلینیک استانی (از صفحهٔ رسمی شرکت رز)
- backend/rose_seed/counselors.json  — ۲۱۶ مشاور (فایل «اسامی مشاورین1»)

قواعد:
- کلینیک: یک Clinic با slug=rose + یک Branch منتشرشده به‌ازای هر استان
  (کلید: province_code) — اجرای مجدد فقط به‌روزرسانی می‌کند و «قبل از» مشاوران
  در تراکنش جداگانه کامیت می‌شود تا نقشهٔ سایت حتی در خطای بخش مشاوران هم
  به‌روز بماند؛
- مشاوران: upsert بر پایهٔ کد ملی (نرمال‌سازی ارقام فارسی/عربی)؛
  حساب کاربری هر مشاور جدید: نام کاربری = کد ملی، رمز عبور اولیه = شماره تماس
  (در نبود آن، کد ملی)، نقش = مشاور، وضعیت = فعال؛ هر مشاور به شعبهٔ استان
  خود وصل می‌شود؛
- پذیرش حساب موجود (فاز ۶۶ب — رفع خطای میدانی ۱.۰.۲۶): اگر کاربری با
  username = کد ملی از قبل موجود باشد ولی «پروندهٔ مشاور» نداشته باشد، به‌جای
  INSERT (که با ix_users_username تضاد می‌گیرد) همان حساب «اتخاذ» می‌شود:
  پروندهٔ مشاور به آن وصل می‌گردد، نام/موبایل/نقش/وضعیت به‌روز می‌شود ولی
  «رمز عبور دست نمی‌خورد»؛ اگر پروندهٔ مشاور همان حساب با کد ملیِ بدقالب
  (ارقام فارسی و…) موجود باشد، همان پرونده به‌روز و کد ملی‌اش كانونی می‌شود؛
- جایگزینی فهرست: مشاوران فعالِ خارج از فهرست فعلی غیرفعال و حسابشان
  غیرفعال می‌شود (حذف فیزیکی نمی‌شوند)؛ مقایسه با نرمال‌سازی ارقام در پایتون
  انجام می‌شود تا کد ملی‌های بدقالب در پایگاه به‌اشتباه غیرفعال نشوند؛
- هر ردیف در «سیوپوینت» جدا اجرا می‌شود؛ خطای یک ردیف بقیهٔ ۲۱۵ ردیف را
  نمی‌کشد و فقط هشدار می‌گذارد؛
- بازنشستگی شعب دمو (فاز ۶۶ج): شعب نمونهٔ «شعبه <استان>» کلینیک دمو
  (slug=rosepsy-main، فاز ۴۹) که با انتشار شعب واقعی رز نشانگرِ تکراری و
  خالی روی نقشهٔ عمومی می‌ساختند — هر شعبهٔ منتشرشدهٔ آن کلینیک در استانی
  که شعبهٔ واقعی رز دارد و «هیچ مشاور فعالی» ندارد، به draft برمی‌گردد
  (بدون حذف؛ کاملاً بازگشت‌پذیر از پنل)؛
- برخلاف ورود اکسل پنل، این seed «رسمی و بخشنده» است: کد ملی با رقم کنترل
  نامعتبر یا موبایل ناموجود (ستاره در فایل) رد نمی‌شود؛ فقط هشدار چاپ
  می‌کند (فهرست رسمی شرکت است).
"""
import json
import os
import sys
from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.dates import normalize_digits
from app.core.security import hash_password
from app.models.branch import Branch, BranchStatus, Clinic
from app.models.location import IRAN_PROVINCE_SEED, Province
from app.models.people import Counselor
from app.models.user import Role, User, UserStatus
from app.services.otp import is_valid_mobile, normalize_mobile
from app.db.session import SessionLocal

# ۱.۰.۲۵: CWD در upgrade برابر $AppDir است؛ برای یافتن .env و مسیرهای نسبی
# به دایرکتوری backend برمی‌گردیم (مثل اجرای داخل Push-Location)
os.chdir(Path(__file__).resolve().parent)

SEED_DIR = Path(__file__).resolve().parent / "rose_seed"
CLINICS_FILE = SEED_DIR / "clinics.json"
COUNSELORS_FILE = SEED_DIR / "counselors.json"

ROSE_CLINIC_SLUG = "rose"
ROSE_CLINIC_NAME = "شرکت مشاوره رز"

MAX_WARNINGS_PRINTED = 20


def _norm_nid(value) -> str:
    """کد ملی كانونی: ارقام فارسی/عربی→انگلیسی، حذف فاصله‌ها و نویسه‌های میانی."""
    return normalize_digits(str(value or "")).replace(" ", "").replace("\u200c", "").strip()


def _ensure_provinces(db) -> dict[str, Province]:
    """جدول استان‌ها باید از مهاجرت 0040 پر شده باشد؛ در نبودش از شاخهٔ کد ساخته می‌شود."""
    provs = {p.code: p for p in db.scalars(select(Province)).all()}
    for code, name, capital, area_code in IRAN_PROVINCE_SEED:
        if code not in provs:
            p = Province(code=code, name=name, capital=capital, area_code=area_code)
            db.add(p)
            db.flush()
            provs[code] = p
    return provs


def _ensure_clinic(db) -> Clinic:
    c = db.scalars(select(Clinic).where(Clinic.slug == ROSE_CLINIC_SLUG)).first()
    if c is None:
        c = Clinic(
            name=ROSE_CLINIC_NAME,
            slug=ROSE_CLINIC_SLUG,
            description="شبکهٔ کلینیک‌های مشاورهٔ شرکت رز در ۳۱ استان کشور",
            is_active=True,
        )
        db.add(c)
        db.flush()
    return c


DEMO_CLINIC_SLUG = "rosepsy-main"  # کلینیک دموی فاز ۴۹ (seed_demo_rich)


def retire_superseded_demo_branches(db, rose_clinic: Clinic) -> int:
    """فاز ۶۶ج — بازنشستگی شعب دموی هم‌استان با شعب واقعی رز.

    seed_demo_rich برای کلینیک دمو (slug=rosepsy-main) در هر استان یک شعبهٔ
    نمونهٔ «شعبه <استان>» منتشر می‌کند. حالا که ۳۱ شعبهٔ واقعی شرکت رز منتشر
    شده‌اند، این شعب نمایشی باعث ۶۲ نشانگر روی نقشهٔ عمومی می‌شوند (هر استان
    یک پین واقعی + یک پین دموی خالی). قاعدهٔ بازنشستگی (همه با هم):
      ۱) منتشرشده باشد؛
      ۲) کلینیکِ مالکش دمو باشد (slug=rosepsy-main) — نه هیچ کلینیک دیگری؛
      ۳) استانش در پوشش شعب واقعی رز باشد؛
      ۴) هیچ مشاور فعالی به آن متصل نباشد.
    نتیجه: status=draft (حذف فیزیکی نیست؛ از پنل قابل بازگشت است).
    """
    rose_provs = {
        b.province for b in db.scalars(
            select(Branch).where(Branch.clinic_id == rose_clinic.id)
        ).all() if b.province
    }
    if not rose_provs:
        return 0
    has_active_counselor = exists(
        select(1).select_from(Counselor).where(
            Counselor.branch_id == Branch.id, Counselor.status == "active"
        )
    )
    superseded = db.scalars(
        select(Branch).where(
            Branch.status == BranchStatus.PUBLISHED,
            Branch.clinic_id != rose_clinic.id,
            Branch.province.in_(rose_provs),
            ~has_active_counselor,
            Branch.clinic.has(Clinic.slug == DEMO_CLINIC_SLUG),
        )
    ).unique().all()
    for b in superseded:
        b.status = BranchStatus.DRAFT
    if superseded:
        db.flush()
        print(f"[OK] شعب دموی جایگزین‌شده به draft: {len(superseded)}")
    return len(superseded)


def seed_clinics(db) -> int:
    docs = json.loads(CLINICS_FILE.read_text(encoding="utf-8"))
    provs = _ensure_provinces(db)
    clinic = _ensure_clinic(db)

    count = 0
    for doc in docs:
        code = doc["province_code"]
        if code not in provs:
            print(f"  [هشدار] استان با کد {code} در جدول پایه نیست — رد شد")
            continue
        b = db.scalars(
            select(Branch).where(Branch.clinic_id == clinic.id, Branch.province_code == code)
        ).first()
        if b is None:
            # سازگاری با نصب‌های قدیمی: جست‌وجو بر اساس نام پیش‌فرض
            b = db.scalars(
                select(Branch).where(Branch.clinic_id == clinic.id, Branch.name == doc["name"])
            ).first()
        if b is None:
            b = Branch(clinic_id=clinic.id, status=BranchStatus.PUBLISHED)
            db.add(b)
        b.name = doc["name"]
        b.province = doc["province_name"]
        b.province_code = code
        b.city = doc.get("city")
        b.address = doc.get("address")
        b.postal_code = doc.get("postal_code")
        b.phone = doc.get("phone")
        b.working_hours = {"text": doc.get("working_hours")} if doc.get("working_hours") else None
        b.latitude = doc.get("latitude")
        b.longitude = doc.get("longitude")
        b.manager_name = doc.get("manager_name")
        b.manager_phone = doc.get("manager_phone")
        b.exec_name = doc.get("exec_name")
        b.exec_phone = doc.get("exec_phone")
        b.map_url = doc.get("map_url")
        b.status = BranchStatus.PUBLISHED
        count += 1
    db.flush()
    retire_superseded_demo_branches(db, clinic)
    return count


def _find_counselor_by_nid(db, nid: str) -> Counselor | None:
    return db.scalars(select(Counselor).where(Counselor.national_id == nid)).first()


def _find_user_by_username(db, username: str) -> User | None:
    return db.scalars(select(User).where(User.username == username)).first()


def _ensure_counselor_role(db, u: User, counselor_role: Role | None) -> None:
    if counselor_role is not None and all(r.code != counselor_role.code for r in u.roles):
        u.roles.append(counselor_role)


def _adopt_or_attach_user(db, u_pre: User | None, nid: str, full_name: str, mobile: str | None,
                          password_src: str, counselor_role: Role | None) -> tuple[User, bool]:
    """حساب کاربری ردیف را برمی‌گرداند؛ خروجی دوم = «اتخاذ حساب موجود» است.

    - اگر حسابی با username=کد ملی موجود باشد همان اتخاذ می‌شود (رمزش دست
      نمی‌خورد) — ریشهٔ خطای میدانی «duplicate key ix_users_username»؛
    - وگرنه حساب جدید با رمز اولیه ساخته می‌شود.
    """
    if u_pre is not None:
        u_pre.display_name = full_name
        if mobile and is_valid_mobile(mobile):
            u_pre.mobile = mobile
        if u_pre.status != UserStatus.ACTIVE:
            u_pre.status = UserStatus.ACTIVE
        _ensure_counselor_role(db, u_pre, counselor_role)
        return u_pre, True
    u = User(
        username=nid,
        display_name=full_name,
        status=UserStatus.ACTIVE,
        must_change_password=False,
        mobile=mobile or None,
    )
    u.password_hash = hash_password(password_src)
    _ensure_counselor_role(db, u, counselor_role)
    db.add(u)
    db.flush()
    return u, False


def _process_counselor_row(db, doc: dict, branch_by_code: dict, counselor_role: Role | None,
                           stats: dict) -> str:
    """یک ردیف فهرست را پردازش می‌کند؛ خروجی = نام کامل ردیف.

    خطاها به فراخوان پرتاب می‌شوند تا در سیوپوینتِ همان ردیف رول‌بک شوند.
    """
    nid = _norm_nid(doc.get("national_id"))
    full_name = (doc.get("full_name") or "").strip()
    if not nid or not full_name:
        stats["skipped"] += 1
        stats["warnings"].append(f"ردیف بدون کد ملی/نام: {doc}")
        return ""

    mobile = normalize_mobile(doc.get("mobile") or "")
    if doc.get("mobile") and not is_valid_mobile(mobile):
        stats["warnings"].append(f"موبایل نامعتبر برای {full_name} ({nid}): {doc.get('mobile')} — ذخیره شد")
        mobile = (doc.get("mobile") or "").strip()
    if not mobile:
        stats["warnings"].append(f"بدون موبایل: {full_name} ({nid}) — رمز اولیه = کد ملی")
    password_src = mobile or nid

    branch = branch_by_code.get(doc.get("province_code"))
    first_name, _, last_name = full_name.partition(" ")
    if not last_name:
        last_name = first_name

    # ۱) پروندهٔ مشاور با کد ملی كانونی
    c = _find_counselor_by_nid(db, nid)
    u_pre = _find_user_by_username(db, nid)

    if c is None and u_pre is not None:
        # ۲) پروندهٔ همان حساب با کد ملیِ بدقالب (ارقام فارسی و…)
        c = db.scalars(select(Counselor).where(Counselor.user_id == u_pre.id)).first()

    outcome: str | None = None  # created / adopted / updated — فقط بعد از flush موفق
    if c is None:
        # ۳) رکورد کاملاً جدید (یا اتخاذ حساب بی‌پرونده)
        counselor_code = f"C-{nid}"
        if db.scalar(select(Counselor.id).where(Counselor.counselor_code == counselor_code)):
            stats["skipped"] += 1
            stats["warnings"].append(f"کد مشاور {counselor_code} تکراری است — رد شد: {full_name}")
            return ""
        u, was_adopted = _adopt_or_attach_user(
            db, u_pre, nid, full_name, mobile or None, password_src, counselor_role,
        )
        c = Counselor(
            counselor_code=counselor_code,
            first_name=first_name,
            last_name=last_name,
            national_id=nid,
            status="active",
            user_id=u.id,
        )
        db.add(c)
        db.flush()
        outcome = "adopted" if was_adopted else "created"
        if was_adopted:
            stats["notices"].append(
                f"حساب موجود {nid} ({full_name}) اتخاذ شد — پروندهٔ مشاور ساخته شد؛ رمز قبلی حفظ شد"
            )
    else:
        # ۴) پروندهٔ موجود: حسابش را تضمین کن (user_id خالی/یتیم هم هندل می‌شود)
        u = db.get(User, c.user_id) if c.user_id else None
        if u is None:
            u, was_adopted = _adopt_or_attach_user(
                db, u_pre, nid, full_name, mobile or None, password_src, counselor_role,
            )
            c.user_id = u.id
            outcome = "adopted" if was_adopted else "created"
            if was_adopted:
                stats["notices"].append(
                    f"حساب موجود {nid} ({full_name}) به پروندهٔ مشاور وصل شد؛ رمز قبلی حفظ شد"
                )
        else:
            u.display_name = full_name
            if mobile and is_valid_mobile(mobile):
                u.mobile = mobile
            if u.status != UserStatus.ACTIVE:
                u.status = UserStatus.ACTIVE
            _ensure_counselor_role(db, u, counselor_role)
            outcome = "updated"
        # کد ملی بدقالب در پایگاه كانونی می‌شود (مقایسهٔ جایگزینی هم درست می‌شود)
        if c.national_id != nid:
            c.national_id = nid

    # جایگزینی کامل فیلدها با نسخهٔ رسمی جدید (semantics: جایگزین)
    c.first_name = first_name
    c.last_name = last_name
    c.degree = doc.get("degree")
    c.license_number = doc.get("license_number")
    c.professional_rank = doc.get("professional_rank")
    c.contract_number = doc.get("contract_number")
    c.detailed_code = doc.get("detailed_code")
    c.province_code = doc.get("province_code")
    c.work_mobile = mobile or None
    c.branch_id = branch.id if branch is not None else None
    if c.status != "active":
        c.status = "active"
    db.flush()
    # شمارش فقط بعد از flush موفق — ردیفِ خطاخورده در آمار «ساخته/به‌روز» نمی‌رود
    if outcome is not None:
        stats[outcome] += 1
    return full_name


def seed_counselors(db) -> dict:
    docs = json.loads(COUNSELORS_FILE.read_text(encoding="utf-8"))
    counselor_role = db.get(Role, "COUNSELOR")
    branch_by_code = {
        b.province_code: b
        for b in db.scalars(select(Branch).where(Branch.province_code.isnot(None))).all()
    }

    stats = {
        "created": 0,
        "updated": 0,
        "adopted": 0,
        "skipped": 0,
        "deactivated": [],
        "warnings": [],
        "notices": [],
    }
    listed_nids: set[str] = set()

    for doc in docs:
        nid = _norm_nid(doc.get("national_id"))
        if nid:
            # حتی اگر پردازش ردیف خطا بخورد، این شخص «در فهرست» است و نباید
            # غیرفعال شود (فقط هشدار می‌گیرد)
            listed_nids.add(nid)
        # فاز ۶۶ب: سیوپوینت هر ردیف — خطای یک ردیف کل اجرا را نمی‌کشد
        try:
            with db.begin_nested():
                _process_counselor_row(db, doc, branch_by_code, counselor_role, stats)
        except SQLAlchemyError as exc:
            stats["skipped"] += 1
            name = (doc.get("full_name") or "?").strip()
            stats["warnings"].append(f"ردیف {name} ({nid or '?'}) درج نشد: {exc.__class__.__name__}")
        except Exception as exc:  # noqa: BLE001 — بخشندگی: هر خطای ردیفی فقط هشدار
            stats["skipped"] += 1
            name = (doc.get("full_name") or "?").strip()
            stats["warnings"].append(f"ردیف {name} ({nid or '?'}) خطای غیرمنتظره: {exc}")

    # جایگزینی فهرست: مشاوران فعالِ خارج از فهرست جدید غیرفعال می‌شوند.
    # مقایسه در پایتون با نرمال‌سازی ارقام — کد ملی بدقالب در پایگاه باعث
    # غیرفعال‌سازی اشتباه نمی‌شود؛ ردیف بدون کد ملی دست‌نخورده می‌ماند.
    others = db.scalars(select(Counselor).where(Counselor.status == "active")).all()
    for c in others:
        cnid = _norm_nid(c.national_id)
        if not cnid or cnid in listed_nids:
            continue
        c.status = "inactive"
        stats["deactivated"].append(f"{c.first_name} {c.last_name}".strip())
        if c.user_id:
            u = db.get(User, c.user_id)
            if u is not None:
                u.status = UserStatus.DISABLED

    db.flush()
    return stats


def main() -> int:
    if not CLINICS_FILE.is_file() or not COUNSELORS_FILE.is_file():
        print("فایل‌های rose_seed یافت نشد")
        return 1
    db = SessionLocal()
    try:
        # فاز ۶۶ب: کلینیک‌ها در تراکنش جداگانه و «قبل از» مشاوران کامیت می‌شوند
        # تا نقشهٔ سایت حتی در خطای بخش مشاوران هم به‌روز بماند
        n_clinics = seed_clinics(db)
        db.commit()
        print(f"[OK] کلینیک‌ها: {n_clinics} شعبهٔ استانی به‌روز شد")

        stats = seed_counselors(db)
        db.commit()
        print(f"[OK] مشاوران: {stats['created']} جدید، {stats['updated']} به‌روز، "
              f"{stats['adopted']} اتخاذحساب‌شده، {stats['skipped']} ردشده، "
              f"{len(stats['deactivated'])} غیرفعال")
        for n in stats["notices"][:MAX_WARNINGS_PRINTED]:
            print(f"  [اتخاذ] {n}")
        for w in stats["warnings"][:MAX_WARNINGS_PRINTED]:
            print(f"  [هشدار] {w}")
        if len(stats["warnings"]) > MAX_WARNINGS_PRINTED:
            print(f"  … و {len(stats['warnings']) - MAX_WARNINGS_PRINTED} هشدار دیگر")
        if stats["deactivated"]:
            print("  غیرفعال‌شده‌ها: " + "، ".join(stats["deactivated"][:MAX_WARNINGS_PRINTED]))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
