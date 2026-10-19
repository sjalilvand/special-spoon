"""B39 سند جامع - سرویس ذخیره‌سازی و اسکن فایل (پروایدر محلی آداپتور ADR-04).

- فایل فیزیکی خارج از پایگاه داده (دایرکتوری volume) ذخیره می‌شود؛
  پایگاه داده فقط کلید ذخیره و فراداده نگه می‌دارد.
- از فاز ۳۷ (ADR-04) این ماژول پروایدر «local» از آداپتور پلاگین‌پذیر
  object_storage است؛ بک‌اند S3/MinIO در app/services/object_storage.py.
- checksum به الگوریتم SHA-256 (بند «فایل و امنیت» سند).
- بلیت دانلود کوتاه‌مدت HMAC در همین ماژول برای همه پروایدرها یکسان است.
- فایل نامعتبر/مشکوک وارد قرنطینه می‌شود و دانلود نمی‌شود.
"""

import hashlib
import hmac
import os
import time
import uuid as uuid_mod
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings


def ensure_upload_dir(upload_dir: str) -> str:
    path = os.path.abspath(upload_dir)
    os.makedirs(path, exist_ok=True)
    return path


def storage_path(upload_dir: str, storage_key: str) -> str:
    # کلید شامل تاریخ + uuid: هیچ نام کاربر در مسیر نمی‌آید (path traversal امن)
    return os.path.join(ensure_upload_dir(upload_dir), storage_key)


def save_bytes(upload_dir: str, data: bytes) -> tuple[str, str]:
    """ذخیره محتوا و بازگرداندن (کلید ذخیره، sha256)."""
    sha = hashlib.sha256(data).hexdigest()
    key = f"{datetime.now(timezone.utc):%Y/%m}/{uuid_mod.uuid4().hex}"
    save_bytes_at_key(upload_dir, key, data)
    return key, sha


def save_bytes_at_key(upload_dir: str, key: str, data: bytes) -> None:
    """ذخیره محتوا با کلید معلوم (مورد استفاده fallback آداپتور ADR-04)."""
    path = storage_path(upload_dir, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def remove_file(upload_dir: str, storage_key: str) -> None:
    try:
        os.remove(storage_path(upload_dir, storage_key))
    except OSError:
        pass


def run_stub_scan(filename: str, mime: str, size: int, allowed_mime: list[str]) -> tuple[str, str]:
    """اسکن ساده: نوع مجاز + نام غیراسکریپتی. خروجی (status, detail)."""
    lowered = filename.lower()
    executable_exts = (".exe", ".bat", ".cmd", ".sh", ".ps1", ".js", ".vbs", ".scr", ".com", ".msi")
    if lowered.endswith(executable_exts):
        return "quarantined", "نوع فایل اجرایی مجاز نیست - قرنطینه"
    if mime not in allowed_mime:
        return "quarantined", f"نوع {mime} در فهرست مجاز نیست - قرنطینه"
    if size <= 0:
        return "quarantined", "فایل خالی است"
    return "clean", "بررسی پایه انجام شد (stub)"


# ---------- بلیت دانلود کوتاه‌مدت با امضای HMAC (بند «URLهای کوتاه‌مدت با امضا») ----------

def _sig(secret: str, payload: str) -> str:
    return urlsafe_b64encode(
        hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")


def make_download_ticket(secret: str, file_id: str, user_id: str, ttl_seconds: int) -> tuple[str, str]:
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    exp_ts = str(int(expires.timestamp()))
    payload = f"{file_id}.{user_id}.{exp_ts}"
    sig = _sig(secret, payload)
    token = urlsafe_b64encode(payload.encode()).decode().rstrip("=") + "." + sig
    return token, expires.isoformat()


def verify_download_ticket(secret: str, token: str) -> tuple[str, str] | None:
    """خروجی (file_id, user_id) یا None در نامعتبر/منقضی."""
    try:
        b64, sig = token.rsplit(".", 1)
        payload = urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)).decode()
        file_id, user_id, exp_ts = payload.split(".", 2)
        if int(exp_ts) < int(time.time()):
            return None
        if not hmac.compare_digest(_sig(secret, payload), sig):
            return None
        return file_id, user_id
    except Exception:
        return None
