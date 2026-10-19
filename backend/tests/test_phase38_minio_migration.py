"""فاز ۳۸ - گام ۲ طرح مهاجرت ADR-04: انتقال idempotent فایل‌های local به S3.

پوشش آزمون (با S3 موک‌شده در حافظه — بدون سرویس بیرونی):
- مهاجرت موفق: put با همان کلید + راستی‌آزمایی sha256 + ثبت storage='s3'
- حفظ نسخه محلی (تسویه فقط در گام ۴ طرح)
- idempotency: اجرای مجدد هیچ ردیفی را دوباره پیمایش نمی‌کند
- فایل محلی ناموجود → skip با گزارش
- ناسازگاری checksum محلی → skip (بدون هرگونه انتقال)
- خطای سرویس S3 → skip همان ردیف؛ بقیه ادامه (fail-soft)
- dry-run: هیچ نوشتنی (نه S3 و نه DB)
- آداپتور ناقص → RuntimeError (migrate الکی ممنوع)
- اعتبار سرویس‌های compose (ساختار minio/minio-init/volume)
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from app.core.config import get_settings
from app.models.file import StoredFile
from app.services import file_storage as fs
from app.services import object_storage as objstore
from app.services.storage_migration import migrate_batch

_REPO_ROOT = Path(__file__).resolve().parents[2]


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
    """ردیف‌های local سایر آزمون‌ها را موقتاً از دید مهاجرت خارج می‌کند.

    مهاجرت ADR-04 سراسری است (همه storage='local')؛ پایگاه آزمون session-scoped
    است و آزمون‌های فایل قبلی ردیف local ساخته‌اند — برای قطعیت شمارش‌ها،
    آن ردیف‌ها در ابتدای هر آزمون موقتاً 's3' و در پایان به حالت اول برمی‌گردند.
    """
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


def test_migrate_batch_moves_files_to_s3(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "up1")})
    row = _mk_local_file(db, s.upload_dir, "2026/01/phase38-a", b"content-A-phase38")

    report = migrate_batch(db, s=s, limit=10)

    assert report.migrated == 1
    assert report.errors == 0
    db.refresh(row)
    assert row.storage == "s3"
    # همان کلید + بایت همان + نسخه محلی حفظ شده (تسویه = گام ۴)
    assert row.storage_key in fake_s3.store
    assert fake_s3.store[row.storage_key] == b"content-A-phase38"
    assert Path(fs.storage_path(s.upload_dir, row.storage_key)).exists()


def test_migrate_batch_is_idempotent(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "up2")})
    _mk_local_file(db, s.upload_dir, "2026/01/phase38-b", b"content-B")

    first = migrate_batch(db, s=s, limit=10)
    assert first.migrated == 1
    # اجرای مجدد: ردیف s3 در پیمایش نمی‌آید
    second = migrate_batch(db, s=s, limit=10)
    assert second.scanned == 0
    assert second.migrated == 0


def test_migrate_batch_skips_missing_local(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "up3")})
    row = StoredFile(
        original_name="gone.pdf", mime="application/pdf", size_bytes=3,
        sha256=hashlib.sha256(b"abc").hexdigest(),
        storage_key="2026/01/phase38-missing", storage="local",
        context="case_document", scan_status="clean",
    )
    db.add(row)
    db.flush()

    report = migrate_batch(db, s=s, limit=10)

    assert report.skipped_missing == 1
    db.refresh(row)
    assert row.storage == "local"
    assert row.storage_key not in fake_s3.store


def test_migrate_batch_skips_checksum_mismatch(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "up4")})
    row = _mk_local_file(db, s.upload_dir, "2026/01/phase38-c", b"real-content")
    # checksum ردیف عمداً ناسازگار با محتوا
    row.sha256 = hashlib.sha256(b"different").hexdigest()
    db.flush()

    report = migrate_batch(db, s=s, limit=10)

    assert report.checksum_mismatch == 1
    db.refresh(row)
    assert row.storage == "local"
    assert row.storage_key not in fake_s3.store


def test_migrate_batch_fail_soft_on_s3_error(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "up5")})
    row_bad = _mk_local_file(db, s.upload_dir, "2026/01/phase38-bad", b"bad-target")
    row_ok = _mk_local_file(db, s.upload_dir, "2026/01/phase38-good", b"good-target")

    fake_s3.fail_put = True
    report = migrate_batch(db, s=s, limit=10)
    assert report.errors == 2
    db.refresh(row_bad)
    db.refresh(row_ok)
    assert row_bad.storage == "local"

    # رفع خرابی → اجرای مجدد هر دو را منتقل می‌کند (idempotent و ادامه‌پذیر)
    fake_s3.fail_put = False
    report2 = migrate_batch(db, s=s, limit=10)
    assert report2.migrated == 2
    db.refresh(row_bad)
    assert row_bad.storage == "s3"


def test_migrate_batch_dry_run_writes_nothing(fake_s3, env, tmp_path, isolate_local_rows):
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "up6")})
    row = _mk_local_file(db, s.upload_dir, "2026/01/phase38-d", b"dry-run-content")

    report = migrate_batch(db, s=s, limit=10, dry_run=True)

    assert report.dry_run is True
    assert report.would_migrate == 1
    assert report.migrated == 0
    db.refresh(row)
    assert row.storage == "local"
    assert fake_s3.store == {}


def test_migrate_batch_requires_ready_adapter(monkeypatch, env, tmp_path):
    monkeypatch.setattr(objstore, "s3_ready", lambda s=None: False)
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "up7")})
    with pytest.raises(RuntimeError):
        migrate_batch(db, s=s, limit=10)


def test_s3_readback_mismatch_is_error(fake_s3, env, tmp_path, monkeypatch, isolate_local_rows):
    """اگر خواندن مجدد از S3 بایت ناسازگار برگرداند → خطا و ماندن روی local."""
    db = env["db"]
    s = get_settings().model_copy(update={"upload_dir": str(tmp_path / "up8")})
    row = _mk_local_file(db, s.upload_dir, "2026/01/phase38-e", b"verify-me")
    # خواندن مجدد خراب: بایت دیگر برمی‌گرداند
    monkeypatch.setattr(objstore, "_s3_get", lambda s_, key: b"corrupted")
    report = migrate_batch(db, s=s, limit=10)
    assert report.errors == 1
    db.refresh(row)
    assert row.storage == "local"


# ---------------------------------------------------------------- compose
def test_compose_has_minio_service_and_volume():
    with open(_REPO_ROOT / "compose.yml", encoding="utf-8") as fh:
        compose = yaml.safe_load(fh)
    services = compose.get("services", {})
    minio = services.get("minio")
    assert minio, "سرویس minio در compose.yml باید تعریف شده باشد (گام ۱ طرح ADR-04)"
    assert "storage" in minio.get("profiles", [])
    assert "minio_data" in minio.get("volumes", [""])[0]
    assert "minio_data" in compose.get("volumes", {})
    init = services.get("minio-init")
    assert init, "سرویس minio-init (ساخت idempotent bucket) باید تعریف شده باشد"
    assert init.get("depends_on", {}).get("minio", {}).get("condition") == "service_healthy"


def test_compose_dev_exposes_minio_ports():
    with open(_REPO_ROOT / "compose.dev.yml", encoding="utf-8") as fh:
        compose = yaml.safe_load(fh)
    minio = compose.get("services", {}).get("minio")
    assert minio, "سرویس minio در compose.dev.yml باید تعریف شده باشد"
    ports = " ".join(minio.get("ports", []))
    assert "9000" in ports and "9001" in ports
    # api در توسعه هم endpoint داخلی MinIO را می‌گیرد
    api_env = compose["services"]["api"].get("environment", {})
    if isinstance(api_env, list):
        api_env = dict(str(e).split("=", 1) for e in api_env if "=" in str(e))
    assert "S3_ENDPOINT_URL" in api_env
    assert "minio:9000" in str(api_env["S3_ENDPOINT_URL"])
