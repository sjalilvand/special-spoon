"""فاز ۲۹ - B10/B11/B31 سند جامع: سفارش، پرداخت، فاکتور + مراکز و شعب.

- B31: slug یکتا؛ مختصات معتبر؛ شعبه منتشرنشده عمومی نیست؛
  «خدمت ناموجود برای شعبه نشان داده نشود».
- B10: سفارش از snapshot قیمت نوبت؛ پرداخت فقط پس از تأیید قطعی سمت سرور؛
  callback تکراری بی‌اثر (بدون فاکتور مضاعف، بدون خطا).
- B11: فاکتور خودکار با شماره یکتا؛ مبلغ فاکتور با snapshot سفارش منطبق.
- D02: معماری درگاه پلاگین‌پذیر؛ sandbox فعال، zarinpal بدون اعتبارنامه غیرفعال.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import bearer, login


@pytest.fixture()
def manager_headers(client, env):
    return bearer(login(client, "t_manager"))


@pytest.fixture()
def supervisor_headers(client, env):
    return bearer(login(client, "t_super"))


@pytest.fixture()
def reception_headers(client, env):
    return bearer(login(client, "t_reception"))


# ---------------- helpers ----------------

def _mk_service(client, headers, name) -> dict:
    r = client.post("/api/v1/specialties", headers=headers, json={"name": f"فاز۲۹-{name}"})
    sp = r.json()
    r = client.post("/api/v1/services", headers=headers, json={
        "specialty_id": sp["id"], "title": f"خدمت {name}", "duration_minutes": 45,
    })
    assert r.status_code == 201, r.text
    svc = r.json()
    on = date.today() - timedelta(days=1)  # دیروز تا +۱۰۰ روز: هم برای سفارش امروز و هم نوبت آینده معتبر
    r = client.post("/api/v1/tariffs", headers=headers, json={
        "service_id": svc["id"], "amount": 1200000,
        "valid_from": str(on), "valid_to": str(on + timedelta(days=101)),
    })
    assert r.status_code == 201, r.text
    return svc


def _mk_appointment_with_price(client, headers, svc) -> dict:
    """نوبت با قیمت snapshot از تعرفه (مبنای سفارش B10)."""
    m = bearer(login(client, "t_manager"))
    case_id = client.get("/api/v1/cases?page_size=1", headers=m).json()["items"][0]["id"]
    sched = datetime.combine(date.today() + timedelta(days=41),
                             datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
    r = client.post("/api/v1/appointments", headers=headers, json={
        "case_id": case_id, "service_id": svc["id"], "scheduled_at": sched.isoformat(),
    })
    assert r.status_code == 201, r.text
    return r.json()


def _pay_flow(client, headers, order_id, approve=True) -> dict:
    r = client.post(f"/api/v1/orders/{order_id}/payments", headers=headers, json={})
    assert r.status_code == 201, r.text
    auth = r.json()["authority"]
    r = client.post(
        f"/api/v1/payments/{auth}/verify?approve={'true' if approve else 'false'}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _manager(client):
    return bearer(login(client, "t_manager"))


def _reception(client):
    return bearer(login(client, "t_reception"))


# ---------------- B31: مراکز و شعب ----------------

def test_clinic_slug_unique(client, manager_headers):
    r = client.post("/api/v1/clinics", headers=manager_headers, json={
        "name": "کلینیک رز", "slug": "rose-clinic",
        "phone": "021-12345678", "website": "https://rose.example",
    })
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "rose-clinic"
    # slug تکراری → 409
    r = client.post("/api/v1/clinics", headers=manager_headers, json={
        "name": "مرکز دوم", "slug": "rose-clinic",
    })
    assert r.status_code == 409
    # slug با حروف بزرگ/فاصله → 422
    r = client.post("/api/v1/clinics", headers=manager_headers, json={
        "name": "مرکز سوم", "slug": "Bad Slug!",
    })
    assert r.status_code == 422


def test_branch_coordinates_validation(client, manager_headers):
    r = client.post("/api/v1/clinics", headers=manager_headers, json={"name": "مرکز مختصات", "slug": "coord-clinic"})
    clinic = r.json()
    # عرض خارج از بازه → 422
    r = client.post(f"/api/v1/clinics/{clinic['id']}/branches", headers=manager_headers, json={
        "name": "شعبه بدرقه", "latitude": 95.0, "longitude": 51.4,
    })
    assert r.status_code == 422
    # طول خارج از بازه → 422
    r = client.post(f"/api/v1/clinics/{clinic['id']}/branches", headers=manager_headers, json={
        "name": "شعبه بدرقه", "latitude": 35.7, "longitude": -200.0,
    })
    assert r.status_code == 422
    # مقادیر مرزی مجاز
    r = client.post(f"/api/v1/clinics/{clinic['id']}/branches", headers=manager_headers, json={
        "name": "شعبه مرزی", "latitude": 90, "longitude": -180,
    })
    assert r.status_code == 201
    # وضعیت نامعتبر
    r = client.post(f"/api/v1/clinics/{clinic['id']}/branches", headers=manager_headers, json={
        "name": "شعبه وضعیت بد", "status": "open",
    })
    assert r.status_code == 422


def test_unpublished_branch_not_public_and_offering_rules(client, manager_headers):
    """B31 پذیرش: شعبه منتشرنشده عمومی نیست؛ خدمت ناموجود/غیرفعال نمایش داده نمی‌شود."""
    svc = _mk_service(client, manager_headers, "شعبه‌ای")
    r = client.post("/api/v1/clinics", headers=manager_headers, json={"name": "مرکز انتشار", "slug": "pub-clinic"})
    clinic = r.json()
    r = client.post(f"/api/v1/clinics/{clinic['id']}/branches", headers=manager_headers, json={
        "name": "شعبه ونک", "province": "تهران", "city": "تهران",
        "address": "ونک، خیابان نمونه", "latitude": 35.76, "longitude": 51.41,
        "status": "draft", "service_ids": [svc["id"]],
    })
    assert r.status_code == 201
    branch = r.json()
    assert branch["status"] == "draft"
    # draft در فهرست عمومی نیست
    r = client.get("/api/v1/public/branches")
    assert all(b["id"] != branch["id"] for b in r.json()["items"])
    # انتشار
    r = client.patch(f"/api/v1/branches/{branch['id']}", headers=manager_headers, json={"status": "published"})
    assert r.json()["status"] == "published"
    r = client.get("/api/v1/public/branches")
    items = [b for b in r.json()["items"] if b["id"] == branch["id"]]
    assert len(items) == 1
    pub = items[0]
    assert pub["clinic_name"] == "مرکز انتشار"
    assert [s["id"] for s in pub["services"]] == [svc["id"]]
    # حذف offering → خدمت ناموجود دیگر نشان داده نمی‌شود
    r = client.put(f"/api/v1/branches/{branch['id']}/offerings", headers=manager_headers,
                   json={"service_ids": []})
    assert r.status_code == 200
    r = client.get("/api/v1/public/branches")
    pub = next(b for b in r.json()["items"] if b["id"] == branch["id"])
    assert pub["services"] == []
    # فیلتر شهر کار می‌کند
    r = client.get("/api/v1/public/branches?city=تهران")
    assert any(b["id"] == branch["id"] for b in r.json()["items"])
    r = client.get("/api/v1/public/branches?city=شیراز")
    assert all(b["id"] != branch["id"] for b in r.json()["items"])


def test_inactive_service_hidden_from_public_branch(client, manager_headers):
    """خدمتِ غیرفعالِ کاتالوگ برای شعبه منتشرشده هم نشان داده نمی‌شود."""
    svc = _mk_service(client, manager_headers, "غیرفعال شعبه")
    r = client.post("/api/v1/clinics", headers=manager_headers, json={"name": "مرکز غیرفعال", "slug": "inact-clinic"})
    clinic = r.json()
    r = client.post(f"/api/v1/clinics/{clinic['id']}/branches", headers=manager_headers, json={
        "name": "شعبه شهرک", "city": "تهران", "status": "published",
        "service_ids": [svc["id"]],
    })
    branch = r.json()
    r = client.get("/api/v1/public/branches")
    pub = next(b for b in r.json()["items"] if b["id"] == branch["id"])
    assert len(pub["services"]) == 1
    # غیرفعال‌سازی خدمت
    r = client.patch(f"/api/v1/services/{svc['id']}", headers=manager_headers, json={"status": "inactive"})
    assert r.status_code == 200
    r = client.get("/api/v1/public/branches")
    pub = next(b for b in r.json()["items"] if b["id"] == branch["id"])
    assert pub["services"] == []


def test_branch_access_control(client, manager_headers, supervisor_headers):
    r = client.get("/api/v1/clinics", headers=manager_headers)
    assert r.status_code == 200
    # مسئول فنی/پذیرش فقط خواندن
    r = client.get("/api/v1/clinics", headers=supervisor_headers)
    assert r.status_code == 200
    r = client.post("/api/v1/clinics", headers=supervisor_headers, json={"name": "x", "slug": "x-clinic"})
    assert r.status_code == 403
    # بدون احراز هویت
    r = client.get("/api/v1/clinics")
    assert r.status_code == 401


# ---------------- B10: سفارش و پرداخت ----------------

def test_order_from_appointment_snapshot(client, manager_headers):
    """B10: سفارش از snapshot قیمت نوبت ساخته می‌شود؛ هر نوبت فقط یک سفارش."""
    m = _manager(client)
    svc = _mk_service(client, manager_headers, "سفارش نوبت")
    appt = _mk_appointment_with_price(client, m, svc)
    assert appt["price_amount"] == 1200000
    r = client.post("/api/v1/orders", headers=m, json={
        "appointment_id": appt["id"],
    })
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["amount"] == 1200000.0
    assert order["payable_amount"] == 1200000.0
    assert order["status"] == "pending"
    assert order["order_number"].startswith("ORD-")
    # سفارش تکراری برای همان نوبت → 409
    r = client.post("/api/v1/orders", headers=m, json={"appointment_id": appt["id"]})
    assert r.status_code == 409


def test_order_with_discount_and_validation(client, manager_headers):
    m = _manager(client)
    svc = _mk_service(client, manager_headers, "سفارش تخفیف")
    r = client.post("/api/v1/orders", headers=m, json={
        "service_id": svc["id"], "discount_amount": 200000,
    })
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["amount"] == 1200000.0
    assert order["payable_amount"] == 1000000.0
    # تخفیف بیشتر از مبلغ → 422
    r = client.post("/api/v1/orders", headers=m, json={
        "service_id": svc["id"], "discount_amount": 999999999,
    })
    assert r.status_code == 422
    # خدمت بدون پارامتر → 422
    r = client.post("/api/v1/orders", headers=m, json={"title": "بد مرجع"})
    assert r.status_code == 422


def test_sandbox_payment_verify_and_idempotent_callback(client, manager_headers):
    """B10 پذیرش: تأیید قطعی سمت سرور؛ callback تکراری بی‌اثر."""
    m = _manager(client)
    svc = _mk_service(client, manager_headers, "پرداخت idem")
    order = client.post("/api/v1/orders", headers=m, json={"service_id": svc["id"]}).json()
    pay = _pay_flow(client, m, order["id"], approve=True)
    assert pay["ok"] is True
    assert pay["status"] == "success"
    assert pay["order_status"] == "paid"
    assert pay["gateway_ref"]
    # callback تکراری با همان authority → همان وضعیت، بدون خطا، بی‌اثر
    r = client.post(f"/api/v1/payments/callback/sandbox?authority={pay['authority']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert body["order_status"] == "paid"
    # verify تکراری هم idempotent است
    r = client.post(f"/api/v1/payments/{pay['authority']}/verify", headers=m)
    assert r.status_code == 200
    assert r.json()["idempotent"] is True


def test_failed_verify_marks_order_failed(client, manager_headers):
    m = _manager(client)
    svc = _mk_service(client, manager_headers, "پرداخت رد")
    order = client.post("/api/v1/orders", headers=m, json={"service_id": svc["id"]}).json()
    pay = _pay_flow(client, m, order["id"], approve=False)
    assert pay["ok"] is False
    assert pay["status"] == "failed"
    assert pay["order_status"] == "failed"


def test_cancelled_order_rejects_payment(client, manager_headers):
    m = _manager(client)
    svc = _mk_service(client, manager_headers, "سفارش لغو")
    order = client.post("/api/v1/orders", headers=m, json={"service_id": svc["id"]}).json()
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=m)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    # پرداخت روی سفارش لغوشده → 409
    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=m, json={})
    assert r.status_code == 409
    # سفارش پرداخت‌شده قابل لغو نیست
    order2 = client.post("/api/v1/orders", headers=m, json={"service_id": svc["id"]}).json()
    _pay_flow(client, m, order2["id"], approve=True)
    r = client.post(f"/api/v1/orders/{order2['id']}/cancel", headers=m)
    assert r.status_code == 409


def test_gateways_status_and_unknown_gateway(client, manager_headers):
    """D02: sandbox فعال و پیش‌فرض؛ zarinpal بدون merchant غیرفعال."""
    m = _manager(client)
    r = client.get("/api/v1/payments/gateways", headers=m)
    assert r.status_code == 200
    items = {g["code"]: g for g in r.json()["items"]}
    assert items["sandbox"]["enabled"] is True
    assert items["sandbox"]["is_default"] is True
    assert items["zarinpal"]["enabled"] is False
    # درگاه ناشناخته → 409
    svc = _mk_service(client, manager_headers, "درگاه ناشناخته")
    order = client.post("/api/v1/orders", headers=m, json={"service_id": svc["id"]}).json()
    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=m, json={"gateway": "idpay"})
    assert r.status_code == 409


def test_order_visibility_access_control(client, manager_headers, supervisor_headers):
    """سفارش مالک‌محور است؛ کاربر بدون نقش دید نمی‌تواند سفارش دیگری را ببیند."""
    m = _manager(client)
    from conftest import PASSWORD
    r = client.post("/api/v1/auth/login", json={"username": "t_reception", "password": PASSWORD})
    rcpt = bearer(r.json()["access_token"])
    svc = _mk_service(client, manager_headers, "دسترسی سفارش")
    order = client.post("/api/v1/orders", headers=m, json={"service_id": svc["id"]}).json()
    # پذیرش (CREATE_ROLES) آغاز پرداخت دارد ولی دیدن سفارش مدیر هم مجاز (VIEW)
    r = client.get(f"/api/v1/orders/{order['id']}", headers=rcpt)
    assert r.status_code == 200
    # بدون احراز هویت → 401
    r = client.get(f"/api/v1/orders/{order['id']}")
    assert r.status_code == 401


# ---------------- B11: فاکتور ----------------

def test_invoice_issued_once_with_unique_number(client, manager_headers):
    """B11: پس از پرداخت موفق دقیقاً یک فاکتور با شماره یکتا؛ مبلغ منطبق snapshot."""
    m = _manager(client)
    svc = _mk_service(client, manager_headers, "فاکتور یگانه")
    order = client.post("/api/v1/orders", headers=m, json={"service_id": svc["id"]}).json()
    pay = _pay_flow(client, m, order["id"], approve=True)
    assert pay["ok"] is True
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=m).json()
    inv_id = detail["invoice_id"]
    assert inv_id is not None
    assert detail["invoice_number"].startswith("INV-")
    # callback/verify تکراری فاکتور مضاعف نمی‌سازد
    client.post(f"/api/v1/payments/callback/sandbox?authority={pay['authority']}")
    client.post(f"/api/v1/payments/{pay['authority']}/verify", headers=m)
    detail2 = client.get(f"/api/v1/orders/{order['id']}", headers=m).json()
    assert detail2["invoice_id"] == inv_id
    # جزئیات فاکتور: مبلغ منطبق snapshot سفارش + اقلام
    r = client.get(f"/api/v1/invoices/{inv_id}", headers=m)
    assert r.status_code == 200
    inv = r.json()
    assert inv["total_amount"] == order["payable_amount"]
    assert len(inv["items"]) == 1
    assert inv["items"][0]["line_total"] == order["payable_amount"]
    assert inv["status"] == "issued"


def test_invoice_numbers_are_sequential_and_unique(client, manager_headers):
    m = _manager(client)
    numbers = []
    for i in range(3):
        svc = _mk_service(client, manager_headers, f"شماره فاکتور {i}")
        order = client.post("/api/v1/orders", headers=m, json={"service_id": svc["id"]}).json()
        _pay_flow(client, m, order["id"], approve=True)
        detail = client.get(f"/api/v1/orders/{order['id']}", headers=m).json()
        numbers.append(detail["invoice_number"])
    assert len(set(numbers)) == 3
    seqs = sorted(int(n.rsplit("-", 1)[1]) for n in numbers)
    assert seqs[1] == seqs[0] + 1 and seqs[2] == seqs[1] + 1


def test_invoice_not_created_before_payment(client, manager_headers):
    m = _manager(client)
    svc = _mk_service(client, manager_headers, "فاکتور قبل پرداخت")
    order = client.post("/api/v1/orders", headers=m, json={"service_id": svc["id"]}).json()
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=m).json()
    assert detail["invoice_id"] is None
    # فهرست فاکتورها بدون پرداخت موفق خالی از این سفارش است
    r = client.get("/api/v1/invoices", headers=m)
    assert all(i["order_id"] != order["id"] for i in r.json()["items"])
