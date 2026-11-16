"""فاز ۹۱ — فراخوان همکاری: ریشه‌یابی «ثبت با خطا» + مدیریت کامل خطا + تقویم شمسی.

گزارش میدانی کاربر (کنسول مرورگر):
- یک ۴۲۲ و دو ۵۰۰ با ERR_INCOMPLETE_CHUNKED_ENCODING روی POST /farakhan/submissions
- «لطفاً دقیقاً علت خطا و اینکه خطا از کدوم فیلد است را بنویسید»

ریشه‌های پیدا‌شده و پوشش آزمون این فایل:
1) سقف بدنهٔ درخواست Caddyfile «15MB» بود در حالی که فرم تا ۷×۵MB=۳۵MB می‌پذیرد →
   بارگذاری بزرگ وسط استریم قطع می‌شد (رفع: max_size 40MB در قالب استقرار؛ رفع زیرساختی است)
2) پیام‌های فنی انگلیسی pydantic در ۴۲۲ نشت می‌کرد («String should have at most…»،
   «Input should be a valid integer…») → اکنون همیشه فارسی با برچسب فیلد
3) ارقام فارسی در فیلدهای عددی رد می‌شد → اکنون نرمال می‌شود
4) هر خطای غیرمنتظرهٔ ذخیره (پایگاه‌داده/فایل) «۵۰۰ بی‌پیام» می‌ساخت → اکنون
   rollback + ردیابی کامل در لاگ + پاسخ JSON ساختاریافته با پیام فارسی
5) ثبت دوباره با همان کد ملی: در فاز ۹۱ آزاد بود؛ از فاز ۹۳ (خواستهٔ صاحب سامانه)
   ثبت‌نامِ فعالِ تکراری با همان کد ملی ۴۲۲ با پیام فارسی می‌گیرد (پوشش در test_phase93)
6) تقویم شمسی سمت مرورگر است (JalaliDatePicker)؛ سمت سرور همان اعتبارسنجی قبلی
"""

from __future__ import annotations

import io
import json

from conftest import bearer, login, next_national_code

META_URL = "/api/v1/farakhan/meta"


def _png_bytes(width=40, height=40) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _jpg_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (30, 200, 90)).save(buf, format="JPEG")
    return buf.getvalue()


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF"


def _meta_and_captcha(client):
    m = client.get(META_URL).json()
    sid = m["session_id"]
    cap = client.get("/api/v1/farakhan/captcha").json()
    # برای ثبت موفق، پاسخ واقعی کپچا از فروشگاه مرجع ماژول خوانده می‌شود (فقط آزمون؛ فاز ۹۲)
    from app.api.v1.farakhan import _peek_captcha_answer

    answer = str(_peek_captcha_answer(cap["captcha_id"]))
    return sid, cap, answer


def _valid_payload(sid, captcha_id, answer, **over):
    base = {
        "first_name": "آزمون", "last_name": "فراخوانی۹۱",
        # فاز ۹۳ — ثبت تکراری با یک کد ملی ۴۲۲ می‌گیرد؛ هر ثبت آزمونی کد یکتای معتبر می‌گیرد
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


def _submit(client, payload, files: dict[str, tuple[str, bytes, str]] | None = None):
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


# ---------------------------------------------------------------- جریان سالم
def test_happy_path_with_three_files(client):
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans))
    assert r.status_code == 201, r.text
    assert r.json()["tracking_code"].startswith("FRK-")


def test_persian_filenames_ok(client):
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans), {
        "national_id_card": ("کارت ملی.jpg", _jpg_bytes(), "image/jpeg"),
        "degree_document": ("مدرک تحصیلی.PDF", _pdf_bytes(), "application/pdf"),
        "center_activity_license": ("پروانه.PNG", _png_bytes(), "image/png"),
    })
    assert r.status_code == 201, r.text


def test_same_national_code_second_submit_blocked(client):
    """فاز ۹۳ — ثبت دوم با همان کد ملی: تکراری شمرده می‌شود و ۴۲۲ پیام فارسی می‌گیرد
    (رفتار فاز ۹۱ یعنی «ثبت مستقل» با خواستهٔ صاحب سامانه برای تشخیص تکراری عوض شد)"""
    pinned = next_national_code()
    sid, cap, ans = _meta_and_captcha(client)
    r1 = _submit(client, _valid_payload(sid, cap["captcha_id"], ans, national_code=pinned))
    assert r1.status_code == 201, r1.text
    sid2, cap2, ans2 = _meta_and_captcha(client)
    r2 = _submit(client, _valid_payload(sid2, cap2["captcha_id"], ans2, national_code=pinned))
    assert r2.status_code == 422, f"ثبت تکراری باید ۴۲۲ شود: {r2.status_code} {r2.text[:300]}"
    errors = r2.json()["detail"]["errors"]
    assert any("کد ملی" in k and "قبلاً" in v for k, v in errors.items()), errors


# ---------------------------------------------------------------- پیام‌های فارسی + ارقام فارسی
def test_persian_digits_in_int_fields_accepted(client):
    """«۳» و «۲» در فیلدهای عددی — دیگر «Input should be a valid integer» نیست"""
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(
        sid, cap["captcha_id"], ans,
        individual_rooms="۳", group_rooms="0", child_rooms=2, counselors_count=" 5 ",
    ))
    assert r.status_code == 201, r.text


def test_no_english_pydantic_messages_leak(client):
    """پاسخ طولانی کپچا → پیام فارسی «حداکثر ۱۲ نویسه مجاز است.» بدون متن انگلیسی"""
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], "x" * 50))
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    assert any("String should" not in m and "characters" not in m for m in errors.values()), errors
    assert any("حداکثر" in m for m in errors.values()), errors
    assert any("کپچا" in k for k in errors), errors


def test_non_numeric_int_field_message_is_persian(client):
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans, counselors_count="دو"))
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    assert any("باید عدد باشد" in m for m in errors.values()), errors
    assert any("تعداد مشاوران" in k for k in errors), errors


# ---------------------------------------------------------------- سپر خطای سرور
def test_unexpected_server_error_is_structured_not_silent(client, monkeypatch):
    """خرابی داخلی (اینجا: خراب‌کردن عمدی ذخیرهٔ فایل) → ۵۰۰ ساختاریافته با پیام فارسی"""
    sid, cap, ans = _meta_and_captcha(client)
    from app.services import object_storage as objstore

    def _boom(data, settings=None):
        raise RuntimeError("disk failure simulation")

    monkeypatch.setattr(objstore, "store", _boom)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans))
    assert r.status_code == 500, r.text
    body = r.json()["detail"]
    assert "خطای غیرمنتظره" in body["message"], body
    assert "ذخیره نشد" in body["message"], body


def test_db_outage_returns_503_structured(client, monkeypatch):
    """قطع پایگاه‌داده در میانهٔ ذخیره → ۵۰۳ با پیام فارسی و راهنمای تلاش دوباره"""
    sid, cap, ans = _meta_and_captcha(client)
    from sqlalchemy.exc import OperationalError

    from app.api.v1 import farakhan as fk

    real_store = fk.objstore.store

    def _db_down(data, settings=None):
        raise OperationalError("stmt", {}, Exception("connection refused"))

    monkeypatch.setattr(fk.objstore, "store", _db_down)
    monkeypatch.setattr(fk.objstore, "save_bytes_at_key", lambda *a, **kw: None, raising=False)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans))
    assert r.status_code == 503, r.text
    body = r.json()["detail"]
    assert "دوباره تلاش" in body["message"], body
    assert real_store is not None


def test_file_validation_failure_keeps_422_and_rolls_back(client):
    """فایل نامعتبر → ۴۲۲ روی فیلد همان فایل؛ ثبت ناقص باقی نمی‌ماند"""
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans), {
        "national_id_card": ("card.png", _png_bytes(), "image/png"),
        "degree_document": ("degree.pdf", _pdf_bytes(), "application/pdf"),
        "center_activity_license": ("license.jpg", _jpg_bytes(), "image/jpeg"),
        "center_permit": ("permit.exe", b"MZfake", "application/octet-stream"),
    })
    # پسوند .exe پیش از خواندن رد می‌شود؛ کلید فایل در پیام است
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    assert any("center_permit" in k for k in errors), errors
