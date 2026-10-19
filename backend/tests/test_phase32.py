"""فاز ۳۲ - B40 سند جامع: نقشه شعب + تصمیم D03 (سرویس نقشه پلاگین‌پذیر).

- B40: /public/branches/nearby با هاروساین؛ شعبه منتشرنشده عمومی نیست؛
  فاقد مختصات در انتها؛ پذیرش سند: «مکان کاربر فقط برای مرتب‌سازی،
  ذخیره نمی‌شود» — بدون نوشتن در DB، بدون audit، بدون بازتاب در پاسخ.
- D03: همان الگوی D02 — پیش‌فرض OSM بدون کلید؛ نشنال/Map.ir فقط با کلید
  فعال می‌شوند؛ کلید هرگز به کلاینت نمی‌رود؛ fallback به OSM وقتی سرویس
  پیش‌فرض پیکربندی نشده باشد.
"""
import uuid

import pytest

from conftest import bearer, login


@pytest.fixture()
def manager_headers(client, env):
    return bearer(login(client, "t_manager"))


# ---------------- helpers ----------------

def _setup_branches(client, manager_headers) -> dict:
    """کلینیک + شعب با مختصات مشخص: تهران، کرج، اصفهان + بی‌مختصات + پیش‌نویس."""
    r = client.post("/api/v1/clinics", headers=manager_headers, json={
        "name": "کلینیک فاز۳۲", "slug": f"map-{uuid.uuid4().hex[:8]}",
    })
    assert r.status_code == 201, r.text
    clinic_id = r.json()["id"]

    coords = [
        ("شعبه تهران", "تهران", 35.7448, 51.3753),   # نزدیک‌ترین به مرکز تهران
        ("شعبه کرج", "البرز", 35.8400, 50.9391),     # بعدی
        ("شعبه اصفهان", "اصفهان", 32.6546, 51.6680), # دورترین
    ]
    ids = {}
    for name, city, la, lo in coords:
        r = client.post(f"/api/v1/clinics/{clinic_id}/branches", headers=manager_headers, json={
            "name": name, "city": city, "address": f"نشانی {name}",
            "latitude": la, "longitude": lo, "status": "published",
        })
        assert r.status_code == 201, r.text
        ids[name] = r.json()["id"]
    # شعبه بی‌مختصات منتشرشده
    r = client.post(f"/api/v1/clinics/{clinic_id}/branches", headers=manager_headers, json={
        "name": "شعبه بی‌مختصات", "city": "قم", "status": "published",
    })
    assert r.status_code == 201, r.text
    ids["شعبه بی‌مختصات"] = r.json()["id"]
    # شعبه پیش‌نویس با مختصات — عمومی نیست
    r = client.post(f"/api/v1/clinics/{clinic_id}/branches", headers=manager_headers, json={
        "name": "شعبه پیش‌نویس", "city": "تهران", "latitude": 35.70, "longitude": 51.40,
        "status": "draft",
    })
    assert r.status_code == 201, r.text
    return {"clinic_id": clinic_id, **ids}


# ---------------- B40: nearby ----------------

def test_nearby_sorted_by_haversine(client, manager_headers):
    b = _setup_branches(client, manager_headers)
    # مختصات کاربر: مرکز تهران
    r = client.get("/api/v1/public/branches/nearby", params={
        "lat": 35.7150, "lng": 51.4040, "limit": 50,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["sorted_by"] == "distance"
    names = [i["name"] for i in data["items"]]
    # شعبه پیش‌نویس عمومی نیست
    assert "شعبه پیش‌نویس" not in names
    # ترتیب فاصله شعب آزمون: تهران → کرج → اصفهان؛ همه مکان‌دارها پیش از بی‌مختصات‌ها
    ti = names.index("شعبه تهران"); ki = names.index("شعبه کرج"); ef = names.index("شعبه اصفهان")
    assert ti < ki < ef
    by_name = {i["name"]: i for i in data["items"]}
    assert by_name["شعبه تهران"]["distance_km"] < by_name["شعبه کرج"]["distance_km"] < \
        by_name["شعبه اصفهان"]["distance_km"]
    # فاصله منطقی: مرکز تهران → شعبه تهران < ۱۰ کیلومتر؛ اصفهان > ۳۰۰
    assert by_name["شعبه تهران"]["distance_km"] < 10
    assert by_name["شعبه اصفهان"]["distance_km"] > 300
    # همه شعبه‌های بی‌مختصات (آزمون یا فازهای دیگر) در انتها و با distance_km=null
    first_unlocated = min(
        (idx for idx, i in enumerate(data["items"]) if i["distance_km"] is None),
        default=len(data["items"]),
    )
    assert max(ti, ki, ef) < first_unlocated
    assert by_name["شعبه بی‌مختصات"]["distance_km"] is None
    # فاصله‌های موجود صعودی‌اند
    dists = [i["distance_km"] for i in data["items"] if i["distance_km"] is not None]
    assert dists == sorted(dists)


def test_nearby_privacy_location_never_persisted(client, manager_headers):
    """پذیرش سند: مکان کاربر فقط برای مرتب‌سازی؛ نه در DB، نه در audit،
    نه در پاسخ بازتاب نمی‌یابد."""
    from app.db.session import SessionLocal
    from app.models.audit import AuditEvent
    from app.models.branch import Branch

    _setup_branches(client, manager_headers)
    db = SessionLocal()
    audit_before = len(db.query(AuditEvent.id).all())
    branch_before = len(db.query(Branch.id).all())
    db.close()

    # مختصات ویژه و قابل جستجو در کل پاسخ
    user_lat, user_lng = 35.7150123, 51.4040456
    r = client.get("/api/v1/public/branches/nearby", params={
        "lat": user_lat, "lng": user_lng, "limit": 50,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "privacy_note" in body
    # بازتاب مختصات کاربر در پاسخ ممنوع
    assert str(user_lat) not in str(body)
    assert str(user_lng) not in str(body)
    assert "lat" not in body and "lng" not in body
    assert body["sorted_by"] == "distance"

    db = SessionLocal()
    audit_after = len(db.query(AuditEvent.id).all())
    branch_after = len(db.query(Branch.id).all())
    db.close()
    assert branch_after == branch_before  # هیچ ردیفی نوشته نشد
    assert audit_after == audit_before    # هیچ رویداد audit با مختصات ثبت نشد


def test_nearby_requires_both_coords(client, manager_headers):
    _setup_branches(client, manager_headers)
    r = client.get("/api/v1/public/branches/nearby", params={"lat": 35.71})
    assert r.status_code == 422
    r = client.get("/api/v1/public/branches/nearby", params={"lng": 51.40})
    assert r.status_code == 422
    # خارج از بازه مختصات → 422 (اعتبارسنجی Query)
    r = client.get("/api/v1/public/branches/nearby", params={"lat": 95, "lng": 51})
    assert r.status_code == 422


def test_nearby_limit_and_total(client, manager_headers):
    _setup_branches(client, manager_headers)
    r = client.get("/api/v1/public/branches/nearby", params={
        "lat": 35.7150, "lng": 51.4040, "limit": 2,
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 4  # شعب منتشرشده فاز۳۲ + هر داده عمومی دیگر


def test_nearby_without_coords_name_sorted(client, manager_headers):
    _setup_branches(client, manager_headers)
    r = client.get("/api/v1/public/branches/nearby")
    assert r.status_code == 200
    data = r.json()
    assert data["sorted_by"] == "name"
    assert all(i["distance_km"] is None for i in data["items"])
    assert all(i["name"] != "شعبه پیش‌نویس" for i in data["items"])


def test_nearby_city_filter(client, manager_headers):
    _setup_branches(client, manager_headers)
    r = client.get("/api/v1/public/branches/nearby", params={
        "lat": 35.7150, "lng": 51.4040, "city": "تهران",
    })
    assert r.status_code == 200
    items = r.json()["items"]
    assert items, "شعبه تهران باید برگردد"
    assert all(i["city"] == "تهران" for i in items)


# ---------------- D03: map config ----------------

def test_map_config_default_osm_no_key_leak(client):
    r = client.get("/api/v1/public/map/config")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["provider"]["code"] == "osm"
    assert "openstreetmap" in data["provider"]["tile_url"]
    codes = {p["code"]: p for p in data["providers"]}
    assert codes["osm"]["enabled"] is True and codes["osm"]["is_default"] is True
    # نشنال/Map.ir بدون کلید غیرفعال‌اند
    assert codes["neshan"]["enabled"] is False
    assert codes["mapir"]["enabled"] is False
    assert codes["neshan"]["tile_url"] is None
    # کلید در پاسخ نیست (هرگز به کلاینت نمی‌رود)
    assert "api_key" not in r.text.lower().replace("requires_key", "")
    assert data["provider"].get("requires_key", False) is False or "key" not in r.text


def test_map_provider_fallback_and_key_gating():
    """D03 در لایه سرویس: سرویس پیش‌فرض بدون کلید → سقوط به OSM؛
    با کلید → فعال ولی tile_url صادر نمی‌شود (کلید سمت سرور می‌ماند)."""
    from types import SimpleNamespace

    from app.services.maps import active_map_provider, configured_map_providers

    s = SimpleNamespace(map_provider="neshan", neshan_api_key="", mapir_api_key="")
    assert active_map_provider(s)["code"] == "osm"  # fallback
    provs = {p["code"]: p for p in configured_map_providers(s)}
    assert provs["neshan"]["enabled"] is False

    s2 = SimpleNamespace(map_provider="neshan", neshan_api_key="secret-key-123", mapir_api_key="")
    active = active_map_provider(s2)
    assert active["code"] == "neshan"
    assert active["tile_url"] is None           # کلید/URL کلیددار صادر نمی‌شود
    assert "secret-key-123" not in str(active)  # کلید هرگز بیرون نمی‌رود
    provs2 = {p["code"]: p for p in configured_map_providers(s2)}
    assert provs2["neshan"]["enabled"] is True
    assert provs2["neshan"]["is_default"] is True
    assert provs2["neshan"]["tile_url"] is None
    assert "secret-key-123" not in str(provs2)

    s3 = SimpleNamespace(map_provider="mapir", neshan_api_key="", mapir_api_key="mapir-key-456")
    assert active_map_provider(s3)["code"] == "mapir"


def test_haversine_known_distances():
    from app.services.maps import haversine_km
    # تهران → کرج ~ ۳۹ کیلومتر
    d = haversine_km(35.7150, 51.4040, 35.8400, 50.9391)
    assert 30 < d < 50
    # تهران → اصفهان ~ ۳۴۰ کیلومتر
    d2 = haversine_km(35.7150, 51.4040, 32.6546, 51.6680)
    assert 300 < d2 < 400
    # صفر فاصله
    assert haversine_km(35.7, 51.4, 35.7, 51.4) == 0
