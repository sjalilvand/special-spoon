"""فاز ۳۰ - B18/B19/B20 سند جامع: کیف پول، کد تخفیف و استرداد وجه.

- B19: «مصرف هم‌زمان بیش از سقف پذیرفته نشود» — سقف کل/هر کاربر،
  انقضا/غیرفعال، آزادسازی سهمیه با لغو سفارش؛ مبلغ/درصد با سقف مبلغ.
- B18: «مانده با جمع گردش‌ها سازگار و دوباره‌مصرفی ممنوع» — شارژ از
  درگاه (سفارش topup)، پرداخت سفارش از اعتبار با قفل ردیفی، تعدیل مدیر.
- B20: «استرداد از مبلغ مجاز بیشتر و اجرای تکراری ممنوع» — چرخه
  درخواست → بررسی → اجرا با بازگشت به کیف پول یا ثبت درگاه.
"""
import uuid as _uuid

import pytest

from conftest import bearer, login

from app.db.session import SessionLocal
from app.services.wallet import verify_consistency


@pytest.fixture(autouse=True)
def _fresh_applicant_wallet(env):
    """استقلال تست‌ها: کیف پول متقاضی پیش از هر آزمون صفر می‌شود."""
    from sqlalchemy import delete, select, update

    from app.models.user import User
    from app.models.wallet import Wallet, WalletEntry

    db = SessionLocal()
    try:
        u = db.scalars(select(User).where(User.username == "t_appa")).first()
        if u is not None:
            w = db.scalars(select(Wallet).where(Wallet.user_id == u.id)).first()
            if w is not None:
                db.execute(delete(WalletEntry).where(WalletEntry.wallet_id == w.id))
                db.execute(update(Wallet).where(Wallet.id == w.id).values(balance=0))
                db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def manager_headers(client, env):
    return bearer(login(client, "t_manager"))


@pytest.fixture()
def admin_headers(client, env):
    return bearer(login(client, "t_admin"))


@pytest.fixture()
def applicant_headers(client, env):
    return bearer(login(client, "t_appa"))


@pytest.fixture()
def reception_headers(client, env):
    return bearer(login(client, "t_reception"))


# ---------------- helpers ----------------

def _mk_service(client, headers, name) -> dict:
    tag = _uuid.uuid4().hex[:6]
    r = client.post("/api/v1/specialties", headers=headers, json={"name": f"فاز۳۰-{name}-{tag}"})
    sp = r.json()
    r = client.post("/api/v1/services", headers=headers, json={
        "specialty_id": sp["id"], "title": f"خدمت {name}", "duration_minutes": 45,
    })
    svc = r.json()
    from datetime import date, timedelta
    on = date.today() - timedelta(days=1)
    r = client.post("/api/v1/tariffs", headers=headers, json={
        "service_id": svc["id"], "amount": 1000000,
        "valid_from": str(on), "valid_to": str(on + timedelta(days=200)),
    })
    assert r.status_code == 201, r.text
    return svc


def _mk_order(client, headers, svc, **over) -> dict:
    payload = {"service_id": svc["id"]}
    payload.update(over)
    r = client.post("/api/v1/orders", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _pay(client, headers, order_id, approve=True) -> dict:
    r = client.post(f"/api/v1/orders/{order_id}/payments", headers=headers, json={})
    assert r.status_code == 201, r.text
    auth = r.json()["authority"]
    r = client.post(
        f"/api/v1/payments/{auth}/verify?approve={'true' if approve else 'false'}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _wallet(client, headers) -> dict:
    r = client.get("/api/v1/wallet", headers=headers)
    assert r.status_code == 200
    return r.json()


def _topup(client, headers, amount) -> None:
    """شارژ کیف پول از مسیر درگاه sandbox."""
    r = client.post("/api/v1/wallet/topup", headers=headers, json={"amount": amount})
    assert r.status_code == 201, r.text
    auth = r.json()["authority"]
    r = client.post(f"/api/v1/payments/{auth}/verify?approve=true", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


# ---------------- B19: کد تخفیف ----------------

def test_discount_create_and_duplication(client, manager_headers):
    r = client.post("/api/v1/discounts", headers=manager_headers, json={
        "code": "rose10", "kind": "percent", "value": 10, "max_uses": 5,
    })
    assert r.status_code == 201, r.text
    assert r.json()["code"] == "ROSE10"
    # کد تکراری → 409
    r = client.post("/api/v1/discounts", headers=manager_headers, json={
        "code": "ROSE10", "kind": "amount", "value": 50000,
    })
    assert r.status_code == 409
    # درصد > ۱۰۰ → 422
    r = client.post("/api/v1/discounts", headers=manager_headers, json={
        "code": "BAD", "kind": "percent", "value": 150,
    })
    assert r.status_code == 422


def test_discount_validate_endpoint(client, manager_headers, applicant_headers):
    client.post("/api/v1/discounts", headers=manager_headers, json={
        "code": "VAL20", "kind": "percent", "value": 20,
    })
    r = client.post("/api/v1/discounts/validate", headers=applicant_headers, json={
        "code": "VAL20", "amount": 1000000,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["discount_amount"] == 200000
    # کد ناموجود
    r = client.post("/api/v1/discounts/validate", headers=applicant_headers, json={
        "code": "NOPE", "amount": 1000000,
    })
    assert r.json()["valid"] is False


def test_order_with_discount_code_applies_snapshot(client, manager_headers, applicant_headers):
    """B19: کد روی سفارش اعمال و مصرف ثبت می‌شود؛ خروجی سفارش کد را نشان می‌دهد."""
    svc = _mk_service(client, manager_headers, "تخفیف سفارش")
    client.post("/api/v1/discounts", headers=manager_headers, json={
        "code": "APPLY10", "kind": "percent", "value": 10,
    })
    order = _mk_order(client, manager_headers, svc, discount_code="APPLY10",
                      owner_user_id=_applicant_id(client, applicant_headers))
    assert order["amount"] == 1000000.0
    assert order["discount_amount"] == 100000.0
    assert order["payable_amount"] == 900000.0
    assert order["discount_code"] == "APPLY10"
    # مصرف ثبت شده در فهرست استفاده‌ها
    r = client.get("/api/v1/discounts", headers=manager_headers)
    row = next(d for d in r.json()["items"] if d["code"] == "APPLY10")
    assert row["effective_uses"] == 1


def _applicant_id(client, applicant_headers) -> str:
    from app.core.security import decode_access_token

    return decode_access_token(applicant_headers["Authorization"].split(" ", 1)[1])["sub"]


def test_discount_cap_concurrent_rejected(client, manager_headers, applicant_headers, reception_headers):
    """B19 پذیرش: مصرف هم‌زمان بیش از سقف پذیرفته نشود."""
    svc = _mk_service(client, manager_headers, "سقف تخفیف")
    client.post("/api/v1/discounts", headers=manager_headers, json={
        "code": "CAP1", "kind": "amount", "value": 100000, "max_uses": 1,
    })
    owner = _applicant_id(client, applicant_headers)
    o1 = _mk_order(client, manager_headers, svc, discount_code="CAP1", owner_user_id=owner)
    assert o1["payable_amount"] == 900000.0
    # مصرف دوم (سقف ۱) → 422 و سفارش ساخته نمی‌ماند
    rcpt_id = bearer(login(client, "t_reception"))
    from app.core.security import decode_access_token
    me_id = decode_access_token(rcpt_id["Authorization"].split(" ", 1)[1])["sub"]
    r = client.post("/api/v1/orders", headers=manager_headers, json={
        "service_id": svc["id"], "discount_code": "CAP1", "owner_user_id": me_id,
    })
    assert r.status_code == 422
    # لغو سفارش اول → سهمیه آزاد و مصرف بعدی ممکن می‌شود
    r = client.post(f"/api/v1/orders/{o1['id']}/cancel", headers=manager_headers)
    assert r.status_code == 200
    o2 = _mk_order(client, manager_headers, svc, discount_code="CAP1", owner_user_id=owner)
    assert o2["payable_amount"] == 900000.0


def test_discount_per_user_cap_and_expiry(client, manager_headers, applicant_headers):
    """سقف هر کاربر + انقضا."""
    from datetime import date, timedelta
    svc = _mk_service(client, manager_headers, "سقف کاربر")
    client.post("/api/v1/discounts", headers=manager_headers, json={
        "code": "PERUSER1", "kind": "percent", "value": 5, "max_uses_per_user": 1,
    })
    owner = _applicant_id(client, applicant_headers)
    _mk_order(client, manager_headers, svc, discount_code="PERUSER1", owner_user_id=owner)
    r = client.post("/api/v1/orders", headers=manager_headers, json={
        "service_id": svc["id"], "discount_code": "PERUSER1", "owner_user_id": owner,
    })
    assert r.status_code == 422
    assert "کاربر" in r.json()["detail"]
    # کد منقضی
    yesterday = date.today() - timedelta(days=1)
    client.post("/api/v1/discounts", headers=manager_headers, json={
        "code": "EXPIRED", "kind": "amount", "value": 50000,
        "starts_at": str(yesterday - timedelta(days=10)), "expires_at": str(yesterday),
    })
    r = client.post("/api/v1/orders", headers=manager_headers, json={
        "service_id": svc["id"], "discount_code": "EXPIRED", "owner_user_id": owner,
    })
    assert r.status_code == 422
    assert "منقضی" in r.json()["detail"]


# ---------------- B18: کیف پول ----------------

def test_wallet_topup_via_gateway_and_consistency(client, manager_headers, applicant_headers):
    """B18: شارژ از درگاه (سفارش topup) → مانده = جمع گردش‌ها."""
    _topup(client, applicant_headers, 500000)
    _topup(client, applicant_headers, 300000)
    w = _wallet(client, applicant_headers)
    assert w["balance"] == 800000.0
    assert verify_consistency(SessionLocal(), __import__("uuid").UUID(w["user_id"]))
    entries = client.get("/api/v1/wallet/entries", headers=applicant_headers).json()["items"]
    assert len(entries) == 2
    assert all(e["direction"] == "credit" and e["reason"] == "topup" for e in entries)
    # سفارش topup فاکتور هم دارد (از موتور پرداخت فاز ۲۹)
    orders = client.get("/api/v1/orders", headers=applicant_headers).json()["items"]
    topups = [o for o in orders if o["kind"] == "topup"]
    assert len(topups) == 2
    assert all(o["invoice_id"] for o in topups)


def test_pay_order_from_wallet_success_and_ledger(client, manager_headers, applicant_headers):
    """B18: پرداخت سفارش از اعتبار؛ برداشت ثبت و مانده سازگار می‌ماند."""
    _topup(client, applicant_headers, 700000)
    svc = _mk_service(client, manager_headers, "پرداخت کیفی")
    owner = _applicant_id(client, applicant_headers)
    order = _mk_order(client, manager_headers, svc, owner_user_id=owner)
    # مانده ۷۰۰٬۰۰۰ < ۱٬۰۰۰٬۰۰۰ → 409 و بدون برداشت
    r = client.post(f"/api/v1/orders/{order['id']}/pay-from-wallet", headers=applicant_headers)
    assert r.status_code == 409
    # شارژ بیشتر → سفارش دوم از کیف پول پرداخت می‌شود
    _topup(client, applicant_headers, 500000)
    order2 = _mk_order(client, manager_headers, svc, owner_user_id=owner)
    r = client.post(f"/api/v1/orders/{order2['id']}/pay-from-wallet", headers=applicant_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gateway"] == "wallet"
    assert body["order_status"] == "paid"
    w = _wallet(client, applicant_headers)
    # 700000 + 500000 − 1000000 = 200000
    assert w["balance"] == 200000.0
    assert verify_consistency(SessionLocal(), _uuid.UUID(w["user_id"]))
    detail = client.get(f"/api/v1/orders/{order2['id']}", headers=applicant_headers).json()
    assert detail["invoice_id"] is not None
    assert detail["payments"][0]["gateway"] == "wallet"


def test_pay_from_wallet_insufficient_and_double(client, manager_headers, applicant_headers):
    """دوباره‌مصرفی ممنوع: مانده ناکافی → 409 و بدون تغییر مانده؛ سفارش paid دوباره پرداخت نمی‌شود."""
    _topup(client, applicant_headers, 100000)
    svc = _mk_service(client, manager_headers, "پرداخت ناکافی")
    owner = _applicant_id(client, applicant_headers)
    order = _mk_order(client, manager_headers, svc, owner_user_id=owner)
    r = client.post(f"/api/v1/orders/{order['id']}/pay-from-wallet", headers=applicant_headers)
    assert r.status_code == 409
    assert "کافی نیست" in r.json()["detail"]
    assert _wallet(client, applicant_headers)["balance"] == 100000.0
    _topup(client, applicant_headers, 1000000)
    r = client.post(f"/api/v1/orders/{order['id']}/pay-from-wallet", headers=applicant_headers)
    assert r.status_code == 200
    r = client.post(f"/api/v1/orders/{order['id']}/pay-from-wallet", headers=applicant_headers)
    assert r.status_code == 409


def test_wallet_admin_list_adjust_and_access(client, manager_headers, admin_headers,
                                             applicant_headers, reception_headers):
    """تعدیل مدیریتی با یادداشت؛ دسترسی: پذیرش مجاز به تعدیل نیست."""
    _topup(client, applicant_headers, 200000)
    wid = _wallet(client, applicant_headers)["user_id"]
    r = client.get("/api/v1/wallets", headers=manager_headers)
    assert r.status_code == 200
    assert any(x["user_id"] == wid for x in r.json()["items"])
    # تعدیل مثبت
    r = client.post(f"/api/v1/wallets/{wid}/adjust", headers=manager_headers, json={
        "amount": 50000, "note": "بستانکاری بابت خطای ثبت",
    })
    assert r.status_code == 200
    assert r.json()["balance"] == 250000.0
    # تعدیل منفی با کنترل مانده
    r = client.post(f"/api/v1/wallets/{wid}/adjust", headers=manager_headers, json={
        "amount": -1000000, "note": "کسر آزمون",
    })
    assert r.status_code == 409
    # پذیرش اجازه تعدیل ندارد
    r = client.post(f"/api/v1/wallets/{wid}/adjust", headers=reception_headers, json={
        "amount": 1, "note": "تست دسترسی",
    })
    assert r.status_code == 403
    # گردش کاربر برای مدیر
    r = client.get(f"/api/v1/wallets/{wid}/entries", headers=manager_headers)
    assert r.status_code == 200
    reasons = {e["reason"] for e in r.json()["items"]}
    assert "adjustment" in reasons


# ---------------- B20: استرداد ----------------

def _refund_full_cycle(client, manager_headers, applicant_headers, pay_via_wallet: bool) -> dict:
    svc = _mk_service(client, manager_headers, "استرداد چرخه")
    owner = _applicant_id(client, applicant_headers)
    order = _mk_order(client, manager_headers, svc, owner_user_id=owner)
    if pay_via_wallet:
        _topup(client, applicant_headers, 1000000)
        r = client.post(f"/api/v1/orders/{order['id']}/pay-from-wallet", headers=applicant_headers)
        assert r.status_code == 200
    else:
        _pay(client, manager_headers, order["id"], approve=True)
    return order


def test_refund_request_validation(client, manager_headers, applicant_headers):
    """استرداد فقط برای سفارش پرداخت‌شده و ≤ مبلغ مجاز."""
    svc = _mk_service(client, manager_headers, "استرداد اعتبار")
    owner = _applicant_id(client, applicant_headers)
    unpaid = _mk_order(client, manager_headers, svc, owner_user_id=owner)
    r = client.post("/api/v1/refund-requests", headers=applicant_headers, json={
        "order_id": unpaid["id"], "amount": 100000, "reason": "سفارش پرداخت نشده است",
    })
    assert r.status_code == 422
    order = _refund_full_cycle(client, manager_headers, applicant_headers, pay_via_wallet=False)
    r = client.post("/api/v1/refund-requests", headers=applicant_headers, json={
        "order_id": order["id"], "amount": 2000000, "reason": "بیش از مبلغ پرداختی",
    })
    assert r.status_code == 422
    assert "مجاز" in r.json()["detail"]


def test_refund_full_cycle_wallet_channel(client, manager_headers, applicant_headers):
    """چرخه کامل: درخواست → تأیید → اجرا → شارژ مجدد کیف پول؛ اجرای تکراری 409."""
    balance_before = _wallet(client, applicant_headers)["balance"]
    order = _refund_full_cycle(client, manager_headers, applicant_headers, pay_via_wallet=True)
    r = client.post("/api/v1/refund-requests", headers=applicant_headers, json={
        "order_id": order["id"], "amount": 400000, "reason": "انصراف از ادامه جلسات",
    })
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "pending"
    # اجرا پیش از تأیید → 409
    r = client.post(f"/api/v1/refund-requests/{req['id']}/execute", headers=manager_headers)
    assert r.status_code == 409
    # تأیید
    r = client.post(f"/api/v1/refund-requests/{req['id']}/review", headers=manager_headers,
                    json={"action": "approve", "note": "تأیید طبق سیاست انصراف"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    # اجرا
    r = client.post(f"/api/v1/refund-requests/{req['id']}/execute", headers=manager_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "executed"
    assert body["refund"]["channel"] == "wallet"
    # کیف پول شارژ مجدد شد (قبل از چرخه: صفر؛ ۱٬۰۰۰٬۰۰۰ شارژ − ۱٬۰۰۰٬۰۰۰ پرداخت + ۴۰۰٬۰۰۰ بازگشت)
    balance_after = _wallet(client, applicant_headers)["balance"]
    assert balance_after == 400000.0
    wid = _wallet(client, applicant_headers)["user_id"]
    assert verify_consistency(SessionLocal(), _uuid.UUID(wid))
    # سفارش refunded_amount به‌روز شد
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=applicant_headers).json()
    assert detail["refunded_amount"] == 400000.0
    # اجرای تکراری ممنوع
    r = client.post(f"/api/v1/refund-requests/{req['id']}/execute", headers=manager_headers)
    assert r.status_code == 409
    assert "تکراری" in r.json()["detail"]


def test_refund_total_cannot_exceed_paid(client, manager_headers, applicant_headers):
    """جمع استردادها هرگز از مبلغ پرداختی عبور نمی‌کند."""
    order = _refund_full_cycle(client, manager_headers, applicant_headers, pay_via_wallet=True)
    r = client.post("/api/v1/refund-requests", headers=applicant_headers, json={
        "order_id": order["id"], "amount": 700000, "reason": "استرداد بخش اول",
    })
    req1 = r.json()
    client.post(f"/api/v1/refund-requests/{req1['id']}/review", headers=manager_headers, json={"action": "approve"})
    client.post(f"/api/v1/refund-requests/{req1['id']}/execute", headers=manager_headers)
    # استرداد دوم 400000 → مجاز فقط 300000 → 422
    r = client.post("/api/v1/refund-requests", headers=applicant_headers, json={
        "order_id": order["id"], "amount": 400000, "reason": "استرداد بخش دوم بیش از حد",
    })
    assert r.status_code == 422
    # استرداد 300000 مجاز است
    r = client.post("/api/v1/refund-requests", headers=applicant_headers, json={
        "order_id": order["id"], "amount": 300000, "reason": "استرداد باقیمانده",
    })
    assert r.status_code == 201
    req2 = r.json()
    client.post(f"/api/v1/refund-requests/{req2['id']}/review", headers=manager_headers, json={"action": "approve"})
    r = client.post(f"/api/v1/refund-requests/{req2['id']}/execute", headers=manager_headers)
    assert r.status_code == 200
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=applicant_headers).json()
    assert detail["refunded_amount"] == 1000000.0


def test_refund_reject_and_access_control(client, manager_headers, applicant_headers, reception_headers):
    """رد با یادداشت؛ پذیرش نمی‌تواند بررسی/اجرا کند."""
    order = _refund_full_cycle(client, manager_headers, applicant_headers, pay_via_wallet=False)
    r = client.post("/api/v1/refund-requests", headers=applicant_headers, json={
        "order_id": order["id"], "amount": 100000, "reason": "درخواست آزمون رد",
    })
    req = r.json()
    # پذیرش: بررسی/اجرا ممنوع
    r = client.post(f"/api/v1/refund-requests/{req['id']}/review", headers=reception_headers,
                    json={"action": "approve"})
    assert r.status_code == 403
    # رد توسط مدیر
    r = client.post(f"/api/v1/refund-requests/{req['id']}/review", headers=manager_headers,
                    json={"action": "reject", "note": "مطابق سیاست قابل استرداد نیست"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    # اجرای درخواست ردشده → 409
    r = client.post(f"/api/v1/refund-requests/{req['id']}/execute", headers=manager_headers)
    assert r.status_code == 409
    # فهرست برای مالک فقط استردادهای خودش را نشان می‌دهد
    r = client.get("/api/v1/refund-requests", headers=applicant_headers)
    assert all(x["order_id"] == order["id"] or x["requested_by_name"] for x in r.json()["items"])
