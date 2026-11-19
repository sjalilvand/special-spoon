# ============================================================================
# rosepsy-phase98-tests.ps1
# Phase 98 - Official test bank rebuild: server update + seed + verification
# ----------------------------------------------------------------------------
# Run in PowerShell (Run as Administrator):
#     Set-ExecutionPolicy -Scope Process Bypass -Force
#     C:\rosepsy\app\deploy\windows\rosepsy-phase98-tests.ps1
#
# What it does:
#   1) Sync repo (git fetch + reset --hard origin/main)
#   2) Rebuild panel frontend (npm install + build --base=/panel/)
#   3) Run seed_psych_tests.py + seed_psych_scales.py (idempotent)
#   4) Restart rosepsy-api service
#   5) Verify: /api/v1/public/psych-tests must return 41 items incl. hexaco-pi-r-100
#      and the rebuilt cattell-16pf-187 / mcmi-iii-175 / mmpi-sf-370
# ============================================================================
param(
    [string]$BaseDir = 'C:\rosepsy'
)
$ErrorActionPreference = 'Stop'
$AppDir   = Join-Path $BaseDir 'app'
$VenvPy   = Join-Path $BaseDir 'runtime\venv\Scripts\python.exe'
$Stamp    = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupDir = Join-Path $BaseDir "backups\phase98-$Stamp"

function Write-Step([string]$m) { Write-Host ("==> " + $m) -ForegroundColor Cyan }
function Write-Ok2([string]$m)  { Write-Host ("  OK " + $m) -ForegroundColor Green }
function Write-Warn3([string]$m){ Write-Host ("  !! " + $m) -ForegroundColor Yellow }

if (-not (Test-Path $AppDir)) { throw "app dir not found: $AppDir" }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

# ---- 1) backup current bank + dist -----------------------------------------
Write-Step 'backup current psych_seed + panel dist'
foreach ($p in @('backend\psych_seed', 'frontend\dist')) {
    $src = Join-Path $AppDir $p
    if (Test-Path $src) {
        $dst = Join-Path $BackupDir ($p -replace '\\', '_')
        Copy-Item $src $dst -Recurse -Force
        Write-Ok2 ("backup: {0}" -f $dst)
    }
}

# ---- 2) git sync ------------------------------------------------------------
Write-Step 'git fetch + reset --hard origin/main'
$git = (Get-Command git).Source
$oldEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
Remove-Item (Join-Path $AppDir '.git\index.lock') -Force -ErrorAction SilentlyContinue
& $git -C $AppDir fetch origin
if ($LASTEXITCODE -ne 0) { throw 'git fetch failed (network?)' }
& $git -C $AppDir checkout main
& $git -C $AppDir reset --hard origin/main
if ($LASTEXITCODE -ne 0) { throw ('git reset failed (code {0})' -f $LASTEXITCODE) }
$ErrorActionPreference = $oldEap
$head = (& $git -C $AppDir log -1 --format='%h %s').Trim()
Write-Ok2 ("repo at: {0}" -f $head)

# ---- 3) rebuild panel frontend ----------------------------------------------
Write-Step 'npm install + build panel (base=/panel/)'
Push-Location (Join-Path $AppDir 'frontend')
try {
    & cmd.exe /c "npm install --no-audit --no-fund"
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
    & cmd.exe /c "npm run build -- --base=/panel/"
    if ($LASTEXITCODE -ne 0) { throw 'panel build failed' }
    Write-Ok2 'panel dist rebuilt (frontend\dist)'
} finally { Pop-Location }

# ---- 4) seeds ----------------------------------------------------------------
Write-Step 'seed psych tests + scales (idempotent)'
if (Test-Path (Join-Path $AppDir '.env')) {
    Copy-Item (Join-Path $AppDir '.env') (Join-Path $AppDir 'backend\.env') -Force
}
Push-Location (Join-Path $AppDir 'backend')
try {
    & $VenvPy seed_psych_tests.py
    if ($LASTEXITCODE -ne 0) { throw 'seed_psych_tests failed' }
    & $VenvPy seed_psych_scales.py
    if ($LASTEXITCODE -ne 0) { throw 'seed_psych_scales failed' }
} finally { Pop-Location }
Write-Ok2 'test bank + scales seeded into DB'

# ---- 5) restart api ----------------------------------------------------------
Write-Step 'restart rosepsy-api'
try {
    Restart-Service rosepsy-api -ErrorAction Stop
    Start-Sleep -Seconds 6
    Write-Ok2 'rosepsy-api restarted'
} catch {
    Write-Warn3 ('service restart failed: {0} - restart it manually from services.msc' -f $_.Exception.Message)
}

# ---- 6) verify ----------------------------------------------------------------
Write-Step 'verify public test catalog'
$ok = $false
foreach ($u in @('http://127.0.0.1:8000/api/v1/public/psych-tests', 'http://127.0.0.1:8080/api/v1/public/psych-tests')) {
    try {
        $r = Invoke-RestMethod -Uri $u -TimeoutSec 12
        $items = @($r.items)
        Write-Ok2 ("{0} -> {1} tests" -f $u, $items.Count)
        $want = @('hexaco-pi-r-100', 'cattell-16pf-187', 'mcmi-iii-175', 'mmpi-sf-370', 'baron-eq-i-90')
        foreach ($s in $want) {
            $t = $items | Where-Object { $_.slug -eq $s }
            if ($t) {
                Write-Ok2 ("  {0}: {1} (qs={2})" -f $s, $t.title, $t.question_count)
            } else {
                Write-Warn3 ("  MISSING: {0}" -f $s)
                $script:ok = $false
            }
        }
        if ($items.Count -ge 41) { $script:ok = $true }
        break
    } catch {
        Write-Warn3 ("{0} unreachable: {1}" -f $u, $_.Exception.Message)
    }
}
if ($ok) {
    Write-Host ''
    Write-Host 'PHASE 98 DEPLOY COMPLETE - test bank rebuilt (41 tests, HEXACO added)' -ForegroundColor Green
} else {
    Write-Host ''
    Write-Host 'CHECK WARNINGS ABOVE - catalog may be incomplete' -ForegroundColor Yellow
}
