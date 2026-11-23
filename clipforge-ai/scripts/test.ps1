#Requires -Version 5.1
<#
.SYNOPSIS
    ClipForge AI — Run test suite
.DESCRIPTION
    Runs pytest test suite and checks health endpoint if the server is running.
#>

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ApiDir      = Join-Path $ProjectRoot "services\api"
$VenvDir     = Join-Path $ApiDir ".venv"

function Write-Step  { param([string]$msg) Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail  { param([string]$msg) Write-Host "[FAIL] $msg" -ForegroundColor Red }
function Write-Warn  { param([string]$msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }

$venvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Fail "Python venv not found — run setup.ps1 first"
    exit 1
}

# 1. Run pytest
Write-Step "Running pytest from services/api/ ..."
Push-Location $ApiDir
try {
    & $venvPython -m pytest app/tests -v
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "All tests passed"
    } else {
        Write-Fail "Some tests failed (exit code $LASTEXITCODE)"
    }
}
finally {
    Pop-Location
}

# 2. Health endpoint check
Write-Step "Checking if backend server is running..."
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -Method Get -TimeoutSec 3 -ErrorAction Stop
    Write-Ok "Health endpoint returned status: $($response.status) (v$($response.version))"
}
catch {
    Write-Warn "Backend not currently running on :8000 — skipping live HTTP probe"
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Test run complete." -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
