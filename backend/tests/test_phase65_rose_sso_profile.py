"""فاز ۶۵ - انتقال مشخصات کامل کاربر از رز هاب در ورود یکپارچه (SSO).

توکن رز هاب حالا علاوه بر email/name/role/nationalId، ``mobile``،
``province``، ``provinceCode`` و ``clinic`` را هم حمل می‌کند؛ این آزمون‌ها
رفتار سرتاسری ``GET /api/v1/auth/rose-sso`` را با توکن واقعاً امضاشده
بررسی می‌کنند:

- ساخت حساب + پروندهٔ مشاور با کد ملی، موبایل، استان (حل کد رسمی از نام)
  و کلینک؛
- ورود دوم با مشخصات تغییر‌یافته → بروزرسانی بدون ساختن پروندهٔ تکراری؛
- پروندهٔ موجود اکسل (کد ملی یکسان) → همان پرونده پیدا و متصل می‌شود.
"""
import uuid

import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.branch import Branch, Clinic
from app.models.people import Counselor
from app.models.user import User

settings = get_settings()


def _make_ardabil_branch(db) -> Branch:
    """شعبهٔ کلینیک اردبیل (فاز ۶۶) — برای آزمون اتصال خودکار شعبه."""
    clinic = db.scalar(select(Clinic).where(Clinic.slug == "rose-ardabil-test"))
    if clinic is None:
        clinic = Clinic(name="کلینیک رز اردبیل آزمون", slug="rose-ardabil-test")
        db.add(clinic)
        db.flush()
    branch = db.scalar(select(Branch).where(Branch.province_code == "03"))
    if branch is None:
        branch = Branch(
            clinic_id=clinic.id,
            name="کلینیک مرکزی رز — اردبیل",
            province_code="03",
            status="published",
        )
        db.add(branch)
        db.commit()
        db.refresh(branch)
    return branch

EMAIL = "5550001111@rose.ir"
NID = "5550001111"


def _hub_token(**overrides) -> str:
    """توکن SSO با همان قواعد رز هاب (HS256 با clientSecret رز سای)."""
    claims = {
        "iss": "rose-hub",
        "aud": settings.rose_hub_client_id,
        "sub": "test-hub-user-1",
        "email": EMAIL,
        "name": "پری ملکی گلندوز",
        "role": "THERAPIST",
        "nationalId": NID,
        "mobile": "09147446047",
        "province": "اردبیل",
        "provinceCode": "009006",  # کد غیررسمی فایل شرکت — باید از نام حل شود
        "clinic": "کلینیک رز اردبیل",
        "systemId": "sys-x",
        "systemName": "رز سای",
        "scope": "sso-launch",
    }
    claims.update(overrides)
    return jwt.encode(
        claims,
        settings.rose_hub_client_secret,
        algorithm="HS256",
    )


def test_rose_sso_creates_user_and_counselor_profile(client):
    db = SessionLocal()
    try:
        branch = _make_ardabil_branch(db)
    finally:
        db.close()

    r = client.get("/api/v1/auth/rose-sso", params={"sso_token": _hub_token()}, follow_redirects=False)
    assert r.status_code == 303, r.text

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == EMAIL))
        assert user is not None
        assert user.display_name == "پری ملکی گلندوز"
        assert user.mobile == "09147446047"
        assert any(role.code == "COUNSELOR" for role in user.roles)

        counselor = db.scalar(select(Counselor).where(Counselor.national_id == NID))
        assert counselor is not None
        assert counselor.first_name == "پری"
        assert counselor.last_name == "ملکی گلندوز"
        assert counselor.work_mobile == "09147446047"
        assert counselor.province_code == "03"  # اردبیل — حل‌شده از نام استان
        assert counselor.clinic == "کلینیک رز اردبیل"
        assert counselor.branch_id == branch.id  # اتصال به شعبهٔ کلینیک استان
        assert str(counselor.user_id) == str(user.id)
    finally:
        db.close()


def test_rose_sso_updates_profile_without_duplicate(client):
    # ورود اول
    r1 = client.get("/api/v1/auth/rose-sso", params={"sso_token": _hub_token()}, follow_redirects=False)
    assert r1.status_code == 303
    # ورود دوم با کلینک و موبایل تغییر‌یافته
    r2 = client.get(
        "/api/v1/auth/rose-sso",
        params={"sso_token": _hub_token(clinic="کلینیک رز تهران", mobile="09121111111")},
        follow_redirects=False,
    )
    assert r2.status_code == 303

    db = SessionLocal()
    try:
        counselors = db.scalars(select(Counselor).where(Counselor.national_id == NID)).all()
        assert len(counselors) == 1
        assert counselors[0].clinic == "کلینیک رز تهران"
        assert counselors[0].work_mobile == "09121111111"
        users = db.scalars(select(User).where(User.email == EMAIL)).all()
        assert len(users) == 1
    finally:
        db.close()


def test_rose_sso_links_existing_excel_counselor(client):
    """پروندهٔ واردشده از اکسل (بدون حساب) با کد ملی یکسان پیدا و متصل می‌شود."""
    db = SessionLocal()
    nid2 = f"777{uuid.uuid4().int % 1000000:07d}"
    try:
        pre = Counselor(
            counselor_code=f"C-{nid2}",
            first_name="شهاب",
            last_name="ولی زاده شفق",
            status="active",
        )
        db.add(pre)
        db.commit()

        email2 = f"{nid2}@rose.ir"
        r = client.get(
            "/api/v1/auth/rose-sso",
            params={"sso_token": _hub_token(
                email=email2,
                nationalId=nid2,
                name="شهاب ولی زاده شفق",
                province="اردبیل",
                provinceCode="",
            )},
            follow_redirects=False,
        )
        assert r.status_code == 303

        db.expire_all()
        user2 = db.scalar(select(User).where(User.email == email2))
        assert user2 is not None
        db.refresh(pre)
        assert str(pre.user_id) == str(user2.id)
        assert pre.national_id == nid2
        assert pre.province_code == "03"
        assert pre.branch_id is not None  # اتصال به شعبهٔ استان از نام استان
        assert pre.work_mobile == "09147446047"
    finally:
        db.close()
