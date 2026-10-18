"""B39-plus فاز ۲۷ - اتصال آنتی‌ویروس واقعی (ClamAV) به خط اسکن فایل.

ترتیب بسترهای اسکن (اولین بستر موجود استفاده می‌شود):
1) clamd از راه TCP - پروتکل INSTREAM (حالت استاندارد docker compose)
2) clamscan از راه subprocess (نصب بومی روی سرور، برای استقرار خارج از داکر)
3) قواعد پایه داخلی - در نبود ClamAV؛ شامل امضای استاندارد EICAR و قواعد
   نوع/پسوند فاز ۲۵ (fallback ایمن، تفکیک‌شدنی در ستون scanner از file_scans)

سیاست خطا:
- قطع بودن clamd → رفتن به بستر بعدی (توقف آپلودها ممنوع؛ بند B39)
- پاسخ ERROR از clamd (مثلاً سقف حجم INSTREAM) → قرنطینه احتیاطی (fail-closed)
- شناسایی قطعی بدافزار → quarantined؛ دانلود فایل قرنطینه مسدود است

خروجی هر اسکن: ScanResult(status, detail, scanner)
status یکی از clean / quarantined / failed
"""

import hashlib
import os
import socket
import struct
import subprocess
from dataclasses import dataclass

from app.core.config import get_settings

# امضای آزمایشی استاندارد EICAR - همه آنتی‌ویروس‌های واقعی آن را شناسایی می‌کنند
EICAR_SHA256 = "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"
EICAR_PREFIX = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

CHUNK_SIZE = 8192  # سقف بلوک INSTREAM (مطابق پیش‌فرض clamd)


@dataclass
class ScanResult:
    status: str
    detail: str
    scanner: str


def _static_rules(filename: str, mime: str, allowed_mime: list[str], data: bytes) -> tuple[str, str] | None:
    """قواعد پایه: امضای EICAR + پسوند اجرایی + MIME غیرمجاز + فایل خالی.

    خروجی (status, detail) در صورت برخورد؛ None یعنی مشکلی از این قواعد نیست.
    """
    lowered = (filename or "").lower()
    executable_exts = (".exe", ".bat", ".cmd", ".sh", ".ps1", ".js", ".vbs", ".scr", ".com", ".msi")
    if lowered.endswith(executable_exts):
        return "quarantined", "نوع فایل اجرایی مجاز نیست - قرنطینه"
    if mime not in allowed_mime:
        return "quarantined", f"نوع {mime} در فهرست مجاز نیست - قرنطینه"
    if not data:
        return "quarantined", "فایل خالی است"
    sha = hashlib.sha256(data).hexdigest()
    if sha == EICAR_SHA256 or EICAR_PREFIX in data:
        return "quarantined", "امضای آزمایشی بدافزار (EICAR) شناسایی شد - قرنطینه"
    return None


# ---------- بستر ۱: clamd (TCP / INSTREAM) ----------

def _clamd_instream(data: bytes, host: str, port: int, timeout: float) -> ScanResult:
    """پروتکل INSTREAM: zINSTREAM\\0 سپس بلوک‌های [طول ۴ بایتی][داده] و بلوک پایانی صفر."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(b"zINSTREAM\0")
        for offset in range(0, len(data), CHUNK_SIZE):
            chunk = data[offset:offset + CHUNK_SIZE]
            sock.sendall(struct.pack("!L", len(chunk)) + chunk)
        sock.sendall(struct.pack("!L", 0))
        response = b""
        while True:
            try:
                part = sock.recv(4096)
            except socket.timeout:
                break
            if not part:
                break
            response += part
            if b"\n" in part:
                break
    text = response.decode("utf-8", errors="replace").strip()
    if not text:
        raise OSError("پاسخی از clamd دریافت نشد")
    lowered = text.lower()
    if "ok" in lowered and "found" not in lowered:
        return ScanResult("clean", f"ClamAV: تمیز ({text})", "clamav-clamd")
    if "found" in lowered:
        # شکل پاسخ: stream: <نام بدافزار> FOUND
        virus = text.split(":", 1)[1].replace("FOUND", "").strip() if ":" in text else text
        return ScanResult("quarantined", f"ClamAV: شناسایی بدافزار ({virus}) - قرنطینه", "clamav-clamd")
    # ERROR / size limit / پاسخ نامفهوم → قرنطینه احتیاطی
    return ScanResult("quarantined", f"ClamAV: اسکن ناموفق، قرنطینه احتیاطی ({text[:200]})", "clamav-clamd")


def _try_clamd(data: bytes) -> ScanResult | None:
    settings = get_settings()
    if not settings.clamav_enabled or not settings.clamav_host:
        return None
    try:
        return _clamd_instream(
            data, settings.clamav_host, settings.clamav_port, settings.clamav_timeout_seconds
        )
    except Exception:
        return None


# ---------- بستر ۲: clamscan (subprocess) ----------

def _try_clamscan(data: bytes) -> ScanResult | None:
    """اجرای clamscan با ورودی استاندارد؛ خروجی ۰=تمیز، ۱=بدافزار، ۲=خطا."""
    clamscan = None
    for candidate in ("/usr/bin/clamscan", "/usr/local/bin/clamscan"):
        if os.path.exists(candidate):
            clamscan = candidate
            break
    if clamscan is None:
        return None
    try:
        proc = subprocess.run(
            [clamscan, "--no-summary", "--stdout", "-"],
            input=data, capture_output=True, timeout=60,
        )
    except Exception:
        return None
    if proc.returncode == 0:
        return ScanResult("clean", "ClamAV: تمیز (clamscan)", "clamav-clamscan")
    if proc.returncode == 1:
        out = proc.stdout.decode("utf-8", errors="replace").strip()[:300]
        return ScanResult("quarantined", f"ClamAV: شناسایی بدافزار ({out}) - قرنطینه", "clamav-clamscan")
    return None  # خطای اجرا → بستر بعدی


# ---------- نقطه ورود ----------

def scan_bytes(filename: str, mime: str, data: bytes, allowed_mime: list[str]) -> ScanResult:
    """اسکن کامل محتوا؛ fallback شفاف به قواعد پایه در نبود ClamAV."""
    static = _static_rules(filename, mime, allowed_mime, data)
    if static is not None:
        return ScanResult(static[0], static[1], "builtin-rules")

    for backend in (_try_clamd, _try_clamscan):
        result = backend(data)
        if result is not None:
            return result

    return ScanResult(
        "clean",
        "بررسی پایه انجام شد (ClamAV در دسترس نبود؛ قواعد پایه)",
        "builtin-rules",
    )


def scanner_status() -> dict:
    """وضعیت بسترهای اسکن - برای گزارش DPO و صف مدیریت."""
    settings = get_settings()
    clamd_up = False
    if settings.clamav_enabled and settings.clamav_host:
        try:
            with socket.create_connection(
                (settings.clamav_host, settings.clamav_port), timeout=settings.clamav_timeout_seconds
            ):
                clamd_up = True
        except Exception:
            clamd_up = False
    clamscan_up = any(
        os.path.exists(p) for p in ("/usr/bin/clamscan", "/usr/local/bin/clamscan")
    )
    return {
        "clamd_configured": bool(settings.clamav_enabled and settings.clamav_host),
        "clamd_reachable": clamd_up,
        "clamscan_available": clamscan_up,
        "fallback": "builtin-rules",
    }
