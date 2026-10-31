"""فاز ۶۶ - نقشهٔ کلینیک‌های رز + جایگزینی فهرست مشاوران (seed_rose_data).

- seed کلینیک‌ها: ۳۱ شعبهٔ استانی منتشرشده (idempotent)؛
- seed مشاوران: upsert ۲۱۶ ردیف بر پایهٔ کد ملی + ساخت حساب فعال
  (username=کد ملی، رمز=موبایل) + اتصال به شعبهٔ استان؛
- جایگزینی فهرست: مشاور فعالِ خارج از فهرست غیرفعال و حسابش disabled می‌شود؛
- اجرای دوباره: هیچ رکورد تکراری ساخته نمی‌شود (created=0)؛
- /branches/public/clinics-map بدون احراز هویت کار می‌کند و مشاورانِ
  هر کلینیک را برمی‌گرداند.
"""
import pytest

from conftest import login
from app.db.session import SessionLocal
from app.models.people import Counselor
from app.models.user import User, UserStatus
from seed_rose_data import seed_clinics, seed_counselors


@pytest.fixture(scope="module")
def seeded():
    """دو بار اجرا برای اطمینان از idempotent بودن."""
    db = SessionLocal()
    stats1 = {}
    stats1["clinics"] = seed_clinics(db)
    stats1["counselors"] = seed_counselors(db)
    db.commit()
    stats2 = {}
    stats2["clinics"] = seed_clinics(db)
    stats2["counselors"] = seed_counselors(db)
    db.commit()
    db.close()
    return stats1, stats2


def test_seed_clinics_idempotent(seeded):
    s1, s2 = seeded
    assert s1["clinics"] == 31
    assert s2["clinics"] == 31  # اجرای دوباره همان ۳۱ شعبه را به‌روز می‌کند


def test_seed_counselors_upsert_and_replace(seeded):
    s1, s2 = seeded
    c1 = s1["counselors"]
    c2 = s2["counselors"]
    # فایل رسمی ۲۱۶ ردیف دارد؛ اجرای اول همه ساخته/به‌روز شده‌اند
    assert c1["created"] + c1["updated"] == 216
    assert c1["skipped"] == 0
    # اجرای دوم: هیچ رکورد جدیدی ساخته نمی‌شود (idempotent)
    assert c2["created"] == 0
    assert c2["created"] + c2["updated"] == 216


def test_replacement_deactivates_missing_counselor(seeded):
    """مشاوری که در فهرست رسمی نیست، غیرفعال و حسابش disabled می‌شود."""
    s1, _s2 = seeded
    db = SessionLocal()
    try:
        # مشاور آزمایشی خارج از فهرست
        u = User(username="9999900001", display_name="مشاور حذف‌شدنی",
                 status=UserStatus.ACTIVE, must_change_password=False)
        db.add(u)
        db.flush()
        c = Counselor(counselor_code="C-9999900001", first_name="مشاور", last_name="حذف‌شدنی",
                      national_id="9999900001", status="active", user_id=u.id)
        db.add(c)
        db.commit()

        seed_counselors(db)
        db.commit()

        db.refresh(c)
        db.refresh(u)
        assert c.status == "inactive"
        assert u.status == UserStatus.DISABLED
        assert any("حذف‌شدنی" in d for d in s1["counselors"]["deactivated"]) or c.status == "inactive"
    finally:
        # پاک‌سازی تا سایر تست‌ها بی‌تأثیر بمانند
        from sqlalchemy import select
        c2 = db.scalars(
            select(Counselor).where(Counselor.national_id == "9999900001")
        ).first()
        if c2 is not None:
            db.delete(c2)
        u2 = db.scalars(select(User).where(User.username == "9999900001")).first()
        if u2 is not None:
            db.delete(u2)
        db.commit()
        db.close()


def test_public_clinics_map(client, seeded):
    r = client.get("/api/v1/public/clinics-map")
    assert r.status_code == 200, r.text
    data = r.json()
    # فقط شعب کلینیک «رز» (تست‌های دیگر ممکن است کلینیک/شعبهٔ خودشان را ساخته باشند)
    rose = [x for x in data["items"] if x["clinic_name"] == "شرکت مشاوره رز"]
    assert len(rose) == 31
    assert sum(x["counselor_count"] for x in rose) == 216
    by_prov = {x["province_code"]: x for x in rose}
    # تهران: ۲۵ مشاور + ۵ نفر ستاد = ۳۰
    assert by_prov["08"]["counselor_count"] == 30
    assert by_prov["08"]["manager_name"] == "حامد طالب نژاد"
    assert by_prov["08"]["address"]
    assert by_prov["08"]["map_url"]
    names = [c["name"] for c in by_prov["08"]["counselors"]]
    assert any("الهام رمضان لواسانی" in n for n in names)
    # استان‌های بدون مشاور هم روی نقشه‌اند (کلینیک موجود، مشاور صفر)
    assert by_prov["09"]["counselor_count"] == 0


def test_new_counselor_can_login_with_mobile_password(client, seeded):
    """حساب مشاور جدید: username=کد ملی، رمز اولیه=شماره تماس، نقش مشاور، فعال."""
    from sqlalchemy import select
    token = login(client, "1639818146", "09147446047")  # پری ملکی گلندوز (اردبیل)
    assert token
    db = SessionLocal()
    try:
        u = db.scalars(select(User).where(User.username == "1639818146")).first()
        assert u is not None
        assert u.status == UserStatus.ACTIVE
        assert any(r.code == "COUNSELOR" for r in u.roles)
    finally:
        db.close()
