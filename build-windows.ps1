#Requires -Version 5.1
<#
.SYNOPSIS
    Build Windows executable for Synapse Desktop using PyInstaller.

.DESCRIPTION
    Creates a distributable Windows .exe from the Synapse Desktop codebase.
    Supports both --onedir (default, faster startup) and --onefile (single .exe) modes.

.PARAMETER OneFile
    Build as a single .exe file instead of a directory bundle.
    Single .exe is more portable but has slower startup time.

.EXAMPLE
    .\build-windows.ps1
    .\build-windows.ps1 -OneFile
#>

param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"

# ── Config ──
$AppName = "Synapse-Desktop"
$AppVersion = "1.0.0"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildDir = Join-Path $ScriptDir "build-win"
$DistDir = Join-Path $BuildDir "dist"
$WorkDir = Join-Path $BuildDir "work"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Building $AppName v$AppVersion for Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Check Python ──
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "       Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found! Install Python 3.12+ and add to PATH." -ForegroundColor Red
    exit 1
}

# ── Step 2: Activate venv ──
Write-Host "[2/5] Activating virtual environment..." -ForegroundColor Yellow
$venvActivate = Join-Path $ScriptDir ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
    Write-Host "       Virtual environment activated." -ForegroundColor Green
} else {
    Write-Host "       [WARNING] No .venv found. Using system Python." -ForegroundColor DarkYellow
    Write-Host "       Run: python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt" -ForegroundColor DarkYellow
}

# ── Step 3: Install PyInstaller ──
Write-Host "[3/5] Ensuring PyInstaller is installed..." -ForegroundColor Yellow
pip install pyinstaller --quiet 2>&1 | Out-Null
Write-Host "       PyInstaller ready." -ForegroundColor Green

# ── Step 4: Clean previous build ──
Write-Host "[4/5] Cleaning previous build..." -ForegroundColor Yellow
if (Test-Path $BuildDir) {
    Remove-Item -Recurse -Force $BuildDir
}
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null

# ── Step 5: Build ──
$mode = if ($OneFile) { "--onefile" } else { "--onedir" }
$modeLabel = if ($OneFile) { "single-file" } else { "directory bundle" }
Write-Host "[5/5] Building $modeLabel with PyInstaller..." -ForegroundColor Yellow
Write-Host "       This may take 2-5 minutes..." -ForegroundColor DarkGray

$assetsDir = Join-Path $ScriptDir "assets"
$templatesDir = Join-Path $ScriptDir "core\prompting\templates"
$iconPath = Join-Path $ScriptDir "assets\icon.ico"

# Build PyInstaller arguments
$pyiArgs = @(
    "--name", $AppName,
    $mode,
    "--windowed",
    "--noconfirm",
    "--clean",
    "--add-data", "$assetsDir;assets",
    "--add-data", "$templatesDir;core/prompting/templates",
    "--hidden-import", "tiktoken_ext",
    "--hidden-import", "tiktoken_ext.openai_public",
    "--collect-all", "tiktoken_ext",
    "--distpath", $DistDir,
    "--workpath", $WorkDir,
    "--specpath", $BuildDir
)

# Add icon if it exists
if (Test-Path $iconPath) {
    $pyiArgs += @("--icon", $iconPath)
    Write-Host "       Using icon: $iconPath" -ForegroundColor DarkGray
} else {
    Write-Host "       [WARNING] assets/icon.ico not found, building without icon." -ForegroundColor DarkYellow
    Write-Host "       Convert your PNG to ICO at: https://convertio.co/png-ico/" -ForegroundColor DarkYellow
}

$pyiArgs += "main_window.py"

# Run PyInstaller
$startTime = Get-Date
pyinstaller @pyiArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] PyInstaller build failed! Check output above." -ForegroundColor Red
    exit 1
}

$elapsed = (Get-Date) - $startTime

# ── Done ──
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Build complete! ($([math]::Round($elapsed.TotalSeconds))s)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

if ($OneFile) {
    $exePath = Join-Path $DistDir "$AppName.exe"
    $size = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Host "  Single .exe: $exePath" -ForegroundColor White
    Write-Host "  Size: ${size} MB" -ForegroundColor DarkGray
} else {
    $exePath = Join-Path $DistDir "$AppName\$AppName.exe"
    Write-Host "  Executable:  $exePath" -ForegroundColor White
    Write-Host "  Directory:   $(Join-Path $DistDir $AppName)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Tip: Distribute the entire '$AppName' folder." -ForegroundColor DarkGray
    Write-Host "  For a single .exe: .\build-windows.ps1 -OneFile" -ForegroundColor DarkGray
}

Write-Host ""