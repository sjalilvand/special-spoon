"""فاز ۵۸ - درج نمونهٔ «پنل آزمون‌های سازمانی»: شرکت نفت پارس.

اجرا:  python seed_org_program.py  (در محیط backend)
Idempotent: سازمان با slug و برنامه با عنوان یکتا بررسی می‌شود.

- سازمان «شرکت نفت پارس» (slug: pars-oil-co)؛
- برنامهٔ «پروژهٔ ارزیابی سلامت روان و فرسودگی شغلی کارکنان» با:
  * آزمون‌های منتخب شغلی از بانک آزمون (در صورت وجود در بانک)؛
  * راهنمای کامل پروژه؛
  * سوالات پرتکرار (۵ سوال)؛
  * مشاوران: تا ۲ کاربر فعال دارای نقش COUNSELOR (در صورت وجود)؛
  * اعضای نمونه (بدون حساب کاربری — قابل پیوند بعدی از پنل).
"""
import sys
from datetime import date

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.org_contract import Organization
from org_program_seed_data import PROGRAM_FAQS, PROGRAM_GUIDE, PROGRAM_TESTS_SLUGS, PROGRAM_TITLE, MEMBER_SAMPLES
from app.models.org_program import (
    OrgProgram,
    OrgProgramCounselor,
    OrgProgramFaq,
    OrgProgramMember,
    OrgProgramStatus,
    OrgProgramTest,
)
from app.models.psych_test import PsychStatus, PsychTest
from app.models.user import User, UserStatus

ORG_NAME = "شرکت نفت پارس"
ORG_SLUG = "pars-oil-co"


def main() -> int:
    db = SessionLocal()
    try:
        # ---------- سازمان
        org = db.scalars(select(Organization).where(Organization.slug == ORG_SLUG)).first()
        if org is None:
            org = Organization(
                name=ORG_NAME,
                slug=ORG_SLUG,
                phone="021-81234567",
                email="hr@parsoil.demo",
                address="تهران، منطقهٔ ۲۰، مجتمع پتروشیمی پارس",
                note="سازمان نمونهٔ فاز ۵۸ — پنل آزمون‌های سازمانی",
                is_active=True,
            )
            db.add(org)
            db.flush()
            print(f"+ سازمان «{ORG_NAME}» ساخته شد")
        else:
            print(f"~ سازمان «{ORG_NAME}» از قبل موجود است")

        # ---------- آزمون‌های منتخب (فقط منتشرشده)
        tests = []
        for slug in PROGRAM_TESTS_SLUGS:
            t = db.scalars(select(PsychTest).where(PsychTest.slug == slug)).first()
            if t is not None and t.status == PsychStatus.PUBLISHED:
                tests.append(t)
            else:
                print(f"  (آزمون {slug} در بانک نیست/منتشر نشده — رد شد)")
        if not tests:
            print("! هیچ آزمونی از بانک یافت نشد؛ اول -Mode psychseed را اجرا کنید")

        # ---------- برنامهٔ آزمون
        prog = db.scalars(
            select(OrgProgram).where(OrgProgram.organization_id == org.id, OrgProgram.title == PROGRAM_TITLE)
        ).first()
        if prog is None:
            prog = OrgProgram(
                organization_id=org.id,
                title=PROGRAM_TITLE,
                description=(
                    "پروژهٔ سالانهٔ سنجش سلامت روان، فرسودگی شغلی و رضایت شغلی کارکنان "
                    "شرکت نفت پارس — نتایج محرمانه است و صرفاً در قالب گزارش تجمیعی "
                    "به مدیریت منابع انسانی ارائه می‌شود."
                ),
                guide_text=PROGRAM_GUIDE,
                status=OrgProgramStatus.ACTIVE,
                due_date=date(date.today().year, 12, 29),
            )
            db.add(prog)
            db.flush()
            print(f"+ برنامهٔ «{PROGRAM_TITLE}» ساخته شد")
        else:
            print(f"~ برنامهٔ «{PROGRAM_TITLE}» از قبل موجود است")

        # ---------- آزمون‌های برنامه
        existing_test_ids = {
            r.test_id
            for r in db.scalars(select(OrgProgramTest).where(OrgProgramTest.program_id == prog.id)).all()
        }
        added_tests = 0
        for idx, t in enumerate(tests):
            if t.id not in existing_test_ids:
                db.add(OrgProgramTest(program_id=prog.id, test_id=t.id, sort_order=idx))
                added_tests += 1
        print(f"+ آزمون‌های برنامه: {len(existing_test_ids)} موجود + {added_tests} جدید")

        # ---------- سوالات پرتکرار
        if db.scalars(select(OrgProgramFaq).where(OrgProgramFaq.program_id == prog.id)).first() is None:
            for idx, (q, a) in enumerate(PROGRAM_FAQS):
                db.add(OrgProgramFaq(program_id=prog.id, question=q, answer=a, sort_order=idx))
            print(f"+ {len(PROGRAM_FAQS)} سوال پرتکرار درج شد")

        # ---------- مشاوران (کاربران فعال با نقش COUNSELOR)
        users_active = db.scalars(
            select(User).where(User.status == UserStatus.ACTIVE).limit(200)
        ).all()
        counselors = [u for u in users_active if any(r.code == "COUNSELOR" for r in u.roles)]
        existing_c = {
            r.user_id
            for r in db.scalars(
                select(OrgProgramCounselor).where(OrgProgramCounselor.program_id == prog.id)
            ).all()
        }
        added_c = 0
        for u in counselors[:2]:
            if u.id not in existing_c:
                db.add(
                    OrgProgramCounselor(
                        program_id=prog.id,
                        user_id=u.id,
                        role_in_project="مشاور ارشد پروژه" if added_c == 0 else "مشاور پروژه",
                    )
                )
                added_c += 1
        print(f"+ مشاوران پروژه: {added_c} نفر افزوده شد (از {len(counselors)} مشاور فعال سامانه)")

        # ---------- اعضای نمونه (بدون حساب کاربری)
        existing_m = {
            m.full_name
            for m in db.scalars(select(OrgProgramMember).where(OrgProgramMember.program_id == prog.id)).all()
        }
        added_m = 0
        for m in MEMBER_SAMPLES:
            if m["full_name"] not in existing_m:
                db.add(OrgProgramMember(program_id=prog.id, **m))
                added_m += 1
        print(f"+ اعضای نمونه: {added_m} نفر افزوده شد")

        db.commit()
        print("[OK] seed سازمانی کامل شد — پنل «آزمون‌های سازمانی» در دسترس است")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
