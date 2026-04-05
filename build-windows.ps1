# build-windows.ps1
# Build Synapse Desktop thành EXE cho Windows
#
# Usage:
#   .\build-windows.ps1              # Build bản onedir (nhanh, dễ debug)
#   .\build-windows.ps1 -OneFile     # Build bản single EXE (tiện phân phối)
#   .\build-windows.ps1 -Clean       # Xóa build cũ trước khi build
#
# Requirements:
#   - Python 3.10+ với .venv đã cài đặt
#   - pip install pyinstaller (tự động cài nếu thiếu)
#
# CRITICAL NOTES cho Windows EXE:
#   1. --windowed: Tránh console window xuất hiện
#   2. --hidden-import: Bundle tất cả dynamic imports
#   3. subprocess CREATE_NO_WINDOW: Tránh git/cmd flash (patch trong code)
#   4. multiprocessing.freeze_support(): Tránh fork bomb trên Windows EXE

param(
    [switch]$OneFile,
    [switch]$Clean,
    [switch]$Debug
)

$ErrorActionPreference = "Stop"

# ── Configuration ──────────────────────────────────────────────
$APP_NAME = "Synapse-Desktop"
$APP_VERSION = "1.0.0"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BUILD_DIR = Join-Path $SCRIPT_DIR "build"
$DIST_DIR = Join-Path $BUILD_DIR "dist"
$WORK_DIR = Join-Path $BUILD_DIR "work"
$SPEC_DIR = Join-Path $BUILD_DIR "spec"
$VENV_DIR = Join-Path $SCRIPT_DIR ".venv"
$VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
$VENV_PIP = Join-Path $VENV_DIR "Scripts\pip.exe"
$ASSETS_DIR = Join-Path $SCRIPT_DIR "assets"
$TEMPLATES_DIR = Join-Path $SCRIPT_DIR "domain\prompt\templates"
$ICON_FILE = Join-Path $ASSETS_DIR "icon.ico"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building $APP_NAME v$APP_VERSION for Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 0: Validate environment ──────────────────────────────
if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "[ERROR] Virtual environment not found at: $VENV_DIR" -ForegroundColor Red
    Write-Host "Run: python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

Write-Host "[0/7] Activating virtual environment..." -ForegroundColor Green
& $VENV_PYTHON --version

# ── Step 1: Clean previous build (optional) ───────────────────
if ($Clean -and (Test-Path $BUILD_DIR)) {
    Write-Host "[1/7] Cleaning previous build..." -ForegroundColor Green
    Remove-Item -Recurse -Force $BUILD_DIR
} else {
    Write-Host "[1/7] Skipping clean (use -Clean to force)" -ForegroundColor DarkGray
}

New-Item -ItemType Directory -Force -Path $BUILD_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $SPEC_DIR | Out-Null

# ── Step 2: Install/update PyInstaller ────────────────────────
Write-Host "[2/7] Ensuring PyInstaller is installed..." -ForegroundColor Green
& $VENV_PIP install pyinstaller --quiet --upgrade
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install PyInstaller" -ForegroundColor Red
    exit 1
}

# ── Step 3: Prepare icon ──────────────────────────────────────
Write-Host "[3/7] Checking assets..." -ForegroundColor Green

$iconArg = @()
if (Test-Path $ICON_FILE) {
    Write-Host "  Found icon: $ICON_FILE" -ForegroundColor DarkGray
    $iconArg = @("--icon", $ICON_FILE)
} elseif (Test-Path (Join-Path $ASSETS_DIR "icon.png")) {
    Write-Host "  WARNING: icon.ico not found, using icon.png (may not display in taskbar)" -ForegroundColor Yellow
    Write-Host "  Convert PNG to ICO: https://convertio.co/png-ico/" -ForegroundColor Yellow
} else {
    Write-Host "  No icon found, building without custom icon" -ForegroundColor Yellow
}

# ── Step 4: Collect add-data paths ────────────────────────────
Write-Host "[4/7] Collecting data files..." -ForegroundColor Green

$addDataArgs = @()

# Assets directory (fonts, icons, images)
if (Test-Path $ASSETS_DIR) {
    $addDataArgs += @("--add-data", "${ASSETS_DIR};assets")
    Write-Host "  + assets/" -ForegroundColor DarkGray
}

# Prompt templates
if (Test-Path $TEMPLATES_DIR) {
    $addDataArgs += @("--add-data", "${TEMPLATES_DIR};domain\prompt\templates")
    Write-Host "  + domain/prompt/templates/" -ForegroundColor DarkGray
}

# ── Step 5: Determine hidden imports ──────────────────────────
Write-Host "[5/7] Resolving hidden imports..." -ForegroundColor Green

# Danh sach cac module can bundle ma PyInstaller khong tu detect duoc.
# Bao gom: dynamic imports, lazy imports, va optional dependencies.
$hiddenImports = @(
    # --- Tokenization (tiktoken registry loaded dynamically) ---
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    # --- Tree-sitter language parsers (loaded via importlib) ---
    "tree_sitter_python",
    "tree_sitter_javascript",
    "tree_sitter_typescript",
    "tree_sitter_rust",
    "tree_sitter_go",
    "tree_sitter_java",
    "tree_sitter_c_sharp",
    "tree_sitter_c",
    "tree_sitter_cpp",
    "tree_sitter_ruby",
    "tree_sitter_php",
    "tree_sitter_swift",
    "tree_sitter_css",
    "tree_sitter_solidity",
    # --- PySide6 plugins (platform-specific, not always detected) ---
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    # --- Persistence / Infrastructure ---
    "infrastructure.persistence.settings_manager",
    "infrastructure.persistence.history_service",
    "infrastructure.adapters.cache_registry",
    "infrastructure.adapters.clipboard_utils",
    "infrastructure.adapters.safe_timer",
    "infrastructure.adapters.security_check",
    "infrastructure.adapters.token_display",
    "infrastructure.adapters.qt_utils",
    # --- Filesystem / Git ---
    "infrastructure.filesystem.file_watcher.service",
    "infrastructure.filesystem.file_actions",
    "infrastructure.filesystem.file_scanner",
    "infrastructure.filesystem.file_utils",
    "infrastructure.filesystem.ignore_engine",
    "infrastructure.git.git_utils",
    "infrastructure.git.repo_manager",
    # --- Application Layer ---
    "application.services.prompt_build_service",
    "application.services.ai_context_worker",
    "application.services.workspace_config",
    "application.services.preview_analyzer",
    "application.services.error_context",
    "application.services.graph_service",
    "application.services.tokenization_service",
    # --- Domain Layer ---
    "domain.prompt.opx_parser",
    "domain.prompt.generator",
    "domain.prompt.template_manager",
    "domain.prompt.context_builder_prompts",
    "domain.prompt.assembler",
    "domain.tokenization.cancellation",
    "domain.smart_context.parser",
    "domain.smart_context.config",
    "domain.smart_context.loader",
    # --- Presentation / UI ---
    "presentation.config.theme_qss",
    "presentation.config.output_format",
    "presentation.config.model_config",
    "presentation.views.context.ui_builder",
    "presentation.views.context.copy_action_controller",
    "presentation.views.context.related_files_controller",
    "presentation.views.context.tree_management_controller",
    "presentation.components.dialogs.custom_template_dialog",
    "presentation.components.file_tree.file_tree_widget",
    "presentation.components.file_tree.file_tree_model",
    "presentation.components.diff_viewer_qt",
    "presentation.components.toggle_switch",
    "presentation.components.tag_chips_widget",
    # --- Optional Rust-accelerated libraries ---
    "scandir_rs",
    "rs_bpe",
    # --- Third-party ---
    "pathspec",
    "psutil",
    "watchdog",
    "watchdog.observers",
    "watchdog.events",
    "detect_secrets",
    "rapidfuzz",
    "filetype",
    "qtawesome",
    "requests",
    "tokenizers",
    # --- Standard library ---
    "multiprocessing",
    "json",
    "threading",
    "concurrent.futures",
    "logging",
    "inspect"
)

$hiddenImportArgs = @()
foreach ($mod in $hiddenImports) {
    $hiddenImportArgs += @("--hidden-import", $mod)
}

# ── Step 6: Build with PyInstaller ────────────────────────────
Write-Host "[6/7] Building with PyInstaller..." -ForegroundColor Green

$mode = if ($OneFile) { "--onefile" } else { "--onedir" }
$modeLabel = if ($OneFile) { "single EXE" } else { "directory" }
Write-Host "  Mode: $modeLabel" -ForegroundColor DarkGray

# Construct full argument list
$pyinstallerArgs = @(
    "-m", "PyInstaller",
    "--name", $APP_NAME,
    $mode,
    "--windowed",          # CRITICAL: Không tạo console window
    "--noconfirm",         # Overwrite output mà không hỏi
    "--clean",             # Clean PyInstaller cache
    "--distpath", $DIST_DIR,
    "--workpath", $WORK_DIR,
    "--specpath", $SPEC_DIR
)

# Add icon if available
$pyinstallerArgs += $iconArg

# Add data files
$pyinstallerArgs += $addDataArgs

# Add hidden imports
$pyinstallerArgs += $hiddenImportArgs

# Collect-all for packages that have data files
$pyinstallerArgs += @(
    "--collect-all", "tiktoken_ext",
    "--collect-all", "tiktoken",
    "--collect-all", "detect_secrets"
)

# Debug mode: don't strip debug info
if ($Debug) {
    $pyinstallerArgs += @("--debug", "all", "--log-level", "DEBUG")
    Write-Host "  Debug mode enabled" -ForegroundColor Yellow
}

# Version info (Windows-specific metadata)
# PyInstaller can embed version info via --version-file, but we skip for simplicity

# Entry point
$pyinstallerArgs += "presentation\main_window.py"

Write-Host "  Running: python $($pyinstallerArgs -join ' ')" -ForegroundColor DarkGray
Write-Host ""

& $VENV_PYTHON @pyinstallerArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "" -ForegroundColor Red
    Write-Host "[ERROR] PyInstaller build failed with exit code $LASTEXITCODE" -ForegroundColor Red
    Write-Host "Tips:" -ForegroundColor Yellow
    Write-Host "  - Run with -Debug flag for detailed output" -ForegroundColor Yellow
    Write-Host "  - Check that all imports in requirements.txt are installed" -ForegroundColor Yellow
    Write-Host "  - Try: pip install --force-reinstall pyinstaller" -ForegroundColor Yellow
    exit 1
}

# ── Step 7: Verify output ─────────────────────────────────────
Write-Host ""
Write-Host "[7/7] Verifying build output..." -ForegroundColor Green

if ($OneFile) {
    $exePath = Join-Path $DIST_DIR "$APP_NAME.exe"
} else {
    # Join-Path chi nhan 2 tham so (Path, ChildPath), nen can join 2 lan.
    $appDir = Join-Path $DIST_DIR $APP_NAME
    $exePath = Join-Path $appDir "$APP_NAME.exe"
}

if (Test-Path $exePath) {
    $fileInfo = Get-Item $exePath
    $sizeMB = [math]::Round($fileInfo.Length / 1MB, 1)

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESSFUL" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  EXE: $exePath" -ForegroundColor White
    Write-Host "  Size: ${sizeMB} MB" -ForegroundColor White
    Write-Host ""

    if (-not $OneFile) {
        $dirSize = (Get-ChildItem -Recurse (Join-Path $DIST_DIR $APP_NAME) | Measure-Object -Property Length -Sum).Sum
        $dirSizeMB = [math]::Round($dirSize / 1MB, 1)
        Write-Host "  Total directory size: ${dirSizeMB} MB" -ForegroundColor White
        Write-Host ""
        Write-Host "  To distribute, zip the entire folder:" -ForegroundColor DarkGray
        Write-Host "    Compress-Archive -Path '$DIST_DIR\$APP_NAME' -DestinationPath '$BUILD_DIR\$APP_NAME-v$APP_VERSION-win64.zip'" -ForegroundColor DarkGray
    }

    # ── Step 8: Move to Desktop ───────────────────────────────────
    # Tự động di chuyển file EXE ra ngoài Desktop nếu build bản OneFile (theo yêu cầu)
    if ($OneFile -and (Test-Path $exePath)) {
        Write-Host ""
        Write-Host "[8/8] Moving output to Desktop..." -ForegroundColor Green
        $desktopPath = [Environment]::GetFolderPath("Desktop")
        $destPath = Join-Path $desktopPath "$APP_NAME.exe"
        
        try {
            # Dùng Copy-Item thay vì Move-Item để giữ lại backup trong dist
            # Flag -Force đảm bảo sẽ ghi đè file cũ trên Desktop nếu đã tồn tại
            Copy-Item -Path $exePath -Destination $destPath -Force
            $exePath = $destPath  # Cập nhật đường dẫn để hiển thị trong báo cáo bên dưới
            Write-Host "  ✨ [Copied to Desktop] $exePath" -ForegroundColor Cyan
        } catch {
            Write-Host "  [WARNING] Could not move to Desktop: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "  To run:" -ForegroundColor DarkGray
    Write-Host "    & '$exePath'" -ForegroundColor DarkGray
    Write-Host ""
} else {
    Write-Host "[ERROR] Expected EXE not found at: $exePath" -ForegroundColor Red
    Write-Host "Check build output above for errors." -ForegroundColor Yellow
    exit 1
}