from abc import ABC, abstractmethod
from typing import Callable, Optional
from dataclasses import dataclass


@dataclass
class MemoryStats:
    """
    Thống kê memory usage.
    """

    rss_mb: float
    token_cache_count: int = 0
    file_count: int = 0
    warning: Optional[str] = None


class IMemoryMonitor(ABC):
    """
    Interface cho service theo dõi memory usage của app.
    """

    @property
    @abstractmethod
    def on_update(self) -> Optional[Callable[[MemoryStats], None]]:
        """Lấy callback update."""
        pass

    @on_update.setter
    @abstractmethod
    def on_update(self, callback: Optional[Callable[[MemoryStats], None]]) -> None:
        """Thiết lập callback update."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Bắt đầu monitoring."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Dừng monitoring."""
        pass

    @abstractmethod
    def set_token_cache_count(self, count: int) -> None:
        """Cập nhật token cache count."""
        pass

    @abstractmethod
    def set_file_count(self, count: int) -> None:
        """Cập nhật file count."""
        pass

    @abstractmethod
    def get_current_stats(self) -> MemoryStats:
        """Lấy stats hiện tại."""
        pass


def format_memory_display(stats: MemoryStats) -> str:
    """
    Format memory stats thành string để hiển thị.
    """
    parts = [f"Mem: {stats.rss_mb:.0f}MB"]

    if stats.token_cache_count > 0:
        if stats.token_cache_count >= 1000:
            cache_str = f"{stats.token_cache_count / 1000:.1f}k"
        else:
            cache_str = str(stats.token_cache_count)
        parts.append(f"Cache: {cache_str}")

    if stats.file_count > 0:
        parts.append(f"Files: {stats.file_count}")

    return " | ".join(parts)
