"""
Settings Manager - Quan ly load/save settings cua ung dung.

Service nay tap trung logic quan ly settings tu views/settings_view.py va mo rong
de ho tro them cac settings khac (nhu selected model).

File: ~/.synapse-desktop/settings.json

API moi (typed):
    settings = load_app_settings()  # -> AppSettings
    save_app_settings(settings)
    update_app_setting(model_id="claude-sonnet-4.5")

API cu (backward compat, DEPRECATED):
    load_settings()  # -> Dict[str, Any]
    save_settings(data)
    get_setting(key, default)
    set_setting(key, value)
"""

import json
import threading
from typing import Dict, Any

from config.paths import SETTINGS_FILE
from config.app_settings import AppSettings

# Thread-safe lock de tranh race condition khi save settings
_settings_lock = threading.Lock()

# DEFAULT_SETTINGS giu lai de backward compat voi code cu chua migrate
DEFAULT_SETTINGS = {
    "excluded_folders": "node_modules\ndist\nbuild\n.next\n__pycache__\n.pytest_cache\npnpm-lock.yaml\npackage-lock.json\ncoverage",
    "use_gitignore": True,
    "model_id": "claude-sonnet-4.5",  # Default model
    "enable_security_check": True,  # Enable security check
    "include_git_changes": True,  # Integrate git diff/log in prompt
    "use_relative_paths": True,  # Xuat path tuong doi workspace (tranh PII trong prompt)
}


# ============================================================
# New typed settings API
# ============================================================


def _load_app_settings_unlocked() -> AppSettings:
    """
    Load settings tu file KHONG co lock.

    Chi duoc goi tu ben trong code da acquire _settings_lock,
    hoac tu load_app_settings() (read-only, khong can lock).

    Returns:
        AppSettings instance voi values tu file + defaults
    """
    try:
        if SETTINGS_FILE.exists():
            content = SETTINGS_FILE.read_text(encoding="utf-8")
            saved = json.loads(content)
            return AppSettings.from_dict(saved)
    except (OSError, json.JSONDecodeError):
        pass
    return AppSettings()


def _save_app_settings_unlocked(settings: AppSettings) -> bool:
    """
    Save AppSettings ra file KHONG co lock.

    Chi duoc goi tu ben trong code da acquire _settings_lock.
    Merge voi existing data de bao toan extra keys.

    Returns:
        True neu save thanh cong
    """
    try:
        existing_data: dict[str, Any] = {}
        try:
            if SETTINGS_FILE.exists():
                content = SETTINGS_FILE.read_text(encoding="utf-8")
                existing_data = json.loads(content)
        except (OSError, json.JSONDecodeError):
            pass

        updated = {**existing_data, **settings.to_dict()}
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(updated, indent=2), encoding="utf-8")
        return True
    except (OSError, IOError):
        return False


def load_app_settings() -> AppSettings:
    """
    Load settings tu file va tra ve AppSettings typed instance.

    Read-only operation, khong can lock vi chi doc file.
    Merge saved settings voi defaults cua AppSettings.
    Neu file khong ton tai hoac loi, tra ve defaults.

    Returns:
        AppSettings instance voi values tu file + defaults
    """
    return _load_app_settings_unlocked()


def save_app_settings(settings: AppSettings) -> bool:
    """
    Save AppSettings ra file (thread-safe).

    Args:
        settings: AppSettings instance can luu

    Returns:
        True neu save thanh cong
    """
    with _settings_lock:
        return _save_app_settings_unlocked(settings)


def update_app_setting(**kwargs: Any) -> bool:
    """
    Update mot hoac nhieu settings fields cung luc (thread-safe, atomic).

    Toan bo read-modify-write duoc bao ve boi _settings_lock
    de tranh race condition khi 2 threads update dong thoi.

    Args:
        **kwargs: Field names va values can update (vd: model_id="gpt-4")

    Returns:
        True neu save thanh cong

    Raises:
        TypeError: Neu key khong phai la AppSettings field
    """
    # Validate fields truoc khi acquire lock de fail-fast
    valid_fields = {f for f in AppSettings.__dataclass_fields__}
    for key in kwargs:
        if key not in valid_fields:
            raise TypeError(
                f"'{key}' is not a valid AppSettings field. "
                f"Valid fields: {sorted(valid_fields)}"
            )

    # Atomic read-modify-write duoi lock
    with _settings_lock:
        settings = _load_app_settings_unlocked()
        for key, value in kwargs.items():
            setattr(settings, key, value)
        return _save_app_settings_unlocked(settings)


# ============================================================
# Legacy API (DEPRECATED - giu lai de backward compat)
# ============================================================


def load_settings() -> Dict[str, Any]:
    """
    [DEPRECATED] Load settings tu file.

    Su dung load_app_settings() thay the de co typed access.

    Returns:
        Dict merged voi default settings.
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
    [DEPRECATED] Save settings ra file (thread-safe).

    Su dung save_app_settings() thay the.

    Args:
        settings: Dict settings can luu (se merge voi settings hien tai)

    Returns:
        True neu save thanh cong.
    """
    with _settings_lock:
        try:
            current = load_settings()
            updated = {**current, **settings}

            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps(updated, indent=2), encoding="utf-8")
            return True
        except (OSError, IOError):
            return False


def get_setting(key: str, default: Any = None) -> Any:
    """[DEPRECATED] Helper de lay 1 setting specific. Su dung load_app_settings().field thay the."""
    settings = load_settings()
    return settings.get(key, default or DEFAULT_SETTINGS.get(key))


def set_setting(key: str, value: Any) -> bool:
    """[DEPRECATED] Helper de luu 1 setting specific. Su dung update_app_setting() thay the."""
    return save_settings({key: value})
