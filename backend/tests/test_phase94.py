"""فاز ۹۴ — جدول عمومی «افراد ثبت‌نام‌شدهٔ فراخوان» + برند دامنهٔ rosedoctor.ir.

خواستهٔ صاحب سامانه: «هنوز صفحهٔ تعداد ثبت‌شده‌ها خالی است» — پس فهرست عمومی
ثبت‌نام‌شده‌ها روی خود صفحهٔ /farakhan منتشر می‌شود (بدون ورود) با کمترین
دادهٔ شخصی: نام، استان/شهرستان، مدرک تحصیلی و زمان ثبت. کد ملی، تلفن، نشانی،
فایل‌ها، وضعیت بررسی و یادداشت‌ها هرگز در پاسخ عمومی نیستند.
"""

from __future__ import annotations

import io
import json
import time

from conftest import bearer, login, next_national_code

PUBLIC_LIST_URL = "/api/v1/farakhan/public/submissions"


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
    m = client.get("/api/v1/farakhan/meta").json()
    sid = m["session_id"]
    cap = client.get("/api/v1/farakhan/captcha").json()
    from app.api.v1.farakhan import _peek_captcha_answer

    answer = str(_peek_captcha_answer(cap["captcha_id"]))
    return sid, cap, answer


def _valid_payload(sid, captcha_id, answer, **over):
    base = {
        "first_name": "آزمون", "last_name": "فراخوانی۹۴",
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


def _submit(client, payload):
    files = {
        "national_id_card": ("card.png", _png_bytes(), "image/png"),
        "degree_document": ("degree.pdf", _pdf_bytes(), "application/pdf"),
        "center_activity_license": ("license.jpg", _jpg_bytes(), "image/jpeg"),
    }
    return client.post(
        "/api/v1/farakhan/submissions",
        data={"payload": json.dumps(payload, ensure_ascii=False)},
        files=[(k, (f, c, m)) for k, (f, c, m) in files.items()],
    )


def _clear_public_rate():
    from app.api.v1 import farakhan as fk

    fk._public_list_ip_hits.clear()


# ---------------------------------------------------------------- بدون ورود در دسترس است
def test_public_list_requires_no_auth(client):
    _clear_public_rate()
    r = client.get(PUBLIC_LIST_URL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) >= {"items", "total"}
    assert isinstance(body["total"], int)
    assert isinstance(body["items"], list)


# ---------------------------------------------------------------- جریان کامل: ثبت → دیده‌شدن در جدول عمومی
def test_submission_appears_in_public_table_without_sensitive_fields(client):
    _clear_public_rate()
    before = client.get(PUBLIC_LIST_URL).json()["total"]

    sid, cap, ans = _meta_and_captcha(client)
    nc = next_national_code()
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans, national_code=nc))
    assert r.status_code == 201, r.text
    tracking = r.json()["tracking_code"]

    r2 = client.get(PUBLIC_LIST_URL)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["total"] == before + 1  # شمارندهٔ «تعداد ثبت‌شده‌ها» افزایش یافته

    row = next((x for x in body["items"] if x["name"].endswith("فراخوانی۹۴")), None)
    assert row is not None, body["items"]
    assert row["name"] == "آزمون فراخوانی۹۴"
    assert row["province_name"] == "تهران" and row["county_name"] == "تهران"
    assert row["education_degree_label"] == "کارشناسی"
    assert row["created_at"]  # زمان ثبت هست

    # حریم خصوصی: هیچ دادهٔ حساسی در پاسخ عمومی نیست
    text = r2.text
    assert nc not in text            # کد ملی
    assert "02112345678" not in text  # تلفن ثابت
    for forbidden_key in ("national_code", "phone", "mobile_number", "postal_code",
                          "address", "status", "review_note", "submit_ip", "tracking_code"):
        assert forbidden_key not in text, forbidden_key


# ---------------------------------------------------------------- ترتیب: جدیدترین اول
def test_public_list_newest_first(client):
    _clear_public_rate()
    sid, cap, ans = _meta_and_captcha(client)
    first = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                          first_name="اولین", last_name="ثبت۹۴"))
    assert first.status_code == 201, first.text

    sid2, cap2, ans2 = _meta_and_captcha(client)
    second = _submit(client, _valid_payload(sid2, cap2["captcha_id"], ans2,
                                            first_name="دومین", last_name="ثبت۹۴"))
    assert second.status_code == 201, second.text

    body = client.get(PUBLIC_LIST_URL).json()
    names = [x["name"] for x in body["items"]]
    idx_first, idx_second = names.index("اولین ثبت۹۴"), names.index("دومین ثبت۹۴")
    assert idx_second < idx_first  # جدیدترین (دومین) بالاتر از اولین است


# ---------------------------------------------------------------- سقف نرخ عمومی
def test_public_list_rate_limit(client):
    from app.api.v1 import farakhan as fk

    fk._public_list_ip_hits.clear()
    r = client.get(PUBLIC_LIST_URL, headers={"x-forwarded-for": "203.0.113.77"})
    assert r.status_code == 200, r.text
    # پر کردن سقف نرخ همان IP
    fk._public_list_ip_hits["203.0.113.77"] = [time.monotonic()] * fk._PUBLIC_LIST_RATE
    r2 = client.get(PUBLIC_LIST_URL, headers={"x-forwarded-for": "203.0.113.77"})
    assert r2.status_code == 429, r2.text
    assert "بیش از حد مجاز" in r2.json()["detail"]
    # IP دیگر بدون تأثیر
    r3 = client.get(PUBLIC_LIST_URL, headers={"x-forwarded-for": "203.0.113.78"})
    assert r3.status_code == 200, r3.text
    fk._public_list_ip_hits.clear()


# ---------------------------------------------------------------- برند/دامنهٔ فاز ۹۴ در متادیتا
def test_meta_still_reports_phase93_rules(client):
    """قواعد فاز ۹۳ (سن ۱۸–۸۰ + الگوریتم کد ملی) پس از فاز ۹۴ دست‌نخورده‌اند."""
    m = client.get("/api/v1/farakhan/meta").json()
    assert m["rules"]["min_age"] == 18
    assert m["rules"]["max_age"] == 80
    assert m["rules"]["national_code_checksum"] is True


# ---------------------------------------------------------------- پنل: جدول مدیریت همان‌طور کار می‌کند
def test_admin_table_still_lists_submissions(client, env):
    """ثبت‌نام عمومی بلافاصله در جدول پنل (فاز ۹۳ بند ۵) دیده می‌شود."""
    sid, cap, ans = _meta_and_captcha(client)
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans,
                                       first_name="پنلی", last_name="فراخوانی۹۴"))
    assert r.status_code == 201, r.text

    token = login(client, "t_admin")
    r2 = client.get("/api/v1/farakhan/admin/submissions",
                    headers=bearer(token), params={"q": "فراخوانی۹۴"})
    assert r2.status_code == 200, r2.text
    names = [f"{x['first_name']} {x['last_name']}" for x in r2.json()["items"]]
    assert "پنلی فراخوانی۹۴" in names
