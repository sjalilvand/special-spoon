"""فاز ۶۶ - درج کلینیک‌های شرکت رز و جایگزینی فهرست مشاوران (idempotent).

اجرا (در محیط backend):  python seed_rose_data.py

منابع داده (نسخهٔ منجمد در مخزن):
- backend/rose_seed/clinics.json     — ۳۱ کلینیک استانی (از صفحهٔ رسمی شرکت رز)
- backend/rose_seed/counselors.json  — ۲۱۶ مشاور (فایل «اسامی مشاورین1»)

قواعد:
- کلینیک: یک Clinic با slug=rose + یک Branch منتشرشده به‌ازای هر استان
  (کلید: province_code) — اجرای مجدد فقط به‌روزرسانی می‌کند؛
- مشاوران: upsert بر پایهٔ کد ملی؛ حساب کاربری هر مشاور جدید:
  نام کاربری = کد ملی، رمز عبور اولیه = شماره تماس (در نبود آن، کد ملی)،
  نقش = مشاور، وضعیت = فعال؛ هر مشاور به شعبهٔ استان خود وصل می‌شود؛
- جایگزینی فهرست: مشاوران فعالِ خارج از فهرست فعلی غیرفعال و حسابشان
  غیرفعال می‌شود (حذف فیزیکی نمی‌شوند)؛
- برخلاف ورود اکسل پنل، این seed «رسمی و بخشنده» است: کد ملی با رقم کنترل
  نامعتبر یا موبایل ناموجود (ستاره در فایل) رد نمی‌شود؛ فقط هشدار چاپ
  می‌کند (فهرست رسمی شرکت است).
"""
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select

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
    return count


def seed_counselors(db) -> dict:
    docs = json.loads(COUNSELORS_FILE.read_text(encoding="utf-8"))
    counselor_role = db.get(Role, "COUNSELOR")
    branch_by_code = {
        b.province_code: b
        for b in db.scalars(select(Branch).where(Branch.province_code.isnot(None))).all()
    }

    created = updated = skipped = 0
    warnings: list[str] = []
    listed_nids: set[str] = set()

    for doc in docs:
        nid = (doc.get("national_id") or "").strip()
        full_name = (doc.get("full_name") or "").strip()
        if not nid or not full_name:
            skipped += 1
            warnings.append(f"ردیف بدون کد ملی/نام: {doc}")
            continue
        listed_nids.add(nid)

        mobile = normalize_mobile(doc.get("mobile") or "")
        if doc.get("mobile") and not is_valid_mobile(mobile):
            warnings.append(f"موبایل نامعتبر برای {full_name} ({nid}): {doc.get('mobile')} — ذخیره شد")
            mobile = (doc.get("mobile") or "").strip()
        if not mobile:
            warnings.append(f"بدون موبایل: {full_name} ({nid}) — رمز اولیه = کد ملی")
        password_src = mobile or nid

        branch = branch_by_code.get(doc.get("province_code"))
        first_name, _, last_name = full_name.partition(" ")
        if not last_name:
            last_name = first_name

        c = db.scalars(select(Counselor).where(Counselor.national_id == nid)).first()
        if c is None:
            counselor_code = f"C-{nid}"
            if db.scalar(select(Counselor.id).where(Counselor.counselor_code == counselor_code)):
                skipped += 1
                warnings.append(f"کد مشاور {counselor_code} تکراری است — رد شد: {full_name}")
                continue
            u = User(
                username=nid,
                display_name=full_name,
                status=UserStatus.ACTIVE,
                must_change_password=False,
                mobile=mobile or None,
            )
            u.password_hash = hash_password(password_src)
            if counselor_role is not None:
                u.roles.append(counselor_role)
            db.add(u)
            db.flush()
            c = Counselor(
                counselor_code=counselor_code,
                first_name=first_name,
                last_name=last_name,
                national_id=nid,
                status="active",
                user_id=u.id,
            )
            db.add(c)
            created += 1
        else:
            updated += 1
            if c.user_id:
                u = db.get(User, c.user_id)
                if u is not None:
                    u.display_name = full_name
                    u.mobile = mobile or u.mobile
                    if u.status != UserStatus.ACTIVE:
                        u.status = UserStatus.ACTIVE

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

    # جایگزینی فهرست: مشاوران فعالِ خارج از فهرست جدید غیرفعال می‌شوند
    deactivated: list[str] = []
    others = db.scalars(
        select(Counselor).where(
            Counselor.status == "active",
            Counselor.national_id.notin_(listed_nids) if listed_nids else True,
        )
    ).all()
    for c in others:
        c.status = "inactive"
        deactivated.append(f"{c.first_name} {c.last_name}".strip())
        if c.user_id:
            u = db.get(User, c.user_id)
            if u is not None:
                u.status = UserStatus.DISABLED

    db.flush()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "deactivated": deactivated,
        "warnings": warnings,
    }


def main() -> int:
    if not CLINICS_FILE.is_file() or not COUNSELORS_FILE.is_file():
        print("فایل‌های rose_seed یافت نشد")
        return 1
    db = SessionLocal()
    try:
        n_clinics = seed_clinics(db)
        stats = seed_counselors(db)
        db.commit()
        print(f"[OK] کلینیک‌ها: {n_clinics} شعبهٔ استانی به‌روز شد")
        print(f"[OK] مشاوران: {stats['created']} جدید، {stats['updated']} به‌روز، "
              f"{stats['skipped']} ردشده، {len(stats['deactivated'])} غیرفعال")
        for w in stats["warnings"][:20]:
            print(f"  [هشدار] {w}")
        if stats["deactivated"]:
            print("  غیرفعال‌شده‌ها: " + "، ".join(stats["deactivated"][:20]))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
