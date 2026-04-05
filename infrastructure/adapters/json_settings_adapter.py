from typing import Any
from domain.ports.settings import ISettingsProvider
from infrastructure.persistence.settings_manager import (
    load_app_settings,
    save_app_settings,
    update_app_setting,
    AppSettings,
)


class JsonSettingsAdapter(ISettingsProvider):
    """
    Adapter cho cài đặt ứng dụng, sử dụng tệp JSON và AppSettings DTO.
    """

    def __init__(self):
        self._settings: AppSettings = load_app_settings()

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self._settings, key, default)

    def set(self, key: str, value: Any) -> None:
        setattr(self._settings, key, value)

    def save(self) -> None:
        save_app_settings(self._settings)

    def reload(self) -> None:
        self._settings = load_app_settings()

    def update(self, **kwargs: Any) -> bool:
        """Cập nhật nhiều settings cùng lúc."""
        res = update_app_setting(**kwargs)
        if res:
            self.reload()
        return res
