# ====================================================================
#  rosepsy-boot.ps1  -  Rosepsy one-line bootstrap for a fresh
#                       Windows Server (2019 / 2022 / 2025)
#
#  Run it with a single line in "Run as Administrator" PowerShell:
#
#     iex (irm <raw-url-of-this-file>)
#
#  What it does:
#    1) downloads rosepsy-server-deploy.ps1 + rosepsy-server-tls.ps1
#       from GitHub into C:\rosepsy
#    2) runs "setup"  (PowerShell 7 + WSL2 + Git + Docker Desktop)
#    3) if no restart is required, runs "deploy" automatically
#       (clone + build + migrate + demo data + firewall + health)
#
#  !!! IMPORTANT - DO NOT CHANGE THIS FILE'S ENCODING !!!
#  This file MUST stay pure ASCII and WITHOUT a UTF-8 BOM.
#  Why: "iex (irm ...)" hands the file text to Invoke-Expression as a
#  STRING. If the string starts with a BOM (EF BB BF), Windows
#  PowerShell 5.1 no longer recognizes "<#" as a comment opener - it
#  becomes part of the first token - so every comment line gets
#  EXECUTED as a command (endless red CommandNotFoundException flood).
#  If an executable line (like the bootstrap one-liner itself) sits
#  inside that comment block, the script even re-downloads and
#  re-invokes itself: an infinite red recursion loop.
#  Keep this file ASCII-only; Persian UI text lives in the other two
#  scripts - they keep their BOM ON PURPOSE because they are executed
#  as FILES (PowerShell then reads the BOM correctly).
# ====================================================================

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

$Base   = 'https://raw.githubusercontent.com/sjalilvand/special-spoon/main/deploy/windows'
$Dir    = 'C:\rosepsy'
$Deploy = Join-Path $Dir 'rosepsy-server-deploy.ps1'
$Tls    = Join-Path $Dir 'rosepsy-server-tls.ps1'

try { $host.UI.RawUI.WindowTitle = 'Rosepsy bootstrap' } catch { }

function Write-Step([string]$Text)  { Write-Host ''; Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text)    { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn2([string]$Text) { Write-Host "  [!]  $Text" -ForegroundColor Yellow }
function Write-Err2([string]$Text)  { Write-Host "  [X]  $Text" -ForegroundColor Red }

Write-Host ''
Write-Host '==============================================' -ForegroundColor DarkCyan
Write-Host ' ROSEPSY - fresh Windows Server bootstrap'       -ForegroundColor DarkCyan
Write-Host '==============================================' -ForegroundColor DarkCyan

# ---- 0) must be Administrator ---------------------------------------
$id      = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host ''
    Write-Err2 'Please open PowerShell with "Run as Administrator" and run this again.'
    return
}

try {
    # ---- 1) prepare folder + execution policy ------------------------
    New-Item -Path $Dir -ItemType Directory -Force | Out-Null
    try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force } catch { }

    # ---- 2) download the two deployment scripts ----------------------
    foreach ($f in @('rosepsy-server-deploy.ps1', 'rosepsy-server-tls.ps1')) {
        $target = Join-Path $Dir $f
        Write-Step "Downloading $f from GitHub"
        $done = $false
        for ($attempt = 1; $attempt -le 3 -and -not $done; $attempt++) {
            try {
                Invoke-WebRequest -Uri "$Base/$f" -OutFile $target -UseBasicParsing -TimeoutSec 120
                try { Unblock-File -Path $target -ErrorAction SilentlyContinue } catch { }
                $done = $true
            } catch {
                if ($attempt -ge 3) { throw "Download of $f failed: $($_.Exception.Message)" }
                Write-Warn2 "retry $attempt/3 ..."
                Start-Sleep -Seconds 3
            }
        }
        Write-Ok $target
    }

    # ---- 3) setup: PowerShell 7 + WSL2 + Git + Docker Desktop --------
    Write-Step 'Running setup  (PowerShell 7 + WSL2 + Git + Docker Desktop)'
    Write-Host '    (this can take 10-30 minutes on a fresh server)' -ForegroundColor DarkGray
    & $Deploy 'setup'

    # ---- 4) if the docker engine is alive, deploy right away ---------
    $dockerExe = "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
    if (-not (Test-Path $dockerExe)) {
        try { $dockerExe = (Get-Command docker -ErrorAction Stop).Source } catch { $dockerExe = '' }
    }
    $engineUp = $false
    if ($dockerExe -and (Test-Path $dockerExe)) {
        & $dockerExe info *> $null
        if ($LASTEXITCODE -eq 0) { $engineUp = $true }
    }

    if (-not $engineUp) {
        Write-Host ''
        Write-Err2 'Docker engine is not running yet - most likely a RESTART is required.'
        Write-Host '    1) RESTART the server.' -ForegroundColor Yellow
        Write-Host '    2) Run the SAME one-line bootstrap command again.' -ForegroundColor Yellow
        Write-Host '    (everything is idempotent - finished steps are not repeated)' -ForegroundColor DarkGray
        return
    }

    Write-Step 'Running deploy  (clone + build + migrate + demo data + firewall)'
    Write-Host '    (first build can take 10-40 minutes - do not close the window)' -ForegroundColor DarkGray
    & $Deploy 'deploy'

    # ---- 5) done ------------------------------------------------------
    Write-Host ''
    Write-Host '=================================================' -ForegroundColor DarkGreen
    Write-Ok  'ROSEPSY IS UP'
    Write-Host '=================================================' -ForegroundColor DarkGreen
    Write-Host '  Panel : http://130.185.73.157:8080/panel/'           -ForegroundColor White
    Write-Host '  Site  : http://130.185.73.157:8080/'                 -ForegroundColor White
    Write-Host '  API   : http://130.185.73.157:8080/api/v1/health'    -ForegroundColor White
    Write-Host ''
    Write-Host '  NEXT STEP - free HTTPS certificate:'                   -ForegroundColor White
    Write-Host "    C:\rosepsy\rosepsy-server-tls.ps1"                   -ForegroundColor Yellow
    Write-Host "    (Caddy + Let's Encrypt  ->  https://130.185.73.157.sslip.io" -ForegroundColor Gray
    Write-Host '     ports 80 + 443 must be open in the hosting panel too)'      -ForegroundColor Gray
    Write-Host ''
    Write-Host '  Manage later (from C:\rosepsy):'                       -ForegroundColor DarkGray
    Write-Host '    .\rosepsy-server-deploy.ps1 status | logs | update | backup | seed-reset' -ForegroundColor DarkGray
    Write-Host ''
} catch {
    Write-Host ''
    Write-Err2 "Bootstrap failed: $($_.Exception.Message)"
    Write-Warn2 'Fix the cause and simply run the same one-line bootstrap command again (it is safe to re-run).'
}
