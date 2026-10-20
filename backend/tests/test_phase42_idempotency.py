"""فاز ۴۲ - ADR-05 گام ۳: Idempotency-Key واقعی عملیات مالی.

- تکرار همان کلید + همان بدنه → همان پاسخ قبلی، بدون ردیف دوم (سفارش/پرداخت)
- همان کلید با بدنه یا مسیر متفاوت → ۴۰۹ تعارض (هرگز بازپخش بی‌صدا نیست)
- بدون هدر → رفتار فعلی بدون تغییر (قرارداد opt-in)
- آزادسازی رزرو در خطا (۴۲۲/۴۰۹) → تلاش مجدد با همان کلید ممکن
- در جریان بودن کلید → ۴۰۹؛ رزرو رهاشده کهنه → جایگزینی خودکار
- بازپخش روی v2 هم پاکت‌بندی می‌شود و هدرهای اکو دارد
- پاک‌سازی کهنه‌ها با روت ادمین (فقط SYSTEM_ADMIN) + ثبت audit
- آزمون هم‌زمانی: دو درخواست هم‌زمان با کلید واحد → فقط یک منبع (طرح ADR-05 گام ۴)
- مستندسازی هدر در OpenAPI برای دو روت مالی
"""
from __future__ import annotations

import threading
import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest

from conftest import bearer, login

from app.db.session import SessionLocal
from app.models.idempotency import IdempotencyKey
from app.models.payment import Order, Payment
from app.services import idempotency as idem


@pytest.fixture(scope="module")
def module_headers(client, env):
    return bearer(login(client, "t_admin"))


def _headers(module_headers, key: str | None = None) -> dict:
    h = dict(module_headers)
    if key:
        h["Idempotency-Key"] = key
    return h


@pytest.fixture()
def svc(client, module_headers):
    """خدمت با تعرفه معتبر برای ساخت سفارش."""
    tag = _uuid.uuid4().hex[:6]
    r = client.post("/api/v1/specialties", headers=module_headers, json={"name": f"فاز۴۲-{tag}"})
    sp = r.json()
    r = client.post("/api/v1/services", headers=module_headers, json={
        "specialty_id": sp["id"], "title": f"خدمت فاز ۴۲ {tag}", "duration_minutes": 45,
    })
    svc_id = r.json()["id"]
    from datetime import date, timedelta

    on = date.today() - timedelta(days=1)
    r = client.post("/api/v1/tariffs", headers=module_headers, json={
        "service_id": svc_id, "amount": 800000,
        "valid_from": str(on), "valid_to": str(on + timedelta(days=200)),
    })
    assert r.status_code == 201, r.text
    return {"id": svc_id}


def _order_payload(svc: dict) -> dict:
    # نشانگر یکتا در عنوان برای شمارش دقیق در پایگاه داده اشتراکی
    return {"service_id": svc["id"], "title": f"فاز۴۲-{_uuid.uuid4().hex[:10]}"}


def _count_orders(title_prefix: str) -> int:
    db = SessionLocal()
    try:
        from sqlalchemy import func, select

        return int(
            db.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.title.like(f"{title_prefix}%"))
            )
            or 0
        )
    finally:
        db.close()


def _backdate(key: str, minutes: int, *, with_snapshot: bool = False) -> None:
    """قدیمی‌کردن/حالت‌گذاری ردیف موجود برای آزمون inflight/کهنه/purge.

    ردیف باید از یک درخواست واقعی وجود داشته باشد تا endpoint و payload_hash
    با بدنه آزمون یکسان بماند (وگرنه reserve به‌جای حالت هدف، تعارض می‌دهد).
    """
    db = SessionLocal()
    try:
        row = db.get(IdempotencyKey, key)
        assert row is not None, f"ردیف {key} باید از درخواست واقعی وجود داشته باشد"
        row.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        if with_snapshot:
            row.response_snapshot = {"status_code": 201, "body": {"backdated": True}}
        else:
            row.response_snapshot = None
        db.commit()
    finally:
        db.close()


# ===========================================================================
# مسیر پایه — سفارش
# ===========================================================================
def test_order_replay_same_key_same_body(client, module_headers, svc):
    key = str(_uuid.uuid4())
    payload = _order_payload(svc)
    r1 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r2.status_code == 201, r2.text
    # همان پاسخ قبلی — نه سفارش دوم
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.headers.get("Idempotency-Key") == key
    assert r2.headers.get("Idempotency-Replayed") == "true"
    assert _count_orders(payload["title"]) == 1


def test_order_key_conflict_with_different_body(client, module_headers, svc):
    key = str(_uuid.uuid4())
    p1 = _order_payload(svc)
    r1 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=p1)
    assert r1.status_code == 201
    p2 = _order_payload(svc)  # بدنه متفاوت — همان کلید
    r2 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=p2)
    assert r2.status_code == 409
    assert "کلید" in r2.json()["detail"]
    # سفارش دوم ساخته نشده
    assert _count_orders(p2["title"]) == 0


def test_key_conflict_across_endpoints(client, module_headers, svc):
    key = str(_uuid.uuid4())
    payload = _order_payload(svc)
    r1 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r1.status_code == 201
    order_id = r1.json()["id"]
    # همان کلید روی منبع دیگر (مسیر متفاوت) → ۴۰۹
    r2 = client.post(
        f"/api/v1/orders/{order_id}/payments", headers=_headers(module_headers, key), json={}
    )
    assert r2.status_code == 409


def test_no_key_keeps_current_behaviour(client, module_headers, svc):
    """قرارداد opt-in — بدون هدر هیچ تغییری در رفتار (دو سفارش مستقل مجاز)."""
    payload1 = _order_payload(svc)
    r1 = client.post("/api/v1/orders", headers=module_headers, json=payload1)
    payload2 = _order_payload(svc)
    r2 = client.post("/api/v1/orders", headers=module_headers, json=payload2)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]
    assert "Idempotency-Key" not in r1.headers


def test_invalid_key_rejected(client, module_headers, svc):
    r = client.post(
        "/api/v1/orders",
        headers=_headers(module_headers, "x" * 200),
        json=_order_payload(svc),
    )
    assert r.status_code == 422
    assert "Idempotency" in r.json()["detail"]


# ===========================================================================
# آزادسازی رزرو در خطا — تلاش مجدد با همان کلید
# ===========================================================================
def test_release_after_validation_error(client, module_headers, svc):
    key = str(_uuid.uuid4())
    # بدنه نامعتبر (نه appointment_id و نه service_id) → ۴۲۲ و رزرو آزاد
    r1 = client.post(
        "/api/v1/orders", headers=_headers(module_headers, key), json={"note": "بی‌سرویس"}
    )
    assert r1.status_code == 422
    # تلاش مجدد با همان کلید و بدنه معتبر → ۲۰۱ عادی (رزرو قبلی آزاد شده)
    payload = _order_payload(svc)
    r2 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r2.status_code == 201, r2.text
    assert r2.headers.get("Idempotency-Replayed") is None
    assert _count_orders(payload["title"]) == 1


def test_release_after_gateway_conflict(client, module_headers, svc):
    payload = _order_payload(svc)
    r1 = client.post("/api/v1/orders", headers=module_headers, json=payload)
    order_id = r1.json()["id"]
    # کلید تازه روی مسیر پرداخت که با ۴۰۴ شکست می‌خورد → آزادسازی رزرو
    key = str(_uuid.uuid4())
    fake = str(_uuid.uuid4())
    r2 = client.post(
        f"/api/v1/orders/{fake}/payments", headers=_headers(module_headers, key), json={}
    )
    assert r2.status_code == 404
    # حالا همان کلید روی پرداخت واقعی → ۲۰۱ عادی (رزرو قبلی آزاد شده)
    r3 = client.post(
        f"/api/v1/orders/{order_id}/payments", headers=_headers(module_headers, key), json={}
    )
    assert r3.status_code == 201, r3.text
    assert r3.headers.get("Idempotency-Replayed") is None
    # و کلیدِ سفارش (متصل به مسیر /orders) روی مسیر پرداخت → تعارض ۴۰۹
    key_order = str(_uuid.uuid4())
    payload2 = _order_payload(svc)
    client.post("/api/v1/orders", headers=_headers(module_headers, key_order), json=payload2)
    order2 = payload2["title"]
    r4 = client.post(
        f"/api/v1/orders/{order_id}/payments", headers=_headers(module_headers, key_order), json={}
    )
    assert r4.status_code == 409
    assert _count_orders(order2) == 1


# ===========================================================================
# بازپخش روی پرداخت و v2
# ===========================================================================
def test_payment_start_replay_same_payment(client, module_headers, svc):
    # هر عملیات کلید خودش را دارد — کلیدِ سفارش جدا از کلیدِ پرداخت
    order_key = str(_uuid.uuid4())
    pay_key = str(_uuid.uuid4())
    payload = _order_payload(svc)
    r = client.post("/api/v1/orders", headers=_headers(module_headers, order_key), json=payload)
    order_id = r.json()["id"]

    p1 = client.post(
        f"/api/v1/orders/{order_id}/payments", headers=_headers(module_headers, pay_key), json={}
    )
    assert p1.status_code == 201, p1.text
    p2 = client.post(
        f"/api/v1/orders/{order_id}/payments", headers=_headers(module_headers, pay_key), json={}
    )
    assert p2.status_code == 201
    assert p2.json()["payment_id"] == p1.json()["payment_id"]
    assert p2.headers.get("Idempotency-Replayed") == "true"

    db = SessionLocal()
    try:
        n = db.query(Payment).filter(Payment.order_id == order_id).count()
        assert n == 1
    finally:
        db.close()


def test_v2_replay_is_enveloped_with_meta_echo(client, module_headers, svc):
    key = str(_uuid.uuid4())
    payload = _order_payload(svc)
    r1 = client.post("/api/v2/orders", headers=_headers(module_headers, key), json=payload)
    assert r1.status_code == 201
    env1 = r1.json()
    assert env1["data"]["id"] and env1["errors"] is None
    assert env1["meta"]["idempotency_key"] == key

    r2 = client.post("/api/v2/orders", headers=_headers(module_headers, key), json=payload)
    assert r2.status_code == 201
    env2 = r2.json()
    # همان data در همان پاکت — بازپخش پاکت‌بندی می‌شود
    assert env2["data"]["id"] == env1["data"]["id"]
    assert env2["meta"]["idempotency_key"] == key
    assert r2.headers.get("Idempotency-Replayed") == "true"


def test_key_from_v1_replays_on_v2(client, module_headers, svc):
    """مسیر نرمال‌شده — یک کلید بین دو نسخه بازپخش می‌شود (نه سفارش دوم)."""
    key = str(_uuid.uuid4())
    payload = _order_payload(svc)
    r1 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/v2/orders", headers=_headers(module_headers, key), json=payload)
    assert r2.status_code == 201
    assert r2.json()["data"]["id"] == r1.json()["id"]
    assert _count_orders(payload["title"]) == 1


# ===========================================================================
# در جریان / کهنه / پاک‌سازی
# ===========================================================================
def test_inflight_key_conflicts(client, module_headers, svc):
    """رزرو بدون snapshot (در جریان) → ۴۰۹ با پیام تلاش مجدد."""
    key = str(_uuid.uuid4())
    payload = _order_payload(svc)
    r0 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r0.status_code == 201
    # رزرو واقعی را به حالت «در جریان» برمی‌گردانیم (snapshot حذف، زمان حال)
    _backdate(key, minutes=0)
    r = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r.status_code == 409
    assert "در جریان" in r.json()["detail"]


def test_stale_pending_key_is_replaced(client, module_headers, svc):
    """رزرو رهاشده کهنه (سقوط سرور بین دو فاز) → جایگزین و اجرا ادامه می‌یابد.

    نکته طرح: با گم‌شدن رزرو، سرور نتیجه اجرای اول را نمی‌داند → درخواست با
    همان کلید «دوباره اجرا» می‌شود (نه بازپخش) — ریسک باقیماندهٔ سند ADR-05
    که با قیود یکتایی DB (خط دفاعی دوم) مهار می‌شود؛ مهم این است که کلاینت
    هرگز با ۴۰۹ همیشگی قفل نمی‌شود.
    """
    key = str(_uuid.uuid4())
    payload = _order_payload(svc)
    r0 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r0.status_code == 201
    # snapshot حذف + سن ۱۵ دقیقه (TTL پیش‌فرض ۶۰۰ ثانیه) → کهنه
    _backdate(key, minutes=15)
    r = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r.status_code == 201, r.text
    assert r.headers.get("Idempotency-Replayed") is None
    # اجرای مجدد — سفارش دوم (نه بازپخش سفارش اول)
    assert r.json()["id"] != r0.json()["id"]
    assert _count_orders(payload["title"]) == 2


def test_purge_endpoint_admin_only(client, module_headers, svc):
    key = str(_uuid.uuid4())
    payload = _order_payload(svc)
    r = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload)
    assert r.status_code == 201
    _backdate(key, minutes=48 * 60, with_snapshot=True)  # کهنه‌تر از ۲۴ ساعت

    # غیرمدیر → ۴۰۳
    other = bearer(login(client, "t_reception"))
    r403 = client.post("/api/v1/idempotency-keys/purge", headers=other)
    assert r403.status_code == 403

    rp = client.post("/api/v1/idempotency-keys/purge", headers=module_headers)
    assert rp.status_code == 200, rp.text
    assert rp.json()["purged"] >= 1
    # idempotent — اجرای مجدد چیزی برای حذف ندارد
    rp2 = client.post("/api/v1/idempotency-keys/purge", headers=module_headers)
    assert rp2.status_code == 200
    # ردیف پاک‌شده دیگر بازپخش نمی‌شود — کلید آزاد است
    payload2 = _order_payload(svc)
    r3 = client.post("/api/v1/orders", headers=_headers(module_headers, key), json=payload2)
    assert r3.status_code == 201
    assert r3.headers.get("Idempotency-Replayed") is None


def test_keys_list_endpoint(client, module_headers):
    key = str(_uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(IdempotencyKey(key=key, endpoint="/orders", payload_hash="a" * 64))
        db.commit()
    finally:
        db.close()
    r = client.get("/api/v1/idempotency-keys", headers=module_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["summary"]["total"] >= 1
    assert any(item["key"] == key for item in data["items"])
    assert all("payload_hash" in item for item in data["items"])


# ===========================================================================
# هم‌زمانی — دو درخواست هم‌زمان با کلید واحد → فقط یک منبع (طرح گام ۴)
# ===========================================================================
def test_concurrent_same_key_creates_one_resource(client, module_headers, svc):
    key = str(_uuid.uuid4())
    payload = _order_payload(svc)
    results: dict[int, tuple[int, dict]] = {}
    barrier = threading.Barrier(2)

    def worker(i: int) -> None:
        from fastapi.testclient import TestClient

        local = TestClient(client.app)
        tok = bearer(login(local, "t_admin"))
        tok["Idempotency-Key"] = key
        barrier.wait()
        r = local.post("/api/v1/orders", headers=tok, json=payload)
        results[i] = (r.status_code, r.json())

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert len(results) == 2
    order_ids = {
        res[1]["id"] for res in results.values() if isinstance(res[1], dict) and "id" in res[1]
    }
    codes = {res[0] for res in results.values()}
    assert 201 in codes
    # حداکثر یک شناسه سفارش — برنده + (بازپخش یا تعارض در جریان)
    assert len(order_ids) == 1, results
    assert codes <= {201, 409}
    assert _count_orders(payload["title"]) == 1


# ===========================================================================
# مستندسازی OpenAPI (طرح ADR-05 گام ۴ — بخش هدرها برای کلاینت‌ها)
# ===========================================================================
def test_openapi_documents_idempotency_header(client):
    schema = client.get("/api/v1/openapi.json").json()
    for path in ("/api/v1/orders", "/api/v1/orders/{order_id}/payments"):
        params = schema["paths"][path]["post"].get("parameters", [])
        assert any(
            p.get("name") == "Idempotency-Key" and p.get("in") == "header"
            for p in params
        ), path


def test_reserve_states_directly(svc):
    """تست مستقیم سرویس: owner → replay → conflict + محافظت snapshot از release."""
    db = SessionLocal()
    try:
        key = str(_uuid.uuid4())
        st1, snap1 = idem.reserve(db, key, "/orders", "h1")
        assert (st1, snap1) == (idem.OWNER, None)
        idem.store_snapshot(db, key, 201, {"ok": True})
        st2, snap2 = idem.reserve(db, key, "/orders", "h1")
        assert st2 == idem.REPLAY and snap2["body"] == {"ok": True}
        st3, _ = idem.reserve(db, key, "/orders", "h2")
        assert st3 == idem.CONFLICT
        # release فقط رزرو pending را حذف می‌کند — ردیف snapshot‌دار محافظت می‌شود
        idem.release(db, key)
        st4, snap4 = idem.reserve(db, key, "/orders", "h1")
        assert st4 == idem.REPLAY and snap4["body"] == {"ok": True}
        # شبیه‌سازی purge → کلید آزاد و دوباره قابل استفاده
        db.get(IdempotencyKey, key)
        db.execute(__import__("sqlalchemy").delete(IdempotencyKey).where(IdempotencyKey.key == key))
        db.commit()
        st5, _ = idem.reserve(db, key, "/orders", "h2")
        assert st5 == idem.OWNER  # کلید آزاد شد
        idem.release(db, key)
    finally:
        db.close()
