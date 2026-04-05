"""
Memory Types - DTOs for memory monitoring and formatting.
"""

from dataclasses import dataclass
from typing import Optional


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
