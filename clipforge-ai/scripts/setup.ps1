#Requires -Version 5.1
<#
.SYNOPSIS
    ClipForge AI — Development Environment Setup
.DESCRIPTION
    Checks prerequisites, creates virtual environment, installs dependencies,
    and prepares storage directories for native Windows development.
#>

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ApiDir      = Join-Path $ProjectRoot "services\api"
$WebDir      = Join-Path $ProjectRoot "apps\web"
$VenvDir     = Join-Path $ApiDir ".venv"
$DataDir     = Join-Path $ApiDir "data"
$StorageRoot = Join-Path $ProjectRoot "storage"

function Write-Step  { param([string]$msg) Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn  { param([string]$msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Fail  { param([string]$msg) Write-Host "[FAIL] $msg" -ForegroundColor Red }

$script:Errors = 0

# ─────────────────────────────────────────────
# 1. Python version check (>=3.10)
# ─────────────────────────────────────────────
Write-Step "Checking Python version..."
try {
    $pyVer = & python --version 2>&1
    if ($pyVer -match "(\d+)\.(\d+)\.(\d+)") {
        $major = [int]$Matches[1]; $minor = [int]$Matches[2]
        if ($major -ge 3 -and $minor -ge 10) {
            Write-Ok "Python $($Matches[0]) detected"
        } else {
            Write-Fail "Python >= 3.10 required, found $($Matches[0])"
            $script:Errors++
        }
    }
} catch {
    Write-Fail "Python not found in PATH"
    $script:Errors++
}

# ─────────────────────────────────────────────
# 2. Node.js version check (>=18)
# ─────────────────────────────────────────────
Write-Step "Checking Node.js version..."
try {
    $nodeVer = & node --version 2>&1
    if ($nodeVer -match "v(\d+)\.") {
        $nodeMajor = [int]$Matches[1]
        if ($nodeMajor -ge 18) {
            Write-Ok "Node.js $nodeVer detected"
        } else {
            Write-Fail "Node.js >= 18 required, found $nodeVer"
            $script:Errors++
        }
    }
} catch {
    Write-Fail "Node.js not found in PATH"
    $script:Errors++
}

# ─────────────────────────────────────────────
# 3. npm version check
# ─────────────────────────────────────────────
Write-Step "Checking npm version..."
try {
    $npmVer = & npm --version 2>&1
    Write-Ok "npm $npmVer detected"
} catch {
    Write-Fail "npm not found in PATH"
    $script:Errors++
}

# ─────────────────────────────────────────────
# 4. FFmpeg / FFprobe check (warn only)
# ─────────────────────────────────────────────
Write-Step "Checking for FFmpeg / FFprobe..."
$toolsFfmpeg = Join-Path $ProjectRoot "tools\ffmpeg\ffmpeg.exe"
$toolsFfprobe = Join-Path $ProjectRoot "tools\ffmpeg\ffprobe.exe"
$ffmpegOk = $false; $ffprobeOk = $false
try {
    if (Test-Path $toolsFfmpeg) { $null = & $toolsFfmpeg -version 2>&1; $ffmpegOk = $true }
    else { $null = & ffmpeg -version 2>&1; $ffmpegOk = $true }
} catch {}
try {
    if (Test-Path $toolsFfprobe) { $null = & $toolsFfprobe -version 2>&1; $ffprobeOk = $true }
    else { $null = & ffprobe -version 2>&1; $ffprobeOk = $true }
} catch {}
if ($ffmpegOk -and $ffprobeOk) {
    Write-Ok "FFmpeg and FFprobe verified"
} else {
    Write-Warn "FFmpeg/FFprobe not found -- video processing will not work until installed"
}

# ─────────────────────────────────────────────
# 5. Create Python virtual environment
# ─────────────────────────────────────────────
Write-Step "Setting up Python virtual environment at services/api/.venv ..."
if (-not (Test-Path $VenvDir)) {
    & python -m venv --system-site-packages $VenvDir
    if ($LASTEXITCODE -eq 0) { Write-Ok "Virtual environment created" }
    else { Write-Fail "Failed to create virtual environment"; $script:Errors++ }
} else {
    Write-Ok "Virtual environment already exists"
}

# ─────────────────────────────────────────────
# 6. Install / Verify Python dependencies
# ─────────────────────────────────────────────
Write-Step "Checking Python dependencies..."
$venvPython = Join-Path $VenvDir "Scripts\python.exe"
$testImport = & $venvPython -c "import fastapi, uvicorn, pydantic, sqlalchemy, alembic, apscheduler, httpx, pytest; print('OK')" 2>&1
if ($testImport -match "OK") {
    Write-Ok "Python dependencies verified (all packages accessible)"
} else {
    Write-Step "Installing Python dependencies via pip..."
    $pipExe = Join-Path $VenvDir "Scripts\pip.exe"
    $reqFile = Join-Path $ApiDir "requirements.txt"
    if (Test-Path $pipExe) {
        & $pipExe install -r $reqFile 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Ok "Python dependencies installed" }
        else { Write-Fail "pip install failed"; $script:Errors++ }
    } else {
        Write-Fail "pip not found in venv"
        $script:Errors++
    }
}

# ─────────────────────────────────────────────
# 7. Create data directory
# ─────────────────────────────────────────────
Write-Step "Creating data directory (services/api/data/) ..."
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}
Write-Ok "Data directory ready"

# ─────────────────────────────────────────────
# 8. Create storage directories
# ─────────────────────────────────────────────
Write-Step "Creating storage directories..."
foreach ($sub in @("uploads", "clips", "thumbnails", "temp")) {
    $dir = Join-Path $StorageRoot $sub
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Ok "Storage directories ready (uploads, clips, thumbnails, temp)"

# ─────────────────────────────────────────────
# 9. Install frontend dependencies
# ─────────────────────────────────────────────
Write-Step "Installing frontend dependencies (apps/web/) ..."
Push-Location $WebDir
try {
    & npm install 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Ok "Frontend dependencies installed" }
    else { Write-Fail "npm install failed"; $script:Errors++ }
} catch {
    Write-Fail "npm install failed: $_"
    $script:Errors++
} finally {
    Pop-Location
}

# ─────────────────────────────────────────────
# 10. Copy .env.example → .env
# ─────────────────────────────────────────────
$envExample = Join-Path $ProjectRoot ".env.example"
$envFile    = Join-Path $ProjectRoot ".env"
Write-Step "Checking .env file..."
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Ok ".env created from .env.example — edit it with your secrets"
} else {
    Write-Ok ".env already exists"
}

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
Write-Host ""
if ($script:Errors -eq 0) {
    Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  Setup complete! Run .\scripts\start.ps1 to launch." -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
} else {
    Write-Host "═══════════════════════════════════════════════" -ForegroundColor Red
    Write-Host "  Setup finished with $($script:Errors) error(s). Fix them and re-run." -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════" -ForegroundColor Red
}
