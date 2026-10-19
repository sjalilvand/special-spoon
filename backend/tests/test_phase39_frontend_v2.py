"""فاز ۳۹ - مهاجرت فرانت‌اند به پاکت v2 + اصلاح دامنه split_items.

پوشش آزمون:
- تفکیک صفحه‌بندی فقط برای پاسخ‌های واقعاً صفحه‌بندی‌شده (نشانگر total/page/...)
- عبور دست‌نخورده پاسخ‌های تکی/ساختاری دارای items داخلی (صورتحساب، فرم، سرویس)
- عبور دست‌نخورده فهرست‌های بدون نشانگر صفحه‌بندی (اعلان‌ها {items, unread})
- قرارداد مصرف‌کننده فرانت: login و refresh از مسیر /api/v2 با پاکت
- سازگاری معکوس: همان نقاط انتهایی روی v1 بدون پاکت باقی می‌مانند
"""
from __future__ import annotations

from conftest import PASSWORD, bearer, login

from app.core.envelope import split_items


# ---------------------------------------------------------------- unit tests
def test_split_items_still_lifts_true_pagination():
    data, extra = split_items({"items": [1, 2, 3], "total": 3, "page": 1, "page_size": 20})
    assert data == [1, 2, 3]
    assert extra == {"pagination": {"total": 3, "page": 1, "page_size": 20}}


def test_split_items_total_only_also_splits():
    data, extra = split_items({"items": ["a"], "total": 1})
    assert data == ["a"]
    assert extra == {"pagination": {"total": 1}}


def test_split_items_page_size_only_also_splits():
    data, extra = split_items({"items": [], "page_size": 30})
    assert data == []
    assert extra == {"pagination": {"page_size": 30}}


def test_split_items_detail_object_with_inner_items_passes_intact():
    """صورتحساب تکی — items آن اقلام صورتحساب است نه صفحه‌بندی (فاز ۳۹)."""
    invoice = {
        "id": "inv-1",
        "invoice_number": "INV-1",
        "total_amount": 1000,
        "items": [{"title": "مشاوره", "quantity": 1, "line_total": 1000}],
    }
    data, extra = split_items(invoice)
    assert data is invoice  # دست‌نخورده — بدون تفکیک
    assert extra == {}


def test_split_items_items_only_list_passes_intact():
    """فهرست بدون هیچ نشانگر صفحه‌بندی — شیء {items} حفظ می‌شود."""
    payload = {"items": [{"id": "x", "label": "گزینه"}]}
    data, extra = split_items(payload)
    assert data is payload
    assert extra == {}


def test_split_items_notifications_shape_passes_intact():
    """اعلان‌ها {items, unread} — بدون نشانگر صفحه‌بندی، دست‌نخورده."""
    payload = {"items": [{"id": "n1"}], "unread": 2}
    data, extra = split_items(payload)
    assert data is payload
    assert extra == {}


def test_split_items_plain_payload_passthrough():
    data, extra = split_items({"status": "ok"})
    assert data == {"status": "ok"}
    assert extra == {}


# ---------------------------------------------------------------- API-level
def test_v2_login_enveloped_and_v1_login_untouched(client, env):
    # v2: پاکت استاندارد با data.access_token — قرارداد جدید فرانت
    r = client.post("/api/v2/auth/login", json={"username": "t_admin", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] is None
    assert body["data"]["access_token"]
    assert body["meta"]["version"] == "v2"

    # v1: پاسخ خام — سازگاری موبایل/مصرف‌کنندگان فعلی
    r1 = client.post("/api/v1/auth/login", json={"username": "t_admin", "password": PASSWORD})
    assert r1.status_code == 200
    assert "access_token" in r1.json()
    assert "data" not in r1.json()


def test_v2_refresh_enveloped(client, env):
    login(client, "t_admin")  # کوکی refresh روی client ثبت می‌شود
    r = client.post("/api/v2/auth/refresh")  # قرارداد فرانت: فقط با کوکی، بدون Bearer
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] is None
    assert body["data"]["access_token"]


def test_v2_users_list_still_splits(client, env):
    token = login(client, "t_admin")
    r = client.get("/api/v2/users?page_size=5", headers=bearer(token))
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["data"], list)
    pagination = body["meta"].get("pagination") or {}
    assert "total" in pagination
    assert pagination.get("page_size") == 5


def test_v2_notifications_list_passes_intact(client, env):
    """قرارداد مصرف‌کننده فرانت: {items, unread} در data حفظ می‌شود."""
    token = login(client, "t_admin")
    r = client.get("/api/v2/notifications", headers=bearer(token))
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] is None
    assert isinstance(body["data"], dict)  # شیء واحد — نه آرایه
    assert "items" in body["data"]
    assert "unread" in body["data"]
    assert body["meta"].get("pagination") is None


def test_v2_options_endpoints_pass_intact(client, env):
    """گزینه‌های انتخابگر {items} — بدون تفکیک؛ همان قرارداد v1 داخل data."""
    token = login(client, "t_reception")  # CASE_MANAGE_ROLES شامل پذیرش است
    r = client.get("/api/v2/cases/applicant-options", headers=bearer(token))
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] is None
    assert isinstance(body["data"], dict)
    assert "items" in body["data"]


def test_v2_single_invoice_shape_untouched(client, env):
    """فاکتور تکی نباید تفکیک شود — کلید items آن اقلام صورتحساب است."""
    token = login(client, "t_admin")
    r = client.get("/api/v2/invoices/00000000-0000-0000-0000-000000000000", headers=bearer(token))
    # چه 404 باشد چه 200، پاکت باید کل پاسخ را به‌عنوان شیء حفظ کند
    body = r.json()
    assert body["data"] is None or isinstance(body["data"], dict)
    if r.status_code == 200:
        assert "items" in body["data"]  # اقلام صورتحساب داخل خود شیء


# ------------------------------------------ یافته‌های Schemathesis (فاز ۳۹)
def test_nul_byte_rejected_before_db(client, env):
    """بایت NUL هرگز نباید به لایه دیتابیس برسد (سرریز 500 psycopg)."""
    token = login(client, "t_admin")
    payload = {"title": "عنوان\u0000", "body": "متن", "kind": "treatment"}
    # v2: پاکت با کد پایدار validation_error
    r = client.post("/api/v2/consent-versions", headers=bearer(token), json=payload)
    assert r.status_code == 422, r.text
    assert r.json()["errors"][0]["code"] == "validation_error"
    # v1: همان سیاست، قرارداد خام
    r1 = client.post("/api/v1/consent-versions", headers=bearer(token), json=payload)
    assert r1.status_code == 422
    assert "detail" in r1.json()


def test_nul_byte_in_query_rejected(client, env):
    token = login(client, "t_admin")
    r = client.get("/api/v2/users?search=abc%00", headers=bearer(token))
    assert r.status_code == 422


def test_pagination_page_bounded_422_not_500(client, env):
    """صفحه‌های نجومی → 422 اعتبارسنجی، نه 500 سرریز bigint در OFFSET."""
    token = login(client, "t_admin")
    r = client.get("/api/v2/users?page=703422046849588878", headers=bearer(token))
    assert r.status_code == 422
    assert r.json()["data"] is None


def test_wallet_topup_amount_bounded(client, env):
    """مبلغ شارژ نجومی → 422 سقف Field، نه 500 سرریز Numeric(16,2)."""
    token = login(client, "t_admin")
    r = client.post("/api/v2/wallet/topup", headers=bearer(token),
                    json={"amount": 140_737_488_355_531})
    assert r.status_code == 422
    r2 = client.post("/api/v1/wallet/topup", headers=bearer(token),
                     json={"amount": 140_737_488_355_531})
    assert r2.status_code == 422
