"""فاز ۳۳ - B32 + B21 سند جامع: دسته‌بندی موضوعی + سازمان/قرارداد/سهم پرداخت.

- B32: slug یکتا؛ چرخه والد ممنوع؛ حذف دسته استفاده‌شده ممنوع (409)؛
  «دسته غیرفعال در صفحات عمومی نشان داده نشود».
- B21: قرارداد سازمان (درصد/سقف/بازه/وضعیت/دامنه خدمت)؛ تقسیم سهم در
  ساخت سفارش snapshot می‌شود؛ «قرارداد و تخفیف هم‌زمان ممنوع»؛
  draft/منقضی/ملغی اعمال نمی‌شود؛ مطالبه از سازمان گزارش می‌شود.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import bearer, login


@pytest.fixture()
def manager_headers(client, env):
    return bearer(login(client, "t_manager"))


# ---------------- helpers ----------------

def _mk_service(client, headers, name, amount=1000000) -> dict:
    r = client.post("/api/v1/specialties", headers=headers, json={"name": f"فاز۳۳-{name}"})
    sp = r.json()
    r = client.post("/api/v1/services", headers=headers, json={
        "specialty_id": sp["id"], "title": f"خدمت {name}", "duration_minutes": 45,
    })
    assert r.status_code == 201, r.text
    svc = r.json()
    on = date.today() - timedelta(days=1)
    r = client.post("/api/v1/tariffs", headers=headers, json={
        "service_id": svc["id"], "amount": amount,
        "valid_from": str(on), "valid_to": str(on + timedelta(days=200)),
    })
    assert r.status_code == 201, r.text
    return svc


def _mk_appointment(client, headers, svc) -> dict:
    """نوبت با قیمت snapshot برای سفارش."""
    m = bearer(login(client, "t_manager"))
    case_id = client.get("/api/v1/cases?page_size=1", headers=m).json()["items"][0]["id"]
    sched = datetime.combine(date.today() + timedelta(days=30),
                             datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
    r = client.post("/api/v1/appointments", headers=headers, json={
        "case_id": case_id, "service_id": svc["id"], "scheduled_at": sched.isoformat(),
    })
    assert r.status_code == 201, r.text
    return r.json()


def _get_case_id(client, headers) -> str:
    return client.get("/api/v1/cases?page_size=1", headers=headers).json()["items"][0]["id"]


def _mk_org(client, headers, name=None, slug=None, **kw) -> dict:
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/api/v1/organizations", headers=headers, json={
        "name": name or f"سازمان {suffix}", "slug": slug or f"org-{suffix}",
        "phone": "021-88776655", **kw,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _mk_contract(client, headers, org_id, percent=30, cap=None, status=None,
                 from_off=1, days=30, service_ids=None, title="قرارداد آزمون") -> dict:
    r = client.post(f"/api/v1/organizations/{org_id}/contracts", headers=headers, json={
        "title": title, "coverage_percent": percent,
        "coverage_cap_amount": cap,
        "valid_from": str(date.today() - timedelta(days=from_off)),
        "valid_to": str(date.today() + timedelta(days=days)) if days is not None else None,
        "service_ids": service_ids or [],
    })
    assert r.status_code == 201, r.text
    contract = r.json()
    if status:
        r = client.patch(f"/api/v1/contracts/{contract['id']}", headers=headers,
                         json={"status": status})
        assert r.status_code == 200, r.text
        contract = r.json()
    return contract


def _assign_org(client, headers, applicant_id, org_id) -> dict:
    r = client.patch(f"/api/v1/applicants/{applicant_id}", headers=headers,
                     json={"organization_id": org_id})
    assert r.status_code == 200, r.text
    return r.json()


def _applicant_id(client, headers) -> str:
    """متقاضی پرونده آزمون (اولین متقاضی لیست) — همان متقاضی پرونده conftest."""
    r = client.get("/api/v1/applicants?page_size=1", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["items"][0]["id"]


# ---------------- B32: دسته‌بندی موضوعی ----------------

def test_topic_create_slug_unique_and_validation(client, manager_headers):
    r = client.post("/api/v1/topics", headers=manager_headers, json={
        "name": "اضطراب", "slug": "anxiety",
        "description": "دسته اضطراب و اختلالات مرتبط",
    })
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "anxiety"
    # slug تکراری → 409
    r = client.post("/api/v1/topics", headers=manager_headers, json={"name": "دوم", "slug": "anxiety"})
    assert r.status_code == 409
    # slug نامعتبر → 422
    r = client.post("/api/v1/topics", headers=manager_headers, json={"name": "سوم", "slug": "Bad Slug!"})
    assert r.status_code == 422
    # نام کوتاه → 422
    r = client.post("/api/v1/topics", headers=manager_headers, json={"name": "ا", "slug": "short-name"})
    assert r.status_code == 422


def test_topic_hierarchy_parent_and_cycle(client, manager_headers):
    r = client.post("/api/v1/topics", headers=manager_headers, json={"name": "سلامت روان", "slug": "mental-health"})
    parent = r.json()
    r = client.post("/api/v1/topics", headers=manager_headers, json={
        "name": "اضطراب", "slug": "anxiety-child", "parent_id": parent["id"],
    })
    assert r.status_code == 201, r.text
    child = r.json()
    assert child["parent_name"] == "سلامت روان"
    r = client.post("/api/v1/topics", headers=manager_headers, json={
        "name": "وحشت", "slug": "panic", "parent_id": child["id"],
    })
    grandchild = r.json()
    # چرخه: والدِ «اضطراب» را «وحشت» کن (فرزند خودش) → 422
    r = client.patch(f"/api/v1/topics/{child['id']}", headers=manager_headers,
                     json={"parent_id": grandchild["id"]})
    assert r.status_code == 422
    # خودِ خود → 422
    r = client.patch(f"/api/v1/topics/{child['id']}", headers=manager_headers,
                     json={"parent_id": child["id"]})
    assert r.status_code == 422
    # والد غیرفعال → 422
    r = client.patch(f"/api/v1/topics/{parent['id']}", headers=manager_headers, json={"is_active": False})
    assert r.status_code == 200
    r = client.post("/api/v1/topics", headers=manager_headers, json={
        "name": "فرزندِ والد غیرفعال", "slug": "under-inactive", "parent_id": parent["id"],
    })
    assert r.status_code == 422


def test_topic_delete_rules(client, manager_headers):
    svc = _mk_service(client, manager_headers, "حذف‌دسته")
    r = client.post("/api/v1/topics", headers=manager_headers, json={"name": "دسته حذف", "slug": "del-topic"})
    topic = r.json()
    # اتصال خدمت → حذف 409
    r = client.put(f"/api/v1/topics/{topic['id']}/services", headers=manager_headers,
                   json={"service_ids": [svc["id"]]})
    assert r.status_code == 200, r.text
    assert r.json()["service_count"] == 1
    r = client.delete(f"/api/v1/topics/{topic['id']}", headers=manager_headers)
    assert r.status_code == 409
    # برداشتن اتصال → حذف مجاز
    r = client.put(f"/api/v1/topics/{topic['id']}/services", headers=manager_headers,
                   json={"service_ids": []})
    assert r.status_code == 200
    # فرزند دارد → 409
    r = client.post("/api/v1/topics", headers=manager_headers, json={
        "name": "فرزند حذف", "slug": "del-topic-child", "parent_id": topic["id"],
    })
    assert r.status_code == 201
    r = client.delete(f"/api/v1/topics/{topic['id']}", headers=manager_headers)
    assert r.status_code == 409
    # دسته بی‌فرزند بی‌خدمت → 204
    r = client.delete(f"/api/v1/topics/{r.json()['id'] if False else client.post('/api/v1/topics', headers=manager_headers, json={'name': 'خالی', 'slug': 'empty-topic'}).json()['id']}", headers=manager_headers)
    assert r.status_code == 204


def test_topic_public_only_active_with_service_count(client, manager_headers):
    svc_a = _mk_service(client, manager_headers, "عمومی‌الف")
    svc_b = _mk_service(client, manager_headers, "عمومی‌ب")
    r = client.post("/api/v1/topics", headers=manager_headers, json={
        "name": "روابط", "slug": "relations", "sort_order": 2,
    })
    topic = r.json()
    client.put(f"/api/v1/topics/{topic['id']}/services", headers=manager_headers,
               json={"service_ids": [svc_a["id"], svc_b["id"]]})
    # عمومی: فعال با شمارش خدمات فعال
    r = client.get("/api/v1/public/topics")
    assert r.status_code == 200, r.text
    items = {i["id"]: i for i in r.json()["items"]}
    assert topic["id"] in items
    assert items[topic["id"]]["active_service_count"] == 2
    # غیرفعال → از عمومی حذف
    r = client.patch(f"/api/v1/topics/{topic['id']}", headers=manager_headers, json={"is_active": False})
    assert r.status_code == 200
    r = client.get("/api/v1/public/topics")
    assert topic["id"] not in {i["id"] for i in r.json()["items"]}
    # فهرست مدیریتی include_inactive=False فقط فعال‌ها
    r = client.get("/api/v1/topics", headers=manager_headers, params={"include_inactive": False})
    assert topic["id"] not in {i["id"] for i in r.json()["items"]}


# ---------------- B21: سازمان/قرارداد ----------------

def test_org_create_unique_slug_and_national_id(client, manager_headers):
    org = _mk_org(client, manager_headers, name="شرکت آزمون", slug="test-co", national_id="14005554433")
    assert org["slug"] == "test-co"
    # slug تکراری
    r = client.post("/api/v1/organizations", headers=manager_headers,
                    json={"name": "دو", "slug": "test-co"})
    assert r.status_code == 409
    # شناسه ملی تکراری
    r = client.post("/api/v1/organizations", headers=manager_headers,
                    json={"name": "سه", "slug": "third-co", "national_id": "14005554433"})
    assert r.status_code == 409
    # slug نامعتبر
    r = client.post("/api/v1/organizations", headers=manager_headers,
                    json={"name": "چهار", "slug": "BAD SLUG"})
    assert r.status_code == 422


def test_contract_validation_rules(client, manager_headers):
    org = _mk_org(client, manager_headers)
    # درصد خارج از بازه → 422 (pydantic)
    r = client.post(f"/api/v1/organizations/{org['id']}/contracts", headers=manager_headers, json={
        "title": "قرارداد بد", "coverage_percent": 150,
        "valid_from": str(date.today()),
    })
    assert r.status_code == 422
    r = client.post(f"/api/v1/organizations/{org['id']}/contracts", headers=manager_headers, json={
        "title": "قرارداد صفر", "coverage_percent": 0,
        "valid_from": str(date.today()),
    })
    assert r.status_code == 422
    # بازه تاریخ معکوس → 422
    r = client.post(f"/api/v1/organizations/{org['id']}/contracts", headers=manager_headers, json={
        "title": "قرارداد معکوس", "coverage_percent": 50,
        "valid_from": str(date.today()),
        "valid_to": str(date.today() - timedelta(days=1)),
    })
    assert r.status_code == 422
    # وضعیت نامعتبر
    r = client.post(f"/api/v1/organizations/{org['id']}/contracts", headers=manager_headers, json={
        "title": "قرارداد وضعیت", "coverage_percent": 50, "valid_from": str(date.today()),
    })
    cid = r.json()["id"]
    r = client.patch(f"/api/v1/contracts/{cid}", headers=manager_headers, json={"status": "weird"})
    assert r.status_code == 422
    # ملغی دوباره فعال نمی‌شود
    client.patch(f"/api/v1/contracts/{cid}", headers=manager_headers, json={"status": "active"})
    r = client.patch(f"/api/v1/contracts/{cid}", headers=manager_headers, json={"status": "terminated"})
    assert r.status_code == 200
    r = client.patch(f"/api/v1/contracts/{cid}", headers=manager_headers, json={"status": "active"})
    assert r.status_code == 422


def test_applicant_org_assignment(client, manager_headers):
    org = _mk_org(client, manager_headers, name="سازمان پرسنلی", slug="staff-co")
    ap_id = _applicant_id(client, manager_headers)
    out = _assign_org(client, manager_headers, ap_id, org["id"])
    assert out["organization_id"] == org["id"]
    assert out["organization_name"] == org["name"]


def test_order_org_share_split_snapshot(client, manager_headers):
    """قرارداد فعال ۳۰٪ → سهم سازمان snapshot؛ متقاضی ۷۰٪ می‌پردازد."""
    svc = _mk_service(client, manager_headers, "سهم‌سازمان", amount=1000000)
    appt = _mk_appointment(client, manager_headers, svc)
    org = _mk_org(client, manager_headers)
    _mk_contract(client, manager_headers, org["id"], percent=30, status="active")
    ap_id = _applicant_id(client, manager_headers)
    _assign_org(client, manager_headers, ap_id, org["id"])

    r = client.post("/api/v1/orders", headers=manager_headers,
                    json={"appointment_id": appt["id"]})
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["amount"] == 1000000.0
    assert order["organization_id"] == org["id"]
    assert order["contract_id"] is not None
    assert order["coverage_percent"] == 30.0
    assert order["org_share_amount"] == 300000.0
    assert order["applicant_share_amount"] == 700000.0
    assert order["payable_amount"] == 700000.0


def test_order_org_share_cap(client, manager_headers):
    """سقف سهم: ۵۰٪ از یک میلیون = ۵۰۰٬۰۰۰ ولی سقف ۲۰۰٬۰۰۰ → ۲۰۰٬۰۰۰."""
    svc = _mk_service(client, manager_headers, "سهم‌سقف", amount=1000000)
    appt = _mk_appointment(client, manager_headers, svc)
    org = _mk_org(client, manager_headers)
    _mk_contract(client, manager_headers, org["id"], percent=50, cap=200000, status="active")
    ap_id = _applicant_id(client, manager_headers)
    _assign_org(client, manager_headers, ap_id, org["id"])

    r = client.post("/api/v1/orders", headers=manager_headers,
                    json={"appointment_id": appt["id"]})
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["org_share_amount"] == 200000.0
    assert order["payable_amount"] == 800000.0


def test_order_contract_and_discount_conflict(client, manager_headers):
    """قرارداد و تخفیف هم‌زمان ممنوع (منع دو‌جبری شدن هزینه)."""
    svc = _mk_service(client, manager_headers, "سهم‌تخفیف", amount=1000000)
    appt = _mk_appointment(client, manager_headers, svc)
    org = _mk_org(client, manager_headers)
    _mk_contract(client, manager_headers, org["id"], percent=30, status="active")
    ap_id = _applicant_id(client, manager_headers)
    _assign_org(client, manager_headers, ap_id, org["id"])

    r = client.post("/api/v1/orders", headers=manager_headers,
                    json={"appointment_id": appt["id"], "discount_amount": 100000})
    assert r.status_code == 422
    # بدون تخفیف، سفارش با سهم سازمان ساخته می‌شود
    r = client.post("/api/v1/orders", headers=manager_headers,
                    json={"appointment_id": appt["id"]})
    assert r.status_code == 201
    assert r.json()["org_share_amount"] == 300000.0


def test_contract_draft_expired_terminated_not_applied(client, manager_headers):
    """پیش‌نویس/منقضی/ملغی در تقسیم سهم اعمال نمی‌شود."""
    svc = _mk_service(client, manager_headers, "سهم‌وضعیت", amount=1000000)
    org = _mk_org(client, manager_headers)
    ap_id = _applicant_id(client, manager_headers)
    _assign_org(client, manager_headers, ap_id, org["id"])

    def _order():
        appt = _mk_appointment(client, manager_headers, svc)  # هر سفارش نوبت خودش
        r = client.post("/api/v1/orders", headers=manager_headers,
                        json={"appointment_id": appt["id"]})
        assert r.status_code == 201, r.text
        return r.json()

    # پیش‌نویس → بدون تقسیم
    c_draft = _mk_contract(client, manager_headers, org["id"], percent=40)  # status پیش‌فرض draft
    assert _order()["org_share_amount"] is None

    # منقضی (active ولی بازه گذشته) → بدون تقسیم
    r = client.post(f"/api/v1/organizations/{org['id']}/contracts", headers=manager_headers, json={
        "title": "قرارداد منقضی", "coverage_percent": 40,
        "valid_from": str(date.today() - timedelta(days=20)),
        "valid_to": str(date.today() - timedelta(days=1)),
    })
    expired = r.json()
    r = client.patch(f"/api/v1/contracts/{expired['id']}", headers=manager_headers, json={"status": "active"})
    assert r.status_code == 200
    assert _order()["org_share_amount"] is None

    # فعال‌سازی قرارداد اول → تقسیم اعمال می‌شود
    r = client.patch(f"/api/v1/contracts/{c_draft['id']}", headers=manager_headers, json={"status": "active"})
    assert r.status_code == 200
    assert _order()["org_share_amount"] == 400000.0


def test_contract_service_scope(client, manager_headers):
    """دامنه خدمت قرارداد: فقط خدمات مندرج؛ بدون ردیف = همه."""
    svc_a = _mk_service(client, manager_headers, "دامنه‌الف", amount=1000000)
    svc_b = _mk_service(client, manager_headers, "دامنه‌ب", amount=2000000)
    org = _mk_org(client, manager_headers)
    _mk_contract(client, manager_headers, org["id"], percent=25, status="active",
                 service_ids=[svc_a["id"]])
    ap_id = _applicant_id(client, manager_headers)
    _assign_org(client, manager_headers, ap_id, org["id"])

    # نوبت خدمت خارج از دامنه → بدون تقسیم
    appt_b = _mk_appointment(client, manager_headers, svc_b)
    r = client.post("/api/v1/orders", headers=manager_headers, json={"appointment_id": appt_b["id"]})
    assert r.status_code == 201
    assert r.json()["org_share_amount"] is None
    # نوبت خدمت در دامنه → تقسیم ۲۵٪
    appt_a = _mk_appointment(client, manager_headers, svc_a)
    r = client.post("/api/v1/orders", headers=manager_headers, json={"appointment_id": appt_a["id"]})
    assert r.status_code == 201
    assert r.json()["org_share_amount"] == 250000.0


def test_org_receivables_report(client, manager_headers):
    """مطالبه از سازمان: سهم سازمان سفارش پرداخت‌شده گزارش می‌شود."""
    svc = _mk_service(client, manager_headers, "مطالبه", amount=1000000)
    appt = _mk_appointment(client, manager_headers, svc)
    org = _mk_org(client, manager_headers)
    _mk_contract(client, manager_headers, org["id"], percent=30, status="active")
    ap_id = _applicant_id(client, manager_headers)
    _assign_org(client, manager_headers, ap_id, org["id"])

    r = client.post("/api/v1/orders", headers=manager_headers, json={"appointment_id": appt["id"]})
    order = r.json()
    # پرداخت سهم متقاضی (۷۰۰ هزار) از درگاه sandbox
    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=manager_headers, json={})
    assert r.status_code == 201, r.text
    auth = r.json()["authority"]
    r = client.post(f"/api/v1/payments/{auth}/verify?approve=true", headers=manager_headers)
    assert r.status_code == 200, r.text

    r = client.get(f"/api/v1/organizations/{org['id']}/receivables", headers=manager_headers)
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["paid_orders_with_share"] >= 1
    assert rep["org_share_total"] >= 300000
    assert rep["total_amount"] >= 1000000
    assert rep["applicant_share_total"] == rep["total_amount"] - rep["org_share_total"]
    assert rep["items"][0]["order_number"] == order["order_number"]


def test_org_receivables_access_control(client, manager_headers):
    """گزارش مطالبه فقط نقش‌های مدیریتی؛ پذیرش/مشاور ممنوع."""
    org = _mk_org(client, manager_headers)
    r = client.get(f"/api/v1/organizations/{org['id']}/receivables",
                   headers=bearer(login(client, "t_counsa")))
    assert r.status_code == 403
    r = client.get(f"/api/v1/organizations/{org['id']}/receivables",
                   headers=bearer(login(client, "t_reception")))
    assert r.status_code == 403
    # مشاهده سازمان‌ها برای پذیرش مجاز است (VIEW_ROLES)
    r = client.get("/api/v1/organizations", headers=bearer(login(client, "t_reception")))
    assert r.status_code == 200
