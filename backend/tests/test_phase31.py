"""فاز ۳۱ - B22 سند جامع: کدینگ، سند حسابداری، تسویه، مغایرت و گزارش مالی.

قواعد آزمون‌شده سند:
- «سند متوازن» — سند نامتوازن/دوسمتی/صفر 422؛ هر سند خودکار متوازن است.
- «قابل ردیابی به رویداد مالی» — پرداخت/استرداد/تعدیل سند خودکار با
  مرجع رویداد دارند؛ تکرار (backfill دوباره) سند مضاعف نمی‌سازد.
- «فروش گزارش با داده مالی تطبیق کند» (B24×B22) — reconciliation پس
  از backfill بدون مغایرت است.
- تسویه: فقط پرداخت‌های تسویه‌نشده، اجرای تکراری ممنوع، سند تسویه متوازن.
"""
import uuid as _uuid
from datetime import date, timedelta

import pytest

from conftest import bearer, login

from app.db.session import SessionLocal


@pytest.fixture()
def manager_headers(client, env):
    return bearer(login(client, "t_manager"))


@pytest.fixture()
def admin_headers(client, env):
    return bearer(login(client, "t_admin"))


@pytest.fixture()
def applicant_headers(client, env):
    return bearer(login(client, "t_appa"))


# ---------------- helpers ----------------

def _mk_service(client, headers, name) -> dict:
    tag = _uuid.uuid4().hex[:6]
    r = client.post("/api/v1/specialties", headers=headers, json={"name": f"فاز۳۱-{name}-{tag}"})
    sp = r.json()
    r = client.post("/api/v1/services", headers=headers, json={
        "specialty_id": sp["id"], "title": f"خدمت {name}", "duration_minutes": 45,
    })
    svc = r.json()
    from datetime import date as _d
    on = _d.today() - timedelta(days=1)
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


def _topup(client, headers, amount) -> None:
    r = client.post("/api/v1/wallet/topup", headers=headers, json={"amount": amount})
    assert r.status_code == 201, r.text
    auth = r.json()["authority"]
    r = client.post(f"/api/v1/payments/{auth}/verify?approve=true", headers=headers)
    assert r.status_code == 200, r.text


def _entries_of_source(client, headers, source_type, source_id=None) -> list:
    params = {"source_type": source_type}
    r = client.get("/api/v1/journal-entries", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return [e for e in r.json()["items"] if source_id is None or e["source_id"] == source_id]


def _get(client, headers, url, params=None) -> dict:
    r = client.get(url, headers=headers, params=params or {})
    assert r.status_code == 200, r.text
    return r.json()


def _entry_balanced(entry: dict) -> bool:
    return abs(sum(l["debit"] for l in entry["lines"]) - sum(l["credit"] for l in entry["lines"])) < 0.01


# ---------------- کدینگ ----------------

def test_chart_of_accounts_seeded(client, manager_headers):
    items = _get(client, manager_headers, "/api/v1/accounts")["items"]
    codes = {a["code"] for a in items}
    assert {"1101", "1102", "2101", "2102", "4101", "4102", "5102"} <= codes
    assert len(codes) == len({a["code"] for a in items})  # کد یکتا
    assert all(a["is_system"] for a in items if a["code"] in {"1101", "2101", "4101"})


def test_create_custom_account_and_duplicate(client, manager_headers):
    r = client.post("/api/v1/accounts", headers=manager_headers, json={
        "code": "9901", "name": "حساب آزمونی", "type": "expense",
    })
    assert r.status_code == 201, r.text
    assert r.json()["is_system"] is False
    r = client.post("/api/v1/accounts", headers=manager_headers, json={
        "code": "9901", "name": "تکراری", "type": "expense",
    })
    assert r.status_code == 409


# ---------------- سند دستی و قاعده توازن ----------------

def _two_accounts(client, headers) -> tuple[str, str]:
    items = _get(client, headers, "/api/v1/accounts")["items"]
    a1 = next(a for a in items if a["code"] == "1101")
    a2 = next(a for a in items if a["code"] == "1103")
    return a1["id"], a2["id"]


def test_manual_entry_balanced_ok(client, manager_headers):
    a1, a2 = _two_accounts(client, manager_headers)
    r = client.post("/api/v1/journal-entries", headers=manager_headers, json={
        "description": "سند دستی آزمون متوازن",
        "lines": [
            {"account_id": a1, "debit": 50000, "credit": 0, "description": "بدهکار"},
            {"account_id": a2, "debit": 0, "credit": 50000, "description": "بستانکار"},
        ],
    })
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["source_type"] == "manual"
    assert entry["entry_no"].startswith("JE-")
    assert _entry_balanced(entry)


def test_manual_entry_unbalanced_rejected(client, manager_headers):
    a1, a2 = _two_accounts(client, manager_headers)
    r = client.post("/api/v1/journal-entries", headers=manager_headers, json={
        "description": "سند نامتوازن باید رد شود",
        "lines": [
            {"account_id": a1, "debit": 10000, "credit": 0},
            {"account_id": a2, "debit": 0, "credit": 9999},
        ],
    })
    assert r.status_code == 422
    assert "متوازن" in r.json()["detail"]


def test_manual_entry_two_sided_line_rejected(client, manager_headers):
    a1, a2 = _two_accounts(client, manager_headers)
    r = client.post("/api/v1/journal-entries", headers=manager_headers, json={
        "description": "ردیف دوسمتی باید رد شود",
        "lines": [
            {"account_id": a1, "debit": 1000, "credit": 1000},
            {"account_id": a2, "debit": 0, "credit": 1000},
        ],
    })
    assert r.status_code == 422


# ---------------- سند خودکار پرداخت ----------------

def test_gateway_payment_auto_entry_idempotent(client, admin_headers, manager_headers):
    svc = _mk_service(client, admin_headers, "پرداخت درگاه")
    order = _mk_order(client, admin_headers, svc)
    pay = _pay(client, admin_headers, order["id"])
    assert pay["ok"] is True
    entries = _entries_of_source(client, manager_headers, "payment", pay["payment_id"])
    assert len(entries) == 1
    entry = entries[0]
    assert _entry_balanced(entry)
    assert entry["kind"] == "payment_gateway"
    codes = {l["account_code"] for l in entry["lines"]}
    assert "4101" in codes  # درآمد
    # idempotent: backfill دوباره سند مضاعف نمی‌سازد
    r = client.post("/api/v1/journal-entries/backfill", headers=manager_headers)
    assert r.status_code == 200
    entries2 = _entries_of_source(client, manager_headers, "payment", pay["payment_id"])
    assert len(entries2) == 1


def test_topup_entry_hits_wallet_liability_not_revenue(client, admin_headers, manager_headers):
    tb_before = _get(client, manager_headers, "/api/v1/reports/trial-balance")
    rev_before = next((i["credit"] - i["debit"] for i in tb_before["items"] if i["code"] == "4101"), 0)
    _topup(client, admin_headers, 300000)
    tb = _get(client, manager_headers, "/api/v1/reports/trial-balance")
    wallet_acc = next(i for i in tb["items"] if i["code"] == "2101")
    assert wallet_acc["credit"] - wallet_acc["debit"] >= 300000
    rev_after = next((i["credit"] - i["debit"] for i in tb["items"] if i["code"] == "4101"), 0)
    assert rev_after == rev_before  # شارژ کیف پول درآمد نیست


def test_wallet_payment_entry(client, admin_headers, manager_headers):
    _topup(client, admin_headers, 800000)
    svc = _mk_service(client, admin_headers, "پرداخت کیفی")
    order = _mk_order(client, admin_headers, svc)
    r = client.post(f"/api/v1/orders/{order['id']}/pay-from-wallet", headers=admin_headers)
    assert r.status_code == 200, r.text
    payment_id = r.json()["payment_id"]
    entries = _entries_of_source(client, manager_headers, "payment", payment_id)
    assert len(entries) == 1
    assert entries[0]["kind"] == "payment_wallet"
    assert _entry_balanced(entries[0])
    codes = {l["account_code"] for l in entries[0]["lines"]}
    assert {"2101", "4101"} <= codes


def test_discount_entry_lines(client, admin_headers, manager_headers):
    # کد تخفیف مبلغی
    r = client.post("/api/v1/discounts", headers=admin_headers, json={
        "code": f"P31{_uuid.uuid4().hex[:6].upper()}", "kind": "amount", "value": 200000,
    })
    assert r.status_code == 201, r.text
    code = r.json()["code"]
    svc = _mk_service(client, admin_headers, "با تخفیف")
    order = _mk_order(client, admin_headers, svc, discount_code=code)
    assert order["discount_amount"] == 200000
    pay = _pay(client, admin_headers, order["id"])
    assert pay["ok"] is True
    entries = _entries_of_source(client, manager_headers, "payment", pay["payment_id"])
    assert len(entries) == 1
    entry = entries[0]
    assert _entry_balanced(entry)
    codes = {l["account_code"] for l in entry["lines"]}
    assert "5102" in codes  # هزینه تخفیف
    revenue_line = next(l for l in entry["lines"] if l["account_code"] == "4101")
    assert revenue_line["credit"] == order["amount"]  # درآمد ناخالص


# ---------------- سند خودکار استرداد و تعدیل ----------------

def _refund_flow(client, admin_headers, manager_headers, wallet: bool) -> dict:
    if wallet:
        _topup(client, admin_headers, 1000000)
    svc = _mk_service(client, admin_headers, "استردادی")
    order = _mk_order(client, admin_headers, svc)
    if wallet:
        r = client.post(f"/api/v1/orders/{order['id']}/pay-from-wallet", headers=admin_headers)
        assert r.status_code == 200
        pay = {"ok": True, "payment_id": r.json()["payment_id"]}
    else:
        pay = _pay(client, admin_headers, order["id"])
        assert pay["ok"] is True
    r = client.post("/api/v1/refund-requests", headers=admin_headers, json={
        "order_id": order["id"], "amount": 400000, "reason": "آزمون استرداد فاز ۳۱",
    })
    assert r.status_code == 201, r.text
    req_id = r.json()["id"]
    r = client.post(f"/api/v1/refund-requests/{req_id}/review", headers=admin_headers,
                    json={"action": "approve", "note": "موافقم"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/refund-requests/{req_id}/execute", headers=admin_headers)
    assert r.status_code == 200, r.text
    refund = r.json()["refund"]
    return refund


def test_refund_wallet_entry(client, admin_headers, manager_headers):
    refund = _refund_flow(client, admin_headers, manager_headers, wallet=True)
    entries = _entries_of_source(client, manager_headers, "refund", refund["id"])
    assert len(entries) == 1
    entry = entries[0]
    assert entry["kind"] == "refund_wallet"
    assert _entry_balanced(entry)
    codes = {l["account_code"] for l in entry["lines"]}
    assert {"4102", "2101"} <= codes


def test_refund_gateway_entry(client, admin_headers, manager_headers):
    refund = _refund_flow(client, admin_headers, manager_headers, wallet=False)
    entries = _entries_of_source(client, manager_headers, "refund", refund["id"])
    assert len(entries) == 1
    entry = entries[0]
    assert entry["kind"] == "refund_gateway"
    assert _entry_balanced(entry)
    codes = {l["account_code"] for l in entry["lines"]}
    assert {"4102", "2102"} <= codes


def test_wallet_adjustment_entry(client, admin_headers, manager_headers):
    users = client.get("/api/v1/users", headers=admin_headers).json()
    target = next(u for u in users["items"] if u["username"] == "t_appa")
    r = client.post(f"/api/v1/wallets/{target['id']}/adjust", headers=admin_headers,
                    json={"amount": 25000, "note": "جبران آزمون فاز ۳۱"})
    assert r.status_code == 200, r.text
    # آخرین سند wallet_adjustment متوازن
    items = _get(client, manager_headers, "/api/v1/journal-entries",
                       {"source_type": "wallet_adjustment", "limit": 20})["items"]
    assert items, "سند تعدیل ثبت نشده"
    entry = items[0]
    assert _entry_balanced(entry)
    codes = {l["account_code"] for l in entry["lines"]}
    assert {"5103", "2101"} <= codes


# ---------------- برگشت سند ----------------

def test_reversal_entry(client, manager_headers):
    a1, a2 = _two_accounts(client, manager_headers)
    r = client.post("/api/v1/journal-entries", headers=manager_headers, json={
        "description": "سند مبدأ برای برگشت",
        "lines": [
            {"account_id": a1, "debit": 7000, "credit": 0},
            {"account_id": a2, "debit": 0, "credit": 7000},
        ],
    })
    src = r.json()
    r = client.post(f"/api/v1/journal-entries/{src['id']}/reverse", headers=manager_headers,
                    params={"reason": "اشتباه تایپی در مبلغ"})
    assert r.status_code == 201, r.text
    mirror = r.json()
    assert mirror["is_reversal"] is True
    assert mirror["reversal_of_id"] == src["id"]
    assert _entry_balanced(mirror)
    # سمت‌ها آینه‌ای شده‌اند
    src_lines = {l["account_id"]: (l["debit"], l["credit"]) for l in src["lines"]}
    for l in mirror["lines"]:
        assert (l["credit"], l["debit"]) == src_lines[l["account_id"]]
    # برگشت تکراری بی‌اثر
    r = client.post(f"/api/v1/journal-entries/{src['id']}/reverse", headers=manager_headers)
    assert r.status_code == 201
    assert r.json()["id"] == mirror["id"]


# ---------------- تسویه ----------------

def test_settlement_flow(client, admin_headers, manager_headers):
    today = date.today()
    # دو پرداخت درگاه امروز
    svc = _mk_service(client, admin_headers, "تسویه‌پذیر")
    order1 = _mk_order(client, admin_headers, svc)
    pay1 = _pay(client, admin_headers, order1["id"])
    order2 = _mk_order(client, admin_headers, svc)
    pay2 = _pay(client, admin_headers, order2["id"])
    assert pay1["ok"] and pay2["ok"]

    r = client.post("/api/v1/settlements", headers=manager_headers, json={
        "gateway": "sandbox", "period_start": str(today - timedelta(days=1)),
        "period_end": str(today + timedelta(days=1)),
    })
    assert r.status_code == 201, r.text
    st = r.json()
    assert st["status"] == "draft"
    assert st["payments_count"] >= 2
    assert st["gross_amount"] >= int(order1["payable_amount"]) + int(order2["payable_amount"])
    gross1 = st["gross_amount"]

    # تسویه با کارمزد
    fee = min(5000, int(st["gross_amount"]))
    r = client.post(f"/api/v1/settlements/{st['id']}/settle", headers=manager_headers,
                    json={"fee_amount": fee})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "settled"
    assert done["net_amount"] == gross1 - fee
    assert done["journal_entry"] is not None
    assert _entry_balanced(done["journal_entry"])
    entry_codes = {l["account_code"] for l in done["journal_entry"]["lines"]}
    assert {"1101", "1102"} <= entry_codes
    if fee > 0:
        assert "5101" in entry_codes

    # اجرای تکراری ممنوع
    r = client.post(f"/api/v1/settlements/{st['id']}/settle", headers=manager_headers,
                    json={"fee_amount": 0})
    assert r.status_code == 409

    # تسویه مضاعف ممنوع: پیش‌نویس جدید همان پرداخت‌ها را نمی‌آورد
    r = client.post("/api/v1/settlements", headers=manager_headers, json={
        "gateway": "sandbox", "period_start": str(today - timedelta(days=1)),
        "period_end": str(today + timedelta(days=1)),
    })
    if r.status_code == 201:
        assert r.json()["gross_amount"] <= gross1  # پرداخت‌های قبلی تسویه‌شده برنمی‌گردند
    else:
        assert r.status_code == 409  # پرداخت جدیدی نیست


def test_settlement_wallet_gateway_rejected(client, manager_headers):
    r = client.post("/api/v1/settlements", headers=manager_headers, json={"gateway": "wallet"})
    assert r.status_code == 422  # pattern constraint


# ---------------- تراز و مغایرت ----------------

def test_trial_balance_balanced(client, manager_headers):
    tb = _get(client, manager_headers, "/api/v1/reports/trial-balance")
    assert tb["is_balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]
    assert any(i["code"] == "4101" for i in tb["items"])


def test_reconciliation_zero_uncovered(client, admin_headers, manager_headers):
    # سرویس/پرداخت جدید بساز تا پوشش تازه سنجیده شود
    svc = _mk_service(client, admin_headers, "مغایرت")
    order = _mk_order(client, admin_headers, svc)
    _pay(client, admin_headers, order["id"])
    client.post("/api/v1/journal-entries/backfill", headers=manager_headers)
    rec = _get(client, manager_headers, "/api/v1/reports/financial-reconciliation")
    assert rec["ledger"]["is_balanced"] is True
    assert rec["events"]["payments"]["uncovered"] == 0
    assert rec["events"]["refunds"]["uncovered"] == 0
    assert rec["events"]["wallet_adjustments"]["uncovered"] == 0
    assert rec["sales_reconciliation"]["reconciled"] is True
    assert rec["sales_reconciliation"]["sales_report_amount"] > 0


# ---------------- دسترسی ----------------

def test_rbac_applicant_forbidden(client, applicant_headers):
    for url in ("/api/v1/accounts", "/api/v1/journal-entries", "/api/v1/settlements",
                "/api/v1/reports/trial-balance", "/api/v1/reports/financial-reconciliation"):
        r = client.get(url, headers=applicant_headers)
        assert r.status_code == 403, url
    r = client.post("/api/v1/journal-entries/backfill", headers=applicant_headers)
    assert r.status_code == 403
