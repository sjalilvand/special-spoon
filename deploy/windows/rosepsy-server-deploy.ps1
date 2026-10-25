<#
================================================================================
 rosepsy-server-deploy.ps1
 استقرار سامانهٔ رزپسی (Rosepsy / special-spoon) روی Windows Server 2025 از طریق گیت
================================================================================
 این اسکریپت برنامه را از گیت‌هاب می‌گیرد و با Docker روی سرور بالا می‌آورد:
   بک‌اند FastAPI  +  وب (سایت عمومی + پنل)  +  PostgreSQL  +  Redis  +  ClamAV
 آخرین نسخهٔ مخزن شامل فاز ۵۱ است (رفع صفحهٔ سفید مانیتورینگ فرایندها،
 مرز خطای سراسری به‌جای صفحه سفید، و بهبود تجربهٔ ثبت شعب B31).

 پیش‌نیازها:
   - Windows Server 2025 با دسترسی Administrator
   - اتصال اینترنت و مجازی‌سازی فعال در BIOS/UEFI سرور

 روش استفاده (PowerShell را Run as Administrator باز کنید):

   گام ۱ — بار اول، نصب پیش‌نیازها (PowerShell 7 + Git + WSL2 + Docker Desktop):
       Set-ExecutionPolicy -Scope Process Bypass -Force
       .\rosepsy-server-deploy.ps1 setup
     اگر پیام «ری‌استارت لازم است» دیدید، سرور را یک بار ری‌استارت کنید و
     دوباره همین دستور را اجرا کنید (اسکریپت idempotent است و ادامه می‌دهد).

   گام ۲ — استقرار برنامه (کلون + ساخت .env امن + بیلد + مهاجرت + دادهٔ نمونه):
       .\rosepsy-server-deploy.ps1 deploy
     بار اول ۱۵ تا ۳۰ دقیقه طول می‌کشد (دانلود ایمیج‌ها + بیلد).

   گام ۳ — پس از هر انتشار جدید در گیت‌هاب، به‌روزرسانی:
       .\rosepsy-server-deploy.ps1 update

   گام ۴ — گواهی رایگان HTTPS (پیشنهادشده):
       .\rosepsy-server-tls.ps1
     چون گواهی رایگان برای IP خالی صادر نمی‌شود، از دامنهٔ جایگزین رایگان
     sslip.io استفاده می‌شود:  https://130.185.73.157.sslip.io/panel/
     (پراکسی Caddy + گواهی خودکار Let's Encrypt؛ بازسازی/توقف: حالت‌های status/off)
     پس از خرید دامنهٔ واقعی فقط همین دستور کافی است:
       .\rosepsy-server-tls.ps1 tls -Domain example.com

   نکته: اگر فایل را از گیت‌هاب می‌گیرید، روی سرور تازه فقط کافی است این یک خط را
   در PowerShell اجرا کنید (هم اسکریپت‌ها را می‌گیرد هم setup را اجرا می‌کند):
       iex (irm https://raw.githubusercontent.com/sjalilvand/special-spoon/main/deploy/windows/rosepsy-boot.ps1)

 دستورهای دیگر:
       .\rosepsy-server-deploy.ps1 status        وضعیت سرویس‌ها + سلامت API
       .\rosepsy-server-deploy.ps1 logs          دنبال‌کردن زندهٔ لاگ API (خروج با Ctrl+C)
       .\rosepsy-server-deploy.ps1 seed          اجرای مجدد دادهٔ نمونه (idempotent)
       .\rosepsy-server-deploy.ps1 seed-reset    پاک‌سازی کامل و بازسازی دادهٔ نمونه
       .\rosepsy-server-deploy.ps1 backup        بکاپ دیتابیس در پوشهٔ backups
       .\rosepsy-server-deploy.ps1 help          نمایش همین راهنما

 پارامترهای اختیاری:
       -RepoUrl     آدرس مخزن (پیش‌فرض: https://github.com/sjalilvand/special-spoon.git)
       -InstallDir  محل نصب (پیش‌فرض: C:\rosepsy)
       -Port        پورت عمومی وب (پیش‌فرض: 8080)
       -Token       توکن گیت‌هاب — فقط اگر مخزن خصوصی شد لازم است (مخزن فعلی عمومی است)
       -SkipSeed    پرش از اجرای دادهٔ نمونه در deploy/update

 نکتهٔ مجوز Docker Desktop:
   Docker Desktop برای استفادهٔ شخصی و کسب‌وکار کوچک رایگان است؛ سازمان‌های بزرگ
   به مجوز تجاری نیاز دارند. جایگزین رایگان: نصب Docker Engine داخل WSL2.

 آدرس‌ها پس از استقرار (SERVER-IP را با IP سرور عوض کنید):
   سایت عمومی:   http://SERVER-IP:8080/
   پنل مدیریت:   http://SERVER-IP:8080/panel/
   سلامت API:    http://SERVER-IP:8080/api/v1/health

 حساب‌های نمونهٔ دمو (پس از seed — در بهره‌برداری واقعی حتماً رمزها را عوض کنید):
   admin / Rosepsy@Admin2026
   counselor1..8 , reception1 , manager1 , supervisor1 , dpo1  /  Demo@1234
================================================================================
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'deploy', 'update', 'seed', 'seed-reset', 'status', 'logs', 'backup', 'doctor', 'help')]
    [string]$Mode = 'help',

    [string]$RepoUrl = 'https://github.com/sjalilvand/special-spoon.git',
    [string]$InstallDir = 'C:\rosepsy',
    [int]$Port = 8080,
    [string]$Token = '',
    [switch]$SkipSeed
)

# ---------------------- تنظیمات عمومی نشست ----------------------
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # دانلودها را در PS5.1 سرعت می‌دهد
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

$RepoPath = Join-Path $InstallDir 'special-spoon'
$LogFile  = Join-Path $InstallDir 'rosepsy-deploy.log'

# افزودن مسیر نصب Docker/Git به PATH نشست (برای پنجره‌های تازهٔ PowerShell)
if (Test-Path "$env:ProgramFiles\Docker\Docker\resources\bin") { $env:Path = "$env:Path;$env:ProgramFiles\Docker\Docker\resources\bin" }
if (Test-Path "$env:ProgramFiles\Git\cmd") { $env:Path = "$env:Path;$env:ProgramFiles\Git\cmd" }

# ---------------------- ابزارهای کمکی ----------------------
function Write-Step { param([string]$Text) Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Text) Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn2{ param([string]$Text) Write-Host "  [!]  $Text" -ForegroundColor Yellow }
function Write-Err2 { param([string]$Text) Write-Host "  [X]  $Text" -ForegroundColor Red }

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function New-RandomHex {
    # تولید رشتهٔ تصادفی امن برای رمزها/کلیدها (فقط کاراکتر هگز — سازگار با .env)
    param([int]$Bytes = 24)
    $buf = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($buf)
    $rng.Dispose()
    $sb = New-Object System.Text.StringBuilder
    foreach ($b in $buf) { [void]$sb.Append($b.ToString('x2')) }
    return $sb.ToString()
}

function Get-ServerIp {
    # اولین IP نسخهٔ ۴ معتبر سرور (غیر loopback و غیر APIPA)
    try {
        $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' } |
            Select-Object -First 1
        if ($ip) { return $ip.IPAddress }
    } catch { }
    try {
        return ([System.Net.Dns]::GetHostEntry([System.Net.Dns]::GetHostName()).AddressList |
            Where-Object { $_.AddressFamily -eq 'InterNetwork' } | Select-Object -First 1).IPAddressToString
    } catch { return 'SERVER-IP' }
}

function Write-Log {
    param([string]$Text)
    try {
        if (-not (Test-Path $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null }
        Add-Content -Path $LogFile -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Text) -Encoding UTF8
    } catch { }
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null }
}

function Invoke-ResilientDownload {
    # دانلود مقاوم برای اینترنت ناپایدار:
    #   ۱) curl.exe (در ویندوز سرور ۲۰۱۹ به بعد از پیش نصب است) — با «ادامهٔ دانلود از محل قطع» (-C -) و تلاش خودکار
    #   ۲) در نبود curl یا شکست آن — Invoke-WebRequest با ۳ بار تلاش
    param(
        [Parameter(Mandatory = $true)] [string]$Url,
        [Parameter(Mandatory = $true)] [string]$OutFile,
        [int]$Attempts = 4
    )
    Ensure-Directory (Split-Path $OutFile -Parent)
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        # نکتهٔ مهم: $curl یک آبجکت ApplicationInfo است؛ $curl.exe یعنی پراپرتی «exe» که $null برمی‌گرداند
        # و باعث خطای «The expression after '&' ... not valid» می‌شود. باید از مسیر واقعی فایل استفاده کنیم.
        $curlExe = $curl.Source
        if (-not $curlExe) { $curlExe = 'curl.exe' }
        for ($i = 1; $i -le $Attempts; $i++) {
            & $curlExe -L --fail --progress-bar --connect-timeout 30 --retry 8 --retry-all-errors --retry-delay 3 -C - --output "$OutFile" "$Url"
            if ($LASTEXITCODE -eq 0 -and (Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 0)) { return }
            Write-Warn2 "curl تلاش $i/$Attempts ناتمام ماند (کد $LASTEXITCODE) — ادامهٔ دانلود از محل قبلی..."
            Start-Sleep -Seconds 3
        }
        Write-Warn2 'curl ناموفق ماند — تلاش با Invoke-WebRequest'
    }
    for ($i = 1; $i -le 3; $i++) {
        try {
            Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec 3600
            if ((Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 0)) { return }
        } catch {
            if ($i -ge 3) { throw }
            Write-Warn2 "تلاش $i/3 ناموفق: $($_.Exception.Message)"
            Start-Sleep -Seconds 5
        }
    }
    throw "دانلود پس از چند تلاش ناموفق ماند: $Url"
}

# ---------------------- گام setup: پیش‌نیازها ----------------------
function Install-PowerShell7 {
    # نصب آخرین نسخهٔ پایدار PowerShell 7 (MSI بی‌صدا) — روی سرور تازه PS 5.1 هست
    if (Get-Command pwsh -ErrorAction SilentlyContinue) { Write-Ok 'PowerShell 7 نصب است'; return }
    Write-Step 'دریافت آخرین نسخهٔ PowerShell 7 از گیت‌هاب'
    $msiPath = $null
    try {
        $api = Invoke-WebRequest -Uri 'https://api.github.com/repos/PowerShell/PowerShell/releases/latest' -UseBasicParsing -TimeoutSec 60
        $rel = $api.Content | ConvertFrom-Json
        $asset = $rel.assets | Where-Object { $_.name -like 'PowerShell-*-win-x64.msi' } | Select-Object -First 1
        if ($asset) {
            $msiPath = Join-Path $env:TEMP $asset.name
            Invoke-ResilientDownload -Url $asset.browser_download_url -OutFile $msiPath
        }
    } catch {
        Write-Warn2 "دریافت از API گیت‌هاب ناموفق بود: $($_.Exception.Message) — تلاش با نصب‌کنندهٔ رسمی aka.ms"
    }
    if (-not $msiPath) {
        # جایگزین رسمی: اسکریپت نصب مایکروسافت (خودش آخرین MSI را نصب می‌کند)
        $boot = Join-Path $env:TEMP 'install-powershell.ps1'
        Invoke-WebRequest -Uri 'https://aka.ms/install-powershell.ps1' -OutFile $boot -UseBasicParsing
        & $boot -UseMSI -Quiet
        if (Test-Path "$env:ProgramFiles\PowerShell\7\pwsh.exe") { $env:Path = "$env:Path;$env:ProgramFiles\PowerShell\7" }
        if (Get-Command pwsh -ErrorAction SilentlyContinue) { Write-Ok 'PowerShell 7 نصب شد (aka.ms)'; return }
        throw 'نصب PowerShell 7 ناموفق بود — پنجره را ببندید و setup را دوباره اجرا کنید'
    }
    Write-Step "نصب بی‌صدای $(Split-Path $msiPath -Leaf)"
    $p = Start-Process -FilePath 'msiexec.exe' -ArgumentList "/i `"$msiPath`" /qn ADD_PATH=1 REGISTER_MANIFEST=1 ENABLE_MU=0 USE_MU=0" -Wait -PassThru
    Remove-Item $msiPath -ErrorAction SilentlyContinue
    $env:Path = "$env:Path;$env:ProgramFiles\PowerShell\7"
    if ($p.ExitCode -eq 3010) { $script:NeedRestart = $true }
    elseif ($p.ExitCode -ne 0 -and -not (Get-Command pwsh -ErrorAction SilentlyContinue)) {
        throw "نصب PowerShell 7 ناموفق بود (کد $($p.ExitCode))"
    }
    if (Get-Command pwsh -ErrorAction SilentlyContinue) {
        Write-Ok 'PowerShell 7 نصب شد — از این به بعد می‌توانید پنجرهٔ جدید را با pwsh باز کنید (پیشنهاد می‌شود)'
    }
}

function Enable-Wsl2 {
    # فعال‌سازی WSL2 + Virtual Machine Platform؛ خروجی: آیا ری‌استارت لازم است
    $needReboot = $false
    foreach ($feat in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform')) {
        $state = $null
        try { $state = (Get-WindowsOptionalFeature -Online -FeatureName $feat -ErrorAction Stop).State } catch { }
        if ($state -ne 'Enabled') {
            Write-Step "فعال‌سازی قابلیت ویندوز: $feat"
            try {
                Enable-WindowsOptionalFeature -Online -FeatureName $feat -NoRestart -ErrorAction Stop | Out-Null
            } catch {
                Write-Warn2 "فعال‌سازی $feat ناموفق بود: $($_.Exception.Message)"
                continue
            }
            $state2 = $null
            try { $state2 = (Get-WindowsOptionalFeature -Online -FeatureName $feat -ErrorAction Stop).State } catch { }
            if ($state2 -eq 'EnablePending') { $needReboot = $true }
        } else {
            Write-Ok "قابلیت $feat از قبل فعال است"
        }
    }

    # اگر دستور wsl در دسترس نیست یا کار نمی‌کند، هستهٔ WSL2 را نصب می‌کنیم
    $wslOk = $false
    try { & wsl.exe --status *> $null; if ($LASTEXITCODE -eq 0) { $wslOk = $true } } catch { }
    if (-not $wslOk) {
        Write-Step 'نصب هستهٔ WSL2 (wsl_update_x64.msi)'
        try {
            $msi = Join-Path $env:TEMP 'wsl_update_x64.msi'
            Invoke-ResilientDownload -Url 'https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi' -OutFile $msi
            if (-not (Test-Path $msi) -or (Get-Item $msi).Length -lt 1048576) { throw 'فایل MSI هستهٔ WSL2 سالم دانلود نشد' }
            $p = Start-Process -FilePath 'msiexec.exe' -ArgumentList "/i `"$msi`" /qn" -Wait -PassThru
            if ($p.ExitCode -eq 0 -or $p.ExitCode -eq 3010) {
                try { & wsl.exe --set-default-version 2 *> $null } catch { }
                Write-Ok 'هستهٔ WSL2 نصب شد'
            } else {
                Write-Warn2 "نصب هستهٔ WSL2 با کد $($p.ExitCode) ناتمام ماند — روش جایگزین (بستهٔ مدرن WSL) امتحان می‌شود"
            }
        } catch {
            # این گام نباید ادامهٔ setup را متوقف کند
            Write-Warn2 "نصب هستهٔ WSL2 انجام نشد: $($_.Exception.Message) — روش جایگزین امتحان می‌شود"
        }
        # تلاش دوم: بستهٔ مدرن WSL (روش رسمی Windows Server 2025) — چون MSI قدیمی روی Server 2025 ممکن است 1603 بدهد
        try { & wsl.exe --status *> $null; $wslOk2 = ($LASTEXITCODE -eq 0) } catch { $wslOk2 = $false }
        if (-not $wslOk2) {
            Write-Step 'نصب بستهٔ مدرن WSL از گیت‌هاب (wsl --install --no-distribution)'
            try {
                & wsl.exe --install --no-distribution --web-download 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
                if ($LASTEXITCODE -ne 0) {
                    Write-Warn2 "wsl --install --web-download کد $LASTEXITCODE داد — تلاش بدون --web-download"
                    & wsl.exe --install --no-distribution 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
                }
                Write-Warn2 'اگر این دستور پیام ری‌استارت داد، سرور را RESTART و همان دستور بوت را دوباره اجرا کنید'
            } catch {
                Write-Warn2 "نصب بستهٔ مدرن WSL ناموفق بود: $($_.Exception.Message) — خروجی «doctor» را برای پشتیبانی بفرستید"
            }
        }
    } else {
        Write-Ok 'WSL در دسترس است'
    }
    return $needReboot
}

function Install-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) { Write-Ok 'Git نصب است'; return }
    Write-Step 'دانلود Git for Windows (آخرین نسخهٔ پایدار ۶۴بیتی)'
    $setup = $null
    # نام واقعی نصاب‌ها مثل Git-2.56.0.3-64-bit.exe است (Git-64-bit.exe وجود خارجی ندارد)
    $pattern = 'Git-\d+(\.\d+)*-64-bit\.exe'

    # ۰) اگر نصاب از قبل در C:\rosepsy\installers گذاشته شده باشد، همان استفاده می‌شود
    $pre = Get-ChildItem -Path (Join-Path $InstallDir 'installers') -Filter 'Git-*-64-bit.exe' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch 'arm64' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($pre) {
        Write-Ok "نصاب آمادهٔ محلی: $($pre.FullName)"
        $setup = $pre.FullName
    }

    if (-not $setup) {
        $url = $null
        # ۱) مسیر اصلی: API گیت‌هاب — برداشتن browser_download_url از ریلیز آخر
        try {
            $rel = Invoke-RestMethod -Uri 'https://api.github.com/repos/git-for-windows/git/releases/latest' -Headers @{ 'User-Agent' = 'rosepsy-deploy' } -TimeoutSec 60
            $asset = $rel.assets | Where-Object { $_.name -match $pattern } | Select-Object -First 1
            if ($asset) { $url = $asset.browser_download_url }
        } catch {
            Write-Warn2 "API گیت‌هاب پاسخ نداد: $($_.Exception.Message) — تلاش با روش جایگزین"
        }
        # ۲) جایگزین بدون API: ریدایرکت releases/latest + صفحهٔ expanded_assets
        if (-not $url) {
            try {
                $req = [System.Net.WebRequest]::Create('https://github.com/git-for-windows/git/releases/latest')
                $req.AllowAutoRedirect = $false
                $req.Timeout = 30000
                $rsp = $req.GetResponse()
                $loc = [string]$rsp.Headers['Location']
                $rsp.Close()
                if ($loc -match '/tag/(.+)$') {
                    $tag = $Matches[1]
                    Write-Host "    آخرین ریلیز: $tag" -ForegroundColor DarkGray
                    $html = (Invoke-WebRequest -Uri "https://github.com/git-for-windows/git/releases/expanded_assets/$tag" -UseBasicParsing -TimeoutSec 60).Content
                    if ($html -match $pattern) { $url = "https://github.com/git-for-windows/git/releases/download/$tag/$($Matches[0])" }
                }
            } catch {
                Write-Warn2 "یافتن نصاب از صفحهٔ ریلیزها ناموفق بود: $($_.Exception.Message)"
            }
        }
        # ۳) آخرین جایگزین: نشانی ثابتِ نسخهٔ پایدار آزموده‌شده (اگر API و صفحهٔ ریلیز هر دو در دسترس نبودند)
        if (-not $url) {
            $url = 'https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.3/Git-2.56.0.3-64-bit.exe'
            Write-Warn2 'استفاده از نشانی ثابت نسخهٔ پشتیبان Git 2.56.0.3'
        }
        if (-not $url) {
            throw "نشانی نصاب Git پیدا نشد — فایل Git-*-64-bit.exe را از https://github.com/git-for-windows/git/releases/latest دستی دانلود و در پوشهٔ $InstallDir\installers بگذارید و دوباره اجرا کنید"
        }
        Write-Host "    نصاب: $((Split-Path $url -Leaf))" -ForegroundColor DarkGray
        $setup = Join-Path $env:TEMP 'Git-installer.exe'
        try {
            Invoke-ResilientDownload -Url $url -OutFile $setup
        } catch {
            throw "دانلود نصاب Git ناموفق بود: $($_.Exception.Message) — جایگزین: فایل Git-*-64-bit.exe را از https://github.com/git-for-windows/git/releases/latest دستی دانلود و در پوشهٔ $InstallDir\installers بگذارید و دوباره اجرا کنید"
        }
        if (-not (Test-Path $setup) -or (Get-Item $setup).Length -lt 1048576) {
            throw "نصاب Git سالم دانلود نشد (حجم کمتر از انتظار) — فایل Git-*-64-bit.exe را دستی در پوشهٔ $InstallDir\installers بگذارید و دوباره اجرا کنید"
        }
    }

    Write-Step 'نصب بی‌صدای Git'
    $p = Start-Process -FilePath $setup -ArgumentList '/VERYSILENT', '/NORESTART', '/NOSPLASHPAGE' -Wait -PassThru
    if ($setup -like "$env:TEMP*") { Remove-Item $setup -ErrorAction SilentlyContinue }
    $env:Path = "$env:Path;$env:ProgramFiles\Git\cmd"
    if ($p.ExitCode -ne 0 -or -not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'نصب Git ناموفق بود — پنجرهٔ PowerShell را ببندید، دوباره باز کنید و setup را تکرار کنید'
    }
    Write-Ok 'Git نصب شد'
}

function Install-DockerDesktop {
    $dockerExe = "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path $dockerExe) { Write-Ok 'Docker Desktop نصب است'; return }
    $instDir = Join-Path $InstallDir 'installers'
    Ensure-Directory $instDir
    $pre = Get-ChildItem -Path $instDir -Filter 'DockerDesktop*.exe' -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -gt 1048576 } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($pre) {
        Write-Ok "نصاب آمادهٔ محلی: $($pre.FullName)"
        $installer = $pre.FullName
    } else {
        Write-Step 'دانلود Docker Desktop (حدود ۵۰۰ تا ۷۰۰ مگابایت — بسته به اینترنت ممکن است طولانی شود)'
        # مستقیم در installers ذخیره می‌شود تا اگر نصب شکست خورد، در اجرای بعدی دوباره دانلود نشود
        $installer = Join-Path $instDir 'DockerDesktopInstaller.exe'
        Invoke-ResilientDownload -Url 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' -OutFile $installer
        if (-not (Test-Path $installer) -or (Get-Item $installer).Length -lt 1048576) { throw 'نصاب Docker Desktop سالم دانلود نشد' }
    }
    Write-Step 'نصب بی‌صدای Docker Desktop با بک‌اند WSL2 (چند دقیقه طول می‌کشد)'
    # --always-run-service: سرویس com.docker.service برای کارکرد درست روی Windows Server
    $p = Start-Process -FilePath $installer -ArgumentList 'install', '--quiet', '--accept-license', '--backend=wsl-2', '--always-run-service' -Wait -PassThru
    if ($p.ExitCode -eq 3010) {
        Write-Warn2 'نصب Docker Desktop به ری‌استارت نیاز دارد (کد 3010)'
        $script:NeedRestart = $true
        return
    }
    if ($p.ExitCode -ne 0) {
        if ($p.ExitCode -eq 3) {
            Write-Warn2 "نصاب دانلودشده حفظ شد: $installer (در اجرای بعدی دوباره دانلود نمی‌شود)"
            throw 'نصب Docker Desktop ناموفق بود (کد ۳) — این کد تقریباً همیشه یعنی WSL2/قابلیت‌های مجازی‌سازی هنوز با یک بار ری‌استارت کامل نشده‌اند. سرور را RESTART کنید و دوباره همان دستور بوت را اجرا کنید'
        }
        throw "نصب Docker Desktop ناموفق بود (کد خروج $($p.ExitCode)) — در صورت تکرار، نصب دستی را امتحان کنید (نصاب در $installer حفظ شده)"
    }
    Remove-Item $installer -ErrorAction SilentlyContinue
    Write-Ok 'Docker Desktop نصب شد'
}

function Start-DockerEngine {
    # اطمینان از اینکه CLI docker در PATH نشست هست و موتور در حال اجراست
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) { $env:Path = "$env:Path;$env:ProgramFiles\Docker\Docker\resources\bin" }
    $dockerExe = "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
    if (-not (Test-Path $dockerExe)) {
        try { $dockerExe = (Get-Command docker -ErrorAction Stop).Source } catch { }
    }
    if (-not $dockerExe -or -not (Test-Path $dockerExe)) {
        throw 'docker.exe پیدا نشد — ابتدا setup را کامل کنید و پنجرهٔ PowerShell را دوباره باز کنید'
    }

    & $dockerExe info *> $null
    if ($LASTEXITCODE -eq 0) { Write-Ok 'موتور Docker در حال اجراست'; return $dockerExe }

    Write-Step 'راه‌اندازی Docker Desktop و انتظار برای آماده‌شدن موتور (تا ۵ دقیقه)'
    $dd = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dd) { Start-Process -FilePath $dd | Out-Null }
    $ready = $false
    for ($i = 1; $i -le 60; $i++) {
        Start-Sleep -Seconds 5
        & $dockerExe info *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        if ($i % 6 -eq 0) { Write-Host "  ... منتظر موتور Docker (دقیقهٔ $([int]($i / 12)))" -ForegroundColor DarkGray }
    }
    if (-not $ready) {
        throw 'موتور Docker پس از ۵ دقیقه آماده نشد — Docker Desktop را دستی باز کنید، چند دقیقه صبر کنید و دوباره دستور را اجرا کنید'
    }
    Write-Ok 'موتور Docker آماده است'
    return $dockerExe
}

function Register-DockerAutoStart {
    # شروع خودکار Docker Desktop پس از ورود کاربر (Task Scheduler)
    $dd = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dd)) { return }
    $taskName = 'Rosepsy-DockerDesktop-AutoStart'
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) { Write-Ok 'وظیفهٔ شروع خودکار Docker از قبل ثبت است'; return }
    try {
        $action  = New-ScheduledTaskAction -Execute $dd
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
            -Description 'Rosepsy: اجرای خودکار Docker Desktop پس از ورود به سرور' -Force | Out-Null
        Write-Ok 'شروع خودکار Docker Desktop پس از ورود ثبت شد (Task Scheduler)'
    } catch {
        Write-Warn2 "ثبت وظیفهٔ شروع خودکار ناموفق بود: $($_.Exception.Message)"
        Write-Warn2 'پس از هر ری‌استارت، Docker Desktop را دستی باز کنید یا گزینهٔ Start when I sign in را در تنظیمات آن فعال کنید'
    }
}

function Invoke-Doctor {
    # تشخیص ریشهٔ مشکلات WSL2/مجازی‌سازی/Docker — خروجی برای پشتیبانی فرستاده می‌شود
    Write-Host ''
    Write-Host '================ ROSEPSY doctor — تشخیص WSL2 / مجازی‌سازی / Docker ================' -ForegroundColor DarkCyan
    $os = Get-CimInstance Win32_OperatingSystem
    Write-Host ("Windows            : {0} (build {1})" -f $os.Caption, $os.BuildNumber)

    Write-Step 'مجازی‌سازی (مهم‌ترین بخش)'
    $cs = Get-CimInstance Win32_ComputerSystem
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    Write-Host ("  HypervisorPresent             : {0}   <-- برای کارکرد Docker/WSL2 باید True باشد" -f $cs.HypervisorPresent) -ForegroundColor White
    Write-Host ("  VirtualizationFirmwareEnabled : {0}   <-- اگر False باشد یعنی Nested Virtualization روی VPS خاموش است (در پنل هاست فعال کنید)" -f $cpu.VirtualizationFirmwareEnabled) -ForegroundColor White
    Write-Host ("  SLAT (VT-x/AMD-V)             : {0}" -f $cpu.SecondLevelAddressTranslationExtensions) -ForegroundColor White
    try {
        $bcd = (bcdedit /enum '{current}' | Out-String)
        $m = [regex]::Match($bcd, 'hypervisorlaunchtype\s+(\S+)')
        Write-Host ("  hypervisorlaunchtype          : {0}" -f $m.Groups[1].Value) -ForegroundColor White
    } catch { }

    Write-Step 'قابلیت‌های ویندوز'
    foreach ($feat in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform', 'Containers', 'Microsoft-Hyper-V-All')) {
        try {
            $s = (Get-WindowsOptionalFeature -Online -FeatureName $feat -ErrorAction Stop).State
            Write-Host ("  {0}: {1}" -f $feat, $s)
        } catch { Write-Host ("  {0}: ناموجود/خطا" -f $feat) }
    }

    Write-Step 'خروجی wsl.exe'
    foreach ($a in @(@('--status'), @('--version'))) {
        Write-Host ("  --- wsl.exe $($a -join ' ')")
        try {
            $out = (& wsl.exe @a 2>&1 | Out-String)
            Write-Host ("  exit code: $LASTEXITCODE")
            if ($out.Trim()) { Write-Host ($out.Trim() -split "`n" | ForEach-Object { "    $_" }) }
        } catch { Write-Host "    خطا: $($_.Exception.Message)" }
    }

    Write-Step 'وضعیت ری‌استارت و سرویس‌ها'
    Write-Host ("  CBS RebootPending  : {0}" -f (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'))
    Write-Host ("  WU  RebootRequired : {0}" -f (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'))
    foreach ($svc in @('vmcompute', 'LxssManager', 'WSLService', 'com.docker.service', 'docker')) {
        $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
        if ($s) { Write-Host ("  سرویس {0}: {1}" -f $svc, $s.Status) } else { Write-Host ("  سرویس {0}: ثبت نشده" -f $svc) }
    }

    Write-Step 'Docker'
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd -and (Test-Path "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe")) {
        $env:Path = "$env:Path;$env:ProgramFiles\Docker\Docker\resources\bin"
        $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    }
    Write-Host ("  docker CLI : {0}" -f $(if ($dockerCmd) { $dockerCmd.Source } else { 'پیدا نشد (نصب ناقص/نشده)' }))
    if ($dockerCmd) {
        try { & docker info *> $null; Write-Host ("  docker info exit: $LASTEXITCODE (0 = موتور در حال اجراست)") } catch { }
    }
    Write-Host ("  نصاب ذخیره‌شده: " + $(Get-ChildItem -Path (Join-Path $InstallDir 'installers') -Filter 'DockerDesktop*.exe' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName))

    Write-Step 'لاگ نصاب Docker (آخرین ۲۵ خط هر فایل)'
    $logs = @()
    $logs += Get-ChildItem -Path "$env:TEMP\dd*.log" -ErrorAction SilentlyContinue
    $logs += Get-ChildItem -Path "$env:LOCALAPPDATA\Docker\log\install\*.log" -ErrorAction SilentlyContinue
    if (-not $logs) { Write-Host '  لاگی پیدا نشد' }
    foreach ($lg in ($logs | Sort-Object LastWriteTime -Descending | Select-Object -First 3)) {
        Write-Host ("  --- $($lg.FullName)")
        Get-Content $lg.FullName -Tail 25 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" }
    }

    Write-Host ''
    Write-Host '================ پایان doctor — کل خروجی بالا را برای پشتیبانی بفرستید ================' -ForegroundColor DarkCyan
}

function Invoke-Setup {
    Write-Host '==============================================' -ForegroundColor DarkCyan
    Write-Host ' گام setup: نصب پیش‌نیازهای استقرار رزپسی' -ForegroundColor DarkCyan
    Write-Host '==============================================' -ForegroundColor DarkCyan

    if (-not (Test-Admin)) { throw 'این مرحله باید با PowerShell در حالت Run as Administrator اجرا شود' }

    $script:NeedRestart = $false

    # ۱) PowerShell 7 (اختیاری ولی پیشنهادشده؛ مراحل بعدی با PS 5.1 هم کار می‌کنند)
    Install-PowerShell7

    # ۲) WSL2 (پیش از Docker — چون Docker Desktop به آن وابسته است)
    $wslReboot = Enable-Wsl2
    if ($wslReboot) { $script:NeedRestart = $true }

    # ۳) Git
    Install-Git

    # ۳-ب) چک ری‌استارت پیش از Docker: وقتی فعال‌سازی WSL2 هنوز با ری‌استارت کامل نشده،
    # نصب Docker Desktop با کد ۳ شکست می‌خورد — پس قبل از دانلود/نصب ۶۰۰ مگابایتی همان‌جا متوقف شو
    $rebootPending = $script:NeedRestart -or
        (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') -or
        (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired')
    if ($rebootPending) {
        try {
            $st = (& wsl.exe --status 2>&1 | Out-String).Trim()
            if ($st) { Write-Host "    wsl --status: $st" -ForegroundColor DarkGray }
        } catch { }
        Write-Warn2 'یک ری‌استارت روی ویندوز در صف است (فعال‌سازی WSL2/به‌روزرسانی‌ها هنوز کامل نشده)'
        Write-Err2 'لطفاً سرور را RESTART کنید، سپس دوباره همان دستور بوت را اجرا کنید تا نصب Docker Desktop و استقرار ادامه یابد'
        Write-Host '    (Git نصب شد و پس از ری‌استارت تکرار نمی‌شود؛ مراحل انجام‌شده به‌صورت خودکار رد می‌شوند)' -ForegroundColor DarkGray
        return
    }

    # ۴) Docker Desktop
    Install-DockerDesktop

    if ($script:NeedRestart) {
        Write-Host ''
        Write-Err2 'یک بار سرور را RESTART کنید، سپس دوباره اجرا کنید:  .\rosepsy-server-deploy.ps1 setup'
        Write-Host '    (پس از ری‌استارت، اسکریپت از همان‌جا ادامه می‌دهد و مراحل انجام‌شده را تکرار نمی‌کند)'
        return
    }

    # ۵) راه‌اندازی موتور و ثبت شروع خودکار
    Start-DockerEngine | Out-Null
    Register-DockerAutoStart

    # ۶) پیکربندی git برای این پروژه
    & git config --global core.autocrlf false   # فایل‌های شِل داخل کانتینر LF بمانند (مهم برای deploy/backup.sh)
    & git config --global core.longpaths true

    Write-Host ''
    Write-Ok 'پیش‌نیازها کامل شد.'
    Write-Host '   گام بعدی — استقرار برنامه:' -ForegroundColor White
    Write-Host "   .\rosepsy-server-deploy.ps1 deploy" -ForegroundColor Yellow
}

# ---------------------- گام deploy/update: استقرار برنامه ----------------------
function New-EnvFile {
    # ساخت .env از روی .env.example با رمزهای تصادفی قوی (idempotent: .env موجود دست نمی‌خورد)
    $envExample = Join-Path $RepoPath '.env.example'
    $envFile    = Join-Path $RepoPath '.env'
    if (-not (Test-Path $envExample)) { throw ".env.example در مخزن یافت نشد" }
    if (Test-Path $envFile) { Write-Ok '.env از قبل موجود است — بدون تغییر ماند'; return }

    Write-Step 'ساخت فایل .env با رمزهای تصادفی قوی'
    $dbPass  = New-RandomHex 20
    $authKey = New-RandomHex 32
    $minioPw = New-RandomHex 20
    $serverIp = Get-ServerIp
    $replacements = [ordered]@{
        '^POSTGRES_PASSWORD=.*'   = "POSTGRES_PASSWORD=$dbPass"
        '^DATABASE_URL=.*'        = "DATABASE_URL=postgresql+psycopg://rosepsy:$dbPass@db:5432/rosepsy"
        '^AUTH_SECRET_KEY=.*'     = "AUTH_SECRET_KEY=$authKey"
        '^MINIO_ROOT_PASSWORD=.*' = "MINIO_ROOT_PASSWORD=$minioPw"
        '^S3_ACCESS_KEY=.*'       = 'S3_ACCESS_KEY=rosepsy'
        '^S3_SECRET_KEY=.*'       = "S3_SECRET_KEY=$minioPw"
        '^ENVIRONMENT=.*'         = 'ENVIRONMENT=development'
        '^PUBLIC_BASE_URL=.*'     = "PUBLIC_BASE_URL=http://${serverIp}:$Port"
    }
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in [System.IO.File]::ReadAllLines($envExample)) {
        $newLine = $line
        foreach ($key in $replacements.Keys) {
            if ($line -match $key) { $newLine = $replacements[$key]; break }
        }
        $out.Add($newLine)
    }
    # UTF-8 بدون BOM تا docker compose درست بخواند
    [System.IO.File]::WriteAllLines($envFile, $out)

    # ثبت اعتبارنامه‌های ساخته‌شده در فایل محافظت‌شده (فقط Administrators)
    $credFile = Join-Path $InstallDir 'deploy-credentials.txt'
    $creds = @(
        'رزپسی — اعتبارنامه‌های ساخته‌شده در زمان استقرار'
        "تاریخ: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        ''
        'این مقادیر داخل فایل .env مخزن هم ذخیره شده‌اند:'
        "  POSTGRES_PASSWORD   = $dbPass"
        "  AUTH_SECRET_KEY     = $authKey"
        "  MINIO_ROOT_PASSWORD = $minioPw"
        ''
        "محل فایل پیکربندی: $envFile"
        'حساب‌های نمونهٔ دمو (پس از seed): admin / Rosepsy@Admin2026 و سایر حساب‌ها با Demo@1234'
        '⚠ در بهره‌برداری واقعی: رمز admin را از پنل عوض کنید و این فایل را امن نگه دارید'
    )
    [System.IO.File]::WriteAllLines($credFile, $creds)
    try {
        & icacls $credFile /inheritance:r /grant:r 'Administrators:F' 'SYSTEM:F' | Out-Null
    } catch { }
    Write-Ok ".env ساخته شد؛ اعتبارنامه‌ها در $credFile (دسترسی فقط Administrators)"
}

function Update-Repo {
    # سرور همیشه دقیقاً همان نسخهٔ origin/main گیت‌هاب باشد
    $git = (Get-Command git -ErrorAction SilentlyContinue).Source
    if (-not $git) { $git = "$env:ProgramFiles\Git\cmd\git.exe" }

    if (Test-Path (Join-Path $RepoPath '.git')) {
        Write-Step "به‌روزرسانی مخزن موجود از گیت‌هاب: $RepoPath"
        Push-Location $RepoPath
        try {
            $dirty = & git status --porcelain
            if ($dirty) { Write-Warn2 'تغییرات محلی مشاهده شد — با reset به نسخهٔ گیت‌هاب برگردانده می‌شود' }
            if ($Token) { & $git remote set-url origin ($RepoUrl -replace '^https://', "https://x-access-token:$Token@") | Out-Null }
            & $git fetch origin main
            if ($LASTEXITCODE -ne 0) { throw 'git fetch ناموفق بود — اتصال اینترنت یا آدرس/توکن مخزن را بررسی کنید' }
            & $git reset --hard origin/main
            if ($LASTEXITCODE -ne 0) { throw 'git reset ناموفق بود' }
            if ($Token) { & $git remote set-url origin $RepoUrl | Out-Null }
            & $git log --oneline -1
        } finally { Pop-Location }
    }
    else {
        Ensure-Directory $InstallDir
        Write-Step "کلون مخزن از گیت‌هاب در: $RepoPath"
        $cloneUrl = $RepoUrl
        if ($Token) { $cloneUrl = $RepoUrl -replace '^https://', "https://x-access-token:$Token@" }
        & $git clone $cloneUrl $RepoPath
        if ($LASTEXITCODE -ne 0) { throw 'کلون مخزن ناموفق بود — آدرس مخزن یا توکن را بررسی کنید' }
        if ($Token) { Push-Location $RepoPath; & $git remote set-url origin $RepoUrl | Out-Null; Pop-Location }
        Push-Location $RepoPath; & $git log --oneline -1; Pop-Location
    }
    Push-Location $RepoPath
    $headShort = & $git rev-parse --short HEAD
    Pop-Location
    Write-Log "repo synced to $headShort"
}

function Invoke-Compose {
    # اجرای دستور docker compose در پوشهٔ مخزن
    param([string[]]$ComposeArgs, [switch]$NoFail)
    Push-Location $RepoPath
    try {
        & docker compose @ComposeArgs
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    if (-not $NoFail -and $code -ne 0) {
        throw "دستور «docker compose $($ComposeArgs -join ' ')» ناموفق بود (کد $code)"
    }
}

function Set-FirewallRule {
    Write-Step "پیکربندی فایروال برای پورت ورودی $Port"
    $ruleName = "Rosepsy-Web-$Port"
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if (-not $existing) {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port `
            -Action Allow -Profile Any -Description 'Rosepsy: دسترسی وب (سایت + پنل + API)' | Out-Null
        Write-Ok "قاعدهٔ فایروال «$ruleName» ساخته شد"
    } else {
        Write-Ok 'قاعدهٔ فایروال از قبل موجود است'
    }
}

function Wait-ApiHealth {
    $url = "http://localhost:$Port/api/v1/health"
    Write-Step "انتظار برای سلامت API: $url (تا ۵ دقیقه)"
    for ($i = 1; $i -le 60; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { Write-Ok 'API سالم و در دسترس است'; return $true }
        } catch { }
        Start-Sleep -Seconds 5
    }
    Write-Warn2 'API هنوز پاسخ نمی‌دهد — چند دقیقه صبر کنید و «status» را اجرا کنید؛ برای بررسی خطا: .\rosepsy-server-deploy.ps1 logs'
    return $false
}

function Show-DeploySummary {
    $ip = Get-ServerIp
    $base = "http://${ip}:$Port"
    Write-Host ''
    Write-Host '=================================================' -ForegroundColor DarkGreen
    Write-Ok 'استقرار رزپسی کامل شد'
    Write-Host '=================================================' -ForegroundColor DarkGreen
    Write-Host "  سایت عمومی : $base/"                -ForegroundColor White
    Write-Host "  پنل مدیریت : $base/panel/"          -ForegroundColor White
    Write-Host "  سلامت API  : $base/api/v1/health"   -ForegroundColor White
    Write-Host '  ادمین دمو  : admin / Rosepsy@Admin2026  (در بهره‌برداری واقعی رمز را عوض کنید)' -ForegroundColor White
    Write-Host "  اعتبارنامه‌ها: $(Join-Path $InstallDir 'deploy-credentials.txt')" -ForegroundColor White
    Write-Host ''
    Write-Host '  دستورهای مفید:' -ForegroundColor White
    Write-Host "    .\rosepsy-server-deploy.ps1 status      وضعیت سرویس‌ها"
    Write-Host "    .\rosepsy-server-deploy.ps1 logs        لاگ زندهٔ API"
    Write-Host "    .\rosepsy-server-deploy.ps1 backup      بکاپ دیتابیس"
    Write-Host "    .\rosepsy-server-deploy.ps1 update      دریافت نسخهٔ جدید از گیت‌هاب"
    Write-Host ''
    Write-Host '  گواهی رایگان HTTPS:' -ForegroundColor White
    Write-Host '    .\rosepsy-server-tls.ps1               https://130.185.73.157.sslip.io/panel/'
    Write-Host ''
}

function Invoke-Deploy {
    param([switch]$UpdateOnly)
    $label = 'استقرار (deploy)'
    if ($UpdateOnly) { $label = 'به‌روزرسانی (update)' }
    Write-Host '==============================================' -ForegroundColor DarkCyan
    Write-Host " رزپسی — $label روی Windows Server" -ForegroundColor DarkCyan
    Write-Host '==============================================' -ForegroundColor DarkCyan

    if (-not (Test-Admin)) { throw 'این مرحله باید با PowerShell در حالت Run as Administrator اجرا شود (برای قاعدهٔ فایروال)' }

    Start-DockerEngine | Out-Null
    Update-Repo
    New-EnvFile

    Write-Step 'بیلد ایمیج‌ها (بار اول ۱۵ تا ۳۰ دقیقه؛ دفعات بعد از کش استفاده می‌شود)'
    Write-Log 'docker compose build started'
    Invoke-Compose -ComposeArgs @('build')

    Write-Step 'راه‌اندازی زیرساخت: PostgreSQL + Redis + ClamAV'
    Invoke-Compose -ComposeArgs @('up', '-d', 'db', 'clamav', 'redis')

    Write-Step 'اجرای مهاجرت‌های دیتابیس (alembic upgrade head)'
    Invoke-Compose -ComposeArgs @('run', '--rm', 'migrate')

    Write-Step 'راه‌اندازی API و وب (Nginx + پنل)'
    Invoke-Compose -ComposeArgs @('up', '-d', 'api', 'web')

    if (-not $SkipSeed) {
        Write-Step 'اجرای دادهٔ نمونهٔ جامع (idempotent — اگر قبلاً اجرا شده، بخش‌های جدید را اضافه می‌کند)'
        Write-Host '    ۱۰۰ متقاضی / مشاوره‌ها / نوبت‌ها / فرایندها / شعب ۳۱ استان / بانک آزمون ۳۱ ابزار ...' -ForegroundColor DarkGray
        Invoke-Compose -ComposeArgs @('run', '--rm', 'api', 'python', 'seed_demo_rich.py')
    } else {
        Write-Warn2 'اجرای seed با پرچم -SkipSeed رد شد'
    }

    Set-FirewallRule
    $healthy = Wait-ApiHealth
    Write-Log "deploy finished; healthy=$healthy"
    Show-DeploySummary
}

# ---------------------- بقیهٔ حالت‌ها ----------------------
function Invoke-Seed {
    param([switch]$Reset)
    Start-DockerEngine | Out-Null
    if (-not (Test-Path (Join-Path $RepoPath 'docker-compose.yml')) -and -not (Test-Path (Join-Path $RepoPath 'compose.yml'))) {
        throw "مخزن در $RepoPath پیدا نشد — ابتدا «.\rosepsy-server-deploy.ps1 deploy» را اجرا کنید"
    }
    if ($Reset) {
        Write-Warn2 'seed-reset: همهٔ دادهٔ نمونه و دادهٔ پنل پاک و از نو ساخته می‌شود!'
        $confirm = Read-Host 'مطمئنید؟ (yes/no)'
        if ($confirm -ne 'yes') { Write-Warn2 'لغو شد'; return }
        Invoke-Compose -ComposeArgs @('run', '--rm', 'api', 'python', 'seed_demo_rich.py', '--reset')
    } else {
        Write-Step 'اجرای دادهٔ نمونه (حالت تکمیلی و idempotent)'
        Invoke-Compose -ComposeArgs @('run', '--rm', 'api', 'python', 'seed_demo_rich.py')
    }
    Write-Ok 'seed تمام شد'
}

function Show-Status {
    if (-not (Test-Path $RepoPath)) { Write-Warn2 "مخزن در $RepoPath نصب نشده است"; return }
    Push-Location $RepoPath
    try {
        Write-Step 'وضعیت کانتینرها'
        & docker compose ps
        Write-Step 'نسخهٔ مستقر (آخرین commit)'
        & git log --oneline -1
        Write-Step 'سلامت API'
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:$Port/api/v1/health" -UseBasicParsing -TimeoutSec 5
            Write-Ok "HTTP $($resp.StatusCode) — $($resp.Content)"
        } catch { Write-Warn2 "API پاسخ نمی‌دهد: $($_.Exception.Message)" }
    } finally { Pop-Location }
    $ip = Get-ServerIp
    Write-Host ''
    Write-Host "  سایت: http://${ip}:$Port/   |   پنل: http://${ip}:$Port/panel/   |   API: http://${ip}:$Port/api/v1/health" -ForegroundColor White
}

function Show-Logs {
    if (-not (Test-Path $RepoPath)) { Write-Warn2 "مخزن در $RepoPath نصب نشده است"; return }
    Push-Location $RepoPath
    try { & docker compose logs -f --tail=100 api } finally { Pop-Location }
}

function Invoke-Backup {
    Start-DockerEngine | Out-Null
    if (-not (Test-Path $RepoPath)) { throw "مخزن در $RepoPath پیدا نشد" }
    Write-Step 'اجرای بکاپ دیتابیس (پروفایل ops)'
    Invoke-Compose -ComposeArgs @('--profile', 'ops', 'run', '--rm', 'backup')
    $backupDir = Join-Path $RepoPath 'backups'
    if (Test-Path $backupDir) {
        $latest = Get-ChildItem $backupDir -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latest) { Write-Ok "بکاپ: $($latest.FullName)" }
    }
}

function Show-Help {
    Write-Host @'

 رزپسی — استقرار روی Windows Server 2025 از طریق گیت
 ----------------------------------------------------
   .\rosepsy-server-deploy.ps1 setup        نصب پیش‌نیازها (Git + WSL2 + Docker Desktop)
   .\rosepsy-server-deploy.ps1 deploy       استقرار کامل: کلون + .env + بیلد + مهاجرت + seed + فایروال
   .\rosepsy-server-deploy.ps1 update       به‌روزرسانی از گیت‌هاب + بیلد مجدد + مهاجرت + seed تکمیلی
   .\rosepsy-server-deploy.ps1 status       وضعیت سرویس‌ها و سلامت API
   .\rosepsy-server-deploy.ps1 logs         لاگ زندهٔ API
   .\rosepsy-server-deploy.ps1 seed         دادهٔ نمونه (idempotent)
   .\rosepsy-server-deploy.ps1 seed-reset   پاک‌سازی کامل + بازسازی دادهٔ نمونه
   .\rosepsy-server-deploy.ps1 backup       بکاپ دیتابیس
   .\rosepsy-server-deploy.ps1 doctor       تشخیص WSL2/مجازی‌سازی/Docker (خروجی را برای پشتیبانی بفرستید)
   .\rosepsy-server-deploy.ps1 help         این راهنما

 گواهی رایگان HTTPS (دامنهٔ جایگزین sslip.io برای IP ثابت):
   .\rosepsy-server-tls.ps1                 راه‌اندازی Caddy + Let's Encrypt
   .\rosepsy-server-tls.ps1 status          وضعیت گواهی و لاگ Caddy
   .\rosepsy-server-tls.ps1 tls -Domain example.com     پس از خرید دامنهٔ واقعی

 پارامترها: -RepoUrl -InstallDir -Port -Token -SkipSeed
 آدرس پس از استقرار: http://SERVER-IP:8080/panel/
'@
}

# ---------------------- اجرای اصلی ----------------------
try {
    switch ($Mode) {
        'setup'      { Invoke-Setup }
        'deploy'     { Invoke-Deploy }
        'update'     { Invoke-Deploy -UpdateOnly }
        'seed'       { Invoke-Seed }
        'seed-reset' { Invoke-Seed -Reset }
        'status'     { Show-Status }
        'logs'       { Show-Logs }
        'backup'     { Invoke-Backup }
        'doctor'     { Invoke-Doctor }
        default      { Show-Help }
    }
    exit 0
} catch {
    Write-Host ''
    Write-Err2 "خطا: $($_.Exception.Message)"
    Write-Warn2 "لاگ کامل: $LogFile"
    Write-Warn2 'در صورت مشکل موتور Docker: Docker Desktop را دستی باز کنید و پس از آماده‌شدن، دستور را دوباره اجرا کنید.'
    exit 1
}
