"""داده آزمایشی ساختگی - بند ۱۸ سند.

اجرا:  docker compose run --rm api python seed_demo.py
"""
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.people import Applicant, Counselor, OrganizationUnit, ServiceLocation
from app.models.user import Role, User, UserStatus


def main() -> int:
    db = SessionLocal()
    try:
        if db.scalar(select(OrganizationUnit).where(OrganizationUnit.code == "U1")) is not None:
            print("داده آزمایشی قبلاً ایجاد شده است.")
            return 0
        u1 = OrganizationUnit(code="U1", title="واحد اداری")
        u2 = OrganizationUnit(code="U2", title="واحد تولید")
        l1 = ServiceLocation(code="L1", title="کلینیک مرکزی", address="نشانی نمونه")
        l2 = ServiceLocation(code="L2", title="کلینیک شعبه دو")
        db.add_all([u1, u2, l1, l2])
        db.flush()

        c = Counselor(
            counselor_code="C-1001", first_name="سارا", last_name="محمدی",
            professional_title="روان‌شناس", degree="کارشناسی ارشد", specialty="بالینی",
            capacity=8, status="active", service_location_id=l1.id,
        )
        db.add(c)
        db.flush()

        a1 = Applicant(external_id="EXT-2001", employee_code="1024", national_id="0012345678",
                       first_name="علی", last_name="رضایی", mobile="09121234567",
                       unit_id=u1.id, service_location_id=l1.id, status="active", record_source="manual")
        a2 = Applicant(external_id="EXT-2002", employee_code="1025", national_id="0023456789",
                       first_name="مریم", last_name="کریمی", unit_id=u2.id, status="active", record_source="manual")
        db.add_all([a1, a2])

        acc = User(username="counselor1", display_name="سارا محمدی",
                   status=UserStatus.PENDING, must_change_password=True)
        acc.roles.append(db.get(Role, "COUNSELOR"))
        db.add(acc)
        db.flush()
        c.user_id = acc.id

        db.commit()
        print("داده آزمایشی ایجاد شد:")
        print("  واحدها: U1, U2 | محل‌های خدمت: L1, L2")
        print("  مشاور: C-1001 (حساب pending: counselor1)")
        print("  متقاضیان: EXT-2001, EXT-2002")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
