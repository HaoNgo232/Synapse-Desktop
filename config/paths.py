"""
Application Paths - Centralized path definitions for Synapse Desktop

Module này định nghĩa tất cả các đường dẫn sử dụng trong ứng dụng.
Tập trung ở một nơi để tránh hardcode rải rác và đảm bảo consistency.

App data được lưu tại (theo thứ tự ưu tiên):
1. $XDG_CONFIG_HOME/synapse-desktop/ (nếu XDG_CONFIG_HOME được set)
2. ~/.config/synapse-desktop/ (Linux standard)
3. ~/.synapse-desktop/ (fallback cho backward compatibility)

- logs/      : Log files
- backups/   : Backup files trước khi modify
- settings.json, session.json, history.json, recent_folders.json
"""

import os
from pathlib import Path


# =============================================================================
# Tên ứng dụng - Single source of truth cho naming
# =============================================================================
APP_NAME = "synapse-desktop"

# =============================================================================
# Thư mục gốc của ứng dụng - dùng XDG để đảm bảo persist khi tắt/mở app
# =============================================================================
_LEGACY_APP_DIR = Path.home() / f".{APP_NAME}"  # ~/.synapse-desktop (cũ)


def _get_app_dir() -> Path:
    """Lấy thư mục app data, ưu tiên XDG để đảm bảo persistence."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / APP_NAME
    return Path.home() / ".config" / APP_NAME


# Các file cần migrate từ legacy path khi upgrade
_LEGACY_DATA_FILES = (
    "settings.json",
    "session.json",
    "history.json",
    "recent_folders.json",
)


def _ensure_app_dir_with_migration() -> Path:
    """Lấy APP_DIR và migrate tất cả data files từ legacy path nếu cần.

    Migrate settings.json, session.json, history.json, recent_folders.json
    để user upgrade không mất session, history, recent folders.
    """
    app_dir = _get_app_dir()
    app_dir.mkdir(parents=True, exist_ok=True)

    for filename in _LEGACY_DATA_FILES:
        legacy_path = _LEGACY_APP_DIR / filename
        new_path = app_dir / filename
        if not new_path.exists() and legacy_path.exists():
            try:
                new_path.write_bytes(legacy_path.read_bytes())
            except OSError:
                pass
    return app_dir


APP_DIR = _get_app_dir()

# =============================================================================
# Các thư mục con
# =============================================================================
BACKUP_DIR = APP_DIR / "backups"
LOG_DIR = APP_DIR / "logs"

# =============================================================================
# Các file cấu hình và dữ liệu
# =============================================================================
SETTINGS_FILE = APP_DIR / "settings.json"
SESSION_FILE = APP_DIR / "session.json"
HISTORY_FILE = APP_DIR / "history.json"
RECENT_FOLDERS_FILE = APP_DIR / "recent_folders.json"

# =============================================================================
# Environment Variables - Tên biến môi trường cho debug mode
# =============================================================================
DEBUG_ENV_VAR = "SYNAPSE_DEBUG"

# Kiểm tra debug mode từ environment variable
DEBUG_MODE = os.environ.get(DEBUG_ENV_VAR, "").lower() in ("1", "true", "yes")


def ensure_app_directories() -> None:
    """
    Tạo các thư mục cần thiết nếu chưa tồn tại.
    Migrate settings từ ~/.synapse-desktop nếu có.
    Gọi hàm này khi khởi động ứng dụng.
    """
    _ensure_app_dir_with_migration()
    APP_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_app_dir() -> Path:
    """
    Lấy đường dẫn thư mục gốc của ứng dụng.

    Returns:
        Path đến thư mục ~/.synapse-desktop
    """
    return APP_DIR
