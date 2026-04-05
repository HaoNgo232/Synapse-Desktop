from abc import ABC, abstractmethod
from typing import Any


class ISettingsProvider(ABC):
    """
    Interface cho việc quản lý và lưu trữ cài đặt ứng dụng.
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Lấy giá trị cài đặt theo key."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Lưu giá trị cài đặt theo key."""
        pass

    @abstractmethod
    def save(self) -> None:
        """Lưu toàn bộ cài đặt xuống kho lưu trữ bền vững."""
        pass

    @abstractmethod
    def reload(self) -> None:
        """Tải lại cài đặt từ kho lưu trữ."""
        pass
