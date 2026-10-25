<#
================================================================================
 rosepsy-boot.ps1  —  راه‌انداز اولیهٔ رزپسی روی سرور ویندوزی تازه
================================================================================
 این اسکریپت دو فایل اصلی استقرار را از گیت‌هاب می‌گیرد و «setup» را اجرا می‌کند.
 روی سرور تازه (بدون هیچ نصبی) فقط همین یک خط کافی است:

     iex (irm https://raw.githubusercontent.com/sjalilvand/special-spoon/main/deploy/windows/rosepsy-boot.ps1)

 سپس (در همان پوشه):
     .\rosepsy-server-deploy.ps1 deploy      ← استقرار کامل برنامه
     .\rosepsy-server-tls.ps1                ← گواهی رایگان HTTPS
================================================================================
#>

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

Write-Host '==============================================' -ForegroundColor DarkCyan
Write-Host ' رزپسی — دریافت اسکریپت‌های استقرار از گیت‌هاب' -ForegroundColor DarkCyan
Write-Host '==============================================' -ForegroundColor DarkCyan

# بررسی دسترسی Administrator
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host ''
    Write-Host '  [X]  این دستور باید در PowerShell با حالت Run as Administrator اجرا شود' -ForegroundColor Red
    exit 1
}

$base = 'https://raw.githubusercontent.com/sjalilvand/special-spoon/main/deploy/windows'
$files = @('rosepsy-server-deploy.ps1', 'rosepsy-server-tls.ps1')

foreach ($f in $files) {
    $target = Join-Path (Get-Location) $f
    Write-Host "  دریافت $f ..."
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Invoke-WebRequest -Uri "$base/$f" -OutFile $target -UseBasicParsing -TimeoutSec 120
            Unblock-File -Path $target -ErrorAction SilentlyContinue
            break
        } catch {
            if ($attempt -eq 3) { throw "دریافت $f ناموفق بود: $($_.Exception.Message) — اتصال اینترنت/فیلترینگ را بررسی کنید یا فایل‌ها را دستی دانلود کنید" }
            Start-Sleep -Seconds 3
        }
    }
    Write-Host "  [OK] $target" -ForegroundColor Green
}

Write-Host ''
Write-Host '  اسکریپت‌ها آماده‌اند — اجرای setup (نصب PowerShell 7 + Git + WSL2 + Docker Desktop)' -ForegroundColor White
Write-Host '  اگر پیام ری‌استارت دیدید: سرور را restart کنید و دوباره همین دستور را اجرا کنید' -ForegroundColor DarkGray
Write-Host ''
& .\rosepsy-server-deploy.ps1 setup

Write-Host ''
Write-Host '  گام بعدی پس از اتمام setup:' -ForegroundColor White
Write-Host '    .\rosepsy-server-deploy.ps1 deploy      ← استقرار کامل برنامه (کلون + بیلد + مهاجرت + داده نمونه)' -ForegroundColor Yellow
Write-Host '    .\rosepsy-server-tls.ps1                ← گواهی رایگان HTTPS' -ForegroundColor Yellow
Write-Host ''
