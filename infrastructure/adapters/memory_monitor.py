"""
Memory Monitor Service - Theo dõi memory usage của app

Cung cấp:
- Track RSS memory (resident set size)
- Track cache sizes
- Periodic updates
- Warning khi memory cao
"""

import os
from typing import Callable, Optional
from dataclasses import dataclass

from PySide6.QtCore import QTimer

from core.logging_config import log_error

# psutil should always be available (in requirements.txt)
# but wrap in try/except for runtime errors
import psutil


@dataclass
class MemoryStats:
    """
    Thống kê memory usage.

    Attributes:
        rss_mb: Resident Set Size in MB (actual physical memory used)
        token_cache_count: Số entries trong token cache
        file_count: Số files trong tree
        warning: Warning message nếu có
    """

    rss_mb: float
    token_cache_count: int = 0
    file_count: int = 0
    warning: Optional[str] = None


class MemoryMonitor:
    """
    Service theo dõi memory usage của app.

    Uses QTimer on the main thread — psutil.memory_info() is fast (<1ms)
    so it's safe to call without a background thread. This eliminates
    the need to marshal callbacks back to the UI thread.

    Features:
    - Periodic monitoring (default 10 seconds)
    - Callback khi có update (runs on main thread — safe for UI)
    - Warning khi memory vượt ngưỡng
    """

    # Ngưỡng warning (MB)
    WARNING_THRESHOLD_MB = 500
    CRITICAL_THRESHOLD_MB = 1000

    # Update interval (milliseconds)
    UPDATE_INTERVAL_MS = 10_000

    def __init__(self, on_update: Optional[Callable[[MemoryStats], None]] = None):
        """
        Khởi tạo MemoryMonitor.

        Args:
            on_update: Callback khi có memory stats mới.
                       Called on main thread — safe for direct UI updates.
        """
        self.on_update = on_update
        self._timer: Optional[QTimer] = None
        self._is_running = False
        self._process = psutil.Process(os.getpid())

        # External stats (set từ bên ngoài)
        self._token_cache_count = 0
        self._file_count = 0

    def start(self):
        """Bắt đầu monitoring. Must be called from main thread."""
        if self._is_running:
            return

        # Guard: QTimer must be created on the main thread
        from PySide6.QtCore import QThread, QCoreApplication

        app = QCoreApplication.instance()
        if app and QThread.currentThread() != app.thread():
            log_error("MemoryMonitor.start() called from non-main thread")
            return

        self._is_running = True
        self._timer = QTimer()
        self._timer.setInterval(self.UPDATE_INTERVAL_MS)
        self._timer.timeout.connect(self._do_update)
        self._timer.start()

    def stop(self):
        """Dừng monitoring"""
        self._is_running = False
        if self._timer:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None

    def set_token_cache_count(self, count: int):
        """Update token cache count từ TokenDisplayService"""
        self._token_cache_count = count

    def set_file_count(self, count: int):
        """Update file count từ FileTreeComponent"""
        self._file_count = count

    def get_current_stats(self) -> MemoryStats:
        """
        Lấy memory stats hiện tại.

        Returns:
            MemoryStats với thông tin memory usage
        """
        rss_mb = 0.0

        # Method 1: psutil (chính xác nhất)
        try:
            mem_info = self._process.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
        except Exception:
            # Method 2: Fallback đọc /proc trên Linux
            rss_mb = self._read_proc_memory()

        # Xác định warning
        warning = None
        if rss_mb >= self.CRITICAL_THRESHOLD_MB:
            warning = f"Critical: Memory usage {rss_mb:.0f}MB exceeds {self.CRITICAL_THRESHOLD_MB}MB!"
        elif rss_mb >= self.WARNING_THRESHOLD_MB:
            warning = f"Warning: Memory usage {rss_mb:.0f}MB is high"
        elif rss_mb == 0:
            warning = "Unable to read memory stats"

        return MemoryStats(
            rss_mb=rss_mb,
            token_cache_count=self._token_cache_count,
            file_count=self._file_count,
            warning=warning,
        )

    def _read_proc_memory(self) -> float:
        """Fallback: đọc memory từ /proc/self/status (Linux only)"""
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return int(parts[1]) / 1024  # kB to MB
        except Exception:
            pass
        return 0.0

    def _do_update(self):
        """Thực hiện update và notify callback.

        Runs on main thread via QTimer — safe to update UI directly.
        """
        if not self._is_running:
            return

        stats = self.get_current_stats()

        if self.on_update:
            try:
                self.on_update(stats)
            except Exception as e:
                from core.logging_config import log_debug

                log_debug(f"[MemoryMonitor] Callback error: {e}")


# Singleton instance
_monitor: Optional[MemoryMonitor] = None


def get_memory_monitor() -> MemoryMonitor:
    """
    Lấy singleton MemoryMonitor instance.

    Returns:
        MemoryMonitor instance
    """
    global _monitor
    if _monitor is None:
        _monitor = MemoryMonitor()
    return _monitor


def format_memory_display(stats: MemoryStats) -> str:
    """
    Format memory stats thành string để hiển thị.

    Args:
        stats: MemoryStats object

    Returns:
        Formatted string, ví dụ: "Memory: 156MB | Cache: 1.2k | Files: 350"
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
