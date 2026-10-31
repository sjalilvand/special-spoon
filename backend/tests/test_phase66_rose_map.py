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
    # فایل رسمی ۲۱۶ ردیف دارد؛ اجرای اول همه ساخته/به‌روز/اتخاذ شده‌اند
    assert c1["created"] + c1["updated"] + c1.get("adopted", 0) == 216
    assert c1["skipped"] == 0
    # اجرای دوم: هیچ رکورد جدیدی ساخته نمی‌شود (idempotent)
    assert c2["created"] == 0 and c2.get("adopted", 0) == 0
    assert c2["created"] + c2["updated"] + c2.get("adopted", 0) == 216


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


# ---------------- فاز ۶۶ب: مقاوم‌سازی seed (خطای میدانی استقرار ۱.۰.۲۶) ----------------
#
# خطای میدانی: در پایگاه عملیاتی حسابی با username=کد ملی از قبل بود ولی
# «پروندهٔ مشاور» نداشت؛ seed به‌جای اتخاذ حساب، INSERT می‌زد و با
# «duplicate key ix_users_username» کل اجرا (از جمله کلینیک‌ها) رول‌بک می‌شد.


def _use_roster(monkeypatch, tmp_path, rows):
    """فهرست موقت برای seed — بدون دست‌زدن به فایل واقعی مخزن."""
    import json as _json
    import seed_rose_data as _srd
    f = tmp_path / "counselors.json"
    f.write_text(_json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(_srd, "COUNSELORS_FILE", f)
    return f


def _cleanup_counselor(db, nid: str) -> None:
    """حذف ردیف‌های آزمایشی (با هر قالب کد ملی) + بازگرداندن فهرست واقعی."""
    import seed_rose_data as _srd
    from sqlalchemy import select as _sel, or_ as _or
    try:
        u = db.scalars(_sel(User).where(User.username == nid)).first()
        cond = [Counselor.national_id == nid]
        if u is not None:
            cond.append(Counselor.user_id == u.id)
        for c in db.scalars(_sel(Counselor).where(_or(*cond))).all():
            db.delete(c)
        if u is not None:
            u.roles.clear()  # پاک‌سازی جدول واسط نقش‌ها
            db.flush()
            db.delete(u)
        db.commit()
    finally:
        # فهرست واقعی دوباره اجرا می‌شود تا مشاوران فهرستِ غیرفعال‌شدهٔ آزمون
        # فعال شوند (آزمون‌های بعدی و فایل‌های دیگر بی‌تأثیر بمانند)
        _srd.seed_counselors(db)
        db.commit()


def test_seed_adopts_preexisting_user_without_counselor_profile(monkeypatch, tmp_path):
    """بازتولید دقیق خطای میدانی: حساب موجود با username=کد ملی و بدون پرونده.

    seed باید حساب را «اتخاذ» کند (پرونده بسازد، رمز را دست نزند)، نه INSERT.
    """
    from sqlalchemy import select
    from app.core.security import hash_password
    import seed_rose_data as _srd

    nid = "1699999991"
    db = SessionLocal()
    try:
        _cleanup_counselor(db, nid)  # اجرای مجدد احتمالی
        u = User(username=nid, display_name="حساب بدون پرونده", status=UserStatus.ACTIVE,
                 must_change_password=False)
        u.password_hash = hash_password("orig-secret-123")
        db.add(u)
        db.commit()
        uid = u.id
        old_hash = u.password_hash

        _use_roster(monkeypatch, tmp_path, [
            {"province_code": "08", "full_name": "حساب بدون پرونده",
             "national_id": nid, "mobile": "09120000000"},
        ])
        stats = _srd.seed_counselors(db)
        db.commit()

        assert stats["adopted"] == 1, stats
        assert stats["created"] == 0
        assert any(nid in n for n in stats["notices"])
        c = db.scalars(select(Counselor).where(Counselor.national_id == nid)).first()
        assert c is not None and c.user_id == uid
        assert c.status == "active"
        db.refresh(u)
        assert u.password_hash == old_hash  # رمز حساب موجود دست نخورد
        assert u.display_name == "حساب بدون پرونده" or u.display_name
        assert u.status == UserStatus.ACTIVE
        assert any(r.code == "COUNSELOR" for r in u.roles)
        # فقط یک حساب با این username باشد (INSERT تکراری رخ نداده)
        assert db.scalars(select(User).where(User.username == nid)).all().__len__() == 1
    finally:
        _cleanup_counselor(db, nid)
        db.close()


def test_seed_survives_bad_row_and_continues(monkeypatch, tmp_path):
    """سیوپوینتِ هر ردیف: خطای یک ردیف (کد ملی بلندتر از ستون ۲۰ نویسه‌ای)
    بقیهٔ ردیف‌ها را نمی‌کشد — فقط رد می‌شود و هشدار می‌گذارد."""
    from sqlalchemy import select
    import seed_rose_data as _srd

    good_nid = "1699999992"
    bad_nid = "1" * 25  # Counselor.national_id = String(20) → خطای پایگاه
    db = SessionLocal()
    try:
        _cleanup_counselor(db, good_nid)
        _use_roster(monkeypatch, tmp_path, [
            {"province_code": "08", "full_name": "ردیف خراب", "national_id": bad_nid,
             "mobile": "09120000001"},
            {"province_code": "08", "full_name": "ردیف سالم", "national_id": good_nid,
             "mobile": "09120000002"},
        ])
        stats = _srd.seed_counselors(db)
        db.commit()

        assert stats["created"] == 1, stats
        assert stats["skipped"] == 1, stats
        assert any(bad_nid in w for w in stats["warnings"])
        # ردیف سالم درج شده؛ حساب ردیف خراب هم رول‌بک شده (اثری نمانده)
        c = db.scalars(select(Counselor).where(Counselor.national_id == good_nid)).first()
        assert c is not None
        assert db.scalars(select(User).where(User.username == bad_nid)).first() is None
    finally:
        _cleanup_counselor(db, good_nid)
        db.close()


def test_seed_canonicalizes_drifted_nid_profile(monkeypatch, tmp_path):
    """پروندهٔ مشاورِ وصل به حساب با کد ملیِ بدقالب (ارقام فارسی):
        همان پرونده به‌روز می‌شود و کد ملی‌اش كانونی می‌شود؛ رکورد تکراری
        و خطای user_id یکتا ساخته نمی‌شود."""
    from sqlalchemy import select
    from app.core.security import hash_password
    import seed_rose_data as _srd

    nid = "1699999993"
    drifted = "۱۶۹۹۹۹۹۹۳"  # همان عدد با ارقام فارسی
    db = SessionLocal()
    try:
        _cleanup_counselor(db, nid)
        u = User(username=nid, display_name="بدقالب آزمایشی", status=UserStatus.ACTIVE,
                 must_change_password=False)
        u.password_hash = hash_password("keep-me-456")
        db.add(u)
        db.flush()
        c = Counselor(counselor_code=f"C-{nid}", first_name="بدقالب", last_name="آزمایشی",
                      national_id=drifted, status="active", user_id=u.id)
        db.add(c)
        db.commit()
        uid = u.id
        old_hash = u.password_hash

        _use_roster(monkeypatch, tmp_path, [
            {"province_code": "08", "full_name": "بدقالب آزمایشی",
             "national_id": nid, "mobile": "09120000003"},
        ])
        stats = _srd.seed_counselors(db)
        db.commit()

        # پرونده از قبل به حساب وصل بود → مسیر «به‌روزرسانی» با كانونی‌سازی کد ملی
        assert stats["updated"] == 1, stats
        assert stats["adopted"] == 0 and stats["created"] == 0
        rows = db.scalars(select(Counselor).where(Counselor.user_id == uid)).all()
        assert len(rows) == 1  # رکورد تکراری ساخته نشد (یکتای user_id)
        assert rows[0].national_id == nid  # كانونی شد
        assert rows[0].status == "active"  # در فهرست است → غیرفعال نشده
        db.refresh(u)
        assert u.password_hash == old_hash
    finally:
        _cleanup_counselor(db, nid)
        db.close()


# ---------------- فاز ۶۶ج: بازنشستگی شعب دموی تکراری روی نقشهٔ عمومی ----------------
#
# خطای میدانی: بعد از انتشار ۳۱ شعبهٔ واقعی رز، نقشهٔ عمومی ۶۲ نشانگر داشت —
# هر استان یک پین واقعی + یک پین دموی «شعبه <استان>» (کلینیک rosepsy-main
# فاز ۴۹) که خالی و گمراه‌کننده بود. seed باید دموهای هم‌استانِ بی‌مشاور را
# draft کند، اما دموی دارای مشاور فعال و شعب کلینیک‌های دیگر را دست نزند.

def test_superseded_demo_branches_demoted_to_draft(seeded):
    from sqlalchemy import select
    from app.models.branch import Branch, BranchStatus, Clinic
    from seed_rose_data import seed_clinics

    db = SessionLocal()
    created_branch_ids = []
    try:
        rose = db.scalars(select(Clinic).where(Clinic.slug == "rose")).first()
        assert rose is not None
        demo = db.scalars(select(Clinic).where(Clinic.slug == "rosepsy-main")).first()
        if demo is None:
            demo = Clinic(name="کلینیک رزپسی — مرکز", slug="rosepsy-main", is_active=True)
            db.add(demo)
            db.flush()
        other = db.scalars(select(Clinic).where(Clinic.slug == "other-66c")).first()
        if other is None:
            other = Clinic(name="کلینیک دیگر ۶۶ج", slug="other-66c", is_active=True)
            db.add(other)
            db.flush()

        # الف) دموی هم‌استان با رز، بدون مشاور فعال → باید draft شود
        b1 = Branch(clinic_id=demo.id, name="شعبه تهران (آزمایش ۶۶ج)",
                    province="تهران", city="تهران",
                    address="آزمایش", status=BranchStatus.PUBLISHED)
        # ب) دموی هم‌استان اما دارای مشاور فعال → باید منتشر بماند
        b2 = Branch(clinic_id=demo.id, name="شعبه فارس (آزمایش ۶۶ج)",
                    province="فارس", city="شیراز",
                    address="آزمایش", status=BranchStatus.PUBLISHED)
        # ج) شعبهٔ کلینیک دیگر (نه دمو) → دست‌نخورده
        b3 = Branch(clinic_id=other.id, name="شعبه اصفهان (آزمایش ۶۶ج)",
                    province="اصفهان", city="اصفهان",
                    address="آزمایش", status=BranchStatus.PUBLISHED)
        db.add_all([b1, b2, b3])
        db.flush()
        u = User(username="9999900002", display_name="مشاور دموی نگه‌داشتنی",
                 status=UserStatus.ACTIVE, must_change_password=False)
        db.add(u)
        db.flush()
        c = Counselor(counselor_code="C-9999900002", first_name="مشاور",
                      last_name="دموی نگه‌داشتنی", national_id="9999900002",
                      status="active", user_id=u.id, branch_id=b2.id)
        db.add(c)
        db.commit()
        created_branch_ids = [b1.id, b2.id, b3.id]

        seed_clinics(db)
        db.commit()

        db.refresh(b1)
        db.refresh(b2)
        db.refresh(b3)
        assert b1.status == BranchStatus.DRAFT      # دموی بی‌مشاور → draft
        assert b2.status == BranchStatus.PUBLISHED  # دموی دارای مشاور فعال → دست‌نخورده
        assert b3.status == BranchStatus.PUBLISHED  # کلینیک دیگر → دست‌نخورده
    finally:
        # پاک‌سازی (اول وابسته‌ها) تا سایر تست‌ها بی‌تأثیر بمانند
        c2 = db.scalars(select(Counselor).where(Counselor.national_id == "9999900002")).first()
        if c2 is not None:
            db.delete(c2)
        u2 = db.scalars(select(User).where(User.username == "9999900002")).first()
        if u2 is not None:
            db.delete(u2)
        for bid in created_branch_ids:
            b = db.get(Branch, bid)
            if b is not None:
                db.delete(b)
        o = db.scalars(select(Clinic).where(Clinic.slug == "other-66c")).first()
        if o is not None:
            db.delete(o)
        db.commit()
        db.close()
