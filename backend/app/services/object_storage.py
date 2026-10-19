"""فاز ۳۷ - ADR-04 سند جامع: Object Storage پلاگین‌پذیر (local | S3/MinIO).

تصمیم معماری (همان الگوی D02/D03/D07/B28):
- storage_backend = "local" (پیش‌فرض: دایرکتوری volume، بدون کلید، قطعی) | "s3"
- آداپتور «s3» (سازگار با MinIO و هر endpoint سازگار S3) فقط با هر چهار مقدار
  endpoint + bucket + access_key + secret_key فعال می‌شود؛ نبود هر کدام، نبود
  کتابخانه boto3 یا خطای خود سرویس → fallback به local (fail-soft) به‌جای
  از‌دست‌رفتن فایل؛ وضعیت fallback در خروجی status شفاف گزارش می‌شود.
- کلیدها هرگز به کلاینت/لاگ/پاسخ API نمی‌روند (فقط نام bucket به‌عنوان
  فراداده عملیاتی در /integrations/config می‌آید — راز نیست).
- پروایدر واقعیِ ذخیره هر فایل در ردیف files.storage ثبت می‌شود تا مهاجرت
  تدریجی ممکن باشد (فایل قدیمی local می‌ماند، فایل جدید s3 می‌رود) و دانلود
  همیشه از همان پروایدرِ ردیف خوانده می‌شود — نه از config جاری.
- بند B39 حفظ می‌شود: دانلود همچنان فقط با بلیت امضاشده کوتاه‌مدت از مسیر
  سرور انجام می‌شود؛ URL امضاشده S3 (presigned) برای دانلود کاربر تولید
  نمی‌شود تا «کنترل مجوز در هر بار دانلود» و audit از دست نرود.
"""
from __future__ import annotations

import hashlib
import os
import uuid as uuid_mod
from datetime import datetime, timezone

from app.core.config import Settings, get_settings
from app.services import file_storage as fs

BACKENDS = ("local", "s3")


# ---------------------------------------------------------------- resolution
def configured_backend(s: Settings | None = None) -> str:
    """نام بک‌اند پیکربندی‌شده (پیش‌فرض local)."""
    s = s or get_settings()
    backend = (getattr(s, "storage_backend", "local") or "local").strip().lower()
    return backend if backend in BACKENDS else "local"


def boto3_available() -> bool:
    try:
        import boto3  # noqa: F401
        import botocore  # noqa: F401
        return True
    except ImportError:
        return False


def s3_ready(s: Settings | None = None) -> bool:
    """آیا آداپتور S3 قابل فعال‌سازی است؟ (config کامل + boto3 موجود)"""
    s = s or get_settings()
    return bool(
        (getattr(s, "s3_endpoint_url", "") or "").strip()
        and (getattr(s, "s3_bucket", "") or "").strip()
        and (getattr(s, "s3_access_key", "") or "").strip()
        and (getattr(s, "s3_secret_key", "") or "").strip()
        and boto3_available()
    )


def active_backend(s: Settings | None = None) -> tuple[str, bool]:
    """بک‌اند فعال واقعی + پرچم fallback — S3 ناقص/خراب → local (fail-soft)."""
    s = s or get_settings()
    if configured_backend(s) == "s3" and not s3_ready(s):
        return "local", True
    return configured_backend(s), False


def storage_status(s: Settings | None = None) -> dict:
    """متادیتای شفاف ذخیره‌سازی — بدون هیچ کلیدی (شفافیت ADR-04)."""
    s = s or get_settings()
    active, fallback = active_backend(s)
    return {
        "channel": "storage",
        "configured_backend": configured_backend(s),
        "active_backend": active,
        "fallback_applied": fallback,
        "bucket": (getattr(s, "s3_bucket", "") or "").strip(),
        "boto3_available": boto3_available(),
    }


# ---------------------------------------------------------------- s3 adapter
def _s3_client(s: Settings):
    """کارخانه کلاینت S3 — در آزمون‌ها monkeypatch می‌شود."""
    import boto3  # fail-soft: فراخواننده پیش از این s3_ready را چک کرده است

    return boto3.client(
        "s3",
        endpoint_url=(s.s3_endpoint_url or "").strip(),
        aws_access_key_id=(s.s3_access_key or "").strip(),
        aws_secret_access_key=(s.s3_secret_key or "").strip(),
        config=None,  # پیش‌فرض botocore؛ تایم‌اوت اتصال جداگانه کنترل می‌شود
        region_name="us-east-1",
    )


def _s3_put(s: Settings, key: str, data: bytes) -> None:
    client = _s3_client(s)
    client.put_object(Bucket=(s.s3_bucket or "").strip(), Key=key, Body=data)


def _s3_get(s: Settings, key: str) -> bytes:
    client = _s3_client(s)
    resp = client.get_object(Bucket=(s.s3_bucket or "").strip(), Key=key)
    return resp["Body"].read()


def _s3_delete(s: Settings, key: str) -> None:
    client = _s3_client(s)
    client.delete_object(Bucket=(s.s3_bucket or "").strip(), Key=key)


# ---------------------------------------------------------------- facade
def store(data: bytes, s: Settings | None = None) -> tuple[str, str, str, bool]:
    """ذخیره محتوا در بک‌اند فعال؛ خروجی (پروایدر واقعی، کلید، sha256، fallback).

    خطای آداپتور S3 → ذخیره محلی (fail-soft)؛ فایل هرگز گم نمی‌شود و
    پروایدر واقعی به‌عنوان منبع حقیقت دانلود در ردیف files.storage می‌رود.
    """
    s = s or get_settings()
    sha = hashlib.sha256(data).hexdigest()
    key = f"{datetime.now(timezone.utc):%Y/%m}/{uuid_mod.uuid4().hex}"

    backend, fb = active_backend(s)
    if backend == "s3":
        try:
            _s3_put(s, key, data)
            return "s3", key, sha, False
        except Exception:
            # fail-soft: سقوط به local با همان کلید — پروایدر ثبت‌شده = local
            fs.save_bytes_at_key(s.upload_dir, key, data)
            return "local", key, sha, True

    fs.save_bytes_at_key(s.upload_dir, key, data)
    return "local", key, sha, fb


def open_bytes(upload_dir: str, provider: str, storage_key: str, s: Settings | None = None) -> bytes:
    """خواندن محتوا از پروایدرِ ردیف فایل (منبع حقیقت دانلود)."""
    s = s or get_settings()
    if provider == "s3":
        return _s3_get(s, storage_key)
    path = fs.storage_path(upload_dir, storage_key)
    with open(path, "rb") as fh:
        return fh.read()


def remove(upload_dir: str, provider: str, storage_key: str, s: Settings | None = None) -> None:
    """حذف best-effort از پروایدر مربوطه — شکست نادیده گرفته می‌شود."""
    s = s or get_settings()
    try:
        if provider == "s3":
            _s3_delete(s, storage_key)
        else:
            fs.remove_file(upload_dir, storage_key)
    except Exception:
        pass


def ensure_dir(upload_dir: str) -> str:
    return fs.ensure_upload_dir(upload_dir)


def local_exists(upload_dir: str, storage_key: str) -> bool:
    return os.path.exists(fs.storage_path(upload_dir, storage_key))
