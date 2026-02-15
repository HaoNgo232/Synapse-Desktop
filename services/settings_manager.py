"""
Settings Manager - Quản lý load/save settings của ứng dụng.

Service này tập trung logic quản lý settings từ views/settings_view.py và mở rộng
để hỗ trợ thêm các settings khác (như selected model).

File: ~/.synapse-desktop/settings.json
"""

import json
from typing import Dict, Any

from config.paths import SETTINGS_FILE

DEFAULT_SETTINGS = {
    "excluded_folders": "node_modules\ndist\nbuild\n.next\n__pycache__\n.pytest_cache\npnpm-lock.yaml\npackage-lock.json\ncoverage",
    "use_gitignore": True,
    "model_id": "claude-sonnet-4.5",  # Default model
    "enable_security_check": True,  # Enable security check
    "include_git_changes": True,  # Integrate git diff/log in prompt
}


def load_settings() -> Dict[str, Any]:
    """
    Load settings từ file.

    Returns:
        Dict merged với default settings.
    """
    try:
        if SETTINGS_FILE.exists():
            content = SETTINGS_FILE.read_text(encoding="utf-8")
            saved = json.loads(content)
            return {**DEFAULT_SETTINGS, **saved}
    except (OSError, json.JSONDecodeError):
        pass

    return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict[str, Any]) -> bool:
    """
    Save settings ra file.

    Args:
        settings: Dict settings cần lưu (sẽ merge với settings hiện tại để tránh mất dữ liệu)

    Returns:
        True nếu save thành công.
    """
    try:
        current = load_settings()
        updated = {**current, **settings}

        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(updated, indent=2), encoding="utf-8")
        return True
    except (OSError, IOError):
        return False


def get_setting(key: str, default: Any = None) -> Any:
    """Helper để lấy 1 setting specific"""
    settings = load_settings()
    return settings.get(key, default or DEFAULT_SETTINGS.get(key))


def set_setting(key: str, value: Any) -> bool:
    """Helper để lưu 1 setting specific"""
    return save_settings({key: value})

