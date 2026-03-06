"""
Workspace Config - Cau hinh workspace (excluded patterns, gitignore, relative paths).

Module nay cung cap cac utility functions de doc/ghi workspace config tu settings.
Tach rieng khoi view layer de tuan thu Dependency Inversion Principle:
model/component/service layers KHONG nen import tu view layer.

Functions:
- get_excluded_patterns(): Lay danh sach excluded patterns
- get_use_gitignore(): Kiem tra co respect .gitignore khong
- get_use_relative_paths(): Kiem tra co dung relative paths khong
- add_excluded_patterns(): Them excluded patterns moi
- remove_excluded_patterns(): Xoa excluded patterns
"""

from typing import Callable

from services.settings_manager import (
    load_app_settings,
    update_app_setting,
)


# ============================================================
# Preset profiles cho excluded patterns
# ============================================================

PRESET_PROFILES = {
    "Node.js": "node_modules\ndist\nbuild\n.next\ncoverage\npackage-lock.json\npnpm-lock.yaml\nyarn.lock",
    "Python": "__pycache__\n.pytest_cache\n.venv\nvenv\nbuild\ndist\n*.pyc\n.mypy_cache",
    "Java": "target\nout\n.gradle\n.classpath\n.project\n.settings",
    "Go": "vendor\nbin\ndist\ncoverage.out",
}


# ============================================================
# Public helpers - Doc/ghi workspace config tu settings
# ============================================================


def get_excluded_patterns() -> list[str]:
    """Tra ve danh sach excluded patterns da normalize tu settings."""
    settings = load_app_settings()
    return settings.get_excluded_patterns_list()


def get_use_gitignore() -> bool:
    """Tra ve co respect .gitignore khong (True/False)."""
    return load_app_settings().use_gitignore


def get_use_relative_paths() -> bool:
    """Tra ve co dung workspace-relative paths trong prompts khong."""
    return load_app_settings().use_relative_paths


# ============================================================
# Signal notifier - Thong bao khi excluded patterns thay doi
# ============================================================


class ExcludedChangedNotifier:
    """Notifier phat signal khi excluded patterns thay doi (vd: tu Ignore button)."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[[], None]] = []

    def connect(self, callback: Callable[[], None]) -> None:
        """Subscribe to excluded patterns changes."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def disconnect(self, callback: Callable[[], None]) -> None:
        """Unsubscribe from excluded patterns changes."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def emit(self) -> None:
        """Notify all subscribers that excluded patterns changed."""
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass  # Ignore callback errors


# Singleton notifier instance — subscribe tu bat ky module nao
_excluded_notifier: ExcludedChangedNotifier = ExcludedChangedNotifier()


def add_excluded_patterns(patterns: list[str]) -> bool:
    """
    Them excluded patterns moi, tranh duplicate.

    Su dung typed API `update_app_setting` de dam bao thread-safe
    va tuong thich voi AppSettings.

    Args:
        patterns: Danh sach patterns can them

    Returns:
        True neu luu thanh cong
    """
    existing = get_excluded_patterns()
    merged = existing[:]
    for pattern in patterns:
        normalized = pattern.strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    new_value = "\n".join(merged)
    if update_app_setting(excluded_folders=new_value):
        _excluded_notifier.emit()
        return True
    return False


def remove_excluded_patterns(patterns: list[str]) -> bool:
    """
    Xoa excluded patterns khoi settings.

    Su dung typed API `update_app_setting` de dam bao thread-safe
    va tuong thich voi AppSettings.

    Args:
        patterns: Danh sach patterns can xoa

    Returns:
        True neu luu thanh cong
    """
    to_remove = {p.strip() for p in patterns if p.strip()}
    existing = get_excluded_patterns()
    filtered = [p for p in existing if p not in to_remove]
    new_value = "\n".join(filtered)
    if update_app_setting(excluded_folders=new_value):
        _excluded_notifier.emit()
        return True
    return False
