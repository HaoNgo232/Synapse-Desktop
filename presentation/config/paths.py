"""
Application Paths - Backward compatibility shim.

File này đã được chuyển sang shared/config/paths.py.
Import từ shared/config/paths để tuân theo Clean Architecture.
"""

from shared.config.paths import (
    APP_NAME,
    APP_DIR,
    BACKUP_DIR,
    LOG_DIR,
    SETTINGS_FILE,
    SESSION_FILE,
    HISTORY_FILE,
    RECENT_FOLDERS_FILE,
    DEBUG_ENV_VAR,
    DEBUG_MODE,
    ensure_app_directories,
    get_app_dir,
)

__all__ = [
    "APP_NAME",
    "APP_DIR",
    "BACKUP_DIR",
    "LOG_DIR",
    "SETTINGS_FILE",
    "SESSION_FILE",
    "HISTORY_FILE",
    "RECENT_FOLDERS_FILE",
    "DEBUG_ENV_VAR",
    "DEBUG_MODE",
    "ensure_app_directories",
    "get_app_dir",
]
