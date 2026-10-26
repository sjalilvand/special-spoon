#requires -Version 5.1
# ============================================================================
#  rosepsy-server-native.ps1  -  نسخهٔ ۱.۰.۷ (Plan B)
#  استقرار «بومی» Rosepsy روی Windows Server بدون Docker و بدون مجازی‌سازی
#  ---------------------------------------------------------------------------
#  پیش‌زمینه: Hyper-V/WSL2 روی این VPS غیرفعال است (رویداد ID 41 از
#  Hyper-V-Hypervisor: VMX در BIOS لایهٔ زیرین فعال نیست) و Docker Desktop
#  رسماً از Windows Server پشتیبانی نمی‌کند. بنابراین همهٔ سرویس‌ها به‌صورت
#  سرویس ویندوزی بومی نصب می‌شوند؛ دانلودها ترجیحاً از GitHub Releases.
#
#  جدول پورت‌ها (قابل تغییر با پارامترها؛ همهٔ سرویس‌های داخلی فقط 127.0.0.1):
#     80 / 443        Caddy           عمومی (وب + API)  <- تنها پورت‌های عمومی
#     8000            uvicorn API     127.0.0.1   -ApiPort
#     5432            PostgreSQL      127.0.0.1   -DbPort
#     6379            Redis           127.0.0.1   -RedisPort
#     3310            ClamAV clamd    127.0.0.1   -ClamavPort
#     9000/9001       MinIO (اختیاری) 127.0.0.1   -MinioPort / -MinioConsolePort
#
#  اگر قصد اجرای برنامه‌های دیگر روی همین سرور را دارید، ابتدا:
#     powershell -ExecutionPolicy Bypass -File .\rosepsy-server-native.ps1 -Mode doctor
#  سپس پورت‌های اشغالی را ببینید و در صورت تداخل، پورت دلخواه را با پارامتر بدهید.
#
#  مثال اجرا (PowerShell مدیر):
#     $f = "$env:TEMP\rosepsy-server-native.ps1"
#     irm https://raw.githubusercontent.com/sjalilvand/special-spoon/main/deploy/rosepsy-server-native.ps1 -OutFile $f
#     powershell -ExecutionPolicy Bypass -File $f -Mode doctor
#     powershell -ExecutionPolicy Bypass -File $f -Mode setup
#
#  حالت‌ها: doctor | setup | upgrade | backup | status
# ============================================================================
param(
    [ValidateSet('doctor','setup','upgrade','backup','status')]
    [string]$Mode = 'setup',
    [string]$BaseDir = 'C:\rosepsy',
    [string]$RepoUrl = 'https://github.com/sjalilvand/special-spoon.git',
    [string]$RepoBranch = 'main',
    [string]$Domain = '130.185.73.157.sslip.io',
    [int]$DbPort = 5432,
    [int]$ApiPort = 8000,
    [int]$RedisPort = 6379,
    [int]$ClamavPort = 3310,
    [int]$WebHttpPort = 80,
    [int]$WebHttpsPort = 443,
    [string]$PipIndexUrl = '',
    [string]$NpmRegistry = '',
    [switch]$SkipFrontendBuild,
    [switch]$SkipClamav,
    [switch]$SkipRedis,
    [switch]$SkipGitInstall
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# ---------- ثابت‌ها (نسخه‌های پین‌شده، هماهنگ با compose.yml) ----------
$VER = @{
    pgInstaller = 'https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64.exe'
    pgZip       = 'https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip'
    python      = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'
    node        = 'https://nodejs.org/dist/v22.12.0/node-v22.12.0-win-x64.zip'
    git         = 'https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe'
    winsw       = 'https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe'
    clamav      = 'https://github.com/Cisco-Talos/clamav/releases/download/clamav-1.4.6/clamav-1.4.6.win.x64.msi'
    redisMsi    = 'https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.msi'
    mc          = 'https://github.com/minio/mc/releases/download/RELEASE.2025-08-13T08-35-41Z/mc.windows-amd64.RELEASE.2025-08-13T08-35-41Z.exe'
    caddy       = 'https://github.com/caddyserver/caddy/releases/latest/download/caddy_windows_amd64.exe'
}
$PGBin   = "$BaseDir\runtime\pgsql\bin"
$VenvPy  = "$BaseDir\runtime\venv\Scripts\python.exe"
$AppDir  = "$BaseDir\app"
$DlDir   = "$BaseDir\downloads"
$SvcDir  = "$BaseDir\services"
$LogDir  = "$BaseDir\logs"
$DataDir = "$BaseDir\data"
$EtcDir  = "$BaseDir\etc"

# ---------- ابزارهای لاگ و کمکی ----------
function Write-Step([string]$msg) { Write-Host ''; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Warn2([string]$msg){ Write-Host "  [هشدار] $msg" -ForegroundColor Yellow }
function Write-Err2([string]$msg) { Write-Host "  [خطا]  $msg" -ForegroundColor Red }

function New-RandomHex([int]$bytes = 32) {
    $b = New-Object byte[] $bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($b); $rng.Dispose()
    return ([System.BitConverter]::ToString($b)).Replace('-','').ToLower()
}
function New-RandomPass([int]$len = 24) {
    $set = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789!@#%^*'
    $b = New-Object byte[] $len
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($b); $rng.Dispose()
    $out = ''
    for ($i = 0; $i -lt $len; $i++) { $out += $set[$b[$i] % $set.Length] }
    return $out
}
function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'این اسکریپت باید در PowerShell «Run as Administrator» اجرا شود.'
    }
}
function Invoke-Download([string]$url, [string]$dest, [int]$maxMb = 800) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $curlOk = $true
    try {
        & curl.exe -sSL --retry 3 --retry-delay 2 --connect-timeout 30 --max-time 1800 -o "$dest.part" $url 2>$null
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$dest.part")) { $curlOk = $false }
    } catch { $curlOk = $false }
    if (-not $curlOk) {
        Write-Warn2 "curl ناموفق؛ تلاش با Invoke-WebRequest: $url"
        Invoke-WebRequest -Uri $url -OutFile "$dest.part" -UseBasicParsing -TimeoutSec 1800
    }
    $size = (Get-Item "$dest.part").Length
    if ($size -lt 1000) { throw "فایل دانلودشده بیش‌ازحد کوچک است ($size بایت): $url" }
    if ($size -gt ($maxMb * 1MB)) { throw "فایل دانلودشده بیش‌ازحد بزرگ است: $url" }
    Move-Item "$dest.part" $dest -Force
    $sw.Stop()
    Write-Ok ("دانلود شد: {0}  ({1:N1} MB، {2:N0} ثانیه)" -f (Split-Path $dest -Leaf), ($size/1MB), $sw.Elapsed.TotalSeconds)
    return $dest
}
function Expand-Pkg([string]$zip, [string]$dest) {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    & tar.exe -xf $zip -C $dest
    if ($LASTEXITCODE -ne 0) { Expand-Archive -Path $zip -DestinationPath $dest -Force }
}
# خواندن فایل .env به دیکشنری
function Read-EnvMap([string]$path) {
    $map = @{}
    if (-not (Test-Path $path)) { return $map }
    foreach ($ln in Get-Content $path -Encoding UTF8) {
        if ($ln -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $map[$Matches[1]] = $Matches[2].Trim()
        }
    }
    return $map
}
# نوشتن/به‌روزرسانی یک کلید در فایل .env (مقدار موجود حفظ می‌شود)
function Set-EnvKey([string]$path, [string]$key, [string]$value) {
    $lines = @()
    if (Test-Path $path) { $lines = @(Get-Content $path -Encoding UTF8) }
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match ('^\s*' + [regex]::Escape($key) + '\s*=')) {
            $lines[$i] = "$key=$value"; $found = $true; break
        }
    }
    if (-not $found) { $lines += "$key=$value" }
    [System.IO.File]::WriteAllLines($path, $lines)
}
# اجرای دستور با کنترل کد خروج
function Invoke-Native([string]$exe, [string[]]$argList, [string]$okMsg) {
    & $exe @argList
    if ($LASTEXITCODE -ne 0) { throw "اجرای ناموفق: $exe $($argList -join ' ')  (کد $LASTEXITCODE)" }
    if ($okMsg) { Write-Ok $okMsg }
}

# خواندن امنِ کد خروج پروسهٔ Start-Process (رفع اشکال ۱.۰.۶)
# PS 5.1: در برخی اجراها p.ExitCode حتی پس از پایان پروسه تهی برمی‌گردد؛
# نمونهٔ واقعی روی Windows Server 2025: پیام «کد  برگرداند» با کد خالی،
# در حالی که لاگ خود نصاب می‌گفت Installation completed / Exiting with code 0.
# فراخوانی WaitForExit بدون پارامتر کد خروج را نهایی می‌کند؛ تهی یعنی «نامشخص»،
# پس در تماس‌گیرنده‌ها ملاک، ردپای واقعی نصب است نه صرف کد خروج.
function Get-ExitCode($p) {
    if ($null -eq $p) { return $null }
    try { $null = $p.WaitForExit() } catch {}
    try { return $p.ExitCode } catch { return $null }
}

# پروب سریع HTTP برای انتخاب خودکار مخزن (هر وضعیت زیر ۵۰۰ یعنی «قابل دسترسی»)
function Test-HttpOk([string]$url, [int]$sec = 15) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $sec
        return ($r.StatusCode -gt 0 -and $r.StatusCode -lt 500)
    } catch {
        $sc = 0
        try { if ($_.Exception.Response) { $sc = [int]$_.Exception.Response.StatusCode } } catch {}
        return ($sc -gt 0 -and $sc -lt 500)
    }
}

# ---------- پورت‌ها: جدول شنونده‌ها + سدِ تداخل ----------
$ReservedPorts = @($WebHttpPort, $WebHttpsPort, $ApiPort, $DbPort, $RedisPort, $ClamavPort)

function Get-ListenerTable {
    $rows = @()
    try {
        $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue
        $procMap = @{}
        foreach ($p in Get-Process -ErrorAction SilentlyContinue) { $procMap[$p.Id] = $p.ProcessName }
        foreach ($c in ($conns | Sort-Object LocalPort -Unique)) {
            $pn = '<system>'
            if ($procMap.ContainsKey([int]$c.OwningProcess)) { $pn = $procMap[[int]$c.OwningProcess] }
            $addr = $c.LocalAddress
            $scope = 'loopback'
            if ($addr -eq '0.0.0.0' -or $addr -eq '::') { $scope = 'PUBLIC!' }
            $rows += [pscustomobject]@{ Port = $c.LocalPort; Address = $addr; Scope = $scope; Process = $pn; PID = $c.OwningProcess }
        }
    } catch { Write-Warn2 "خواندن جدول پورت‌ها ناموفق: $($_.Exception.Message)" }
    return $rows
}

# سرویس‌هایی که خودِ Rosepsy می‌شناسد؛ سدِ پورت برای آن‌ها اعمال نمی‌شود (به‌جای آن resume می‌کنیم)
$OwnSvcNames = @('rosepsy-pg','rosepsy-api','rosepsy-caddy','rosepsy-clamd','rosepsy-freshclam','Redis')

function Test-PortHeldByUs([int]$port) {
    # اگر پورت را سرویس‌های خودِ Rosepsy نگه داشته باشند برچسب خودی برمی‌گرداند؛ وگرنه $null
    $hit = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $hit) { return $null }
    $opid = [int]$hit.OwningProcess
    # ۱) سرویس‌های بومی (PostgreSQL/Redis) خودشان شنونده‌اند؛ PID مستقیم به سرویس می‌رسد
    $svc = $null
    try { $svc = Get-CimInstance Win32_Service -Filter ("ProcessId = {0}" -f $opid) -ErrorAction Stop | Select-Object -First 1 } catch {}
    if ($svc) {
        $nm = [string]$svc.Name
        if ($OwnSvcNames -contains $nm) { return $nm }
        if (($nm -like 'postgres*') -and (([string]$svc.PathName) -like ("*{0}\runtime\pgsql*" -f $BaseDir))) { return $nm }
        if (($nm -like 'rosepsy-*') -or ($nm -eq 'Redis')) { return $nm }
    }
    # ۲) فرایندِ فرزند WinSW شنونده است نه خود WinSW (uvicorn/caddy/clamd)؛ پس با مسیر باینری تشخیص می‌دهیم
    $exep = try { (Get-Process -Id $opid -ErrorAction Stop).Path } catch { $null }
    if ($exep) {
        if ($exep -like ("{0}\runtime\*" -f $BaseDir)) { return 'سرویس‌های Rosepsy (runtime)' }
        if ($exep -like 'C:\Program Files\ClamAV\*') { return 'rosepsy-clamd' }
    }
    return $null
}

function Test-ReservedPortsFree {
    $busy = @()
    foreach ($rp in ($ReservedPorts | Select-Object -Unique)) {
        $hit = Get-NetTCPConnection -State Listen -LocalPort $rp -ErrorAction SilentlyContinue
        if ($hit) { $busy += $rp }
    }
    if ($busy.Count -eq 0) {
        Write-Ok ('پورت‌های رزرو Rosepsy آزادند: ' + (($ReservedPorts | Select-Object -Unique) -join ', '))
        return
    }
    # تفاوت ۱.۰.۷: پورت‌هایی که سرویس‌های خودِ اجرای قبلی نگه داشته‌اند «سد» نیستند؛
    # اجرای مجدد به‌صورت «ادامهٔ نصب» (resume) پیش می‌رود، نه شکست.
    $foreign = @()
    foreach ($b in $busy) {
        $ours = Test-PortHeldByUs $b
        if ($ours) {
            Write-Ok ("پورت {0} در اختیار سرویس خودِ Rosepsy («{1}») است - اجرا به‌صورت ادامهٔ نصب پیش می‌رود" -f $b, $ours)
        } else { $foreign += $b }
    }
    if ($foreign.Count -eq 0) { return }
    Write-Err2 'پورت‌های زیر را فرایندهای خارج از Rosepsy اشغال کرده‌اند:'
    $anyPg = $false
    foreach ($b in $foreign) {
        $conn = Get-NetTCPConnection -State Listen -LocalPort $b -ErrorAction SilentlyContinue | Select-Object -First 1
        $opid = 0; $pname = '?'; $svcName = ''
        if ($conn) {
            $opid = [int]$conn.OwningProcess
            $pname = try { (Get-Process -Id $opid -ErrorAction Stop).ProcessName } catch { '?' }
            try {
                $s2 = Get-CimInstance Win32_Service -Filter ("ProcessId = {0}" -f $opid) -ErrorAction Stop | Select-Object -First 1
                if ($s2) { $svcName = [string]$s2.Name; if ($svcName -like 'postgres*') { $anyPg = $true } }
            } catch {}
        }
        if ($svcName) { Write-Err2 ("   پورت {0}  <-  فرایند: {1} (PID {2})  [سرویس: {3}]" -f $b, $pname, $opid, $svcName) }
        else { Write-Err2 ("   پورت {0}  <-  فرایند: {1} (PID {2})" -f $b, $pname, $opid) }
    }
    Write-Host ''
    Write-Host '  راه‌حل‌ها:' -ForegroundColor White
    Write-Host '   1) اگر آن فرایند متعلق به برنامهٔ دیگری است، پورت Rosepsy را عوض کنید؛ مثال:'
    Write-Host '      powershell -File rosepsy-server-native.ps1 -Mode setup -DbPort 5433 -ApiPort 8010'
    Write-Host '   2) یا فرایند/سرویس اشغالکننده را متوقف کنید و دوباره اجرا کنید'
    if ($anyPg) {
        Write-Host '   3) اگر PostgreSQL قدیمی دیگری است (مثلاً postgresql-x64-16):'
        Write-Host '      Stop-Service postgresql-x64-16; Set-Service postgresql-x64-16 -StartupType Manual'
    }
    exit 1
}

function Invoke-Doctor {
    Write-Step 'حالت doctor - بررسی پیش‌شرط‌های استقرار بومی'
    Assert-Admin
    $os = Get-CimInstance Win32_OperatingSystem
    Write-Ok ("OS: {0}  |  RAM: {1:N1} GB  |  دیسک C: آزاد {2:N0} GB" -f $os.Caption, ($os.TotalVisibleMemorySize/1MB), ((Get-PSDrive C).Free/1GB))
    $arch = $env:PROCESSOR_ARCHITECTURE
    Write-Ok "معماری: $arch (استقرار بومی به مجازی‌سازی/VMX نیازی ندارد)"
    foreach ($t in 'curl.exe','tar.exe') {
        if (Get-Command $t -ErrorAction SilentlyContinue) { Write-Ok "$t موجود است" } else { Write-Warn2 "$t یافت نشد" }
    }
    Write-Step 'جدول پورت‌های شنوندهٔ فعلی (برای برنامه‌های دیگر شما هم مفید است)'
    $rows = Get-ListenerTable
    if ($rows.Count -eq 0) { Write-Host '  (هیچ شنونده‌ای یافت نشد)' }
    $rows | Format-Table Port, Address, Scope, Process, PID -AutoSize | Out-Host
    $pub = $rows | Where-Object { $_.Scope -eq 'PUBLIC!' }
    if ($pub) {
        Write-Warn2 ('پورت‌های عمومی فعلی: ' + (($pub | ForEach-Object { "$($_.Port)($($_.Process))" }) -join ', '))
    }
    Write-Step 'سدِ تداخل پورت‌های پیش‌فرض Rosepsy'
    Test-ReservedPortsFree
    Write-Step 'سرویس‌های Rosepsy موجود (اگر قبلاً نصب شده باشند)'
    Get-Service -Name 'rosepsy-*' -ErrorAction SilentlyContinue | Format-Table Name, Status, StartType -AutoSize | Out-Host
    if (Get-Service -Name 'Redis' -ErrorAction SilentlyContinue) { Write-Ok 'سرویس Redis از قبل نصب است' }
    Write-Host ''
    Write-Host 'نتیجه: اگر موارد بالا [OK] بودند، اجرای «-Mode setup» مجاز است.' -ForegroundColor Cyan
    Write-Host ('پورت‌هایی که Rosepsy رزرو می‌کند (قابل تغییر با پارامتر): ' + (($ReservedPorts | Select-Object -Unique) -join ', ')) -ForegroundColor Cyan
}

# ---------- کارخانهٔ سرویس‌ساز WinSW (همهٔ سرویس‌ها Automatic + ری‌استارت خودکار) ----------
function New-WinSvc {
    param(
        [string]$Name, [string]$DisplayName, [string]$Description,
        [string]$Exe, [string]$ArgsStr, [string]$WorkDir,
        [hashtable]$EnvMap = @{}
    )
    $dir = Join-Path $SvcDir $Name
    New-Item -ItemType Directory -Force -Path $dir, (Join-Path $LogDir $Name) | Out-Null
    if (-not (Test-Path "$BaseDir\tools\WinSW-x64.exe")) { throw 'WinSW-x64.exe یافت نشد' }
    Copy-Item "$BaseDir\tools\WinSW-x64.exe" (Join-Path $dir "$Name.exe") -Force
    $envXml = ''
    foreach ($k in $EnvMap.Keys) {
        $v = [System.Security.SecurityElement]::Escape([string]$EnvMap[$k])
        $envXml += "<env name=`"$k`" value=`"$v`" />"
    }
    $exeE  = [System.Security.SecurityElement]::Escape($Exe)
    $argE  = [System.Security.SecurityElement]::Escape($ArgsStr)
    $dirE  = [System.Security.SecurityElement]::Escape((Join-Path $LogDir $Name))
    $workE = [System.Security.SecurityElement]::Escape($WorkDir)
    $xml = @"
<service>
  <id>$Name</id>
  <name>$DisplayName</name>
  <description>$Description</description>
  <executable>$exeE</executable>
  <arguments>$argE</arguments>
  <workingdirectory>$workE</workingdirectory>
  <startmode>Automatic</startmode>
  <delayedautostart>false</delayedautostart>
  <onfailure action="restart" delay="10 sec"/>
  <onfailure action="restart" delay="30 sec"/>
  <resetfailure>1 hour</resetfailure>
  <log mode="roll-by-size">
    <logpath>$dirE</logpath>
    <sizeThreshold>10240</sizeThreshold>
    <keepFiles>4</keepFiles>
  </log>
  $envXml
</service>
"@
    [System.IO.File]::WriteAllText((Join-Path $dir "$Name.xml"), $xml, (New-Object System.Text.UTF8Encoding($false)))
    if (-not (Get-Service -Name $Name -ErrorAction SilentlyContinue)) {
        & (Join-Path $dir "$Name.exe") install | Out-Null
    }
    Write-Ok ("سرویس ویندوزی «{0}» آماده شد" -f $Name)
    return (Join-Path $dir "$Name.exe")
}
function Start-WinSvc([string]$Name) {
    if ((Get-Service -Name $Name).StartType -eq 'Disabled') { Set-Service $Name -StartupType Automatic }
    Start-Service -Name $Name
    (Get-Service -Name $Name).WaitForStatus('Running', '00:01:00')
    Write-Ok ("سرویس «{0}» در حال اجراست" -f $Name)
}

# اعطای حق «Log on as a service» به حساب سرویس (با LSA API). بدون این حق،
# Start-Service برای حساب محلی معمولی با خطای 1069 (logon failure) ترک می‌خورد.
function Grant-ServiceLogonRight([string]$userName) {
    try {
        $src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class LsaRights {
    [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    private static extern bool LookupAccountName(string system, string account, byte[] sid, ref int sidSize, StringBuilder refDomain, ref int refSize, out int use);
    [DllImport("advapi32.dll", SetLastError=true)]
    private static extern int LsaOpenPolicy(IntPtr system, ref LSA_OBJECT_ATTRIBUTES attrs, int access, out IntPtr policy);
    [DllImport("advapi32.dll", SetLastError=true)]
    private static extern int LsaAddAccountRights(IntPtr policy, byte[] sid, LSA_UNICODE_STRING[] rights, int count);
    [DllImport("advapi32.dll")]
    private static extern int LsaClose(IntPtr policy);
    [StructLayout(LayoutKind.Sequential)]
    private struct LSA_OBJECT_ATTRIBUTES {
        public int Length; public IntPtr RootDirectory; public IntPtr ObjectName;
        public int Attributes; public IntPtr SecurityDescriptor; public IntPtr SecurityQualityOfService;
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct LSA_UNICODE_STRING { public ushort Length; public ushort MaximumLength; public IntPtr Buffer; }
    public static void AddServiceLogon(string account) {
        byte[] sid = new byte[68]; int sidSize = sid.Length;
        StringBuilder dom = new StringBuilder(256); int domSize = dom.Capacity; int use;
        if (!LookupAccountName(null, account, sid, ref sidSize, dom, ref domSize, out use))
            throw new Exception("LookupAccountName failed: " + Marshal.GetLastWin32Error());
        LSA_OBJECT_ATTRIBUTES oa = new LSA_OBJECT_ATTRIBUTES();
        oa.Length = Marshal.SizeOf(typeof(LSA_OBJECT_ATTRIBUTES));
        IntPtr policy;
        int st = LsaOpenPolicy(IntPtr.Zero, ref oa, 0x00000800 | 0x00000010, out policy);
        if (st != 0) throw new Exception("LsaOpenPolicy: 0x" + st.ToString("X"));
        try {
            string right = "SeServiceLogonRight";
            LSA_UNICODE_STRING lsa = new LSA_UNICODE_STRING();
            lsa.Buffer = Marshal.StringToHGlobalUni(right);
            lsa.Length = (ushort)(right.Length * 2);
            lsa.MaximumLength = (ushort)((right.Length + 1) * 2);
            int r = LsaAddAccountRights(policy, sid, new LSA_UNICODE_STRING[] { lsa }, 1);
            Marshal.FreeHGlobal(lsa.Buffer);
            if (r != 0) throw new Exception("LsaAddAccountRights: 0x" + r.ToString("X"));
        } finally { LsaClose(policy); }
    }
}
'@
        if (-not ('LsaRights' -as [type])) { Add-Type -TypeDefinition $src -Language CSharp }
        [LsaRights]::AddServiceLogon($userName)
        Write-Ok ("حق «Log on as a service» به {0} داده شد" -f $userName)
    } catch { Write-Warn2 ("اعطای حق سرویس به {0} ناموفق ماند: {1}" -f $userName, $_.Exception.Message) }
}

# ---------- رمز superuser و مسیر دادهٔ PostgreSQL (پشتیبانی اجرای مجدد - ۱.۰.۷) ----------
# datadir واقعی را از خط فرمان سرویس برمی‌تاباند (-D "...") تا اگر نصاب مسیر دیگری ساخته باشد هم درست کار کند
function Get-PgDataDir([string]$svcName) {
    $dd = "$DataDir\pgdata"
    try {
        $svc = Get-CimInstance Win32_Service -Filter ("Name = '{0}'" -f $svcName) -ErrorAction Stop | Select-Object -First 1
        if ($svc -and $svc.PathName -match '-D\s+"([^"]+)"') { $dd = $Matches[1] }
    } catch {}
    return $dd
}
# رمز superuser در فایل محافظت‌شده ذخیره می‌شود تا اجرای مجدد idempotent بماند
function Set-PgSuperPassFile([string]$pass) {
    New-Item -ItemType Directory -Force -Path $EtcDir | Out-Null
    $f = "$EtcDir\pg-superpass.txt"
    [System.IO.File]::WriteAllText($f, $pass, (New-Object System.Text.UTF8Encoding($false)))
    # فقط Administrators و SYSTEM؛ با SID معروف تا به نام‌های محلی‌سازی‌شده وابسته نباشد
    icacls $f /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null
}
function Resolve-PgSuperPass {
    $f = "$EtcDir\pg-superpass.txt"
    if (Test-Path $f) {
        $p = ''
        try { $p = (Get-Content $f -Raw -ErrorAction Stop) } catch {}
        if ($p) { $p = $p.Trim() }
        if ($p) { Write-Ok 'رمز superuser PostgreSQL از فایل محافظت‌شده خوانده شد'; return $p }
    }
    $p = New-RandomHex 12
    Set-PgSuperPassFile $p
    return $p
}
# بازنشانی رمز postgres با trust موقت (وقتی رمزِ به‌جامانده از اجرای نیمه‌کارهٔ قبل در دسترس نیست)
function Reset-PgSuperPass([string]$superPass, [string]$svcName) {
    $hba = Join-Path (Get-PgDataDir $svcName) 'pg_hba.conf'
    if (-not (Test-Path $hba)) { throw ("pg_hba.conf یافت نشد: {0} (خوشهٔ دادهٔ PostgreSQL قابل شناسایی نیست)" -f $hba) }
    Copy-Item $hba "$hba.rosepsy-bak" -Force
    $lines = @('host all postgres 127.0.0.1/32 trust') + @(Get-Content $hba)
    [System.IO.File]::WriteAllLines($hba, $lines)
    try {
        Restart-Service $svcName -ErrorAction Stop
        (Get-Service $svcName).WaitForStatus('Running', '00:01:00')
        Start-Sleep 2
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
        & "$PGBin\psql.exe" -U postgres -h 127.0.0.1 -p $DbPort -v ON_ERROR_STOP=1 -c ("ALTER USER postgres PASSWORD '{0}';" -f $superPass) | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'ALTER USER در حالت trust ناموفق بود' }
        Write-Ok 'رمز superuser بازنشانی شد (pg_hba به حالت قبل برگشت)'
    } finally {
        Copy-Item "$hba.rosepsy-bak" $hba -Force
        try {
            Restart-Service $svcName -ErrorAction SilentlyContinue
            (Get-Service $svcName).WaitForStatus('Running', '00:01:00')
            Start-Sleep 2
        } catch {}
    }
}
# مسیر مشترکِ «راه‌اندازی سرویس + اتصال + هم‌راستاسازی پیکربندی» برای نصب تازه و اجرای مجدد
function Ensure-PgRunning([string]$superPass) {
    $svcName = 'rosepsy-pg'
    if (-not (Get-Service -Name $svcName -ErrorAction SilentlyContinue)) {
        # اگر نصاب EDB نام سرویس دیگری ثبت کرده اما مسیرش همان runtime ماست، همان را به کار می‌بریم
        $alt = Get-CimInstance Win32_Service -ErrorAction SilentlyContinue |
            Where-Object { (([string]$_.PathName) -like ("*{0}\runtime\pgsql*" -f $BaseDir)) -and (([string]$_.Name) -like 'postgres*') } |
            Select-Object -First 1
        if ($alt) { $svcName = [string]$alt.Name; Write-Warn2 ("سرویس PostgreSQL با نام «{0}» یافت شد و به‌کار گرفته می‌شود" -f $svcName) }
        else { throw 'سرویس rosepsy-pg ساخته نشد' }
    }
    Start-WinSvc $svcName
    # صف اتصال اول ممکن است چند ثانیه طول بکشد
    $ok = $false
    for ($i = 0; $i -lt 15; $i++) {
        try {
            $env:PGPASSWORD = $superPass
            & "$PGBin\psql.exe" -U postgres -h 127.0.0.1 -p $DbPort -c 'SELECT version();' | Out-Null
            if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        } catch { Start-Sleep 2 }
        Start-Sleep 2
    }
    # اگر رمزِ به‌جامانده از اجرای نیمه‌کاره گم شده باشد، با trust موقت بازنشانی می‌شود
    if (-not $ok) {
        Write-Warn2 'اتصال با رمز فعلی برقرار نشد - بازنشانی رمز superuser با trust موقت...'
        Reset-PgSuperPass -superPass $superPass -svcName $svcName
        for ($i = 0; $i -lt 10; $i++) {
            try {
                $env:PGPASSWORD = $superPass
                & "$PGBin\psql.exe" -U postgres -h 127.0.0.1 -p $DbPort -c 'SELECT version();' | Out-Null
                if ($LASTEXITCODE -eq 0) { $ok = $true; break }
            } catch { Start-Sleep 2 }
            Start-Sleep 2
        }
    }
    if (-not $ok) { throw 'اتصال به PostgreSQL حتی پس از بازنشانی رمز برقرار نشد' }
    # نصاب EDB پیش‌فرض listen_addresses='*' می‌گذارد؛ فقط-لوکال بودن تضمین می‌شود
    $conf = Join-Path (Get-PgDataDir $svcName) 'postgresql.conf'
    if (Test-Path $conf) {
        $ctxt = [System.IO.File]::ReadAllText($conf)
        $changed = $false
        if ($ctxt -match "(?m)^\s*listen_addresses\s*=\s*'([^']*)'") {
            if ($Matches[1] -ne '127.0.0.1') {
                $ctxt = $ctxt -replace "(?m)^(\s*)listen_addresses\s*=\s*'[^']*'", "`$1listen_addresses = '127.0.0.1'"
                $changed = $true
            }
        } else {
            $ctxt += "`nlisten_addresses = '127.0.0.1'"
            $changed = $true
        }
        if ($ctxt -match "(?m)^\s*port\s*=\s*(\d+)\s*$") {
            if ([int]$Matches[1] -ne $DbPort) {
                $ctxt = $ctxt -replace "(?m)^(\s*)port\s*=\s*\d+", ("`$1port = {0}" -f $DbPort)
                $changed = $true
            }
        } else {
            $ctxt += ("`nport = {0}" -f $DbPort)
            $changed = $true
        }
        if ($changed) {
            [System.IO.File]::WriteAllText($conf, $ctxt)
            Write-Warn2 'listen_addresses/port در postgresql.conf هم‌راستا شد - سرویس یک‌بار دیگر راه‌اندازی می‌شود'
            Restart-Service $svcName -ErrorAction SilentlyContinue
            try { (Get-Service $svcName).WaitForStatus('Running', '00:01:00') } catch {}
            Start-Sleep 2
        }
    }
    Set-PgSuperPassFile $superPass
    Write-Ok ("PostgreSQL روی 127.0.0.1:{0} پاسخ می‌دهد" -f $DbPort)
}
# ---------- گام ۴: PostgreSQL 16 ----------
function Install-PostgreSQL([string]$superPass) {
    Write-Step 'گام ۴: PostgreSQL 16 (سرویس ویندوزی rosepsy-pg، فقط 127.0.0.1)'
    if (Get-Service -Name 'rosepsy-pg' -ErrorAction SilentlyContinue) {
        Write-Ok 'سرویس rosepsy-pg از قبل نصب است - نصب دوباره رد شد'
        Ensure-PgRunning -superPass $superPass
        return
    }
    $msiDone = $false
    try {
        Write-Host '  مسیر اصلی: نصب‌کنندهٔ رسمی EDB در حالت بی‌صدا (چند دقیقه طول می‌کشد)...'
        $pkg = Invoke-Download $VER.pgInstaller "$DlDir\pg-installer.exe" 500
        # نکتهٔ PS 5.1: در ArgumentList آرایه‌ای، رشته‌های دارای فاصله بدون گیومه
        # ارسال می‌شوند؛ «NT AUTHORITY\NetworkService» به دو پارامتر می‌شکند و نصاب
        # با خطای Expected option but got "AUTHORITY\NetworkService" می‌میرد.
        # راه‌حل: ساخت یک رشتهٔ واحد با گیومهٔ داخلی و ارسال آن به‌صورت یک‌جا.
        $pgArgs = (
            '--mode unattended',
            '--unattendedmodeui none',
            ('--superpassword "{0}"' -f $superPass),
            '--servicename "rosepsy-pg"',
            '--serviceaccount "NT AUTHORITY\NetworkService"',
            ('--serverport {0}' -f $DbPort),
            ('--prefix "{0}"' -f "$BaseDir\runtime\pgsql"),
            ('--datadir "{0}"' -f "$DataDir\pgdata"),
            '--locale C',
            '--enable-components server,commandlinetools',
            '--disable-components pgAdmin,stackbuilder'
        ) -join ' '
        # با تایم‌اوت منتظر بمان تا اگر نصاب روی پنجره‌ای قفل شد، اسکریپت بی‌پایان نماند
        $p = Start-Process -FilePath $pkg -ArgumentList $pgArgs -PassThru -NoNewWindow
        if (-not $p.WaitForExit(15 * 60 * 1000)) {
            try { $p.Kill() } catch {}
            throw 'نصب‌کنندهٔ EDB بیش از ۱۵ دقیقه معطل ماند (احتمالاً پنجرهٔ پنهان) - به مسیر جایگزین می‌رویم'
        }
        # رفع اشکال ۱.۰.۶: ملاکِ موفقیت، ردپای نصب است (باینری + خوشهٔ داده + سرویس)
        # نه کد خروجی که در PS 5.1 گاهی تهی برمی‌گردد و شکست کاذب می‌سازد
        $code = Get-ExitCode $p
        $binOk  = (Test-Path "$PGBin\postgres.exe")
        $dataOk = (Test-Path "$DataDir\pgdata\PG_VERSION")
        $svcOk  = ($null -ne (Get-Service -Name 'rosepsy-pg' -ErrorAction SilentlyContinue))
        if ($binOk -and $dataOk -and $svcOk) {
            if ($code -ne 0) { Write-Warn2 ("کد خروج نصاب خوانده نشد ({0}) اما ردپای نصب کامل است - ادامه" -f $code) }
        } else {
            throw ("نصب‌کنندهٔ EDB ناموفق (کد: {0}، باینری: {1}، خوشهٔ داده: {2}، سرویس: {3})" -f $code, $binOk, $dataOk, $svcOk)
        }
        $msiDone = $true
        Write-Ok 'PostgreSQL با نصب‌کنندهٔ EDB نصب شد'
    } catch {
        Write-Warn2 ("نصب‌کنندهٔ EDB ناموفق: {0}" -f $_.Exception.Message)
        # لاگ نصب‌کنندهٔ EDB (BitRock) برای عیب‌یابی
        # فرایند رهاشدهٔ نصاب (پنجرهٔ خطای بازمانده) بسته شود
        Get-Process -Name 'postgresql-*' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        $edblog = Join-Path $env:TEMP 'install-postgresql.log'
        if (Test-Path $edblog) {
            Write-Warn2 'آخرین خطوط لاگ نصب‌کنندهٔ EDB:'
            Get-Content $edblog -Tail 12 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" }
        }
        # رفع اشکال ۱.۰.۶: اگر با وجود این خطا نصب EDB کامل شده باشد (سناریوی «کد خالی»)
        # مسیر جایگزین اجرا نمی‌شود و از همین نصب استفاده می‌شود
        $edbOk = (Test-Path "$PGBin\postgres.exe") -and (Test-Path "$DataDir\pgdata\PG_VERSION") -and ($null -ne (Get-Service -Name 'rosepsy-pg' -ErrorAction SilentlyContinue))
        if ($edbOk) {
            Write-Ok 'با وجود خطای بالا، ردپای نصب کامل EDB پیدا شد (باینری + خوشهٔ داده + سرویس) - از همین نصب استفاده می‌شود'
        } else {
        Write-Host '  مسیر جایگزین: باینری Zip رسمی EDB + initdb دستی...'
        if (-not (Test-Path "$PGBin\initdb.exe")) {
            $zip = Invoke-Download $VER.pgZip "$DlDir\pg-bin.zip" 600
            $pgzRoot = "$BaseDir\runtime\pgz"
            if (Test-Path $pgzRoot) { Remove-Item $pgzRoot -Recurse -Force -ErrorAction SilentlyContinue }
            Expand-Pkg $zip $pgzRoot
            # ساختار zip: pgsql/... -> به runtime\pgsql منتقل شود
            # (رفع اشکال ۱.۰.۵: پیش‌تر مسیر استخراج runtime\pgz بود اما از
            #  $BaseDir\pgz بررسی می‌شد و initdb هرگز پیدا نمی‌شد)
            if (Test-Path "$pgzRoot\pgsql\bin\initdb.exe") {
                if (Test-Path "$BaseDir\runtime\pgsql") { Remove-Item "$BaseDir\runtime\pgsql" -Recurse -Force -ErrorAction SilentlyContinue }
                Move-Item "$pgzRoot\pgsql" "$BaseDir\runtime\pgsql" -Force
            } elseif (Test-Path "$pgzRoot\bin\initdb.exe") {
                if (Test-Path "$BaseDir\runtime\pgsql") { Remove-Item "$BaseDir\runtime\pgsql" -Recurse -Force -ErrorAction SilentlyContinue }
                Move-Item $pgzRoot "$BaseDir\runtime\pgsql" -Force
            }
            if (-not (Test-Path "$PGBin\initdb.exe")) { throw "باینری PostgreSQL بعد از استخراج Zip پیدا نشد" }
            # باینری‌های Zip زمان‌اجرای VC++ را به‌همراه ندارند (نصاب EDB خودش می‌گنجاند)
            if (-not (Test-Path "$env:SystemRoot\System32\vcruntime140.dll") -or -not (Test-Path "$env:SystemRoot\System32\msvcp140.dll")) {
                Write-Host '  نصب Microsoft VC++ 2015-2022 Redistributable (لازم برای باینری‌ها)...'
                try {
                    $vc = Invoke-Download 'https://aka.ms/vs/17/release/vc_redist.x64.exe' "$DlDir\vc_redist.x64.exe" 60
                    $p = Start-Process $vc -ArgumentList '/install','/quiet','/norestart' -Wait -PassThru
                    $vcode = Get-ExitCode $p
                    if ((Test-Path "$env:SystemRoot\System32\vcruntime140.dll") -and (Test-Path "$env:SystemRoot\System32\msvcp140.dll")) { Write-Ok 'VC++ Redistributable نصب شد' }
                    elseif ($null -ne $vcode -and $vcode -in @(0,1638,3010)) { Write-Ok 'VC++ Redistributable نصب شد' }
                    else { Write-Warn2 ("VC++ Redistributable وضعیت نامشخص (کد: {0})" -f $vcode) }
                } catch { Write-Warn2 'نصب VC++ ناموفق بود؛ بدون زمان‌اجرای VC++ ممکن است initdb بالا نیاید' }
            }
        } else {
            Write-Ok 'باینری‌های PostgreSQL از قبل موجودند (دانلود مجدد رد شد)'
        }
        # حساب سرویس کم‌اختیار (postgres به‌عنوان ادمین اجرا نمی‌شود)
        $pgSvcUser = 'rosepsy_pg'
        $pgSvcPass = New-RandomPass 20
        net user $pgSvcUser $pgSvcPass /add /passwordchg:no /passwordreq:yes /active:yes | Out-Null
        if ($LASTEXITCODE -ne 0) {
            # حساب از اجرای نیمه‌کارهٔ قبل مانده؛ رمز آن با مقدار تازه هم‌راستا می‌شود
            Write-Warn2 'حساب rosepsy_pg موجود بود - رمز آن هم‌راستا می‌شود'
            net user $pgSvcUser $pgSvcPass /active:yes /passwordreq:yes | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'تنظیم رمز حساب rosepsy_pg ناموفق بود' }
        }
        net user $pgSvcUser /comment:'Rosepsy PostgreSQL service account' | Out-Null
        New-Item -ItemType Directory -Force -Path "$DataDir\pgdata" | Out-Null
        icacls "$DataDir" /grant "${pgSvcUser}:(OI)(CI)F" /T | Out-Null
        # بدون حق Log on as a service، Start-Service با خطای 1069 ترک می‌خورد
        Grant-ServiceLogonRight $pgSvcUser
        if (Test-Path "$DataDir\pgdata\PG_VERSION") {
            Write-Ok 'خوشهٔ دادهٔ PostgreSQL از قبل مقداردهی شده (initdb رد شد)'
        } else {
            # initdb باید با حساب غیرادمین اجرا شود (سیاست امنیتی خود PostgreSQL)
            $pwFile = "$DataDir\pgpw.txt"
            [System.IO.File]::WriteAllText($pwFile, $superPass)
            icacls $pwFile /grant "${pgSvcUser}:R" | Out-Null
            $cred = New-Object System.Management.Automation.PSCredential(".\$pgSvcUser", (ConvertTo-SecureString $pgSvcPass -AsPlainText -Force))
            $cmd = "`"$PGBin\initdb.exe`" -D `"$DataDir\pgdata`" -U postgres -E UTF8 --locale=C -A scram-sha-256 --pwfile=`"$pwFile`" > `"$DataDir\initdb.log`" 2>&1"
            $p = Start-Process -FilePath 'cmd.exe' -ArgumentList "/c $cmd" -Credential $cred -Wait -PassThru -WindowStyle Hidden
            # رفع اشکال ۱.۰.۶: ملاک، وجود PG_VERSION است نه کد خروج (که گاهی تهی است)
            $icode = Get-ExitCode $p
            if (-not (Test-Path "$DataDir\pgdata\PG_VERSION")) {
                Get-Content "$DataDir\initdb.log" -ErrorAction SilentlyContinue | Select-Object -Last 10 | ForEach-Object { Write-Err2 $_ }
                throw ("initdb ناموفق بود (کد: {0})" -f $icode)
            }
            Remove-Item $pwFile -Force -ErrorAction SilentlyContinue
            Add-Content "$DataDir\pgdata\postgresql.conf" ("listen_addresses = '127.0.0.1'`nport = {0}" -f $DbPort)
            Add-Content "$DataDir\pgdata\pg_hba.conf" ("host all all 127.0.0.1/32 scram-sha-256")
            Write-Ok 'initdb با موفقیت اجرا شد'
        }
        if (-not (Get-Service -Name 'rosepsy-pg' -ErrorAction SilentlyContinue)) {
            & "$PGBin\pg_ctl.exe" register -N 'rosepsy-pg' -U ".\$pgSvcUser" -P $pgSvcPass -D "$DataDir\pgdata" -o "-p $DbPort"
            if ($LASTEXITCODE -ne 0) { throw 'ثبت سرویس rosepsy-pg ناموفق بود' }
            try { Set-Service 'rosepsy-pg' -StartupType Automatic } catch {}
        }
        Write-Ok 'PostgreSQL از باینری Zip نصب شد'
        }
    }
    Ensure-PgRunning -superPass $superPass
}

function New-DbRoleAndDatabase([string]$superPass, [string]$appPass) {
    Write-Step 'ساخت نقش و بانک rosepsy (idempotent)'
    $env:PGPASSWORD = $superPass
    $roleExists = & "$PGBin\psql.exe" -U postgres -h 127.0.0.1 -p $DbPort -tAc "SELECT 1 FROM pg_roles WHERE rolname='rosepsy';"
    if ($LASTEXITCODE -ne 0) { throw 'اتصال superuser به PostgreSQL برای ساخت نقش برقرار نشد' }
    if ("$roleExists".Trim() -ne '1') {
        & "$PGBin\psql.exe" -U postgres -h 127.0.0.1 -p $DbPort -v ON_ERROR_STOP=1 -c ("CREATE ROLE rosepsy LOGIN PASSWORD '{0}';" -f $appPass.Replace("'","''")) | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'ساخت نقش rosepsy ناموفق بود' }
        Write-Ok 'نقش rosepsy ساخته شد'
    } else {
        # هم‌راستاسازی رمز نقش با .env تا وضعیت همیشه converge شود
        & "$PGBin\psql.exe" -U postgres -h 127.0.0.1 -p $DbPort -v ON_ERROR_STOP=1 -c ("ALTER ROLE rosepsy WITH LOGIN PASSWORD '{0}';" -f $appPass.Replace("'","''")) | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'هم‌راستاسازی رمز نقش rosepsy ناموفق بود' }
        Write-Ok 'نقش rosepsy موجود است - رمز با .env هم‌راستا شد'
    }
    $dbExists = & "$PGBin\psql.exe" -U postgres -h 127.0.0.1 -p $DbPort -tAc "SELECT 1 FROM pg_database WHERE datname='rosepsy';"
    if ($LASTEXITCODE -ne 0) { throw 'اتصال superuser به PostgreSQL برای ساخت بانک برقرار نشد' }
    if ("$dbExists".Trim() -ne '1') {
        & "$PGBin\psql.exe" -U postgres -h 127.0.0.1 -p $DbPort -v ON_ERROR_STOP=1 -c 'CREATE DATABASE rosepsy OWNER rosepsy;' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'ساخت بانک rosepsy ناموفق بود' }
        Write-Ok 'بانک rosepsy ساخته شد'
    } else { Write-Ok 'بانک rosepsy از قبل موجود است' }
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

# ---------- گام ۵: Redis (اختیاری؛ نبودش = fail-open مطابق بند ۶ ADR-05) ----------
function Install-Redis {
    Write-Step 'گام ۵: Redis برای ویندوز (سرویس «Redis»، فقط 127.0.0.1)'
    if ($SkipRedis) { Write-Warn2 'با پارامتر SkipRedis رد شد'; return $false }
    if (Get-Service -Name 'Redis' -ErrorAction SilentlyContinue) {
        Write-Ok 'سرویس Redis از قبل نصب است'
        Start-WinSvc 'Redis' ; return $true
    }
    try {
        $msi = Invoke-Download $VER.redisMsi "$DlDir\redis.msi" 60
        $p = Start-Process 'msiexec.exe' -ArgumentList '/i', "`"$msi`"", 'INSTALLDIR="C:\rosepsy\runtime\redis"', '/qn', '/norestart' -Wait -PassThru
        # رفع اشکال ۱.۰.۶: کد خروج در PS 5.1 گاهی تهی است؛ ملاک، وجود redis-server.exe است
        $rcode = Get-ExitCode $p
        if (-not (Test-Path 'C:\rosepsy\runtime\redis\redis-server.exe')) { throw ("msiexec ناموفق بود (کد: {0})" -f $rcode) }
        $conf = 'C:\rosepsy\runtime\redis\redis.windows-service.conf'
        if (Test-Path $conf) {
            $txt = [System.IO.File]::ReadAllText($conf)
            $txt = $txt -replace '(?m)^bind\s+.*$', 'bind 127.0.0.1'
            $txt = $txt -replace '(?m)^port\s+6379\s*$', ("port {0}" -f $RedisPort)
            $txt = $txt -replace '(?m)^appendonly\s+no\s*$', 'appendonly yes'
            $txt = $txt -replace '(?m)^dir\s+.*$', ("dir {0}" -f ($DataDir + '\redis').Replace('\','/'))
            [System.IO.File]::WriteAllText($conf, $txt)
        }
        # تضمین فقط-لوکال‌هاست (مستقل از پیش‌فرض MSI)
        $txt2 = [System.IO.File]::ReadAllText($conf)
        if ($txt2 -notmatch '(?m)^bind\s+127\.0\.0\.1\s*$') { Add-Content $conf 'bind 127.0.0.1' }
        if ($txt2 -notmatch '(?m)^protected-mode\s+yes\s*$') { Add-Content $conf 'protected-mode yes' }
        New-Item -ItemType Directory -Force -Path "$DataDir\redis" | Out-Null
        Start-WinSvc 'Redis'
        & 'C:\rosepsy\runtime\redis\redis-cli.exe' -p $RedisPort ping | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Ok ("Redis روی 127.0.0.1:{0} PING/PONG درست است" -f $RedisPort); return $true }
        return $true
    } catch {
        Write-Warn2 ("Redis نصب نشد: {0}" -f $_.Exception.Message)
        Write-Warn2 'ادامه بدون Redis - سقف نرخ به‌صورت fail-open غیرفعال می‌شود (بند ۶ ADR-05)'
        return $false
    }
}

# ---------- گام ۶: ClamAV بومی (clamd سرویس + freshclam) ----------
function Install-ClamAV {
    Write-Step 'گام ۶: ClamAV 1.4.6 (همان تگ compose؛ دانلود از GitHub Cisco-Talos)'
    if ($SkipClamav) { Write-Warn2 'با پارامتر SkipClamav رد شد'; return $false }
    try {
        $clamDir = 'C:\Program Files\ClamAV'
        if (-not (Test-Path "$clamDir\clamd.exe")) {
            $msi = Invoke-Download $VER.clamav "$DlDir\clamav.msi" 200
            $p = Start-Process 'msiexec.exe' -ArgumentList '/i', "`"$msi`"", '/qn', '/norestart' -Wait -PassThru
            $ccode = Get-ExitCode $p
            if (-not (Test-Path "$clamDir\clamd.exe")) { throw ("msiexec ناموفق بود (کد: {0})" -f $ccode) }
        }
        Write-Ok 'ClamAV نصب شد'
        # تنظیم clamd.conf و freshclam.conf از نمونه‌های رسمی
        New-Item -ItemType Directory -Force -Path "$clamDir\logs" | Out-Null
        foreach ($c in 'clamd','freshclam') {
            $src = "$clamDir\conf_examples\$c.conf.sample"
            $dst = "$clamDir\$c.conf"
            if ((Test-Path $src) -and -not (Test-Path $dst)) {
                $lines = Get-Content $src | Where-Object { $_ -notmatch '^Example\s*$' }
                [System.IO.File]::WriteAllLines($dst, $lines)
            }
        }
        $clamdConf = "$clamDir\clamd.conf"
        $extra = @(
            'LogFile C:\Program Files\ClamAV\logs\clamd.log',
            "TCPSocket $ClamavPort",
            'TCPAddr 127.0.0.1',
            'StreamMaxLength 100M',
            'MaxScanSize 100M',
            'MaxFileSize 100M'
        )
        foreach ($e in $extra) {
            $key = ($e -split '\s+')[0]
            $cur = Get-Content $clamdConf | Where-Object { $_ -match ('^' + [regex]::Escape($key) + '\s') }
            if ($cur) { (Get-Content $clamdConf) | Where-Object { $_ -notmatch ('^' + [regex]::Escape($key) + '\s') } | Set-Content $clamdConf }
            Add-Content $clamdConf $e
        }
        # به‌روزرسانی امضاها (بار اول ممکن است چند دقیقه طول بکشد)
        Write-Host '  به‌روزرسانی پایگاه امضاها (freshclam) - صبور باشید...'
        $fp = Start-Process "$clamDir\freshclam.exe" -ArgumentList '--show-progress' -Wait -PassThru -NoNewWindow
        if ($fp.ExitCode -ne 0) { Write-Warn2 'freshclam ناموفق بود (شبکه؟) - clamd ممکن است تا امضاکنندهٔ بعدی بالا نیاید' }
        else { Write-Ok 'امضاها به‌روز شدند' }
        New-WinSvc -Name 'rosepsy-clamd' -DisplayName 'Rosepsy ClamAV Daemon' `
            -Description 'clamd برای اسکن آنتی‌ویروس آپلودها (TCP 127.0.0.1)' `
            -Exe "$clamDir\clamd.exe" -ArgsStr '--config-file="C:\Program Files\ClamAV\clamd.conf"' `
            -WorkDir $clamDir
        New-WinSvc -Name 'rosepsy-freshclam' -DisplayName 'Rosepsy FreshClam Updater' `
            -Description 'به‌روزرسان دوره‌ای امضاهای ClamAV' `
            -Exe "$clamDir\freshclam.exe" -ArgsStr '-d --quiet --checks=12' -WorkDir $clamDir
        try { Start-WinSvc 'rosepsy-clamd' } catch { Write-Warn2 "clamd هنوز بالا نیامد (احتمالاً امضا ناقص): $($_.Exception.Message)" }
        try { Start-WinSvc 'rosepsy-freshclam' } catch {}
        return $true
    } catch {
        Write-Warn2 ("ClamAV نصب نشد: {0}" -f $_.Exception.Message)
        Write-Warn2 'ادامه بدون clamd - av_scan به clamscan محلی برمی‌گردد (زنجیرهٔ بسترهای B39)'
        return $false
    }
}

# ---------- گام ۷: Node.js + ساخت دو اپ فرانت (site و panel) ----------
function Install-NodeAndBuildFrontend {
    Write-Step 'گام ۷: Node.js 22 + ساخت فرانت‌اند (site روی / و panel روی /panel)'
    if ($SkipFrontendBuild) { Write-Warn2 'با پارامتر SkipFrontendBuild رد شد'; return }
    $nodeDir = "$BaseDir\runtime\node"
    if (-not (Test-Path "$nodeDir\node.exe")) {
        $zip = Invoke-Download $VER.node "$DlDir\node.zip" 200
        Expand-Pkg $zip "$BaseDir\runtime\nodez"
        $inner = Get-ChildItem "$BaseDir\runtime\nodez" -Directory | Select-Object -First 1
        Move-Item $inner.FullName "$nodeDir" -Force
        Write-Ok 'Node.js باز شد'
    }
    $env:Path = "$nodeDir;$env:Path"
    # انتخاب رجیستری npm: اولویت مخزن ایران (ITO)؛ اگر -NpmRegistry داده شده باشد فقط همان
    $regs = @()
    if ($NpmRegistry) {
        $regs = @($NpmRegistry)
    } else {
        foreach ($c in @('https://archive.ito.gov.ir/mirror2/npm/','https://archive.ito.gov.ir/npm/','https://registry.npmjs.org/')) {
            Write-Host ("  بررسی رجیستری npm: {0}" -f $c)
            if (Test-HttpOk $c) { $regs += $c } else { Write-Warn2 "بی‌پاسخ: $c" }
        }
        if ($regs.Count -eq 0) { $regs = @('https://registry.npmjs.org/') }
    }
    foreach ($proj in @(@{d='site'; base=''}, @{d='frontend'; base='/panel/'})) {
        $pdir = Join-Path $AppDir $proj.d
        if (-not (Test-Path (Join-Path $pdir 'package.json'))) { throw "پروژهٔ فرانت یافت نشد: $pdir" }
        Write-Host ("  npm install در {0} ..." -f $proj.d)
        Push-Location $pdir
        try {
            & cmd.exe /c "node --version"
            $npmOk = $false
            foreach ($rg in $regs) {
                Write-Host ("  npm install از {0} ..." -f $rg)
                & cmd.exe /c ("npm install --no-audit --no-fund --fetch-retries=3 --fetch-retry-maxtimeout=60000 --registry=" + $rg)
                if ($LASTEXITCODE -eq 0) { $npmOk = $true; break }
                Write-Warn2 "npm install از $rg ناموفق بود؛ رجیستری بعدی..."
            }
            if (-not $npmOk) { throw "npm install در $($proj.d) ناموفق بود" }
            if ($proj.base) {
                & cmd.exe /c "npm run build -- --base=/panel/"
            } else {
                & cmd.exe /c "npm run build"
            }
            if ($LASTEXITCODE -ne 0) { throw "npm run build در $($proj.d) ناموفق بود" }
            Write-Ok ("ساخت {0} کامل شد (dist)" -f $proj.d)
        } finally { Pop-Location }
    }
}

# ---------- گام ۸: Caddy (وب + ریورس‌پروکسی، TLS خودکار sslip.io) ----------
function Install-Caddy {
    Write-Step 'گام ۸: Caddy - تنها پورت‌های عمومی همین سرور (80/443)'
    $caddyDir = "$BaseDir\runtime\caddy"
    New-Item -ItemType Directory -Force -Path $caddyDir, $EtcDir | Out-Null
    if (-not (Test-Path "$caddyDir\caddy.exe")) {
        Invoke-Download $VER.caddy "$caddyDir\caddy.exe" 60 | Out-Null
    }
    Write-Ok 'caddy.exe آماده است'
    $siteDist  = "$AppDir\site\dist"
    $panelDist = "$AppDir\frontend\dist"
    if ($Domain) {
        $siteAddr = $Domain
        $tlsNote = '# TLS خودکار Let''s Encrypt برای دامنهٔ sslip.io'
    } else {
        $siteAddr = ":$WebHttpPort"
        $tlsNote = '# بدون دامنه: فقط HTTP برای تست داخلی'
    }
    $caddyfile = @"
# Rosepsy - معادل دقیق deploy/nginx.conf در compose
# $tlsNote
# برای اجرای «برنامه‌های دیگر» روی همین سرور، بلوک‌های جدید با زیردامنهٔ sslip.io اضافه کنید؛ مثال:
#   app2.130.185.73.157.sslip.io {  root * C:\apps2  file_server  }
{
        admin off
}

$siteAddr {
        encode gzip zstd
        request_body {
                max_size 15MB
        }
        header {
                X-Content-Type-Options "nosniff"
                X-Frame-Options "DENY"
                Referrer-Policy "strict-origin-when-cross-origin"
                -Server
        }

        handle /api/* {
                reverse_proxy 127.0.0.1:$ApiPort {
                        header_up Host {host}
                        header_up X-Real-IP {remote_host}
                        header_up X-Forwarded-For {remote_host}
                }
                @apinostore path /api/*
                header @apinostore Cache-Control "no-store"
        }

        handle /panel {
                redir /panel/ 301
        }

        handle_path /panel/* {
                root * "$panelDist"
                try_files {path} /index.html
                header Cache-Control "no-cache"
                header X-Content-Type-Options "nosniff"
                header X-Frame-Options "DENY"
                header Referrer-Policy "strict-origin-when-cross-origin"
                file_server
        }

        handle /panel/assets/* {
                root * "$panelDist"
                try_files {path} =404
                header Cache-Control "public, max-age=2592000, immutable"
                file_server
        }

        handle /assets/* {
                root * "$siteDist"
                try_files {path} =404
                header Cache-Control "public, max-age=2592000, immutable"
                file_server
        }

        handle {
                root * "$siteDist"
                try_files {path} /index.html
                header Cache-Control "no-cache"
                file_server
        }
}
"@
    [System.IO.File]::WriteAllText("$EtcDir\Caddyfile", $caddyfile, (New-Object System.Text.UTF8Encoding($false)))
    Write-Ok ("Caddyfile نوشته شد: $EtcDir\Caddyfile")
    New-WinSvc -Name 'rosepsy-caddy' -DisplayName 'Rosepsy Web (Caddy)' `
        -Description 'وب‌سرور + ریورس‌پروکسی API + TLS خودکار' `
        -Exe "$caddyDir\caddy.exe" -ArgsStr ("run --config `"$EtcDir\Caddyfile`" --adapter caddyfile") -WorkDir $caddyDir
    # فایروال: فقط پورت‌های عمومی وب
    foreach ($wp in @($WebHttpPort, $WebHttpsPort) | Select-Object -Unique) {
        try {
            if (-not (Get-NetFirewallRule -DisplayName "Rosepsy Web $wp" -ErrorAction SilentlyContinue)) {
                New-NetFirewallRule -DisplayName "Rosepsy Web $wp" -Direction Inbound -Protocol TCP -LocalPort $wp -Action Allow -Profile Any | Out-Null
            }
            Write-Ok ("فایروال: پورت عمومی {0} باز شد (فقط همین دو پورت عمومی‌اند)" -f $wp)
        } catch { Write-Warn2 "فایروال: $($_.Exception.Message)" }
    }
    try { Start-WinSvc 'rosepsy-caddy' } catch { Write-Warn2 "caddy هنوز بالا نیامد: $($_.Exception.Message)" }
}

# ---------- گام ۹: فایل .env (مقادیر موجود حفظ می‌شود) ----------
function Set-EnvFile([string]$superPassNote) {
    Write-Step 'گام ۹: فایل .env (کلیدهای موجود حفظ، کلیدهای بومی تنظیم می‌شوند)'
    $envPath = "$AppDir\.env"
    if (-not (Test-Path $envPath)) {
        $ex = "$AppDir\.env.example"
        if (Test-Path $ex) { Copy-Item $ex $envPath }
        else { New-Item -ItemType File -Path $envPath -Force | Out-Null }
    }
    $map = Read-EnvMap $envPath
    $dbPass = ''
    if ($map.ContainsKey('POSTGRES_PASSWORD') -and $map['POSTGRES_PASSWORD'] -and $map['POSTGRES_PASSWORD'] -notlike 'CHANGE_ME*') {
        $dbPass = $map['POSTGRES_PASSWORD']
    } else {
        $dbPass = New-RandomHex 16
        Set-EnvKey $envPath 'POSTGRES_PASSWORD' $dbPass
    }
    if (-not ($map.ContainsKey('AUTH_SECRET_KEY') -and $map['AUTH_SECRET_KEY'] -and $map['AUTH_SECRET_KEY'] -notlike 'CHANGE_ME*' -and $map['AUTH_SECRET_KEY'] -notlike 'dev-only*')) {
        Set-EnvKey $envPath 'AUTH_SECRET_KEY' (New-RandomHex 32)
    }
    # --- کلیدهای اختصاصی استقرار بومی ---
    Set-EnvKey $envPath 'DATABASE_URL' ("postgresql+psycopg://rosepsy:{0}@127.0.0.1:{1}/rosepsy" -f $dbPass, $DbPort)
    Set-EnvKey $envPath 'ENVIRONMENT' 'production'
    Set-EnvKey $envPath 'PUBLIC_BASE_URL' ("https://{0}" -f $Domain)
    Set-EnvKey $envPath 'STORAGE_BACKEND' 'local'
    Set-EnvKey $envPath 'UPLOAD_DIR' "$DataDir\uploads"
    Set-EnvKey $envPath 'CLAMAV_ENABLED' 'true'
    Set-EnvKey $envPath 'CLAMAV_PORT' "$ClamavPort"
    if ($script:ClamOk) { Set-EnvKey $envPath 'CLAMAV_HOST' '127.0.0.1' } else { Set-EnvKey $envPath 'CLAMAV_HOST' '' }
    if ($script:RedisOk) { Set-EnvKey $envPath 'RATE_LIMIT_REDIS_URL' ("redis://127.0.0.1:{0}/0" -f $RedisPort) }
    else { Set-EnvKey $envPath 'RATE_LIMIT_REDIS_URL' '' }
    if (-not $map.ContainsKey('V1_DEPRECATION_MODE')) { Set-EnvKey $envPath 'V1_DEPRECATION_MODE' 'warn' }
    if (-not $map.ContainsKey('V1_SUNSET_DATE')) { Set-EnvKey $envPath 'V1_SUNSET_DATE' '2027-04-20' }
    New-Item -ItemType Directory -Force -Path "$DataDir\uploads" | Out-Null
    # pydantic-settings فایل .env را نسبت به cwd می‌خواند -> نسخهٔ backend همگام شود
    Copy-Item $envPath "$AppDir\backend\.env" -Force
    Write-Ok ".env به‌روز شد (root + backend)  $superPassNote"
    return $dbPass
}

# ---------- گام‌های ۱ تا ۳: Git، کد پروژه، Python ----------
function Install-GitIfNeeded {
    Write-Step 'گام ۱: Git for Windows (دانلود از GitHub Releases)'
    if (Get-Command git -ErrorAction SilentlyContinue) { Write-Ok 'git موجود است'; return }
    if ($SkipGitInstall) { Write-Warn2 'SkipGitInstall - git یافت نشد'; throw 'git لازم است' }
    $exe = Invoke-Download $VER.git "$DlDir\git-installer.exe" 100
    $p = Start-Process $exe -ArgumentList '/VERYSILENT','/NORESTART','/SUPPRESSMSGBOXES' -Wait -PassThru -NoNewWindow
    $gcode = Get-ExitCode $p
    $env:Path = "C:\Program Files\Git\cmd;$env:Path"
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        if ($null -ne $gcode -and $gcode -ne 0) { throw ("نصب Git کد {0} برگرداند" -f $gcode) }
        throw 'پس از نصب، git در PATH نیست (PowerShell را دوباره باز کنید)'
    }
    Write-Ok 'Git نصب شد'
}
function Get-AppRepo {
    Write-Step 'گام ۲: کد پروژه (clone/pull)'
    $gitExe = (Get-Command git).Source
    # نکته: در PS 5.1 با ErrorActionPreference=Stop، هر خروجی stderr فرایند بومی
    # (از جمله پیام‌های عادی پیشرفت git) با 2>&1 به خطای مرگبار تبدیل می‌شود؛
    # پس ریدایرکت 2>&1 روی git ممنوع و کد خروجی دستی بررسی می‌شود.
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if (Test-Path "$AppDir\.git") {
            # قفل کهنهٔ git از اجرای نیمه‌کارهٔ قبلی ممکن است checkout/reset را بترکاند
            Remove-Item "$AppDir\.git\index.lock" -Force -ErrorAction SilentlyContinue
            & $gitExe -C $AppDir fetch origin --tags
            if ($LASTEXITCODE -ne 0) { Write-Warn2 'fetch ناموفق (شبکه؟) - با نسخهٔ فعلی مخزن ادامه می‌دهیم' }
            & $gitExe -C $AppDir checkout $RepoBranch
            & $gitExe -C $AppDir reset --hard "origin/$RepoBranch"
            if ($LASTEXITCODE -ne 0) { throw ("همگام‌سازی مخزن ناموفق بود (کد {0})" -f $LASTEXITCODE) }
            Write-Ok ("مخزن به origin/{0} همگام شد (فایل‌های untracked مانند .env دست‌نخورده‌اند)" -f $RepoBranch)
        } else {
            # پاک‌سازی کلون ناقصِ اجرای قبلی (بدون .git)
            if (Test-Path $AppDir) {
                $items = @(Get-ChildItem $AppDir -Force -ErrorAction SilentlyContinue)
                if ($items.Count -gt 0) {
                    Write-Warn2 "پوشهٔ ناقص کلون قبلی حذف می‌شود: $AppDir"
                    Remove-Item $AppDir -Recurse -Force
                }
            }
            & $gitExe clone --branch $RepoBranch $RepoUrl $AppDir
            if ($LASTEXITCODE -ne 0) { throw ("clone ناموفق بود (کد {0}) - اتصال به GitHub را بررسی کنید" -f $LASTEXITCODE) }
            Write-Ok "مخزن در $AppDir کلون شد"
        }
    } finally {
        $ErrorActionPreference = $oldEap
    }
}
function Install-PythonAndVenv {
    Write-Step 'گام ۳: Python 3.12 + venv + وابستگی‌های backend'
    if (-not (Test-Path "$BaseDir\runtime\python\python.exe")) {
        $exe = Invoke-Download $VER.python "$DlDir\python-installer.exe" 60
        $p = Start-Process $exe -ArgumentList '/quiet','InstallAllUsers=1','PrependPath=1',`
                "TargetDir=$BaseDir\runtime\python",'Include_doc=0','Include_test=0','Include_launcher=0' `
                -Wait -PassThru -NoNewWindow
        # رفع اشکال ۱.۰.۶: ملاک، وجود python.exe است نه کد خروج (که گاهی تهی است)
        $pycode = Get-ExitCode $p
        if (-not (Test-Path "$BaseDir\runtime\python\python.exe")) { throw ("نصب Python ناموفق بود (کد: {0})" -f $pycode) }
        Write-Ok 'Python نصب شد'
    }
    if (-not (Test-Path $VenvPy)) {
        & "$BaseDir\runtime\python\python.exe" -m venv "$BaseDir\runtime\venv"
        Write-Ok 'venv ساخته شد'
    }
    # انتخاب مخزن pip: اولویت مخزن ایران (ITO)؛ اگر -PipIndexUrl داده شده باشد فقط همان
    $indexes = @()
    if ($PipIndexUrl) {
        $indexes = @($PipIndexUrl)
    } else {
        foreach ($c in @('https://archive.ito.gov.ir/mirror2/python/simple/','https://archive.ito.gov.ir/python/simple/','https://pypi.org/simple/')) {
            Write-Host ("  بررسی مخزن pip: {0}" -f $c)
            if (Test-HttpOk ($c + 'pip/')) { $indexes += $c } else { Write-Warn2 "بی‌پاسخ: $c" }
        }
        if ($indexes.Count -eq 0) { $indexes = @('https://pypi.org/simple/') }
    }
    # ارتقای pip اختیاری است (از همان مخزن اول)؛ ناموفقی‌اش مرگبار نیست
    $upIdx = $indexes[0]
    & $VenvPy -m pip install --upgrade pip --index-url $upIdx --trusted-host ([uri]$upIdx).Host --timeout 60 --retries 2 --quiet
    if ($LASTEXITCODE -ne 0) { Write-Warn2 'ارتقای pip رد شد (نسخهٔ همراه پایتون کافی است)' }
    $req = "$AppDir\backend\requirements.txt"
    $done = $false
    foreach ($idx in $indexes) {
        $h = ([uri]$idx).Host
        Write-Host ("  pip install از {0} (چند دقیقه)..." -f $h)
        & $VenvPy -m pip install -r $req --index-url $idx --trusted-host $h --timeout 60 --retries 3
        if ($LASTEXITCODE -eq 0) { $done = $true; break }
        Write-Warn2 "این مخزن نصب را کامل نکرد: $idx - مخزن بعدی..."
    }
    if (-not $done) { throw 'pip install ناموفق بود (هیچ مخزنی پاسخگو نبود)' }
    Write-Ok 'وابستگی‌های Python نصب شدند'
}

# ---------- گام ۱۰: مایگریشن + سرویس API ----------
function Invoke-Migration {
    Write-Step 'گام ۱۰: مایگریشن بانک (alembic upgrade head)'
    $map = Read-EnvMap "$AppDir\backend\.env"
    if ($map.ContainsKey('DATABASE_URL')) { $env:DATABASE_URL = $map['DATABASE_URL'] }
    Push-Location "$AppDir\backend"
    try {
        & $VenvPy -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'alembic ناموفق بود' }
        Write-Ok 'بانک داده در آخرین نسخه است'
    } finally { Pop-Location }
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
}
function Install-ApiService {
    Write-Step 'گام ۱۱: سرویس rosepsy-api (uvicorn روی 127.0.0.1)'
    New-WinSvc -Name 'rosepsy-api' -DisplayName 'Rosepsy API (uvicorn)' `
        -Description 'FastAPI backend - فقط 127.0.0.1' `
        -Exe $VenvPy -ArgsStr ("-m uvicorn app.main:app --host 127.0.0.1 --port {0}" -f $ApiPort) `
        -WorkDir "$AppDir\backend"
    Start-WinSvc 'rosepsy-api'
}

# ---------- گام ۱۲: پشتیبان‌گیری زمان‌بندی‌شده ----------
function Install-BackupTask {
    Write-Step 'گام ۱۲: پشتیبان‌گیری روزانه (pg_dump -Fc، ساعت 02:30، نگهداری ۱۴ نسخه)'
    New-Item -ItemType Directory -Force -Path "$BaseDir\scripts", "$BaseDir\backups" | Out-Null
    $bk = @"
`$ErrorActionPreference = 'Stop'
`$map = @{}
foreach (`$ln in Get-Content 'C:\rosepsy\app\backend\.env' -Encoding UTF8) {
  if (`$ln -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { `$map[`$Matches[1]] = `$Matches[2].Trim() }
}
`$env:PGPASSWORD = `$map['POSTGRES_PASSWORD']
`$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
`$out = "C:\rosepsy\backups\rosepsy-`$stamp.dump"
& 'C:\rosepsy\runtime\pgsql\bin\pg_dump.exe' -U rosepsy -h 127.0.0.1 -p $($script:DbPort) -Fc -f `$out rosepsy
if (`$LASTEXITCODE -ne 0) { throw 'pg_dump ناموفق' }
Get-ChildItem 'C:\rosepsy\backups\rosepsy-*.dump' | Where-Object { `$_.LastWriteTime -lt (Get-Date).AddDays(-14) } | Remove-Item -Force
"@
    [System.IO.File]::WriteAllText("$BaseDir\scripts\pg-backup.ps1", $bk, (New-Object System.Text.UTF8Encoding($false)))
    schtasks /Create /TN 'Rosepsy Backup' /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\rosepsy\scripts\pg-backup.ps1" /SC DAILY /ST 02:30 /RU SYSTEM /F | Out-Null
    if ($LASTEXITCODE -ne 0) { throw ("ثبت schtasks ناموفق بود (کد {0})" -f $LASTEXITCODE) }
    Write-Ok 'وظیفهٔ زمان‌بندی‌شدهٔ «Rosepsy Backup» ثبت شد'
}

# ---------- بررسی سلامت نهایی + جمع‌بندی ----------
function Invoke-HealthAndSummary {
    Write-Step 'بررسی سلامت نهایی'
    $apiOk = $false
    for ($i = 0; $i -lt 45; $i++) {
        try {
            $r = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/api/v1/health" -f $ApiPort) -UseBasicParsing -TimeoutSec 4
            if ($r.StatusCode -eq 200) { $apiOk = $true; break }
        } catch { Start-Sleep 2 }
    }
    if ($apiOk) { Write-Ok 'API سالم است (/api/v1/health = 200)' }
    else { Write-Warn2 'API هنوز پاسخ نمی‌دهد - لاگ: C:\rosepsy\logs\rosepsy-api' }
    if ($Domain) {
        try {
            $r2 = Invoke-WebRequest -Uri ("https://{0}/api/v1/health" -f $Domain) -UseBasicParsing -TimeoutSec 20
            Write-Ok ("HTTPS عمومی سالم است: https://{0}" -f $Domain)
        } catch { Write-Warn2 'HTTPS هنوز آماده نیست (گواهی Let''s Encrypt تا چند دقیقه صادر می‌شود؛ بعداً تست کنید)' }
    }
    Write-Host ''
    Write-Host '========================= جمع‌بندی استقرار =========================' -ForegroundColor Cyan
    Write-Host ("  دامنه/وب        : https://{0}   (پنل: /panel/)" -f $Domain)
    Write-Host ("  API داخلی       : http://127.0.0.1:{0}/api/v1" -f $ApiPort)
    Write-Host ("  PostgreSQL      : 127.0.0.1:{0}  (سرویس rosepsy-pg)" -f $DbPort)
    if ($script:RedisOk) { Write-Host ("  Redis           : 127.0.0.1:{0}  (سرویس Redis)" -f $RedisPort) }
    else { Write-Host '  Redis           : نصب نشد - سقف نرخ fail-open' }
    if ($script:ClamOk) { Write-Host ("  ClamAV clamd    : 127.0.0.1:{0}  (سرویس rosepsy-clamd)" -f $ClamavPort) }
    else { Write-Host '  ClamAV          : نصب نشد - fallback به clamscan محلی' }
    Write-Host '  ذخیره‌سازی      : STORAGE_BACKEND=local (پوشهٔ C:\rosepsy\data\uploads)'
    Write-Host '  لاگ‌ها          : C:\rosepsy\logs\<service-name>\'
    Write-Host '  پشتیبان         : C:\rosepsy\backups (روزانه 02:30، ۱۴ نسخه)'
    Write-Host '===================================================================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host 'قدم‌های بعدی پیشنهادی:' -ForegroundColor White
    Write-Host ("  1) ساخت ادمین:   Push-Location {0}\backend; & `"{1}`" create_admin.py; Pop-Location" -f $AppDir, $VenvPy)
    Write-Host '  2) بازبینی .env (درگاه پرداخت، SMTP، OTP_DEV_MODE=false در عملیات)'
    Write-Host '  3) وضعیت پورت‌ها برای برنامه‌های بعدی شما: -Mode status یا -Mode doctor'
}

# ---------- ارکستراتور setup ----------
function Invoke-Setup {
    Assert-Admin
    foreach ($d in @($BaseDir, $DlDir, $SvcDir, $LogDir, $DataDir, $EtcDir, "$BaseDir\tools", "$BaseDir\backups")) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }
    try { Start-Transcript -Path ("$LogDir\native-setup-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss')) | Out-Null } catch {}
    Write-Host '=== Rosepsy - استقرار بومی ویندوز (بدون Docker) - نسخهٔ 1.0.7 ===' -ForegroundColor Cyan
    Test-ReservedPortsFree
    if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) { throw 'curl.exe یافت نشد (باید در Windows Server درون‌ساخت باشد)' }
    Install-GitIfNeeded
    Get-AppRepo
    Install-PythonAndVenv
    $superPass = Resolve-PgSuperPass
    Install-PostgreSQL -superPass $superPass
    if (Test-Path "$BaseDir\runtime\pgz") { Remove-Item "$BaseDir\runtime\pgz" -Recurse -Force -ErrorAction SilentlyContinue }
    $script:RedisOk = Install-Redis
    $script:ClamOk = Install-ClamAV
    Install-NodeAndBuildFrontend
    $dbPass = Set-EnvFile
    New-DbRoleAndDatabase -superPass $superPass -appPass $dbPass
    Invoke-Migration
    Install-ApiService
    Install-Caddy
    Install-BackupTask
    Invoke-HealthAndSummary
    try { Stop-Transcript | Out-Null } catch {}
}

# ---------- ارتقا (upgrade) ----------
function Invoke-Upgrade {
    Assert-Admin
    Write-Step 'ارتقای Rosepsy (git + pip + مایگریشن + ساخت فرانت + ری‌استارت سرویس‌ها)'
    Get-AppRepo
    Install-PythonAndVenv
    if (-not $SkipFrontendBuild) { Install-NodeAndBuildFrontend }
    if (Test-Path "$AppDir\.env") { Copy-Item "$AppDir\.env" "$AppDir\backend\.env" -Force }
    $map = Read-EnvMap "$AppDir\backend\.env"
    if ($map.ContainsKey('DATABASE_URL')) { $env:DATABASE_URL = $map['DATABASE_URL'] }
    Push-Location "$AppDir\backend"
    try { & $VenvPy -m alembic upgrade head; if ($LASTEXITCODE -ne 0) { throw 'alembic ناموفق' } } finally { Pop-Location }
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    foreach ($s in 'rosepsy-api','rosepsy-caddy') {
        if (Get-Service -Name $s -ErrorAction SilentlyContinue) {
            Restart-Service $s
            Write-Ok "سرویس $s ری‌استارت شد"
        }
    }
    Invoke-HealthAndSummary
}

# ---------- وضعیت (status) ----------
function Invoke-Status {
    Write-Step 'وضعیت سرویس‌ها و پورت‌ها'
    Get-Service -Name 'rosepsy-*' -ErrorAction SilentlyContinue | Format-Table Name, Status, StartType -AutoSize | Out-Host
    if (Get-Service -Name 'Redis' -ErrorAction SilentlyContinue) { Get-Service Redis | Format-Table Name, Status, StartType -AutoSize | Out-Host }
    Get-ListenerTable | Format-Table Port, Address, Scope, Process, PID -AutoSize | Out-Host
    foreach ($u in @(("http://127.0.0.1:{0}/api/v1/health" -f $ApiPort)) + $(if ($Domain) { @("https://$Domain/api/v1/health") } else { @() })) {
        try {
            $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 8
            Write-Ok ("{0}  ->  {1}" -f $u, $r.StatusCode)
        } catch { Write-Warn2 ("{0}  ->  پاسخ نداد" -f $u) }
    }
}

# ---------- اجرای backup دستی ----------
function Invoke-ManualBackup {
    if (Test-Path "$BaseDir\scripts\pg-backup.ps1") {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$BaseDir\scripts\pg-backup.ps1"
        Get-ChildItem "$BaseDir\backups" | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | Format-Table Name, Length, LastWriteTime -AutoSize | Out-Host
    } else { throw 'اسکریپت پشتیبان‌گیری هنوز ساخته نشده (اول -Mode setup)' }
}

# ---------- دیسپچر اصلی ----------
switch ($Mode) {
    'doctor' { Invoke-Doctor }
    'setup'  { Invoke-Setup }
    'upgrade'{ Invoke-Upgrade }
    'status' { Invoke-Status }
    'backup' { Invoke-ManualBackup }
    default  { Invoke-Doctor }
}
