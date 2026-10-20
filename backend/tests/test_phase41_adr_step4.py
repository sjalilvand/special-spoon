"""فاز ۴۱ - گام ۴ طرح‌های ADR-03 و ADR-04.

بخش اول — ADR-03 گام ۴ (انقضای اعلام‌شده v1):
- هدرهای Deprecation/Sunset/Warning روی همه پاسخ‌های /api/v1 (موفق و خطا)
- پاکی v2 و ریشه سامانه از هدرهای انقضا
- حالت warn (پیش‌فرض): نوشتن v1 سر جایش است (هیچ رفتاری عوض نمی‌شود)
- حالت readonly: متدهای نوشتاری → 410 با بدنه قرارداد v1 + هدرهای انقضا
- قالب HTTP-date هدر Sunset (RFC 8594) و حذف آن در مقدار نامعتبر

بخش دوم — ADR-04 گام ۴ (تسویه volume محلی) با S3 موک‌شده در حافظه:
- مهاجرت باقی‌مانده‌های local + پاک‌سازی نسخه محلی ردیف‌های s3 فقط با enforce
- حذف بدون راستی‌آزمایی S3 ممنوع (خطا/nاسازگاری/نبود checksum → حفظ نسخه محلی)
- dry-run: هیچ نوشتنی (نه S3، نه DB، نه دیسک)
- idempotency: اجرای مجدد چیزی پیدا نمی‌کند
- شفافیت عملیاتی: local_rows/settlement_ready در /integrations/config
"""
from __future__ import annotations

import hashlib
from email.utils import parsedate_to_datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deprecation import deprecation_mode, sunset_http_date
from app.models.file import StoredFile
from app.services import file_storage as fs
from app.services import object_storage as objstore
from app.services.storage_settlement import settle_batch

from conftest import bearer, login


# ===========================================================================
# بخش اول — ADR-03 گام ۴: انقضای v1
# ===========================================================================
def test_v1_responses_carry_deprecation_headers(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.headers.get("Deprecation") == 'version="v1"'
    # Sunset باید HTTP-date معتبر (RFC 8594) باشد
    sunset = r.headers.get("Sunset")
    assert sunset
    parsedate_to_datetime(sunset)  # نامعتبر → خطا
    assert r.headers.get("Warning", "").startswith("299")


def test_deprecation_headers_on_v1_error_too(client):
    r = client.get("/api/v1/users")  # بدون توکن → 401
    assert r.status_code == 401
    assert r.headers.get("Deprecation") == 'version="v1"'


def test_v2_and_root_have_no_deprecation_headers(client):
    r = client.get("/api/v2/health")
    assert r.status_code == 200
    assert "Deprecation" not in r.headers
    assert "Sunset" not in r.headers
    root = client.get("/")
    assert root.status_code == 200
    assert "Deprecation" not in root.headers


def test_v1_writes_unblocked_in_warn_mode(client):
    # پیش‌فرض warn: فقط هدر — هیچ رفتاری عوض نمی‌شود (سازگاری کامل)
    r = client.post("/api/v1/auth/login", json={"username": "t_admin", "password": "wrong-pass"})
    assert r.status_code == 401  # اجرا شد — نه 410
    assert r.headers.get("Deprecation") == 'version="v1"'


def test_v1_readonly_rejects_writes_but_reads_ok(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "v1_deprecation_mode", "readonly")
    # نوشتن → 410 با بدنه قرارداد v1 و هدرهای انقضا
    r = client.post("/api/v1/auth/login", json={"username": "t_admin", "password": "whatever"})
    assert r.status_code == 410
    assert "/api/v2" in r.json()["detail"]
    assert r.headers.get("Deprecation") == 'version="v1"'
    # خواندن برقرار است
    r2 = client.get("/api/v1/health")
    assert r2.status_code == 200
    assert r2.headers.get("Deprecation") == 'version="v1"'


def test_sunset_omitted_when_config_empty(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "v1_sunset_date", "")
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.headers.get("Deprecation") == 'version="v1"'
    assert "Sunset" not in r.headers


def test_sunset_http_date_unit():
    assert sunset_http_date("2027-04-20") == "Tue, 20 Apr 2027 00:00:00 GMT"
    assert sunset_http_date("") is None
    assert sunset_http_date(None) is None
    assert sunset_http_date("not-a-date") is None
    assert sunset_http_date("2027-13-99") is None
    # خروجی باید با parsedate استاندارد قابل‌خواندن باشد
    parsedate_to_datetime(sunset_http_date("2026-12-01"))


def test_deprecation_mode_fallback(monkeypatch):
    monkeypatch.setattr(get_settings(), "v1_deprecation_mode", "junk")
    assert deprecation_mode() == "warn"


# ===========================================================================
# بخش دوم — ADR-04 گام ۴: تسویه volume محلی (S3 موک‌شده)
# ===========================================================================
class FakeS3:
    """S3 درون‌حافظه‌ای — جایگزین موک برای put/get."""

    def __init__(self):
        self.store: dict[str, bytes] = {}
        self.fail_put = False

    def put(self, s, key, data):
        if self.fail_put:
            raise ConnectionError("simulated s3 outage")
        self.store[key] = bytes(data)

    def get(self, s, key):
        if key not in self.store:
            raise KeyError(key)
        return self.store[key]


@pytest.fixture()
def fake_s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(objstore, "_s3_put", fake.put)
    monkeypatch.setattr(objstore, "_s3_get", fake.get)
    monkeypatch.setattr(objstore, "s3_ready", lambda s=None: True)
    return fake


@pytest.fixture()
def isolate_local_rows(env):
    """ردیف‌های local سایر آزمون‌ها را موقتاً از دید تسویه خارج می‌کند."""
    db = env["db"]
    others = db.execute(select(StoredFile).where(StoredFile.storage == "local")).scalars().all()
    saved_ids = [r.id for r in others]
    for r in others:
        r.storage = "s3"
    db.flush()
    yield
    for row_id in saved_ids:
        row = db.get(StoredFile, row_id)
        if row is not None:
            row.storage = "local"
    db.flush()


def _mk_local_file(db, upload_dir: str, key: str, content: bytes) -> StoredFile:
    fs.ensure_upload_dir(upload_dir)
    fs.save_bytes_at_key(upload_dir, key, content)
    row = StoredFile(
        original_name=f"{key.split('/')[-1]}.pdf",
        mime="application/pdf",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_key=key,
        storage="local",
        context="case_document",
        scan_status="clean",
    )
    db.add(row)
    db.flush()
    return row


def test_settlement_migrates_and_cleans_with_enforce(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "settle-a")})
    content = b"settle-me-phase41"
    row = _mk_local_file(db, s.upload_dir, "2026/10/phase41-a", content)

    report = settle_batch(db, s=s, limit=10_000, enforce=True)

    assert report.migrated == 1
    assert report.cleaned == 1
    assert report.errors == 0
    assert report.bytes_freed == len(content)
    db.refresh(row)
    assert row.storage == "s3"
    assert fake_s3.store[row.storage_key] == content
    # نسخه محلی پس از راستی‌آزمایی حذف شده (تسویه واقعی volume)
    assert not Path(fs.storage_path(s.upload_dir, row.storage_key)).exists()


def test_settlement_without_enforce_keeps_local_bytes(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "settle-b")})
    row = _mk_local_file(db, s.upload_dir, "2026/10/phase41-b", b"report-only")

    report = settle_batch(db, s=s, limit=10_000, enforce=False)

    assert report.migrated == 1
    assert report.would_clean == 1
    assert report.cleaned == 0
    db.refresh(row)
    assert row.storage == "s3"
    # مهاجرت انجام شد اما حذف فیزیکی نیازمند enforce است (تصمیم دستی سند)
    assert Path(fs.storage_path(s.upload_dir, row.storage_key)).exists()


def test_settlement_dry_run_touches_nothing(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "settle-c")})
    # کاندید مهاجرت (local) — dry-run فقط شمارش می‌کند
    local_row = _mk_local_file(db, s.upload_dir, "2026/10/phase41-c1", b"dry-run-content")
    # باقی‌مانده s3 با نسخه محلی — کاندید پاک‌سازی در dry-run
    leftover = _mk_local_file(db, s.upload_dir, "2026/10/phase41-c2", b"leftover-bytes")
    leftover.storage = "s3"
    db.flush()
    fake_s3.store[leftover.storage_key] = b"leftover-bytes"  # راستی‌آزمایی در dry-run پاس می‌شود
    puts_before = set(fake_s3.store)

    report = settle_batch(db, s=s, limit=10_000, dry_run=True, enforce=True)

    assert report.would_migrate == 1
    assert report.would_clean == 1
    assert report.migrated == 0 and report.cleaned == 0
    db.refresh(local_row)
    assert local_row.storage == "local"
    assert Path(fs.storage_path(s.upload_dir, local_row.storage_key)).exists()
    assert Path(fs.storage_path(s.upload_dir, leftover.storage_key)).exists()
    # هیچ put ای به S3 نشده (فقط همان محتوای دستی اولیه)
    assert set(fake_s3.store) == puts_before


def test_settlement_s3_read_failure_blocks_cleanup(fake_s3, env, tmp_path, isolate_local_rows):
    """ردیف s3 با نسخه محلی ولی S3 در دسترس نیست → حذف ممنوع (fail-soft)."""
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "settle-d")})
    row = _mk_local_file(db, s.upload_dir, "2026/10/phase41-d", b"orphan-local")
    # ردیف را دستی s3 می‌کنیم اما در S3 چیزی نمی‌گذاریم → خواندن مجدد شکست می‌خورد
    row.storage = "s3"
    db.flush()

    report = settle_batch(db, s=s, limit=10_000, enforce=True)

    assert report.errors == 1
    assert report.cleaned == 0
    assert Path(fs.storage_path(s.upload_dir, row.storage_key)).exists()


def test_settlement_missing_checksum_blocks_cleanup(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "settle-e")})
    row = _mk_local_file(db, s.upload_dir, "2026/10/phase41-e", b"no-checksum-row")
    row.sha256 = ""
    row.storage = "s3"
    db.flush()
    fake_s3.store[row.storage_key] = b"no-checksum-row"  # در S3 هست ولی ملاکی نیست

    report = settle_batch(db, s=s, limit=10_000, enforce=True)

    assert report.verify_failed == 1
    assert report.cleaned == 0
    assert Path(fs.storage_path(s.upload_dir, row.storage_key)).exists()


def test_settlement_checksum_mismatch_blocks_migration(fake_s3, env, tmp_path, isolate_local_rows):
    """ناسازگاری checksum محلی → نه مهاجرت و نه پاک‌سازی (بررسی دستی)."""
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "settle-f")})
    row = _mk_local_file(db, s.upload_dir, "2026/10/phase41-f", b"actual-bytes")
    row.sha256 = hashlib.sha256(b"different-bytes").hexdigest()
    db.flush()

    report = settle_batch(db, s=s, limit=10_000, enforce=True)

    assert report.checksum_mismatch == 1
    assert report.migrated == 0 and report.cleaned == 0
    db.refresh(row)
    assert row.storage == "local"
    assert Path(fs.storage_path(s.upload_dir, row.storage_key)).exists()


def test_settlement_is_idempotent(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "settle-g")})
    _mk_local_file(db, s.upload_dir, "2026/10/phase41-g", b"idempotent")

    first = settle_batch(db, s=s, limit=10_000, enforce=True)
    assert first.migrated == 1 and first.cleaned == 1

    second = settle_batch(db, s=s, limit=10_000, enforce=True)
    assert second.scanned == 0
    assert second.leftover_scanned == 0
    assert second.migrated == 0 and second.cleaned == 0


def test_settlement_requires_s3_ready(monkeypatch, env, tmp_path):
    monkeypatch.setattr(objstore, "s3_ready", lambda s=None: False)
    with pytest.raises(RuntimeError):
        settle_batch(env["db"], limit=10)


def test_integrations_storage_reports_local_rows(client):
    token = login(client, "t_admin")
    r = client.get("/api/v1/integrations/config", headers=bearer(token))
    assert r.status_code == 200
    storage = r.json()["integrations"]["storage"]
    assert isinstance(storage.get("local_rows"), int)
    assert storage["local_rows"] >= 0
    assert storage["settlement_ready"] == (storage["local_rows"] == 0)
