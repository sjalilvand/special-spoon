"""فاز ۴۳ - گام‌های ۱–۲ طرح ADR-05: سقف نرخ سراسری Redis + آزمون ۴۲۹.

پوشش (طرح ۴ گام سند — بستن آخرین بخش ADR-05):
- پنجره لغزان ZSET: شمارش داخل سقف، عبور با ۴۲۹ + Retry-After دقیق،
  خروج اعضای قدیمی از پنجره (سطح سرویس با ساعت تزریق‌شدنی)؛
- کلید‌بندی: (route, ip) ناشناس / (route, user_id) احرازشده / سطل واحد
  برای مسیرهای پارامتری (فروریختن شناسه به :id)؛
- ۴۲۹ روی v1 با بدنه قرارداد + هدرهای انقضا؛ روی v2 پاکت‌بندی با کد
  ``rate_limited``؛ مستندسازی OpenAPI روت‌های مالی (تکمیل گام ۴)؛
- override per-route (دقیق/هر-متد/پیشوندی) و لیست بی‌سقف (whitelist)؛
- fail-open: نبود Redis یا خطای آن → عبور درخواست با هشدار (بند ۶ سند)؛
- ثبت ۴۲۹ در audit با نرخ نمونه‌برداری (۱.۰ همیشه / ۰.۰ هیچ‌گاه)؛
- معافیت سلامت/اسناد API؛ تمایز IP با X-Forwarded-For.

Redis با فیک درون‌حافظهٔ حداقلی جایگزین می‌شود (همان زیرمجموعهٔ دستورها
که سرویس استفاده می‌کند) — الگوی آزمون‌های FakeS3 فاز ۳۷/۳۸ و SMTP جعلی
فاز ۲۷؛ بدون وابستگی آزمون جدید.
"""
from __future__ import annotations

import uuid as uuid_mod

import pytest

from app.core import redis_client as redis_client_module
from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from app.services.rate_limit import sliding_window_hit

from conftest import bearer, login

PUBLIC_ROUTE = "/api/v1/public/topics"  # روت عمومی بی‌هویت برای آزمون فشار


# ===========================================================================
# فیک Redis — همان زیرمجموعهٔ دستورهای services/rate_limit.py
# ===========================================================================
class _FakePipeline:
    def __init__(self, rc):
        self._rc = rc
        self._cmds: list[tuple] = []

    def zadd(self, key, mapping):
        self._cmds.append(("zadd", key, mapping))
        return self

    def zremrangebyscore(self, key, lo, hi):
        self._cmds.append(("zremrangebyscore", key, lo, hi))
        return self

    def zcard(self, key):
        self._cmds.append(("zcard", key))
        return self

    def pexpire(self, key, ms):
        self._cmds.append(("pexpire", key, ms))
        return self

    def execute(self):
        out = [getattr(self._rc, name)(*args) for name, *args in self._cmds]
        self._cmds = []
        return out


class FakeRedis:
    """فیک حداقلی redis-py؛ ``fail=True`` هر عملیات را به خطای Redis تبدیل می‌کند."""

    def __init__(self):
        self.store: dict[str, dict[str, float]] = {}
        self.fail = False

    def _z(self, key):
        return self.store.setdefault(key, {})

    def pipeline(self, transaction: bool = True):
        return _FakePipeline(self)

    def zadd(self, key, mapping):
        if self.fail:
            raise ConnectionError("redis down")
        self._z(key).update(mapping)
        return len(mapping)

    def zremrangebyscore(self, key, lo, hi):
        if self.fail:
            raise ConnectionError("redis down")
        z = self._z(key)
        lo_f = float("-inf") if lo == "-inf" else float(lo)
        dead = [m for m, sc in z.items() if sc >= lo_f and sc <= float(hi)]
        for m in dead:
            z.pop(m, None)
        return len(dead)

    def zcard(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        return len(self._z(key))

    def pexpire(self, key, ms):
        if self.fail:
            raise ConnectionError("redis down")
        return 1 if key in self.store else 0

    def zrange(self, key, start, stop, withscores=False):
        if self.fail:
            raise ConnectionError("redis down")
        items = sorted(self._z(key).items(), key=lambda kv: (kv[1], kv[0]))
        sel = items[start: stop + 1] if stop >= 0 else items[start:]
        return [(m, float(sc)) for m, sc in sel] if withscores else [m for m, _ in sel]


@pytest.fixture()
def rl(monkeypatch):
    """سقف نرخ فعال با Redis فیک و سقف‌های کوچک؛ برگشت = نمونهٔ فیک برای دستکاری."""
    fake = FakeRedis()
    s = get_settings()
    monkeypatch.setattr(redis_client_module, "get_redis", lambda: fake)
    monkeypatch.setattr(s, "rate_limit_enabled", True)
    monkeypatch.setattr(s, "rate_limit_public_per_minute", 3)
    monkeypatch.setattr(s, "rate_limit_auth_per_minute", 2)
    # مسیر ورود بی‌سقف شود تا کمکیِ login در آزمون‌های دیگر تداخل نسازد
    monkeypatch.setattr(s, "rate_limit_overrides", '{"POST /api/v1/auth/login": 999}')
    monkeypatch.setattr(s, "rate_limit_whitelist_user_ids", "")
    monkeypatch.setattr(s, "rate_limit_audit_sample_rate", 1.0)
    return fake


def _429_audit_count() -> int:
    db = SessionLocal()
    try:
        return db.query(AuditEvent).filter(AuditEvent.action == "rate_limit.429").count()
    finally:
        db.close()


# ===========================================================================
# سرویس پنجره لغزان (سطح پایین، ساعت تزریق‌شدنی)
# ===========================================================================
def test_sliding_window_counts_and_expires(rl):
    key = "rl:unit-test"
    T0 = 1_000_000  # ms
    for _ in range(3):
        d = sliding_window_hit(rl, key, limit=3, window_seconds=60, now_ms=T0)
    assert d.exceeded is False and d.remaining == 0

    # هنوز داخل پنجره → عبور از سقف با retry_after معنادار
    d = sliding_window_hit(rl, key, limit=3, window_seconds=60, now_ms=T0 + 59_000)
    assert d.exceeded is True and 1 <= d.retry_after <= 60

    # قدیمی‌ها از پنجره خارج می‌شوند → سطل آزاد (پنجره لغزان، نه ثابت)
    d = sliding_window_hit(rl, key, limit=3, window_seconds=60, now_ms=T0 + 60_500)
    assert d.exceeded is False and d.remaining == 1


def test_retry_after_reflects_oldest_member(rl):
    key = "rl:unit-retry"
    T0 = 2_000_000
    for _ in range(2):
        sliding_window_hit(rl, key, limit=2, window_seconds=60, now_ms=T0)
    d = sliding_window_hit(rl, key, limit=2, window_seconds=60, now_ms=T0 + 30_000)
    assert d.exceeded is True
    assert d.retry_after == 30  # قدیمی‌ترین عضو دقیقاً ۳۰ ثانیه دیگر خارج می‌شود


# ===========================================================================
# ۴۲۹ — قرارداد پاسخ روی v1/v2
# ===========================================================================
def test_public_path_429_with_retry_after(client, rl):
    for _ in range(3):
        assert client.get(PUBLIC_ROUTE).status_code == 200
    r = client.get(PUBLIC_ROUTE)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    assert r.headers["X-RateLimit-Limit"] == "3"
    assert r.headers["X-RateLimit-Remaining"] == "0"
    assert "detail" in r.json()


def test_429_on_v2_is_enveloped_as_rate_limited(client, rl):
    for _ in range(3):
        assert client.get("/api/v2/public/topics").status_code == 200
    r = client.get("/api/v2/public/topics")
    assert r.status_code == 429
    body = r.json()
    assert body["errors"] and body["errors"][0]["code"] == "rate_limited"
    assert body["meta"]["version"] == "v2"


def test_429_on_v1_carries_deprecation_headers(client, rl):
    for _ in range(3):
        client.get(PUBLIC_ROUTE)
    r = client.get(PUBLIC_ROUTE)
    assert r.status_code == 429
    assert r.headers.get("Deprecation") == 'version="v1"'


def test_authenticated_requests_keyed_by_user(client, rl, env):
    token = login(client, "t_admin")
    auth = bearer(token)
    for _ in range(2):
        assert client.get("/api/v1/orders", headers=auth).status_code == 200
    assert client.get("/api/v1/orders", headers=auth).status_code == 429


def test_param_routes_share_one_bucket(client, rl, env):
    """مسیر پارامتری با شناسه‌های متفاوت در یک سطل است (فروریختن :id)."""
    token = login(client, "t_admin")
    auth = bearer(token)
    assert client.get(f"/api/v1/orders/{uuid_mod.uuid4()}", headers=auth).status_code == 404
    assert client.get(f"/api/v1/orders/{uuid_mod.uuid4()}", headers=auth).status_code == 404
    r = client.get(f"/api/v1/orders/{uuid_mod.uuid4()}", headers=auth)
    assert r.status_code == 429  # سه شناسهٔ متفاوت، یک سطل


def test_xff_ips_have_separate_buckets(client, rl):
    for _ in range(3):
        assert client.get(PUBLIC_ROUTE, headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 200
    assert client.get(PUBLIC_ROUTE, headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 429
    # IP دیگر سطل مستقل دارد
    assert client.get(PUBLIC_ROUTE, headers={"X-Forwarded-For": "5.6.7.8"}).status_code == 200


# ===========================================================================
# override per-route و whitelist (بند گام ۲ طرح)
# ===========================================================================
def test_override_exact_route(client, rl, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_overrides", '{"GET /api/v1/public/topics": 1}')
    assert client.get(PUBLIC_ROUTE).status_code == 200
    assert client.get(PUBLIC_ROUTE).status_code == 429


def test_override_prefix_wildcard(client, rl, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_overrides", '{"GET /api/v1/public/*": 1}')
    assert client.get(PUBLIC_ROUTE).status_code == 200
    assert client.get(PUBLIC_ROUTE).status_code == 429


def test_whitelist_user_is_unlimited(client, rl, env, monkeypatch):
    token = login(client, "t_admin")
    sub = str(decode_access_token(token)["sub"])
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_whitelist_user_ids", sub)
    for _ in range(6):  # بیش از سقف احرازشده (۲) — باید همه عبور کنند
        assert client.get("/api/v1/orders", headers=bearer(token)).status_code == 200


# ===========================================================================
# fail-open (بند ۶ سند) و خاموشی
# ===========================================================================
def test_fail_open_when_redis_absent(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", True)
    monkeypatch.setattr(redis_client_module, "get_redis", lambda: None)
    for _ in range(10):
        assert client.get(PUBLIC_ROUTE).status_code == 200


def test_fail_open_when_redis_errors(client, rl):
    rl.fail = True  # هر عملیات Redis خطا می‌دهد → میان‌افزار باید عبور دهد
    for _ in range(10):
        assert client.get(PUBLIC_ROUTE).status_code == 200


def test_disabled_middleware_passes_all(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)
    for _ in range(10):
        assert client.get(PUBLIC_ROUTE).status_code == 200


# ===========================================================================
# معافیت‌ها، audit و OpenAPI
# ===========================================================================
def test_health_and_docs_are_exempt(client, rl):
    for _ in range(25):
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/openapi.json").status_code == 200


def test_429_is_recorded_in_audit_with_sampling(client, rl):
    base = _429_audit_count()
    for _ in range(3):
        client.get(PUBLIC_ROUTE)
    assert client.get(PUBLIC_ROUTE).status_code == 429
    db = SessionLocal()
    try:
        row = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "rate_limit.429")
            .order_by(AuditEvent.created_at.desc())
            .first()
        )
        assert row is not None
        assert row.entity_id == "GET /public/topics"
        assert row.result == "blocked"
        assert row.detail["limit"] == 3
        assert (row.ip or "").startswith("testclient")
        assert row.actor_user_id is None  # ناشناس
    finally:
        db.close()
    assert _429_audit_count() == base + 1


def test_audit_sampling_zero_records_nothing(client, rl, monkeypatch):
    s = get_settings()
    base = _429_audit_count()
    monkeypatch.setattr(s, "rate_limit_audit_sample_rate", 0.0)
    for _ in range(5):
        client.get(PUBLIC_ROUTE)
    assert _429_audit_count() == base


def test_openapi_documents_429_on_financial_routes(client, rl):
    spec = client.get("/api/v1/openapi.json").json()
    for path in ("/api/v1/orders", "/api/v1/orders/{order_id}/payments"):
        op = spec["paths"][path]["post"]
        assert "429" in op.get("responses", {})
        headers = op["responses"]["429"]["headers"]
        assert "Retry-After" in headers and "X-RateLimit-Limit" in headers
