"""فاز ۹۰ — رفع «ثبت پرونده بی‌خطا ولی خالی» + جست‌وجوی درخواست‌های مشاوره.

ریشهٔ گزارش میدانی: مدیر سامانه (SYSTEM_ADMIN) پرونده می‌ساخت (۲۰۱ بدون خطا)
ولی فهرست پرونده‌ها همیشه خالی می‌ماند؛ چون list_cases او را به شاخهٔ مشاور
می‌برد و چون ردیف مشاور ندارد، بلافاصله «فهرست خالی» برمی‌گشت. همچنین دکمهٔ
«تبدیل» در صفحهٔ درخواست‌ها برای او نمایش داده نمی‌شد و چند نقطهٔ دیگر ۴۰۳
بی‌صدا بود. این مجموعه رگرسیون هر پنج نقطه را می‌بندد:

- GET /cases برای SYSTEM_ADMIN همهٔ پرونده‌ها را برمی‌گرداند (نه فهرست خالی)
- پروندهٔ تازه‌ساختِ مدیر، بلافاصله در فهرست دیده می‌شود
- PATCH پیگیری درخواست با SYSTEM_ADMIN → ۲۰۰ (قبل: ۴۰۳)
- POST تبدیل درخواست با SYSTEM_ADMIN → ۲۰۰ (قبل: ۴۰۳)
- POST ثبت درخواست دستی با SYSTEM_ADMIN → ۲۰۱ (قبل: ۴۰۳)
- GET /consultation-requests?search= روی نام/موبایل/موضوع/شهر/شمارهٔ پرونده
- خروجی فهرست درخواست‌ها شامل case_id/case_number است
- محدودسازی مشاور حفظ شده: مشاورِ بدون تخصیص، فهرست خالی می‌بیند
"""

from __future__ import annotations

from conftest import bearer, login


def _mk_plain_applicant(env, ext: str, code: str):
    """متقاضی بدون کاربر مرتبط — تا پروندهٔ آزمایشی خلاصهٔ متقاضی را نشکند"""
    db = env["db"]
    from app.models.people import Applicant

    ap = Applicant(external_id=ext, employee_code=code, national_id=None,
                   first_name="پرونده", last_name="آزمونی۹۰", status="active",
                   record_source="manual")
    db.add(ap)
    db.commit()
    return ap


def _mk_request(client, tok, name: str, mobile: str, topic: str = "مشاوره فردی",
                city: str | None = None):
    payload = {"full_name": name, "mobile": mobile, "topic": topic,
               "request_type": "in_person"}
    if city:
        payload["city"] = city
    r = client.post("/api/v1/consultation-requests", headers=bearer(tok), json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- فهرست پرونده‌ها
def test_admin_sees_existing_cases(client, env):
    """قبل از فاز ۹۰: مدیر فهرست خالی می‌دید (بدون خطا) — ریشهٔ باگ میدانی"""
    tok = login(client, "t_admin")
    r = client.get("/api/v1/cases", headers=bearer(tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1, "مدیر باید پرونده‌های موجود را ببیند"
    # پروندهٔ seed ممکن است با تست‌های پیشین از صفحهٔ اول بیرون بیفتد؛ با جست‌وجو می‌یابیم
    r = client.get("/api/v1/cases", headers=bearer(tok),
                   params={"search": "RS-TEST-000001"})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1, r.json()
    assert r.json()["items"][0]["case_number"] == "RS-TEST-000001"


def test_admin_created_case_is_immediately_visible(client, env):
    """سناریوی دقیق گزارش: ثبت پرونده بدون خطا → باید همان لحظه در فهرست باشد"""
    tok = login(client, "t_admin")
    ap = _mk_plain_applicant(env, "T-EXT-90A", "9101")
    r = client.post("/api/v1/cases", headers=bearer(tok),
                    json={"applicant_id": str(ap.id), "priority": "normal"})
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["case_number"]

    r = client.get("/api/v1/cases", headers=bearer(tok),
                   params={"search": created["case_number"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    assert any(x["case_number"] == created["case_number"] for x in body["items"])


def test_counselor_list_still_scoped(client, env):
    """محرومیت مشاورِ بدون تخصیص حفظ شود — فاز ۹۰ حق دید را بازتر نکرده باشد"""
    tok = login(client, "t_counsb")  # مشاور B: هیچ پرونده‌ای به او تخصیص نیافته
    r = client.get("/api/v1/cases", headers=bearer(tok))
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0, r.json()


# ---------------------------------------------------------------- درخواست‌ها: نقش مدیر
def test_admin_can_create_manual_request(client, env):
    tok = login(client, "t_admin")
    body = _mk_request(client, tok, "مریم آزمون۹۰", "09120000001")
    assert body["status"] == "in_review"


def test_admin_can_follow_up_request(client, env):
    tok = login(client, "t_admin")
    req = _mk_request(client, tok, "حسین آزمون۹۰", "09120000002")
    r = client.patch(f"/api/v1/consultation-requests/{req['id']}",
                     headers=bearer(tok),
                     json={"status": "in_review", "reception_note": "تماس گرفته شد",
                           "add_contact_attempt": True})
    assert r.status_code == 200, r.text
    assert r.json()["contact_attempts"] == 1


def test_admin_can_convert_request_with_case(client, env):
    """تبدیل + تشکیل پرونده توسط مدیر؛ شمارهٔ پرونده در همان پاسخ برمی‌گردد"""
    tok = login(client, "t_admin")
    req = _mk_request(client, tok, "زهرا آزمون۹۰", "09120000003")
    r = client.post(f"/api/v1/consultation-requests/{req['id']}/convert",
                    headers=bearer(tok), json={"create_case": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "converted"
    assert body["case_id"] and body["case_number"]

    # پروندهٔ تازه در فهرست پرونده‌های مدیر دیده می‌شود (وارسی پروندهٔ ریشه‌ای)
    r = client.get("/api/v1/cases", headers=bearer(tok),
                   params={"search": body["case_number"]})
    assert any(x["case_number"] == body["case_number"] for x in r.json()["items"])


# ---------------------------------------------------------------- جست‌وجوی درخواست‌ها
def test_request_list_search_by_name_mobile_topic_city(client, env):
    tok = login(client, "t_admin")
    _mk_request(client, tok, "نگار جستجونام", "09120000004", topic="زوج‌درمانی", city="کرج")
    _mk_request(client, tok, "رضا دیگر", "09120000005", topic="مشاوره فردی", city="تهران")

    # نام
    r = client.get("/api/v1/consultation-requests", headers=bearer(tok),
                   params={"search": "جستجونام"})
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["full_name"] == "نگار جستجونام"
    # موبایل
    r = client.get("/api/v1/consultation-requests", headers=bearer(tok),
                   params={"search": "09120000005"})
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["mobile"] == "09120000005"
    # موضوع
    r = client.get("/api/v1/consultation-requests", headers=bearer(tok),
                   params={"search": "زوج‌درمانی"})
    assert all("زوج‌درمانی" in x["topic"] for x in r.json()["items"])
    # شهر
    r = client.get("/api/v1/consultation-requests", headers=bearer(tok),
                   params={"search": "کرج"})
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["city"] == "کرج"


def test_request_list_search_by_case_number_and_case_link(client):
    """درخواست تبدیل‌شده با شمارهٔ پرونده هم پیدا می‌شود؛ ردیف پیوند پرونده دارد"""
    tok = login(client, "t_admin")
    req = _mk_request(client, tok, "سمیرا پیوند۹۰", "09120000006")
    r = client.post(f"/api/v1/consultation-requests/{req['id']}/convert",
                    headers=bearer(tok), json={"create_case": True})
    assert r.status_code == 200, r.text
    conv = r.json()
    case_number = conv["case_number"]
    assert case_number

    r = client.get("/api/v1/consultation-requests", headers=bearer(tok),
                   params={"search": case_number})
    items = r.json()["items"]
    assert len(items) == 1, items
    row = items[0]
    assert row["id"] == req["id"]
    assert row["case_number"] == case_number
    assert row["case_id"] == conv["case_id"]
    assert row["status"] == "converted"


def test_request_search_no_match_empty(client, env):
    tok = login(client, "t_admin")
    r = client.get("/api/v1/consultation-requests", headers=bearer(tok),
                   params={"search": "هیچ‌چیز-منطبق-۹۰۰۹۹"})
    assert r.status_code == 200 and r.json()["items"] == []
