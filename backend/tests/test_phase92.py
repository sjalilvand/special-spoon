"""فاز ۹۲ — فراخوان همکاری: دیدپذیری کامل ثبت در لاگ + نشست/کپچای پایدار در برابر ری‌استارت.

عارضهٔ میدانی فاز ۹۱ (لاگ اجرای کاربر روی سرور):
- جست‌وجوی «farakhan» در لاگ rosepsy-api هیچ چیز پیدا نمی‌کرد؛
- علت ۱) هر ردِ اعتبارسنجی ۴۲۲ (کپچا، نشست، فایل‌ها، ...) اصلاً لاگ نمی‌شد —
  فقط خطاهای غیرمنتظرهٔ ۵xx لاگ می‌شدند؛
- علت ۲) نشست فرم و کپچا فقط در حافظهٔ فرایند بودند؛ ری‌استارت سرویس (مثل
  ری‌استارت خودکار هنگام استقرار) همه را می‌خشکاند و کاربرِ در میانهٔ فرم با
  «مهلت منقضی» رد می‌شد — بدون هیچ رد پایی در لاگ.

رفع این فاز (پوشش آزمون همین فایل):
- لاگر اختصاصی farakhan با هندلر مستقل: INFO شروع/موفق، WARNING هر ۴xx با نقشهٔ فیلدها؛
- فروشگاه KV نشست/کپچا: اول Redis (پایدار در برابر ری‌استارت)، نبودش حافظهٔ
  فرایند (fail-open — الگوی بند ۶ ADR-05)؛ پاپ اتمی GET+DELETE (سازگار با Redis 5)؛
- پاپ تک‌مصرف کپچا (ضد replay) حفظ شده است.
"""

from __future__ import annotations

import io
import json
import logging

import pytest

from conftest import next_national_code

META_URL = "/api/v1/farakhan/meta"


# ---------------------------------------------------------------- ابزار آزمون
def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 30, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF"


class _FakePipeline:
    """پایپ‌لاین اتمی GET+DELETE — هم‌ارز رفتار redis-py برای _kv_pop."""

    def __init__(self, client: "_FakeRedis") -> None:
        self._client = client
        self._ops: list[tuple[str, str]] = []

    def get(self, key: str) -> None:
        self._ops.append(("get", key))

    def delete(self, key: str) -> None:
        self._ops.append(("delete", key))

    def execute(self):
        out = []
        for op, key in self._ops:
            if op == "get":
                out.append(self._client.store.get(key))
            else:
                out.append(1 if self._client.store.pop(key, None) is not None else 0)
        self._ops = []
        return out


class _FakeRedis:
    """حداقل رفتار redis-py لازم برای فروشگاه KV (set/get/pipeline)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key, value, ex=None):  # noqa: ANN001
        self.store[key] = value if isinstance(value, str) else value.decode("utf-8")
        return True

    def get(self, key):  # noqa: ANN001
        return self.store.get(key)

    def pipeline(self, transaction: bool = True) -> _FakePipeline:  # noqa: ARG002
        return _FakePipeline(self)


@pytest.fixture()
def fake_redis(monkeypatch):
    """Redis ساختگی + خالی‌کردن حافظهٔ پشتیبان — فروشگاه باید از Redis برود."""
    fr = _FakeRedis()
    from app.api.v1 import farakhan as fk

    monkeypatch.setattr(fk, "_redis", lambda: fr)
    fk._kv_memory.clear()
    return fr


@pytest.fixture(autouse=True)
def _clear_farakhan_rate_hits():
    """سقف نرخ ثبت (۲۰ در ساعت) بین آزمون‌های این فایل ریست می‌شود تا ۴۲۹ مصنوعی نبینیم."""
    from app.api.v1 import farakhan as fk

    fk._submit_ip_hits.clear()
    yield
    fk._submit_ip_hits.clear()


def _valid_payload(sid, captcha_id, answer, **over):
    base = {
        "first_name": "آزمون", "last_name": "فراخوانی۹۲",
        # فاز ۹۳ — ثبت تکراری با یک کد ملی ۴۲۲ می‌گیرد؛ هر ثبت آزمونی کد یکتای معتبر می‌گیرد
        "national_code": next_national_code(),
        "gender": "female", "birth_date": "1370/01/01",
        "education_degree": "bachelor", "education_field": "روان‌شناسی",
        "license_status": "none", "center_ownership": "rented",
        "province_name": "تهران", "county_name": "تهران",
        "phone": "02112345678",
        "individual_rooms": 1, "group_rooms": 0, "child_rooms": 0, "counselors_count": 1,
        "has_waiting_space": True, "accepts_company_pattern": False, "has_accessibility": False,
        "terms_accepted": True,
        "captcha_id": captcha_id, "captcha_answer": str(answer),
        "session_id": sid,
    }
    base.update(over)
    return base


def _meta_captcha(client):
    m = client.get(META_URL).json()
    cap = client.get("/api/v1/farakhan/captcha").json()
    from app.api.v1.farakhan import _peek_captcha_answer

    return m["session_id"], cap, str(_peek_captcha_answer(cap["captcha_id"]))


def _submit(client, payload, files=None):
    files = files or {
        "national_id_card": ("card.png", _png_bytes(), "image/png"),
        "degree_document": ("degree.pdf", _pdf_bytes(), "application/pdf"),
        "center_activity_license": ("license.jpg", _png_bytes(), "image/jpeg"),
    }
    return client.post(
        "/api/v1/farakhan/submissions",
        data={"payload": json.dumps(payload, ensure_ascii=False)},
        files=[(k, (f, c, m)) for k, (f, c, m) in files.items()],
    )


# ---------------------------------------------------------------- لاگ‌پذیری کامل ثبت (فاز ۹۲)
def test_422_rejection_is_logged_with_field_map(client, caplog):
    """رد اعتبارسنجی ۴۲۲ باید در لاگ farakhan بیفتد — پیش‌تر هیچ ردی نداشت."""
    sid, cap, ans = _meta_captcha(client)
    with caplog.at_level(logging.INFO, logger="farakhan"):
        r = _submit(client, _valid_payload(sid, cap["captcha_id"], "0" * 50))
    assert r.status_code == 422, r.text
    recs = [x for x in caplog.records if x.name == "farakhan"]
    assert recs, "رد اعتبارسنجی باید در لاگ «farakhan» ثبت شود"
    joined = " ".join(x.getMessage() for x in recs)
    assert "۴۲۲" in joined
    assert "کپچا" in joined  # برچسب فیلد مقصر در لاگ آمده است
    assert any(x.levelno == logging.INFO and "درخواست رسید" in x.getMessage() for x in recs)


def test_successful_submit_is_logged_with_tracking_code(client, caplog):
    sid, cap, ans = _meta_captcha(client)
    with caplog.at_level(logging.INFO, logger="farakhan"):
        r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans))
    assert r.status_code == 201, r.text
    tracking = r.json()["tracking_code"]
    recs = [x for x in caplog.records if x.name == "farakhan" and x.levelno == logging.INFO]
    assert any(
        "ثبت موفق" in x.getMessage() and tracking in x.getMessage() for x in recs
    ), [x.getMessage() for x in recs]


def test_session_expired_422_is_logged(client, caplog):
    """گم‌شدن نشست (مثل ری‌استارت نسخهٔ حافظه‌ای) → ۴۲۲ «مهلت» + رد در لاگ."""
    sid, cap, ans = _meta_captcha(client)
    from app.api.v1 import farakhan as fk

    fk._kv_pop(f"farakhan:sess:{sid}")  # نشست را گم می‌کنیم
    with caplog.at_level(logging.INFO, logger="farakhan"):
        r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans))
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    assert any("مهلت یک‌ساعته" in v for v in errors.values()), errors
    joined = " ".join(x.getMessage() for x in caplog.records if x.name == "farakhan")
    assert "۴۲۲" in joined
    assert "مهلت" in joined


# ---------------------------------------------------------------- فروشگاه KV پایدار در برابر ری‌استارت
def test_kv_store_prefers_redis_and_survives_memory_reset(fake_redis):
    """با Redis فعال، مقدار باید در Redis باشد — خالی‌شدن حافظهٔ فرایند بی‌اثر است."""
    from app.api.v1 import farakhan as fk

    fk._kv_put("farakhan:sess:abc", "1", 3600)
    assert fk._kv_get("farakhan:sess:abc") == "1"
    assert "farakhan:sess:abc" in fake_redis.store
    fk._kv_memory.clear()  # شبیه‌سازی ری‌استارت فرایند
    assert fk._kv_get("farakhan:sess:abc") == "1"


def test_kv_pop_is_single_use_and_atomic(fake_redis):
    """پاپ اتمی GET+DELETE — دومین پاپ None می‌دهد (ضد replay)."""
    from app.api.v1 import farakhan as fk

    fk._kv_put("farakhan:cap:x1", "77", 600)
    assert fake_redis.store["farakhan:cap:x1"] == "77"
    assert fk._kv_pop("farakhan:cap:x1") == "77"
    assert fk._kv_pop("farakhan:cap:x1") is None


def test_session_survives_restart_across_full_flow(client, fake_redis):
    """نشست صادرشده از meta حتی پس از خالی‌شدن حافظهٔ فرایند باید معتبر بماند."""
    sid, cap, ans = _meta_captcha(client)
    from app.api.v1 import farakhan as fk

    fk._kv_memory.clear()  # شبیه‌سازی ری‌استارت سرویس
    r = _submit(client, _valid_payload(sid, cap["captcha_id"], ans))
    assert r.status_code == 201, r.text


def test_captcha_single_use_after_restart(client, fake_redis):
    """کپچا پس از «ری‌استارت» هم مصرف‌شده می‌ماند — ثبت دوباره با همان کپچا رد می‌شود."""
    sid, cap, ans = _meta_captcha(client)
    from app.api.v1 import farakhan as fk

    fk._kv_memory.clear()
    r1 = _submit(client, _valid_payload(sid, cap["captcha_id"], ans))
    assert r1.status_code == 201, r1.text
    # همان کپچا با نشست تازه → رد (مصرف تک‌بار در فروشگاه Redis)
    sid2, _cap2, _ans2 = _meta_captcha(client)
    r2 = _submit(client, _valid_payload(sid2, cap["captcha_id"], ans))
    assert r2.status_code == 422, r2.text
    assert any("کپچا" in v for v in r2.json()["detail"]["errors"].values())


def test_memory_fallback_still_works_without_redis(monkeypatch):
    """نبود Redis (تنظیمات خاموش — توسعه/آزمون) → حافظهٔ فرایند؛ رفتار فاز ۹۱ حفظ می‌شود."""
    from app.api.v1 import farakhan as fk

    monkeypatch.setattr(fk, "_redis", lambda: None)
    fk._kv_memory.clear()
    fk._kv_put("farakhan:sess:mem", "1", 3600)
    assert fk._kv_get("farakhan:sess:mem") == "1"
    assert fk._kv_pop("farakhan:sess:mem") == "1"
    assert fk._kv_get("farakhan:sess:mem") is None
