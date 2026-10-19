"""فاز ۳۸ - ADR-03: پاکت پاسخ استاندارد {data, meta, errors} روی /api/v2.

پوشش آزمون:
- پاکت موفقیت با meta کامل (request_id/timestamp/version/duration_ms)
- پاسخ صفحه‌بندی‌شده {items,...} → data فهرست + meta.pagination
- پاکت خطا 401/404/422 با کد پایدار
- اکوی Idempotency-Key در meta (زمینه‌سازی ADR-05)
- دست‌نخوردگی کامل v1 (بدون کلید data — سازگاری فرانت/موبایل)
- خروج v2 از OpenAPI (طرح مستندات تمیز)
"""
from __future__ import annotations

from conftest import bearer, login

from app.core.envelope import errors_from, split_items


def test_v2_health_envelope(client):
    r = client.get("/api/v2/health")
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] is None
    assert body["data"]["status"] == "ok"
    meta = body["meta"]
    assert meta["version"] == "v2"
    assert meta["request_id"]
    assert meta["timestamp"].endswith("Z")
    assert isinstance(meta["duration_ms"], int)


def test_v1_untouched_no_envelope(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    # قرارداد v1: پاسخ خام — بدون کلید data/meta/errors
    assert "data" not in body
    assert "meta" not in body
    assert body["status"] == "ok"


def test_v2_login_works_and_list_users_lifts_items(client, env):
    token = login(client, "t_admin")
    r = client.get("/api/v2/users?page_size=5", headers=bearer(token))
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] is None
    # items → data (فهرست) و بقیه کلیدها → meta.pagination
    assert isinstance(body["data"], list)
    pagination = body["meta"].get("pagination") or {}
    assert "total" in pagination
    assert pagination.get("page_size") == 5


def test_v2_unauthorized_error_envelope(client):
    r = client.get("/api/v2/users")
    assert r.status_code == 401
    body = r.json()
    assert body["data"] is None
    errs = body["errors"]
    assert isinstance(errs, list) and errs
    assert errs[0]["code"] == "unauthorized"
    assert errs[0]["message"]
    assert body["meta"]["version"] == "v2"


def test_v2_not_found_error_envelope(client):
    r = client.get("/api/v2/__no_such_route__")
    assert r.status_code == 404
    body = r.json()
    assert body["data"] is None
    assert body["errors"][0]["code"] == "not_found"


def test_v2_validation_error_envelope(client, env):
    token = login(client, "t_admin")
    r = client.get("/api/v2/users?page=0", headers=bearer(token))
    assert r.status_code == 422
    body = r.json()
    assert body["data"] is None
    errs = body["errors"]
    assert errs and errs[0]["code"] == "greater_than_equal"
    assert "page" in errs[0]["message"]
    assert errs[0]["details"]["loc"][-1] == "page"


def test_v2_idempotency_key_echo(client):
    r = client.get("/api/v2/health", headers={"Idempotency-Key": "idem-abc-123"})
    assert r.status_code == 200
    assert r.json()["meta"]["idempotency_key"] == "idem-abc-123"


def test_v2_openapi_not_polluted(client):
    schema = client.get("/api/v1/openapi.json").json()
    paths = list(schema.get("paths", {}).keys())
    assert not any(p.startswith("/api/v2") for p in paths)
    assert any(p.startswith("/api/v1") for p in paths)


# ---------------------------------------------------------------- unit tests
def test_split_items_lifts_pagination():
    payload = {"items": [1, 2, 3], "total": 3, "page": 1, "page_size": 20}
    data, extra = split_items(payload)
    assert data == [1, 2, 3]
    assert extra == {"pagination": {"total": 3, "page": 1, "page_size": 20}}


def test_split_items_plain_payload_passthrough():
    data, extra = split_items({"status": "ok"})
    assert data == {"status": "ok"}
    assert extra == {}


def test_errors_from_string_detail():
    errs = errors_from({"detail": "نام کاربری یا رمز عبور نادرست است"}, 401)
    assert errs == [{"code": "unauthorized", "message": "نام کاربری یا رمز عبور نادرست است"}]


def test_errors_from_validation_list():
    payload = {"detail": [{"loc": ["query", "page"], "msg": "Input should be greater than or equal to 1",
                           "type": "greater_than_equal"}]}
    errs = errors_from(payload, 422)
    assert errs[0]["code"] == "greater_than_equal"
    assert errs[0]["message"].startswith("query.page:")
    assert errs[0]["details"] == {"loc": ["query", "page"], "type": "greater_than_equal"}


def test_errors_from_unknown_shape():
    errs = errors_from({"foo": "bar"}, 409)
    assert errs[0]["code"] == "conflict"
    assert errs[0]["details"] == {"foo": "bar"}
