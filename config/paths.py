"""
Application Paths - Centralized path definitions for Synapse Desktop

Module này định nghĩa tất cả các đường dẫn sử dụng trong ứng dụng.
Tập trung ở một nơi để tránh hardcode rải rác và đảm bảo consistency.

App data được lưu tại: ~/.synapse-desktop/
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
# Thư mục gốc của ứng dụng
# =============================================================================
APP_DIR = Path.home() / f".{APP_NAME}"

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
    Gọi hàm này khi khởi động ứng dụng.
    """
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
