# =====================================================================
#  rosepsy-mobile-8080.ps1  —  نسخهٔ موبایل روی پورت 8080
#  چون پورت 80/443 در فایروال شرکت هاستینگ بسته است، تمام لینک‌های
#  بیرونی و تجربهٔ موبایل باید روی 8080 کار کند.
#
#  کاری که می‌کند:
#    1) همهٔ URLهای بیرونی در فایل‌های .env را به پورت 8080 نرمال می‌کند
#       (OTP، بازیابی رمز، callback پرداخت، BASE_URL ...) — با بکاپ
#    2) ساخت manifest.webmanifest + آیکون 192/512 + متاتگ‌های موبایل
#       و تزریق به صفحهٔ اصلی site (هم در dist سروشده، هم در سورس)
#       → گوشی «افزودن به صفحهٔ اصلی» با آیکون رزپسی می‌دهد
#    3) وارسی باندل‌های ساخته‌شده برای URL هاردکد (گزارش)
#    4) همگام‌سازی APK اندروید (نسخهٔ 8080) از site\public\app به dist سروشده
#    5) انتظار برای بالا آمدن API بعد از ری‌استارت + خودآزمایی کامل مسیرهای موبایل روی 8080
#       (اگر API بالا نیامد، انتهای لاگ سرویس هم چاپ می‌شود)
#
#  مصرف:
#    powershell -ExecutionPolicy Bypass -File C:\rosepsy\app\deploy\rosepsy-mobile-8080.ps1            (اصلاح)
#    powershell -ExecutionPolicy Bypass -File C:\rosepsy\app\deploy\rosepsy-mobile-8080.ps1 -Mode check (فقط گزارش)
#    powershell -ExecutionPolicy Bypass -File C:\rosepsy\app\deploy\rosepsy-mobile-8080.ps1 -Mode revert (بعد از باز شدن پورت 80)
#    ... -UrlHost domain   (اگر می‌خواهید آدرس‌های بیرونی دوباره دامنهٔ sslip.io شوند؛
#                           پیش‌فرض «ip» است چون DNS دامنهٔ sslip.io از بعضی شبکه‌های
#                           ایران کند است و IP خام سریع‌ترین راه است)
# =====================================================================
param(
    [ValidateSet('check','fix','revert')]
    [string]$Mode = 'fix',
    [int]$ExternalPort = 8080,  # در Mode=revert نادیده گرفته می‌شود (هدف = بدون پورت)
    [ValidateSet('ip','domain')]
    [string]$UrlHost = 'ip'     # ip: میزبان بیرونی = IP خام (سریع) — domain: دامنهٔ sslip.io
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$AppRoot   = 'C:\rosepsy\app'
$Stamp     = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupDir = "C:\rosepsy\backups\mobile8080-$Stamp"
$DomainRx  = '^(?:130\.185\.73\.157|.*\.sslip\.io)$'

function Write-Ok    { param($m) Write-Host "  [OK]     $m" -ForegroundColor Green }
function Write-Warn2 { param($m) Write-Host "  [هشدار]  $m" -ForegroundColor Yellow }
function Write-Info  { param($m) Write-Host "  [i]      $m" -ForegroundColor Cyan }

# --- سلامت API ---------------------------------------------------------
# uvicorn بعد از ری‌استارت سرویس چند ثانیه‌ای طول می‌کشد آماده شود (init دیتابیس و …).
# بدون این انتظار، خودآزماییِ بلافاصله بعد از ری‌استارت روی /api/v1/health خطای 502 می‌بیند
# (Caddy به upstream که هنوز گوش نمی‌دهد وصل نمی‌شود) — عارضهٔ میدانی اجرای 2026-11-04.
function Test-ApiUp {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/health' -UseBasicParsing -TimeoutSec 4
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}
function Wait-ApiUp {
    param([int]$TimeoutSec = 90)
    if (Test-ApiUp) { return $true }
    Write-Host "  [i]      API در حال بالا آمدن است" -ForegroundColor Cyan -NoNewline
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        Write-Host "." -ForegroundColor Cyan -NoNewline
        if (Test-ApiUp) { Write-Host ""; return $true }
    }
    Write-Host ""
    return $false
}
function Show-ApiLogTail {
    # اگر API بالا نیامد، انتهای جدیدترین لاگ سرویس را نشان بده (WinSW: C:\rosepsy\logs\rosepsy-api)
    try {
        $logDir = 'C:\rosepsy\logs\rosepsy-api'
        if (Test-Path $logDir) {
            $logs = @(Get-ChildItem $logDir -Filter '*.log' -File -ErrorAction SilentlyContinue)
            if ($logs.Count -gt 0) {
                $newest = $logs |
                    Sort-Object LastWriteTime -Descending |
                    Sort-Object @{Expression={ if ($_.Name -match '\.err\.') { 0 } elseif ($_.Name -match '\.out\.') { 1 } else { 2 } }} |
                    Select-Object -First 1
                Write-Warn2 ("انتهای لاگ {0}:" -f $newest.Name)
                Get-Content $newest.FullName -Tail 12 -ErrorAction SilentlyContinue | ForEach-Object {
                    Write-Host ("             {0}" -f $_) -ForegroundColor DarkGray
                }
            }
        }
    } catch { }
}

$TargetPort = 80
if ($Mode -ne 'revert') { $TargetPort = $ExternalPort }

Write-Host ""
Write-Host "==> نسخهٔ موبایل Rosepsy روی پورت $TargetPort (Mode=$Mode، میزبان=$UrlHost)" -ForegroundColor White
Write-Host ""

# ---------------------------------------------------------------
# گام ۱: یافتن Caddyfile و ریشهٔ site که Caddy روی 8080 سرو می‌کند
# ---------------------------------------------------------------
$Caddyfile = $null
$candidates = @(
    "$AppRoot\deploy\Caddyfile",
    "$AppRoot\deploy\caddy\Caddyfile",
    "$AppRoot\deploy\windows\Caddyfile",
    'C:\rosepsy\Caddyfile',
    'C:\caddy\Caddyfile'
)
foreach ($c in $candidates) {
    if (Test-Path $c) { $Caddyfile = $c; break }
}
if (-not $Caddyfile) {
    try {
        $hit = Get-ChildItem 'C:\rosepsy' -Filter 'Caddyfile' -Recurse -Depth 4 -ErrorAction SilentlyContinue |
               Select-Object -First 1
        if ($hit) { $Caddyfile = $hit.FullName }
    } catch { }
}
if ($Caddyfile) { Write-Ok "Caddyfile: $Caddyfile" }
else { Write-Warn2 "Caddyfile پیدا نشد — بخش PWA ممکن است root را نتواند تشخیص دهد" }

# استخراج بلوک سایت :8080 و یافتن root.
# نکتهٔ مهم: قالب سرور (rosepsy-server-native.ps1) بدنهٔ تنظیمات را در snippet
# مشترک «(rosepsy_site)» می‌گذارد و بلوک :8080 فقط «import» می‌کند؛ پس اگر بلوک
# import داشت، rootها را از خود snippet هم می‌خوانیم. اولویت: مسیر site\dist
# (نه frontend/panel) که index.html واقعی دارد؛ وگرنه مسیر پیش‌فرض شناخته‌شده.
$SiteRoot = $null
if ($Caddyfile) {
    try {
        $lines = Get-Content $Caddyfile
        $start = -1
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '(?<![\w.]):8080\s*\{') { $start = $i; break }
        }
        $blocks = @()
        if ($start -ge 0) {
            $depth = 0
            $end   = $start
            for ($i = $start; $i -lt $lines.Count; $i++) {
                $depth += ([regex]::Matches($lines[$i], '\{')).Count
                $depth -= ([regex]::Matches($lines[$i], '\}')).Count
                if ($depth -le 0 -and $i -gt $start) { $end = $i; break }
            }
            $blocks += ,($lines[$start..$end] -join "`n")
            # اگر بلوک import داشت → snippet مشترک را هم بخوان
            $imports = [regex]::Matches($blocks[0], '(?m)^\s*import\s+([\w-]+)') |
                       ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
            foreach ($sn in $imports) {
                $sStart = -1
                for ($i = 0; $i -lt $lines.Count; $i++) {
                    if ($lines[$i] -match ('^\s*\(' + [regex]::Escape($sn) + '\)\s*\{')) { $sStart = $i; break }
                }
                if ($sStart -ge 0) {
                    $d2 = 0; $sEnd = $sStart
                    for ($i = $sStart; $i -lt $lines.Count; $i++) {
                        $d2 += ([regex]::Matches($lines[$i], '\{')).Count
                        $d2 -= ([regex]::Matches($lines[$i], '\}')).Count
                        if ($d2 -le 0 -and $i -gt $sStart) { $sEnd = $i; break }
                    }
                    $blocks += ,($lines[$sStart..$sEnd] -join "`n")
                    Write-Info ("بلوک :8080 از snippet «{0}» استفاده می‌کند — rootها از آن خوانده شد" -f $sn)
                }
            }
        }
        $rootCands = @()
        foreach ($b in $blocks) {
            $r2 = [regex]::Matches($b, '(?m)^\s*root\s+\*?\s*"?([^\s"{]+)"?') |
                  ForEach-Object { $_.Groups[1].Value.Trim('"') }
            $rootCands += $r2
        }
        $rootCands = @($rootCands | Select-Object -Unique)
        foreach ($r in $rootCands) {
            if (($r -replace '/', '\') -match '(?i)site\\dist' -and (Test-Path (Join-Path $r 'index.html'))) { $SiteRoot = $r; break }
        }
        if (-not $SiteRoot) {
            foreach ($r in $rootCands) {
                if ($r -notmatch '(?i)frontend' -and (Test-Path (Join-Path $r 'index.html'))) { $SiteRoot = $r; break }
            }
        }
    } catch { Write-Warn2 "خواندن بلوک :8080 ناموفق: $($_.Exception.Message)" }
}
if (-not $SiteRoot) {
    # fallback قطعی بر اساس چیدمان شناخته‌شدهٔ rosepsy-server-native
    $defRoot = Join-Path $AppRoot 'site\dist'
    if (Test-Path (Join-Path $defRoot 'index.html')) {
        $SiteRoot = $defRoot
        Write-Info ("ریشهٔ site از مسیر پیش‌فرض شناخته‌شده استفاده شد: {0}" -f $defRoot)
    }
}
if ($SiteRoot) { Write-Ok "ریشهٔ site روی 8080: $SiteRoot" }
else { Write-Warn2 "ریشهٔ site شناسایی نشد — PWA/APK فقط در سورس اعمال می‌شود" }

# ---------------------------------------------------------------
# گام ۲: نرمال‌سازی URLهای بیرونی در .env به پورت هدف
# ---------------------------------------------------------------
$UrlRx      = [regex]'https?://[^\s"''<>]+'
$changedEnvs = @()

Write-Host ""
Write-Host "==> گام ۲: URLهای بیرونی در .env (پورت هدف: $TargetPort | میزبان: $UrlHost)" -ForegroundColor White

$envFiles = @()
try {
    $hits = @(Get-ChildItem $AppRoot -Filter '.env*' -Recurse -Depth 2 -File -Force -ErrorAction SilentlyContinue |
             Where-Object { $_.FullName -notmatch 'node_modules|\\dist\\|runtime' })
    $envFiles = @() + $hits
    $rootEnv = 'C:\rosepsy\.env'
    if (Test-Path $rootEnv) { $envFiles = @($rootEnv) + $envFiles }
} catch { }

if (-not $envFiles -or $envFiles.Count -eq 0) { Write-Warn2 "هیچ فایل .env یافت نشد" }

foreach ($f in $envFiles) {
    $text = [IO.File]::ReadAllText($f.FullName)
    $script:found = $false
    $newText = $UrlRx.Replace($text, {
        param($m)
        $raw = $m.Value
        $u = $null
        if (-not [System.Uri]::TryCreate($raw, [System.UriKind]::Absolute, [ref]$u)) { return $raw }
        $host_ = $u.Host
        if ($host_ -notmatch $DomainRx) { return $raw }
        if ($host_ -match '^(localhost|127\.0\.0\.1)$') { return $raw }

        # میزبان هدف: ip = IP خام (سریع، بدون DNS) — domain = دامنهٔ sslip.io
        $hostOut = $host_
        if ($Mode -ne 'revert') {
            if ($UrlHost -eq 'ip') {
                $hostOut = $host_ -replace '(?i)\.sslip\.io$', ''
            } elseif ($host_ -eq '130.185.73.157') {
                $hostOut = $host_ + '.sslip.io'
            }
            if ($u.Port -eq 80 -or $u.Port -eq 443) { $portOut = $TargetPort } else { $portOut = $u.Port }
        } else {
            $portOut = 80   # revert: بدون پورت (پورت 80)
        }

        $built = $u.Scheme + '://' + $hostOut
        if ($portOut -ne 80) { $built += ':' + $portOut }
        $built += $u.PathAndQuery
        if ($u.Fragment) { $built += $u.Fragment }
        if ($built -eq $raw) { return $raw }
        $script:found = $true
        return $built
    })

    if ($script:found) {
        Write-Ok ("{0}:" -f $f.FullName)
        $oldLines = $text -split "`r?`n"
        $newLines = $newText -split "`r?`n"
        for ($i = 0; $i -lt $oldLines.Count; $i++) {
            if ($i -lt $newLines.Count -and $oldLines[$i] -ne $newLines[$i]) {
                Write-Info ("    {0}" -f $newLines[$i].Trim())
            }
        }
        if ($Mode -ne 'check') {
            if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }
            Copy-Item $f.FullName (Join-Path $BackupDir ($f.Name + '.' + $Stamp + '.bak')) -Force
            [IO.File]::WriteAllText($f.FullName, $newText, (New-Object System.Text.UTF8Encoding($false)))
            Write-Ok ("    ذخیره شد (بکاپ: {0})" -f $BackupDir)
        }
        $changedEnvs += $f.FullName
    }
}
if (-not $changedEnvs) { Write-Ok "URL بیرونیِ نیاز به تغییر پیدا نشد (همه درست‌اند)" }

# ری‌استارت API اگر .env بک‌اند تغییر کرد
if ($Mode -eq 'fix' -and ($changedEnvs | Where-Object { $_ -match '\\backend\\|^C:\\rosepsy\\\.env' })) {
    try {
        Restart-Service rosepsy-api -Force -ErrorAction Stop
        Write-Ok "سرویس rosepsy-api ری‌استارت شد (اعمال .env جدید)"
        # سرویس در SCM «Running» گزارش می‌شود ولی uvicorn هنوز در حال init است — صبر تا آماده شدن
        if (-not (Wait-ApiUp -TimeoutSec 90)) {
            Write-Warn2 "API بعد از ری‌استارت بالا نیامد — جزئیات در لاگ زیر"
            Show-ApiLogTail
        }
    } catch { Write-Warn2 "ری‌استارت rosepsy-api ناموفق: $($_.Exception.Message) — دستی ری‌استارت کنید" }
}

# اگر متغیر VITE_* عوض شد → build لازم است
if ($changedEnvs | Where-Object { $_ -match 'site|frontend' }) {
    Write-Warn2 "متغیرهای VITE تغییر کردند — برای اعمال، یک‌بار deploy را دوباره اجرا کنید (-Mode upgrade)"
}

# ---------------------------------------------------------------
# گام ۳: وارسی باندل‌های ساخته‌شده (گزارش URL هاردکد)
# ---------------------------------------------------------------
Write-Host ""
Write-Host "==> گام ۳: وارسی باندل‌های dist (URL هاردکد)" -ForegroundColor White
if ($SiteRoot -and (Test-Path $SiteRoot)) {
    try {
        $jsFiles = Get-ChildItem $SiteRoot -Filter '*.js' -Recurse -ErrorAction SilentlyContinue
        $hits = @()
        foreach ($j in $jsFiles) {
            $m2 = Select-String -Path $j.FullName -Pattern 'https?://(130\.185\.73\.157|[\w.-]+\.sslip\.io)' -AllMatches -ErrorAction SilentlyContinue
            if ($m2) { $hits += $m2 }
        }
        if ($hits) {
            foreach ($h in $hits) {
                foreach ($mm in $h.Matches) { Write-Info ("{0}: {1}" -f (Split-Path $h.Path -Leaf), $mm.Value) }
            }
            Write-Info "پورت‌های غیر 80 (مثل :8082) اشکالی ندارند؛ فقط URL بدون پورت مشکل‌ساز است"
        } else {
            Write-Ok "هیچ URL هاردکد بیرونی در باندل‌ها نیست (فراخوانی‌ها نسبی‌اند — روی 8080 سالم)"
        }
    } catch { Write-Warn2 "وارسی باندل ناموفق: $($_.Exception.Message)" }
} else {
    Write-Info "ریشهٔ site مشخص نیست — این گام رد شد"
}

# ---------------------------------------------------------------
# گام ۴: PWA — manifest + آیکون + متاتگ موبایل
# ---------------------------------------------------------------
Write-Host ""
Write-Host "==> گام ۴: نسخهٔ موبایل (PWA) — manifest، آیکون، متاتگ" -ForegroundColor White

$manifestJson = @'
{
  "id": "/",
  "name": "رزپسی | کلینیک مشاوره و روان‌درمانی",
  "short_name": "رزپسی",
  "description": "سامانهٔ نوبت‌دهی و مشاورهٔ رزپسی",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "orientation": "portrait",
  "dir": "rtl",
  "lang": "fa",
  "background_color": "#fbf7f4",
  "theme_color": "#7c2740",
  "icons": [
    { "src": "/app-icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },
    { "src": "/app-icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ]
}
'@

function New-RosepsyIcon {
    param([int]$Size, [string]$Path)
    try {
        Add-Type -AssemblyName System.Drawing
        $bmp = New-Object System.Drawing.Bitmap $Size, $Size
        $g   = [System.Drawing.Graphics]::FromImage($bmp)
        $g.SmoothingMode     = 'AntiAlias'
        $g.TextRenderingHint = 'AntiAliasGridFit'
        $bg = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255,15,23,42))
        $g.FillRectangle($bg, 0, 0, $Size, $Size)
        $accent = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255,45,212,191))
        $dot = [int]($Size * 0.10)
        $g.FillEllipse($accent, [int]($Size*0.42), [int]($Size*0.78), $dot, $dot)
        $font = New-Object System.Drawing.Font ('Tahoma', [float]($Size*0.52), [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
        $fg   = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
        $sf   = New-Object System.Drawing.StringFormat
        $sf.Alignment     = 'Center'
        $sf.LineAlignment = 'Center'
        $rect = New-Object System.Drawing.RectangleF ([float]0, [float]([math]::Round($Size * -0.03, 2)), [float]$Size, [float]$Size)
        $g.DrawString([string][char]0x0631, $font, $fg, $rect, $sf)   # «ر»
        $g.Dispose()
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()
        return $true
    } catch {
        Write-Warn2 "ساخت آیکون $Path ناموفق: $($_.Exception.Message)"
        return $false
    }
}

$MetaTags = @(
    '<link rel="manifest" href="/manifest.webmanifest"/>',
    '<meta name="theme-color" content="#0f172a"/>',
    '<link rel="apple-touch-icon" href="/app-icon-192.png"/>',
    '<meta name="apple-mobile-web-app-capable" content="yes"/>',
    '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"/>',
    '<meta name="apple-mobile-web-app-title" content="رزپسی"/>',
    '<meta name="mobile-web-app-capable" content="yes"/>'
) -join "`n  "

function Add-PwaFiles {
    param([string]$Dir, [string]$Label)
    if (-not $Dir -or -not (Test-Path $Dir)) { return $false }
    try {
        $mPath = Join-Path $Dir 'manifest.webmanifest'
        $i192  = Join-Path $Dir 'app-icon-192.png'
        $i512  = Join-Path $Dir 'app-icon-512.png'
        # فاز ۷۹: طرح رز از سورس (site\public) — اگر موجود بود کپی می‌شود؛ رسم فقط fallback است
        $srcPub = Join-Path $AppRoot 'site\public'
        $srcM   = Join-Path $srcPub 'manifest.webmanifest'
        $src192 = Join-Path $srcPub 'app-icon-192.png'
        $src512 = Join-Path $srcPub 'app-icon-512.png'
        if ((Test-Path $srcM) -and (Test-Path $src192) -and (Test-Path $src512) -and
            ($Dir.TrimEnd('\').ToLower() -ne $srcPub.TrimEnd('\').ToLower())) {
            Copy-Item $srcM   $mPath -Force
            Copy-Item $src192 $i192  -Force
            Copy-Item $src512 $i512  -Force
            Write-Ok ("{0}: manifest + آیکون 192/512 از سورس کپی شد (طرح رز)" -f $Label)
            return $true
        }
        [IO.File]::WriteAllText($mPath, $manifestJson, (New-Object System.Text.UTF8Encoding($false)))
        $ok1 = New-RosepsyIcon -Size 192 -Path $i192
        $ok2 = New-RosepsyIcon -Size 512 -Path $i512
        Write-Ok ("{0}: manifest + آیکون 192/512 نوشته شد" -f $Label)
        return ($ok1 -or $ok2)
    } catch {
        Write-Warn2 ("نوشتن PWA در {0} ناموفق: {1}" -f $Label, $_.Exception.Message)
        return $false
    }
}

function Add-PwaMetaToIndex {
    param([string]$IndexPath, [string]$Label)
    if (-not (Test-Path $IndexPath)) { return }
    try {
        $html = [IO.File]::ReadAllText($IndexPath)
        if ($html -match 'manifest\.webmanifest') {
            Write-Ok ("{0}: متاتگ PWA از قبل موجود است" -f $Label)
            return
        }
        $idx = $html.ToLower().IndexOf('</head>')
        if ($idx -lt 0) { Write-Warn2 ("{0}: تگ </head> پیدا نشد" -f $Label); return }
        $newHtml = $html.Insert($idx, "  `n  $MetaTags`n")
        if ($Mode -ne 'check') {
            if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }
            Copy-Item $IndexPath (Join-Path $BackupDir ((Split-Path $IndexPath -Leaf) + '.' + $Stamp + '.bak')) -Force
            [IO.File]::WriteAllText($IndexPath, $newHtml, (New-Object System.Text.UTF8Encoding($false)))
            Write-Ok ("{0}: متاتگ‌های موبایل تزریق شد" -f $Label)
        } else {
            Write-Info ("{0}: متاتگ PWA تزریق خواهد شد (Mode=check — تغییری اعمال نشد)" -f $Label)
        }
    } catch {
        Write-Warn2 ("تزریق متاتگ در {0} ناموفق: {1}" -f $Label, $_.Exception.Message)
    }
}

if ($Mode -ne 'check') {
    # ۴-الف) در dist سروشده (اثر فوری)
    if ($SiteRoot) {
        Add-PwaFiles -Dir $SiteRoot -Label 'dist سروشده' | Out-Null
        Add-PwaMetaToIndex -IndexPath (Join-Path $SiteRoot 'index.html') -Label 'dist سروشده'
    }
    # ۴-ب) در سورس (پایدار برای buildهای بعدی؛ اگر git برگرداند، اسکریپت را دوباره اجرا کنید)
    $srcSite = Join-Path $AppRoot 'site'
    if (Test-Path $srcSite) {
        $pub = Join-Path $srcSite 'public'
        if (-not (Test-Path $pub)) { New-Item -ItemType Directory -Path $pub -Force | Out-Null }
        Add-PwaFiles -Dir $pub -Label 'سورس site/public' | Out-Null
        Add-PwaMetaToIndex -IndexPath (Join-Path $srcSite 'index.html') -Label 'سورس site/index.html'
    }
} else {
    Write-Info "Mode=check — هیچ فایلی نوشته نشد"
}

# ---------------------------------------------------------------
# گام ۵: APK اندروید — نسخهٔ 8080 از ریپو به dist سروشده
# (بعد از git pull لازم نیست حتماً rebuild کل سایت شود)
# ---------------------------------------------------------------
Write-Host ""
Write-Host "==> گام ۵: APK اندروید (/app/rosepsy-1.0.0.apk)" -ForegroundColor White
$repoApk = Join-Path $AppRoot 'site\public\app\rosepsy-1.0.0.apk'
if ($Mode -eq 'check') {
    if (Test-Path $repoApk) { Write-Info ("APK در ریپو موجود است: {0}" -f $repoApk) }
    else { Write-Warn2 ("APK در ریپو نیست (git pull کنید): {0}" -f $repoApk) }
}
elseif ($SiteRoot) {
    if (Test-Path $repoApk) {
        try {
            $apkDest = Join-Path $SiteRoot 'app'
            $dstFile = Join-Path $apkDest 'rosepsy-1.0.0.apk'
            $srcHash = (Get-FileHash $repoApk -Algorithm MD5).Hash
            $dstHash = if (Test-Path $dstFile) { (Get-FileHash $dstFile -Algorithm MD5).Hash } else { '' }
            if ($srcHash -ne $dstHash) {
                if (-not (Test-Path $apkDest)) { New-Item -ItemType Directory -Path $apkDest -Force | Out-Null }
                if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }
                if (Test-Path $dstFile) { Copy-Item $dstFile (Join-Path $BackupDir ('rosepsy-1.0.0.apk.' + $Stamp + '.bak')) -Force }
                Copy-Item $repoApk $dstFile -Force
                Write-Ok ("APK نسخهٔ 8080 در مسیر سروشده کپی شد: {0}" -f $dstFile)
                Write-Info "کاربران: اپ قبلی را باز کنید ← همان آدرس همیشگی، نصب روی نصب قبلی (بدون حذف)"
            } else {
                Write-Ok "APK سروشده از قبل به‌روز است"
            }
        } catch { Write-Warn2 ("کپی APK ناموفق: {0}" -f $_.Exception.Message) }
    } else {
        Write-Warn2 ("APK ریپو پیدا نشد — ابتدا git pull کنید: {0}" -f $repoApk)
    }
} else {
    Write-Info "ریشهٔ site مشخص نیست — کپی APK رد شد"
}

# ---------------------------------------------------------------
# گام ۶: خودآزمایی روی 8080
# ---------------------------------------------------------------
Write-Host ""
Write-Host "==> گام ۶: خودآزمایی (http://127.0.0.1:8080)" -ForegroundColor White
# اگر API هنوز بالا نیامده باشد، /api/v1/health از مسیر Caddy خطای 502 می‌گیرد — اول صبر کن
if (-not (Wait-ApiUp -TimeoutSec 90)) {
    Write-Warn2 "API روی 127.0.0.1:8000 پاسخ نمی‌دهد — انتهای لاگ:"
    Show-ApiLogTail
}
$tests = @(
    @{ U = '/';                                   Want = 'site' },
    @{ U = '/panel/';                             Want = 'panel' },
    @{ U = '/api/v1/health';                      Want = 'API' },
    @{ U = '/manifest.webmanifest';               Want = 'manifest' },
    @{ U = '/app-icon-192.png';                   Want = 'icon' },
    @{ U = '/app/rosepsy-1.0.0.apk';              Want = 'apk' },
    @{ U = '/docs/zarinpal-gateway-request.html'; Want = 'docs' }
)
foreach ($t in $tests) {
    try {
        $resp = Invoke-WebRequest -Uri ("http://127.0.0.1:8080" + $t.U) -UseBasicParsing -TimeoutSec 10
        $len  = $resp.RawContentLength
        $ct   = $resp.Headers['Content-Type']
        $flag = "[OK]  "
        if ($t.U -eq '/manifest.webmanifest' -and $ct -and $ct -notmatch 'manifest|json') {
            $flag = "[هشدار]"
            Write-Host "  $flag $($t.U) → $($resp.StatusCode) ($len بایت، $ct) — fallback SPA! تنظیم try_files در Caddyfile را بررسی کنید" -ForegroundColor Yellow
            continue
        }
        Write-Host "  $flag $($t.U) → $($resp.StatusCode) ($len بایت)" -ForegroundColor Green
    } catch {
        Write-Host "  [خطا]  $($t.U) → $($_.Exception.Message)" -ForegroundColor Red
        if ($t.U -eq '/api/v1/health') {
            if (Test-ApiUp) {
                Write-Host "          (API مستقیم روی 8000 سالم است اما از مسیر Caddy پاسخ نمی‌گیرد — یک‌بار اجرا کنید: Restart-Service rosepsy-caddy" -ForegroundColor Yellow
            } else {
                Write-Host "          (سرویس API بالا نیست — وضعیت: Get-Service rosepsy-api | لاگ: C:\rosepsy\logs\rosepsy-api)" -ForegroundColor Yellow
            }
        }
    }
}

# ---------------------------------------------------------------
# جمع‌بندی
# ---------------------------------------------------------------
Write-Host ""
Write-Host "========================= جمع‌بندی نسخهٔ موبایل =========================" -ForegroundColor White
Write-Host "  آدرس اصلی (سریع‌ترین): http://130.185.73.157:8080/   ← بدون DNS؛ این را به کاربران بدهید"
Write-Host "  آدرس جایگزین (دامنه) : http://130.185.73.157.sslip.io:8080/  (DNS دامنه از بعضی شبکه‌ها کند است)"
Write-Host "  پنل روی موبایل       : http://130.185.73.157:8080/panel/"
Write-Host "  اپ اندروید (APK)     : http://130.185.73.157:8080/app/rosepsy-1.0.0.apk"
Write-Host "  SSO (هم‌اکنون باز)    : http://130.185.73.157:8082"
if ($Mode -eq 'revert') {
    Write-Host "  حالت revert         : URLها به حالت بدون پورت برگشتند (پورت 80 باید باز شده باشد)"
    Write-Host "  گام بعدی            : deploy\windows\rosepsy-server-tls.ps1 را برای HTTPS اجرا کنید"
} else {
    Write-Host "  روی گوشی: آدرس IP بالا را در Chrome/Safari باز کنید ← منو ← «افزودن به صفحهٔ اصلی»"
    Write-Host "  (آیکون رزپسی روی صفحهٔ گوشی می‌نشیند و تمام‌صفحه باز می‌شود)"
    Write-Host "  درگاه پرداخت        : با UrlHost=ip آدرس callback هم روی IP می‌رود — یک پرداخت"
    Write-Host "                        آزمایشی بزنید؛ اگر درگاه واقعی خطای دامنه داد، یک‌بار با"
    Write-Host "                        «-UrlHost domain» اجرا کنید تا callback به دامنه برگردد"
}
Write-Host "  یادآوری             : URL بدون پورت (پورت 80) فقط با باز کردن TCP 80/443 در"
Write-Host "                        پنل شرکت هاستینگ درست می‌شود؛ این مشکل داخل سرور نیست."
Write-Host "  نگه‌داری            : بعد از هر «-Mode upgrade» (rebuild فرانت) این اسکریپت را"
Write-Host "                        یک‌بار دیگر اجرا کنید تا PWA دوباره در dist تزریق شود."
Write-Host "  برگرداندن           : -Mode revert   (بعد از باز شدن پورت 80)"
Write-Host "=====================================================================" -ForegroundColor White
Write-Host ""
