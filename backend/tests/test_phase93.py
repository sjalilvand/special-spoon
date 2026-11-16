"""فاز ۹۳ — فراخوان همکاری: پنج چک خواسته‌شدهٔ صاحب سامانه روی فرم عمومی.

چک‌لیست اعلامی کاربر (پیام فارسی، ۱۷ آبان):
1) الگوریتم کد ملی (جمع وزنی ۹ رقم اول × ۱۰..۲ به پیمانهٔ ۱۱ و رقم کنترل) —
   سمت سرور از فاز ۸۸ موجود بود؛ اکنون endpoint عمومی وارسی زنده هم دارد و
   کلاینت همان الگوریتم را پیش‌آزمون می‌کند (بازهٔ سن تقویم هم زیر).
2) حداقل سن ثبت‌نام ۱۸ سال (سن تکمیل‌شده)
3) حداکثر سن ثبت‌نام ۸۰ سال (سن تکمیل‌شده)
4) مشخص‌کنندهٔ تکراری بودن کد ملی: وارسی پیش از ذخیره + endpoint عمومی
   + ایندکس یکتای جزئی (فقط ثبت‌نام فعال؛ ردشده اجازهٔ ثبت مجدد می‌دهد)
5) نمایش ثبت‌نام‌شده‌ها در جدول پنل — همان endpoint فهرست (آزمون جریان کامل)
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone

from conftest import bearer, login, next_national_code

META_URL = "/api/v1/farakhan/meta"


def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 30, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF"


def _jpg_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (30, 200, 90)).save(buf, format="JPEG")
    return buf.getvalue()


def _meta_and_captcha(client):
    m = client.get(META_URL).json()
    sid = m["session_id"]
    cap = client.get("/api/v1/farakhan/captcha").json()
    from app.api.v1.farakhan import _peek_captcha_answer

    answer = str(_peek_captcha_answer(cap["captcha_id"]))
    return sid, cap, answer


def _valid_payload(sid, captcha_id, answer, **over):
    base = {
        "first_name": "آزمون", "last_name": "فراخوانی۹۳",
        # فاز ۹۳ — هر ثبت آزمونی کد ملی یکتای معتبر؛ ثبت تکراری عمدی با پارامتر over
        "national_code": next_national_code(),
        "gender": "female", "birth_date": "1370/01/01",
        "education_degree": "bachelor", "education_field": "روان‌شناسی",
        "license_status": "none", "center_ownership": "rented",
        "province_name": "تهران", "county_name": "تهران",
        "phone": "02112345678",
        "individual_rooms": 1, "group_rooms": 0, "child_rooms": 0, "counselors_count": 1,
        "has_waiting_space": True, "accepts_company_pattern": False, "has_accessibility": False,
        "terms_accepted": True,
        "captcha_id": captcha_id, "captcha_answer": str(answer),
        "session_id": sid,
    }
    base.update(over)
    return base


def _submit(client, payload, files=None):
    files = files or {
        "national_id_card": ("card.png", _png_bytes(), "image/png"),
        "degree_document": ("degree.pdf", _pdf_bytes(), "application/pdf"),
        "center_activity_license": ("license.jpg", _jpg_bytes(), "image/jpeg"),
    }
    return client.post(
        "/api/v1/farakhan/submissions",
        data={"payload": json.dumps(payload, ensure_ascii=False)},
        files=[(k, (f, c, m)) for k, (f, c, m) in files.items()],
    )


def _jalali_birth(age_years: int, day_offset: int = 0) -> str:
    """تاریخ تولد شمسیِ متناظر با «امروز نابر age_years سال» + انحراف روز.

    مبدأ میلادی است (هم‌راستا با محاسبهٔ سن تکمیل‌شدهٔ سرور) تا در مرزهای
    نوروز هم درست باشد؛ انحراف +۱ یعنی یک روز جوان‌تر، -۱ یعنی یک روز مسن‌تر.
    """
    from app.core.dates import gregorian_to_jalali

    today = datetime.now(timezone.utc).date()
    try:
        g = today.replace(year=today.year - age_years)
    except ValueError:  # تولد مرجع ۲۹ فوریه در سال ناآهسته — ۲۸ فوریه معادل است
        g = today.replace(year=today.year - age_years, month=2, day=28)
    g = g + timedelta(days=day_offset)
    jy, jm, jd = gregorian_to_jalali(g.year, g.month, g.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


# ---------------------------------------------------------------- بند ۱: الگوریتم کد ملی
def test_national_code_checksum_enforced(client):
    """رقم کنترل درست → ثبت؛ همان کد با رقم کنترل غلط → ۴۲۲ فارسی"""
    pinned = next_national_code()
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans, national_code=pinned))
    assert r.status_code == 201, r.text

    sid2, cap2, ans2 = _meta_and_captcha(client)
    bad = pinned[:-1] + ("0" if pinned[-1] != "0" else "1")
    r2 = _submit(client, _valid_payload(sid2, cap2["captcha_id"], ans2,
                                        national_code=bad))
    assert r2.status_code == 422, r2.text
    errors = r2.json()["detail"]["errors"]
    assert any("کد ملی" in k and "معتبر نیست" in v for k, v in errors.items()), errors


def test_national_code_repdigit_rejected(client):
    """ارقام تکراری (۱۱۱۱۱۱۱۱۱۱ و همهٔ صفرها) الگوریتم را رد می‌کنند"""
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                       national_code="1111111111"))
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    assert any("کد ملی" in k for k in errors), errors


def test_national_code_persian_digits_normalized(client):
    """ارقام فارسی همان کد یکتا نرمال و ثبت می‌شود"""
    pinned = next_national_code()
    fa = pinned.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                       national_code=fa))
    assert r.status_code == 201, r.text


def test_check_national_code_endpoint(client):
    """endpoint عمومی: valid=false برای رقم کنترل غلط؛ duplicate پس از ثبت"""
    # رقم کنترل غلط
    r = client.get("/api/v1/farakhan/check-national-code", params={"code": "0123456788"})
    assert r.status_code == 200, r.text
    assert r.json() == {"valid": False, "duplicate": False}

    # کد سالم اما ثبت‌نشده
    r = client.get("/api/v1/farakhan/check-national-code", params={"code": "0451234561"})
    assert r.json() == {"valid": True, "duplicate": False}

    # پس از ثبت با همان کد، duplicate=true (ارقام فارسی هم نرمال می‌شود)
    pinned = next_national_code()
    fa = pinned.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    sid, cap, ans = _meta_and_captcha(client)
    sub = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                         national_code=pinned))
    assert sub.status_code == 201, sub.text
    r = client.get("/api/v1/farakhan/check-national-code", params={"code": fa})
    assert r.json() == {"valid": True, "duplicate": True}


# ---------------------------------------------------------------- بند ۲ و ۳: محدودهٔ سن
def test_minimum_age_18_enforced(client):
    """۱۷ سال و ۳۶۴ روز → ۴۲۲ با «حداقل سن»؛ دقیقاً ۱۸ سال → ثبت می‌شود"""
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                       birth_date=_jalali_birth(18, day_offset=+1)))
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    assert any("تاریخ تولد" in k and "حداقل سن" in v for k, v in errors.items()), errors

    sid2, cap2, ans2 = _meta_and_captcha(client)
    r2 = _submit(client, _valid_payload(sid2, cap2["captcha_id"], ans2,
                                        birth_date=_jalali_birth(18)))
    assert r2.status_code == 201, r2.text


def test_maximum_age_80_enforced(client):
    """۸۱ سال کامل → ۴۲۲ با «حداکثر سن»؛ دقیقاً ۸۰ سال → ثبت می‌شود"""
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                       birth_date=_jalali_birth(81)))
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    assert any("تاریخ تولد" in k and "حداکثر سن" in v for k, v in errors.items()), errors

    sid2, cap2, ans2 = _meta_and_captcha(client)
    r2 = _submit(client, _valid_payload(sid2, cap2["captcha_id"], ans2,
                                        birth_date=_jalali_birth(80)))
    assert r2.status_code == 201, r2.text


def test_meta_exposes_age_limits(client):
    """قواعد سن در meta برای کلاینت (کف/سقف تقویم) منتشر می‌شود"""
    m = client.get(META_URL).json()
    assert m["rules"]["min_age"] == 18
    assert m["rules"]["max_age"] == 80
    assert m["rules"]["national_code_checksum"] is True


# ---------------------------------------------------------------- بند ۴: کد ملی تکراری
def test_duplicate_national_code_submit_blocked(client):
    """ثبت دوم با همان کد ملی فعال → ۴۲۲ با کلید «کد ملی» و پیام «قبلاً»"""
    pinned = next_national_code()
    sid, cap, ans = _meta_and_captcha(client)
    r1 = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                        national_code=pinned))
    assert r1.status_code == 201, r1.text

    sid2, cap2, ans2 = _meta_and_captcha(client)
    r2 = _submit(client, _valid_payload(sid2, cap2["captcha_id"], ans2,
                                        national_code=pinned))
    assert r2.status_code == 422, r2.text
    errors = r2.json()["detail"]["errors"]
    assert any("کد ملی" in k and "قبلاً" in v for k, v in errors.items()), errors


def test_rejected_submission_allows_resubmit(client, env):
    """ثبت‌نامِ «ردشده» مانع ثبت مجدد همان کد ملی نیست (جریان کاری جذب نیرو)"""
    token = login(client, "t_admin")
    pinned = next_national_code()
    sid, cap, ans = _meta_and_captcha(client)
    r1 = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                        national_code=pinned))
    assert r1.status_code == 201, r1.text
    code = r1.json()["tracking_code"]

    # وارسی زنده: تکراری است
    chk = client.get("/api/v1/farakhan/check-national-code",
                     params={"code": pinned}).json()
    assert chk == {"valid": True, "duplicate": True}

    # رد کردن در پنل
    lst = client.get("/api/v1/farakhan/admin/submissions",
                     headers=bearer(token), params={"q": code}).json()
    assert lst["total"] == 1, lst
    sid_id = lst["items"][0]["id"]
    st = client.put(f"/api/v1/farakhan/admin/submissions/{sid_id}/status",
                    headers=bearer(token), json={"status": "rejected", "note": "آزمون رد"})
    assert st.status_code == 200, st.text

    # وارسی زنده: دیگر تکراری نیست
    chk = client.get("/api/v1/farakhan/check-national-code",
                     params={"code": pinned}).json()
    assert chk == {"valid": True, "duplicate": False}

    # ثبت مجدد با همان کد ملی مجاز است
    sid2, cap2, ans2 = _meta_and_captcha(client)
    r2 = _submit(client, _valid_payload(sid2, cap2["captcha_id"], ans2,
                                        national_code=pinned))
    assert r2.status_code == 201, r2.text


def test_admin_list_no_false_duplicate_flag(client, env):
    """ثبت‌نام‌های با کد ملی متفاوت در جدول پنل بی‌مشکل کنار هم می‌نشینند"""
    token = login(client, "t_admin")
    code_a = next_national_code()
    sid, cap, ans = _meta_and_captcha(client)
    r1 = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                        national_code=code_a))
    assert r1.status_code == 201, r1.text
    sid2, cap2, ans2 = _meta_and_captcha(client)
    r2 = _submit(client, _valid_payload(sid2, cap2["captcha_id"], ans2,
                                        national_code=next_national_code()))
    assert r2.status_code == 201, r2.text

    lst = client.get("/api/v1/farakhan/admin/submissions",
                     headers=bearer(token),
                     params={"q": code_a}).json()
    assert lst["total"] >= 1
    assert lst["items"][0]["national_code"] == code_a


# ---------------------------------------------------------------- بند ۵: جدول پنل ثبت‌نام‌شده‌ها
def test_registered_person_shows_in_panel_table(client, env):
    """بند ۵ — ثبت موفق عمومی بلافاصله در فهرست پنل (جدول ثبت‌نام‌شده‌ها) دیده می‌شود"""
    sid, cap, ans = _meta_and_captcha(client)
    pinned = next_national_code()
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                       first_name="سارا", last_name="نمونه",
                                       national_code=pinned))
    assert r.status_code == 201, r.text
    code = r.json()["tracking_code"]

    token = login(client, "t_admin")
    lst = client.get("/api/v1/farakhan/admin/submissions",
                     headers=bearer(token), params={"q": code}).json()
    assert lst["total"] == 1, lst
    row = lst["items"][0]
    assert row["tracking_code"] == code
    assert row["first_name"] == "سارا"
    assert row["last_name"] == "نمونه"
    assert row["national_code"] == pinned
    assert row["file_count"] == 3
    assert row["status_label"]  # برچسب فارسی وضعیت برای جدول
