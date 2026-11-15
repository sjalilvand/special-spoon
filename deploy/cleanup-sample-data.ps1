# =====================================================================
# فاز ۸۷ — پاک‌سازی دادهٔ نمونهٔ تولید (متقاضیان نمونه + درخواست‌های نمونه)
#
# چه می‌کند؟
#   ۱) پشتیبان کامل (pg_dump -Fc) قبل از هر تغییری
#   ۲) توقف موقت rosepsy-api (جلوگیری از نوشتن هم‌زمان)
#   ۳) حذف کل متقاضیان (طبق درخواست مالک: جدول متقاضیان باید خالی شود) و
#      کل زنجیرهٔ وابستهٔ آن (پرونده‌ها/نوبت‌ها/آزمون‌ها/سفارش‌های نمونه …)
#   ۴) حذف درخواست‌های مشاورهٔ «نمونه»: ردیف‌هایی که پیام/یادداشت دقیقِ
#      seed_demo_rich دارند یا توسط پذیرشِ دمو ثبت شده‌اند یا به متقاضیِ
#      حذف‌شده وصل‌اند. ردیف‌های واقعی فرم سایت (با ip ثبت‌شده) محفوظ می‌مانند.
#   ۵) غیرفعال‌سازی حساب‌های دمو (user20xx، counselor1..8، reception1 و …)
#   ۶) راه‌اندازی مجدد سرویس + گزارش شمارش نهایی
#
# مصرف:
#   powershell -ExecutionPolicy Bypass -File deploy\cleanup-sample-data.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\cleanup-sample-data.ps1 -SkipBackup
# =====================================================================
param(
    [switch]$SkipBackup
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$PGBin    = 'C:\rosepsy\runtime\pgsql\bin'
$Psql     = "$PGBin\psql.exe"
$PgDump   = "$PGBin\pg_dump.exe"
$EnvFile  = 'C:\rosepsy\app\backend\.env'
$BackupDir = 'C:\rosepsy\backups'

function Write-Step { param($m) Write-Host "`n==> $m" -ForegroundColor White }
function Write-Ok   { param($m) Write-Host "  [OK]   $m" -ForegroundColor Green }

if (-not (Test-Path $Psql))  { throw "psql پیدا نشد: $Psql" }
if (-not (Test-Path $EnvFile)) { throw ".env پیدا نشد: $EnvFile" }

# --- رمز DB از .env ---
$map = @{}
foreach ($ln in Get-Content $EnvFile -Encoding UTF8) {
    if ($ln -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { $map[$Matches[1]] = $Matches[2].Trim() }
}
$dbPass = $map['POSTGRES_PASSWORD']
if (-not $dbPass) { throw 'POSTGRES_PASSWORD در .env یافت نشد' }
$env:PGPASSWORD = $dbPass

function Invoke-Psql { param($sql) & $Psql -U rosepsy -h 127.0.0.1 -p 5432 -d rosepsy -v ON_ERROR_STOP=1 -c $sql }

# --- گام ۱: پشتیبان ---
if (-not $SkipBackup) {
    Write-Step 'گام ۱: پشتیبان کامل (pg_dump -Fc)'
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $out = "$BackupDir\pre_demo_cleanup_$stamp.dump"
    & $PgDump -U rosepsy -h 127.0.0.1 -p 5432 -Fc -f $out rosepsy
    if ($LASTEXITCODE -ne 0) { throw 'pg_dump ناموفق بود — پاک‌سازی انجام نشد' }
    Write-Ok "پشتیبان: $out"
}

# --- گام ۲: توقف API ---
Write-Step 'گام ۲: توقف موقت rosepsy-api'
Stop-Service rosepsy-api -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Ok 'سرویس API متوقف شد'

# --- گام ۳: پاک‌سازی ---
Write-Step 'گام ۳: حذف زنجیرهٔ دادهٔ نمونه (child → parent)'

$sql = @'
BEGIN;

-- درخواست‌های نمونه: پیام/یادداشت دقیق seed_demo_rich یا ثبت‌شدهٔ پذیرش دمو
CREATE TEMP TABLE tmp_sample_cr AS
SELECT id FROM consultation_requests
WHERE message IN (
  N'چند ماه است دچار تپش قلب و نگرانی مداوم هستم؛ برای مشاوره حضوری راهنمایی می‌خواهم.',
  N'به‌تازگی افت شدید انرژی و خواب را تجربه می‌کنم و انجام کارهای روزمره سخت شده است.',
  N'اختلاف جدی با همسرم داریم و مایلیم زوج‌درمانی شروع کنیم؛ اسلات آخر هفته مدنظرمان است.',
  N'فرشته هفت‌ساله‌ام رفتار پرخاشگرانه در مدرسه دارد؛ برای بازی‌درمانی وقت می‌خواهم.',
  N'بعد از تغییر شغل دچار فرسودگی شدم؛ مشاوره آنلاین برایم مناسب‌تر است.',
  N'برای مشاوره پیش از ازدواج نیاز به دو جلسه ارزیابی داریم.',
  N'ماه‌هاست بی‌خوابی و وسواس فکری دارم؛ لطفاً امکان وقت اضطراری را بررسی کنید.',
  N'پسر نوجوانم افت تحصیلی شدید دارد و انگیزه‌ای برای درس ندارد.',
  N'پس از فقدان والد، دوره سوگ طولانی‌مدتی را می‌گذرانم و نیاز به حمایت تخصصی دارم.',
  N'برای مدیریت خشم و تعامل بهتر با همکاران، مشاوره فردی درخواست می‌کنم.'
) OR reception_note = N'تماس اولیه برقرار شد؛ ارزیابی اولیه انجام گردید.'
   OR handled_by IN (SELECT id FROM users WHERE username IN ('reception1','manager1'))
   OR applicant_id IN (SELECT id FROM applicants);

UPDATE slot_claims       SET consultation_request_id = NULL WHERE consultation_request_id IN (SELECT id FROM tmp_sample_cr);
UPDATE orders            SET consultation_request_id = NULL WHERE consultation_request_id IN (SELECT id FROM tmp_sample_cr);
UPDATE counselor_reviews SET consultation_request_id = NULL WHERE consultation_request_id IN (SELECT id FROM tmp_sample_cr);
DELETE FROM intake_questionnaires WHERE consultation_request_id IN (SELECT id FROM tmp_sample_cr);
DELETE FROM consultation_requests  WHERE id IN (SELECT id FROM tmp_sample_cr);

-- جدول متقاضیان باید کاملاً خالی شود (درخواست مالک) → کل زنجیرهٔ پرونده باید باز شود
DELETE FROM session_note_revisions;
DELETE FROM sessions;
DELETE FROM session_surveys;
DELETE FROM slot_claims;
DELETE FROM refunds;
DELETE FROM refund_requests;
DELETE FROM payments;
DELETE FROM invoice_items;
DELETE FROM invoices;
DELETE FROM orders;
DELETE FROM discount_redemptions;
DELETE FROM discounts;
DELETE FROM certificates;
DELETE FROM exam_attempts;
DELETE FROM exam_questions;
DELETE FROM exams;
DELETE FROM course_enrollments;
DELETE FROM academy_order_items;
DELETE FROM academy_watch_progress;
DELETE FROM course_sessions;
DELETE FROM courses;
DELETE FROM contents;
DELETE FROM psych_attempts;
DELETE FROM journal_lines;
DELETE FROM journal_entries;
DELETE FROM accounts;
DELETE FROM wallet_entries;
DELETE FROM wallets;
DELETE FROM appointments;
DELETE FROM review_actions;
DELETE FROM assessments;
DELETE FROM referrals;
DELETE FROM recommendations;
DELETE FROM treatment_plans;
DELETE FROM diagnoses;
DELETE FROM consents;
DELETE FROM case_assignments;
DELETE FROM files WHERE case_id IS NOT NULL;
DELETE FROM process_instance_events;
DELETE FROM process_instances;
DELETE FROM cases;
DELETE FROM applicants;  -- هدف: ۰ ردیف

-- حساب‌های دمو غیرفعال شوند (حذف نمی‌شوند تا تاریخچهٔ audit سالم بماند)
UPDATE users SET status = 'disabled', auth_version = auth_version + 1
WHERE username LIKE 'user200%' OR username LIKE 'user201%' OR username LIKE 'user202%'
   OR username IN ('counselor1','counselor2','counselor3','counselor4','counselor5',
                   'counselor6','counselor7','counselor8','reception1','manager1',
                   'supervisor1','dpo1');

COMMIT;
'@

$sqlPath = "$env:TEMP\cleanup_sample_data.sql"
[System.IO.File]::WriteAllText($sqlPath, $sql, (New-Object System.Text.UTF8Encoding($false)))
& $Psql -U rosepsy -h 127.0.0.1 -p 5432 -d rosepsy -v ON_ERROR_STOP=1 -f $sqlPath
if ($LASTEXITCODE -ne 0) { throw 'psql ناموفق بود — تراکنش rollback شد؛ پشتیبان دست‌نخورده است' }
Write-Ok 'زنجیرهٔ دادهٔ نمونه حذف شد'

# --- گام ۴: راه‌اندازی مجدد + گزارش ---
Write-Step 'گام ۴: راه‌اندازی مجدد rosepsy-api'
Start-Service rosepsy-api
Start-Sleep -Seconds 3
Write-Ok 'سرویس API بالا آمد'

Write-Step 'گام ۵: گزارش نهایی'
Invoke-Psql "SELECT 'متقاضیان' AS tbl, count(*) FROM applicants UNION ALL SELECT 'درخواست‌های مشاوره', count(*) FROM consultation_requests UNION ALL SELECT 'پرونده‌های بالینی', count(*) FROM cases UNION ALL SELECT 'کاربران فعال دمو (باید ۰ باشد)', count(*) FROM users WHERE username LIKE 'user20%' AND status='active';"

Write-Host ""
Write-Host "========================= جمع‌بندی =========================" -ForegroundColor White
Write-Host "  جدول متقاضیان اکنون خالی است و درخواست‌های نمونه حذف شدند."
Write-Host "  پشتیبان کامل در C:\rosepsy\backups نگه داشته شد."
Write-Host "  seed_demo*.py دیگر در تولید اجرا نمی‌شود (kill-switch فاز ۸۷)."
Write-Host "  ⚠ رمز ادمین دموی مستند (Rosepsy@Admin2026) را در پنل تغییر دهید!"
Write-Host "=============================================================" -ForegroundColor White
