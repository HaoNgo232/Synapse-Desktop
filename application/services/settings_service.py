"""
Settings Application Service - Provides a clean API for settings management.
Decouples Presentation from Persistence (Infrastructure).
"""

from typing import Any
from shared.types.app_settings import AppSettings
from infrastructure.persistence import settings_manager
from infrastructure.persistence.settings_manager import (
    load_settings as load_settings,
    save_settings as save_settings,
    DEFAULT_SETTINGS as DEFAULT_SETTINGS,
)


def load_app_settings() -> AppSettings:
    """Load settings via infrastructure layer (typed)."""
    return settings_manager.load_app_settings()


def save_app_settings(settings: AppSettings) -> bool:
    """Save settings via infrastructure layer (typed)."""
    return settings_manager.save_app_settings(settings)


def update_app_setting(**kwargs: Any) -> bool:
    """Update specific settings atomically via infrastructure layer (typed)."""
    return settings_manager.update_app_setting(**kwargs)


def add_instruction_history(text: str, max_items: int = 30) -> bool:
    """Add instruction to history."""
    return settings_manager.add_instruction_history(text, max_items)
