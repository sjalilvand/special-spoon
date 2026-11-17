<#
.SYNOPSIS
فاز ۹۵ — عیب‌یابی کامل فراخوان همکاری روی سرور ویندوز (rosepsy-farakhan-diag.ps1)

.DESCRIPTION
با عارضهٔ «فرم فراخوان ثبت نمی‌شود / جدول پنل خالی است» اجرا شود:

    powershell -ExecutionPolicy Bypass -File deploy\windows\rosepsy-farakhan-diag.ps1

هر چک نتیجهٔ [OK]/[FAIL] دارد و در انتها «جمع‌بندی» می‌آید. خروجی کامل را برای
تیم پشتیبانی بفرستید. هیچ چیزی را تغییر نمی‌دهد — فقط می‌خواند و آزمایش می‌کند.
#>

$ErrorActionPreference = 'Continue'
$Base    = 'C:\rosepsy'
$App     = "$Base\app"
$Data    = "$Base\data"
$LogsApi = "$Base\logs\rosepsy-api"
$VenvPy  = "$Base\runtime\venv\Scripts\python.exe"

function OK($m)   { Write-Host "  [OK]   $m" -ForegroundColor Green }
function FAIL($m) { Write-Host "  [FAIL] $m" -ForegroundColor Red }
function INF($m)  { Write-Host "  [i]    $m" -ForegroundColor Cyan }

Write-Host ''
Write-Host '=============================================================' -ForegroundColor Yellow
Write-Host ' عیب‌یابی فراخوان همکاری — فاز ۹۵' -ForegroundColor Yellow
Write-Host " زمان: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Yellow
Write-Host '=============================================================' -ForegroundColor Yellow

# ---------------------------------------------------------------- ۱) سرویس‌ها
Write-Host ''
Write-Host '==> ۱) وضعیت سرویس‌ها'
foreach ($svc in @('rosepsy-api','rosepsy-pg','Redis','rosepsy-caddy','rosepsy-clamd')) {
    $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($s) {
        if ($s.Status -eq 'Running') { OK "سرویس $svc در حال اجراست" }
        else { FAIL "سرویس $svc وضعیت: $($s.Status)" }
    } else { INF "سرویس $svc یافت نشد" }
}

# ---------------------------------------------------------------- ۲) فضا
Write-Host ''
Write-Host '==> ۲) فضای دیسک'
try {
    $c = Get-PSDrive C
    $freeGB = [math]::Round($c.Free / 1GB, 1)
    if ($freeGB -ge 5) { OK "فضای آزاد C: حدود $freeGB گیگابایت" }
    else { FAIL "فضای آزاد C: فقط $freeGB گیگابایت — اگر زیر ۲ گیگ شود ذخیرهٔ فایل‌ها با خطا می‌شکند" }
} catch { INF "خواندن فضای دیسک ممکن نشد: $($_.Exception.Message)" }

# ---------------------------------------------------------------- ۳) .env
Write-Host ''
Write-Host '==> ۳) کلیدهای .env سرویس API'
$envPath = "$App\backend\.env"
if (Test-Path $envPath) {
    foreach ($key in @('UPLOAD_DIR','STORAGE_BACKEND','CLAMAV_ENABLED','CLAMAV_HOST','CLAMAV_PORT','REDIS_URL','RATE_LIMIT_REDIS_URL','DATABASE_URL','PUBLIC_BASE_URL','CORS_ORIGINS')) {
        $line = Select-String -Path $envPath -Pattern ('^\s*' + [regex]::Escape($key) + '\s*=') -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($line) {
            $val = ($line.Line -split '=', 2)[1]
            if ($key -in @('DATABASE_URL','REDIS_URL','RATE_LIMIT_REDIS_URL')) {
                # رمز عبور داخل URL نمایش داده نمی‌شود
                $val = ($val -replace '://[^@]+@', '://***:***@')
            }
            OK "$key = $val"
        } else {
            INF "$key تنظیم نشده (پیش‌فرض کد استفاده می‌شود)"
        }
    }
} else { FAIL "فایل .env یافت نشد: $envPath" }

# ---------------------------------------------------------------- ۴) پوشهٔ آپلود
Write-Host ''
Write-Host '==> ۴) پوشهٔ ذخیرهٔ فایل‌ها (UPLOAD_DIR)'
$uploadDir = $null
if (Test-Path $envPath) {
    $l = Select-String -Path $envPath -Pattern '^\s*UPLOAD_DIR\s*=' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($l) { $uploadDir = ($l.Line -split '=', 2)[1].Trim() }
}
if (-not $uploadDir) { $uploadDir = "$Data\uploads" }
INF "مسیر مورد بررسی: $uploadDir"
if (Test-Path $uploadDir) {
    OK 'پوشه وجود دارد'
    try {
        $probe = Join-Path $uploadDir ('diag-{0}.tmp' -f (Get-Random))
        Set-Content -Path $probe -Value 'rosepsy-diag' -Encoding ASCII -ErrorAction Stop
        Remove-Item $probe -Force -ErrorAction SilentlyContinue
        OK 'نوشتن/حذف فایل آزمایشی در پوشه موفق بود (با حساب کاربری همین ترمینال)'
        INF 'اگر API (سرویس ویندوز) حساب دیگری دارد، دسترسی آن می‌تواند متفاوت باشد — ACL:'
        icacls $uploadDir | Select-Object -First 6 | ForEach-Object { Write-Host "       $_" }
    } catch { FAIL "نوشتن آزمایشی شکست خورد: $($_.Exception.Message)" }
} else { FAIL "پوشهٔ آپلود وجود ندارد: $uploadDir" }

# ---------------------------------------------------------------- ۵) لاگ API — ردیابی خطای فراخوان
Write-Host ''
Write-Host '==> ۵) آخرین خطای ثبت‌شدهٔ فراخوان در لاگ سرویس rosepsy-api'
if (Test-Path $LogsApi) {
    $logs = Get-ChildItem -Path $LogsApi -Filter '*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if ($logs) {
        INF ("فایل‌های لاگ: " + (($logs | Select-Object -First 4 | ForEach-Object { $_.Name + ' (' + $_.LastWriteTime.ToString('MM-dd HH:mm') + ')' }) -join ', '))
        $hit = $null
        foreach ($f in $logs) {
            $found = Select-String -Path $f.FullName -Pattern 'خطای غیرمنتظره در ذخیرهٔ فرم' -SimpleMatch -ErrorAction SilentlyContinue | Select-Object -Last 1
            if ($found) { $hit = $found; break }
        }
        if ($hit) {
            FAIL ("آخرین خطای غیرمنتظرهٔ ذخیره: " + $hit.Path + " خط " + $hit.LineNumber + " (" + $hit.Line.Substring(0, [Math]::Min(120, $hit.Line.Length)) + ")")
            Write-Host '  ---- ۳۵ خط بعد از خطای آخر (ردیابی کامل exception) ----' -ForegroundColor Yellow
            Get-Content -Path $hit.Path -TotalCount ($hit.LineNumber + 35) -ErrorAction SilentlyContinue |
                Select-Object -Skip ($hit.LineNumber - 1) |
                ForEach-Object { Write-Host "  $_" }
            Write-Host '  ---- پایان ردیابی ----' -ForegroundColor Yellow
        } else {
            OK 'هیچ «خطای غیرمنتظرهٔ ذخیره» در لاگ‌ها نیست (یا لاگ چرخیده و پاک شده)'
        }
        INF 'آخرین ۱۰ خط farakhan در لاگ:'
        foreach ($f in $logs) {
            $lines = Select-String -Path $f.FullName -Pattern 'farakhan' -SimpleMatch -ErrorAction SilentlyContinue | Select-Object -Last 10
            if ($lines) { $lines | ForEach-Object { Write-Host "  $($_.Line)" }; break }
        }
    } else { INF "فایل .log داخل $LogsApi پیدا نشد" }
} else { FAIL "پوشهٔ لاگ یافت نشد: $LogsApi" }

# ---------------------------------------------------------------- ۶) آزمون درون‌فرایندی با venv خود پروژه
Write-Host ''
Write-Host '==> ۶) آزمون مسیر ذخیره با همان venv پروژه (بخوانید: نتیجهٔ خود اجزای سامانه)'
if (Test-Path $VenvPy) {
    $py = @'
# -*- coding: utf-8 -*-
"""فاز ۹۵ — خودآزمون مسیر ذخیرهٔ فراخوان: فایل‌سیستم، بانک، Redis، ClamAV."""
import os, sys, uuid
sys.path.insert(0, r"C:\rosepsy\app\backend")
os.chdir(r"C:\rosepsy\app\backend")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

def ok(m): print("[OK]   " + m)
def fail(m): print("[FAIL] " + m)
def info(m): print("[i]    " + m)

from app.core.config import get_settings
s = get_settings()
info("STORAGE_BACKEND=" + str(getattr(s, "storage_backend", "?")))
info("UPLOAD_DIR=" + str(s.upload_dir))

# ۱ — فایل‌سیستم
try:
    from app.services import file_storage as fs
    key = "diag/%s" % (uuid.uuid4().hex,)
    fs.save_bytes_at_key(s.upload_dir, key, b"rosepsy-farakhan-diag")
    got = open(fs.storage_path(s.upload_dir, key), "rb").read()
    if got == b"rosepsy-farakhan-diag":
        ok("ذخیرهٔ فایل محلی در UPLOAD_DIR موفق بود")
    else:
        fail("محتوای ذخیره‌شده بازخوانی‌نشده")
    fs.remove_file(s.upload_dir, key)
except Exception as e:
    fail("ذخیرهٔ فایل محلی: %s: %s" % (type(e).__name__, e))

# ۲ — بانک (INSERT + ROLLBACK — چیزی باقی نمی‌ماند)
try:
    from app.db.session import SessionLocal
    from sqlalchemy import select, func
    from app.models.farakhan import FarakhanSubmission
    db = SessionLocal()
    n = db.scalar(select(func.count(FarakhanSubmission.id))) or 0
    info("شمار ردیف‌های فعلی farakhan_submissions: %s" % n)
    row = FarakhanSubmission(
        tracking_code="FRK-DIAG-%s" % uuid.uuid4().hex[:8].upper(),
        first_name="diag", last_name="diag", national_code="0000000000",
        gender="female", birth_date_jalali="1370/01/01",
        education_degree="bachelor", education_field="diag",
        license_status="none", center_ownership="owned",
        province_name="diag", county_name="diag", phone="02100000000",
        individual_rooms=0, group_rooms=0, child_rooms=0, counselors_count=0,
        has_waiting_space=False, accepts_company_pattern=False,
        has_accessibility=False, terms_accepted_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        status="new",
    )
    db.add(row); db.flush()
    ok("INSERT آزمایشی در farakhan_submissions موفق بود (rollback می‌شود)")
    db.rollback()
    db.close()
except Exception as e:
    fail("INSERT آزمایشی بانک: %s: %s" % (type(e).__name__, str(e)[:300]))

# ۳ — Redis
try:
    from app.core.redis_client import get_redis
    r = get_redis()
    if r is None:
        info("Redis پیکربندی نشده (KV به حافظهٔ فرایند می‌رود)")
    else:
        r.ping(); ok("Redis پاسخ داد")
except Exception as e:
    fail("Redis: %s: %s" % (type(e).__name__, str(e)[:200]))

# ۴ — ClamAV clamd (قطع بودن عیب نیست — بستر جایگزین قواعد پایه فعال می‌شود)
try:
    import socket
    st = get_settings()
    if not getattr(st, "clamav_enabled", False) or not getattr(st, "clamav_host", ""):
        info("ClamAV غیرفعال است (clamav_enabled=False)")
    else:
        with socket.create_connection((st.clamav_host, st.clamav_port), timeout=3):
            ok("ClamAV clamd روی %s:%s پاسخ داد" % (st.clamav_host, st.clamav_port))
except Exception as e:
    info("ClamAV clamd در دسترس نیست (%s) — اسکن به قواعد پایه برمی‌گردد؛ ثبت را نمی‌بندد" % type(e).__name__)
'@
    $pyFile = Join-Path $env:TEMP 'farakhan-diag.py'
    [System.IO.File]::WriteAllText($pyFile, $py, (New-Object System.Text.UTF8Encoding($false)))
    & $VenvPy $pyFile
    Remove-Item $pyFile -Force -ErrorAction SilentlyContinue
} else { FAIL "python venv یافت نشد: $VenvPy" }

# ---------------------------------------------------------------- جمع‌بندی
Write-Host ''
Write-Host '=============================================================' -ForegroundColor Yellow
Write-Host ' جمع‌بندی عیب‌یابی' -ForegroundColor Yellow
Write-Host '=============================================================' -ForegroundColor Yellow
Write-Host ' این خروجی را کامل برای تیم پشتیبانی بفرستید.'
Write-Host ' درخواست‌های [FAIL] همان ریشهٔ «ثبت‌نشدن فراخوان» هستند.'
Write-Host ''
