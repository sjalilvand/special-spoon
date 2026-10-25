<#
================================================================================
 rosepsy-server-tls.ps1
 گواهی رایگان HTTPS برای رزپسی روی Windows Server (Caddy + Let's Encrypt)
================================================================================
 چون مراج گواهی رایگان (Let's Encrypt و ...) گواهی برای «IP خالی» صادر نمی‌کنند،
 از دامنهٔ جایگزینِ رایگان sslip.io استفاده می‌شود:

     130.185.73.157.sslip.io   ←→   همین حالا به 130.185.73.157 حل می‌شود

 نتیجه:  https://130.185.73.157.sslip.io/panel/   با گواهی معتبر و نوار سبز قفل
 (Caddy خودش گواهی را از Let's Encrypt می‌گیرد و هر ۹۰ روز خودکار تمدید می‌کند)

 پیش‌نیاز:
   - deploy قبلاً انجام شده باشد (docker compose در حال اجرا)
   - پورت‌های 80 و 443 در فایروال و در پنل هاستینگ/کلود سرور باز باشند
   - PowerShell در حالت Run as Administrator

 روش استفاده:

   راه‌اندازی (حالت پیش‌فرض با sslip.io):
       .\rosepsy-server-tls.ps1

   با دامنهٔ واقعی خودتان (بعد از خرید دامنه و تنظیم A-record به 130.185.73.157):
       .\rosepsy-server-tls.ps1 tls -Domain example.com

   اگر سرور به Let's Encrypt دسترسی ندارد یا فیلترینگ مشکل ساخت:
       .\rosepsy-server-tls.ps1 tls -SelfSigned
     (گواهی داخلی؛ مرورگر یک بار هشدار می‌دهد و با «Advanced → Proceed» رد می‌شود)

   وضعیت/لاگ:      .\rosepsy-server-tls.ps1 status
   ری‌استارت Caddy: .\rosepsy-server-tls.ps1 renew
   غیرفعال‌سازی:    .\rosepsy-server-tls.ps1 off

   فعال‌کردن حالت production کوکی‌ها (فقط پس از اطمینان از کارکرد HTTPS):
       .\rosepsy-server-tls.ps1 tls -SetProduction

 پارامترها: -Domain -Email -ServerIp -InstallDir -SelfSigned -SetProduction
 نکته: دسترسی مستقیم http://130.185.73.157:8080 هم همچنان به‌عنوان مسیر پشتیبان
 باز می‌ماند؛ برای امنیت کامل بعداً می‌توانید آن را در فایروال ببندید.
================================================================================
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet('tls', 'status', 'renew', 'off', 'help')]
    [string]$Mode = 'tls',

    [string]$Domain = '130.185.73.157.sslip.io',
    [string]$ServerIp = '',
    [string]$Email = '',
    [string]$InstallDir = 'C:\rosepsy',
    [switch]$SelfSigned,
    [switch]$SetProduction
)

# ---------------------- تنظیمات عمومی نشست ----------------------
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

$RepoPath    = Join-Path $InstallDir 'special-spoon'
$CaddyDir    = Join-Path $InstallDir 'caddy'
$LogFile     = Join-Path $InstallDir 'rosepsy-tls.log'

if (Test-Path "$env:ProgramFiles\Docker\Docker\resources\bin") { $env:Path = "$env:Path;$env:ProgramFiles\Docker\Docker\resources\bin" }

# ---------------------- ابزارهای کمکی ----------------------
function Write-Step { param([string]$Text) Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Text) Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn2{ param([string]$Text) Write-Host "  [!]  $Text" -ForegroundColor Yellow }
function Write-Err2 { param([string]$Text) Write-Host "  [X]  $Text" -ForegroundColor Red }

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ServerIp {
    if ($ServerIp) { return $ServerIp }
    try {
        $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' } |
            Select-Object -First 1
        if ($ip) { return $ip.IPAddress }
    } catch { }
    return '127.0.0.1'
}

function Write-Log {
    param([string]$Text)
    try { Add-Content -Path $LogFile -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Text) -Encoding UTF8 } catch { }
}

function Start-DockerEngine {
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) { $env:Path = "$env:Path;$env:ProgramFiles\Docker\Docker\resources\bin" }
    $dockerExe = "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
    if (-not (Test-Path $dockerExe)) {
        try { $dockerExe = (Get-Command docker -ErrorAction Stop).Source } catch { }
    }
    if (-not $dockerExe -or -not (Test-Path $dockerExe)) {
        throw 'docker.exe پیدا نشد — ابتدا .\rosepsy-server-deploy.ps1 setup را اجرا کنید'
    }
    & $dockerExe info *> $null
    if ($LASTEXITCODE -eq 0) { return $dockerExe }
    Write-Step 'راه‌اندازی Docker Desktop'
    $dd = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dd) { Start-Process -FilePath $dd | Out-Null }
    for ($i = 1; $i -le 60; $i++) {
        Start-Sleep -Seconds 5
        & $dockerExe info *> $null
        if ($LASTEXITCODE -eq 0) { return $dockerExe }
    }
    throw 'موتور Docker آماده نشد — Docker Desktop را دستی باز کنید و دوباره تلاش کنید'
}

function Test-HttpsUrl {
    # بررسی یک آدرس HTTPS با چشم‌پوشی از اعتبارسنجی گواهی (سازگار با PS 5.1 و pwsh 7)
    param([string]$Url, [int]$TimeoutSec = 8)
    try {
        if ($PSVersionTable.PSEdition -eq 'Core') {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -SkipCertificateCheck -TimeoutSec $TimeoutSec
        } else {
            if (-not ('Rosepsy.TrustAllCerts' -as [type])) {
                Add-Type -TypeDefinition @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
namespace Rosepsy {
    public class TrustAllCerts : ICertificatePolicy {
        public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int problem) { return true; }
    }
}
"@ -ErrorAction SilentlyContinue
                [System.Net.ServicePointManager]::CertificatePolicy = New-Object Rosepsy.TrustAllCerts
            }
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        }
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
    } catch { return $false }
}

# ---------------------- ساخت فایل‌های Caddy ----------------------
function New-CaddyFiles {
    # تولید Caddyfile خارج از مخزن + compose.override.yml داخل مخزن (هر دو idempotent)
    if (-not (Test-Path $RepoPath)) { throw "مخزن در $RepoPath پیدا نشد — ابتدا deploy را اجرا کنید" }
    Ensure-Dir $CaddyDir

    if ($SelfSigned) {
        $ip = Get-ServerIp
        Write-Step "ساخت پیکربندی Caddy با گواهی داخلی (self-signed) برای $Domain و $ip"
        $caddyfile = @"
# رزپسی — پراکسی لبهٔ Caddy با گواهی داخلی (self-signed)
# تولیدشده توسط rosepsy-server-tls.ps1 — بازتولید: .\rosepsy-server-tls.ps1 tls -SelfSigned
# مرورگر یک بار هشدار گواهی می‌دهد؛ با Advanced → Proceed ادامه دهید

https://$Domain, https://$ip {
    tls internal
    reverse_proxy web:80
}
"@
    } else {
        $globalBlock = ''
        if ($Email) { $globalBlock = "{`n    email $Email`n}`n`n" }
        Write-Step "ساخت پیکربندی Caddy با گواهی خودکار Let's Encrypt برای $Domain"
        $caddyfile = @"
# رزپسی — پراکسی لبهٔ Caddy با گواهی خودکار Let's Encrypt
# تولیدشده توسط rosepsy-server-tls.ps1 — دامنه: $Domain
# تمدید گواهی هر ۹۰ روز به‌صورت خودکار انجام می‌شود

${globalBlock}$Domain {
    reverse_proxy web:80
}
"@
    }
    [System.IO.File]::WriteAllText((Join-Path $CaddyDir 'Caddyfile'), $caddyfile, (New-Object System.Text.UTF8Encoding($false)))

    $caddyWinPath = ($CaddyDir -replace '\\', '/')
    $override = @"
# رزپسی — سرویس لبهٔ TLS (Caddy) — تولیدشده توسط rosepsy-server-tls.ps1
# این فایل توسط git حذف نمی‌شود (untracked) و docker compose خودکار آن را با compose.yml ترکیب می‌کند
# غیرفعال‌سازی: .\rosepsy-server-tls.ps1 off
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - $caddyWinPath/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - web

volumes:
  caddy_data:
  caddy_config:
"@
    [System.IO.File]::WriteAllText((Join-Path $RepoPath 'compose.override.yml'), $override, (New-Object System.Text.UTF8Encoding($false)))
    Write-Ok "Caddyfile: $(Join-Path $CaddyDir 'Caddyfile')"
    Write-Ok "Override : $(Join-Path $RepoPath 'compose.override.yml')"
}

function Update-EnvAfterTls {
    # PUBLIC_BASE_URL به آدرس HTTPS + در صورت درخواست، ENVIRONMENT=production
    $envFile = Join-Path $RepoPath '.env'
    if (-not (Test-Path $envFile)) { Write-Warn2 '.env یافت نشد — PUBLIC_BASE_URL به‌روز نشد'; return }
    $lines = [System.IO.File]::ReadAllLines($envFile)
    $out = New-Object System.Collections.Generic.List[string]
    $changed = $false
    foreach ($line in $lines) {
        $newLine = $line
        if ($line -match '^PUBLIC_BASE_URL=') { $newLine = "PUBLIC_BASE_URL=https://$Domain"; $changed = $true }
        if ($SetProduction -and $line -match '^ENVIRONMENT=') { $newLine = 'ENVIRONMENT=production'; $changed = $true }
        $out.Add($newLine)
    }
    if ($changed) {
        [System.IO.File]::WriteAllLines($envFile, $out)
        $msg = "PUBLIC_BASE_URL ← https://$Domain" + $(if ($SetProduction) { ' + ENVIRONMENT=production' })
        Write-Ok $msg
        Push-Location $RepoPath
        try { & docker compose up -d api | Out-Null } finally { Pop-Location }
    }
}

function Test-Port80Conflict {
    # اگر سرویس دیگری (مثلاً IIS) پورت 80 را گرفته باشد، ACME شکست می‌خورد
    try {
        $conns = Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -notmatch 'docker|com\.docker') {
                Write-Warn2 "پورت 80 توسط پروسهٔ «$($proc.ProcessName)» (PID $($proc.Id)) اشغال است"
                Write-Warn2 'اگر IIS است:  Stop-Service W3SVC -WarningAction SilentlyContinue;  Set-Service W3SVC -StartupType Disabled'
                return $false
            }
        }
    } catch { }
    return $true
}

function Set-FirewallTls {
    foreach ($p in @(80, 443)) {
        $ruleName = "Rosepsy-TLS-$p"
        $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        if (-not $existing) {
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $p `
                -Action Allow -Profile Any -Description 'Rosepsy: Caddy TLS edge (HTTP + HTTPS)' | Out-Null
        }
    }
    New-NetFirewallRule -DisplayName 'Rosepsy-TLS-443-UDP' -Direction Inbound -Protocol UDP -LocalPort 443 `
        -Action Allow -Profile Any -Description 'Rosepsy: HTTP/3 (QUIC)' -ErrorAction SilentlyContinue | Out-Null
    Write-Ok 'فایروال: پورت‌های 80 و 443 (TCP) و 443 (UDP) باز شد'
    Write-Warn2 'اگر سرور روی کلود/هاستر با پنل است، همین پورت‌ها را در پنل هم باز کنید (Security Group)'
}

function Invoke-Tls {
    Write-Host '==============================================' -ForegroundColor DarkCyan
    Write-Host ' رزپسی — گواهی رایگان HTTPS (Caddy + Let''s Encrypt)' -ForegroundColor DarkCyan
    Write-Host '==============================================' -ForegroundColor DarkCyan

    if (-not (Test-Admin)) { throw 'این مرحله باید با PowerShell در حالت Run as Administrator اجرا شود (برای فایروال)' }
    Start-DockerEngine | Out-Null
    if (-not (Test-Path (Join-Path $RepoPath 'compose.yml'))) { throw "مخزن در $RepoPath پیدا نشد — ابتدا deploy را اجرا کنید" }

    Test-Port80Conflict | Out-Null
    New-CaddyFiles
    Set-FirewallTls

    Write-Step 'اجرای سرویس Caddy (در صورت نیاز، ایمیج دانلود می‌شود)'
    Push-Location $RepoPath
    try {
        & docker compose up -d caddy
        if ($LASTEXITCODE -ne 0) { throw 'راه‌اندازی Caddy ناموفق بود' }
    } finally { Pop-Location }

    if ($SelfSigned) {
        Write-Log "tls self-signed configured for $Domain"
        Update-EnvAfterTls
        Show-TlsSummary
        return
    }

    Write-Step "انتظار برای صدور گواهی Let's Encrypt برای $Domain (تا ۸ دقیقه)"
    Write-Host '    (پورت 80 باید از اینترنت در دسترس باشد؛ در پنل هاستینگ هم باز بودن 80 و 443 را چک کنید)' -ForegroundColor DarkGray
    $ok = $false
    for ($i = 1; $i -le 32; $i++) {
        Start-Sleep -Seconds 15
        if (Test-HttpsUrl "https://$Domain/api/v1/health") { $ok = $true; break }
        if ($i % 4 -eq 0) {
            Write-Host "  ... در حال تلاش (دقیقهٔ $([int]($i / 4)))" -ForegroundColor DarkGray
            if ($i -eq 8) {
                Push-Location $RepoPath
                try { & docker compose logs --tail=8 caddy } finally { Pop-Location }
            }
        }
    }

    if (-not $ok) {
        Write-Host ''
        Write-Err2 "صدور گواهی برای $Domain انجام نشد."
        Write-Warn2 'علت‌های رایج: پورت 80 از اینترنت بسته است (پنل هاستینگ)، محدودیت نرخ sslip.io در Let''s Encrypt، یا فیلترینگ ACME.'
        Write-Log "tls acme FAILED for $Domain"
        $ans = Read-Host 'فعال‌سازی گواهی داخلی self-signed برای ادامهٔ کار؟ (y/n)'
        if ($ans -eq 'y') {
            $script:SelfSigned = $true
            New-CaddyFiles
            Push-Location $RepoPath
            try { & docker compose up -d caddy } finally { Pop-Location }
            Start-Sleep -Seconds 5
            Update-EnvAfterTls
            Show-TlsSummary
            return
        }
        throw 'حالت TLS فعال نشد — بعد از رفع مشکل پورت 80 دوباره اجرا کنید'
    }

    Write-Log "tls OK for $Domain"
    Update-EnvAfterTls
    Show-TlsSummary
}

function Show-TlsSummary {
    $panel = "https://$Domain/panel/"
    Write-Host ''
    Write-Host '=================================================' -ForegroundColor DarkGreen
    Write-Ok 'HTTPS فعال شد'
    Write-Host '=================================================' -ForegroundColor DarkGreen
    Write-Host "  پنل مدیریت : $panel" -ForegroundColor White
    Write-Host "  سایت عمومی : https://$Domain/" -ForegroundColor White
    Write-Host "  سلامت API  : https://$Domain/api/v1/health" -ForegroundColor White
    if ($SelfSigned) {
        Write-Host '  نوع گواهی  : داخلی (self-signed) — مرورگر یک بار هشدار می‌دهد (Advanced → Proceed)' -ForegroundColor Yellow
    } else {
        Write-Host '  نوع گواهی  : Let''s Encrypt — معتبر و خودکار-تمدیدشونده' -ForegroundColor White
    }
    Write-Host '  مسیر پشتیبان: http://SERVER-IP:8080/panel/ (همچنان باز است)' -ForegroundColor DarkGray
    Write-Host ''
    Write-Host '  وضعیت/لاگ: .\rosepsy-server-tls.ps1 status     توقف: .\rosepsy-server-tls.ps1 off' -ForegroundColor DarkGray
    Write-Host ''
}

function Show-TlsStatus {
    if (-not (Test-Path $RepoPath)) { Write-Warn2 "مخزن در $RepoPath پیدا نشد"; return }
    Push-Location $RepoPath
    try {
        Write-Step 'وضعیت سرویس Caddy'
        & docker compose ps caddy
        Write-Step '۱۵ خط آخر لاگ Caddy'
        & docker compose logs --tail=15 caddy
    } finally { Pop-Location }
    Write-Step 'تست HTTPS'
    if (Test-HttpsUrl "https://$Domain/api/v1/health") {
        Write-Ok "https://$Domain پاسخ می‌دهد"
    } else {
        Write-Warn2 "https://$Domain پاسخ نمی‌دهد — اگر تازه اجرا کرده‌اید چند دقیقه صبر کنید"
    }
}

# ---------------------- حالت‌های کمکی ----------------------
function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null }
}

function Invoke-TlsRenew {
    # Caddy خودش تمدید می‌کند؛ این فقط ری‌استارت/اجبار مجدد است
    Start-DockerEngine | Out-Null
    if (-not (Test-Path (Join-Path $RepoPath 'compose.override.yml'))) { throw 'Caddy نصب نشده است — ابتدا «tls» را اجرا کنید' }
    Write-Step 'ری‌استارت Caddy (تمدید مجدد گواهی‌ها)'
    Push-Location $RepoPath
    try { & docker compose restart caddy } finally { Pop-Location }
    Write-Ok 'انجام شد'
}

function Invoke-TlsOff {
    Start-DockerEngine | Out-Null
    if (Test-Path (Join-Path $RepoPath 'compose.override.yml')) {
        Write-Step 'توقف و حذف کانتینر Caddy (فایل‌های پیکربندی حفظ می‌شوند)'
        Push-Location $RepoPath
        try {
            & docker compose stop caddy
            & docker compose rm -f caddy
        } finally { Pop-Location }
        Write-Ok 'TLS لبه خاموش شد؛ برای فعال‌سازی دوباره: .\rosepsy-server-tls.ps1'
    } else {
        Write-Warn2 'Caddy نصب نشده بود — کاری انجام نشد'
    }
}

function Show-TlsHelp {
    Write-Host @'

 رزپسی — گواهی رایگان HTTPS روی سرور ویندوزی
 --------------------------------------------
   .\rosepsy-server-tls.ps1                          راه‌اندازی با 130.185.73.157.sslip.io (Let's Encrypt خودکار)
   .\rosepsy-server-tls.ps1 tls -Domain example.com  با دامنهٔ واقعی (A-record → 130.185.73.157)
   .\rosepsy-server-tls.ps1 tls -SelfSigned          گواهی داخلی (بدون نیاز به پورت 80؛ هشدار مرورگر)
   .\rosepsy-server-tls.ps1 tls -SetProduction       + کوکی‌های امن production
   .\rosepsy-server-tls.ps1 status                   وضعیت و لاگ Caddy
   .\rosepsy-server-tls.ps1 renew                    ری‌استارت Caddy
   .\rosepsy-server-tls.ps1 off                      غیرفعال‌سازی TLS لبه

 نتیجه: https://130.185.73.157.sslip.io/panel/
'@
}

# ---------------------- اجرای اصلی ----------------------
try {
    switch ($Mode) {
        'tls'    { Invoke-Tls }
        'status' { Show-TlsStatus }
        'renew'  { Invoke-TlsRenew }
        'off'    { Invoke-TlsOff }
        default  { Show-TlsHelp }
    }
} catch {
    Write-Host ''
    Write-Err2 "خطا: $($_.Exception.Message)"
    Write-Warn2 "لاگ: $LogFile"
    Write-Warn2 'راهنما: .\rosepsy-server-tls.ps1 help'
    exit 1
}
