from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class HistoryEntry:
    """Một entry trong lịch sử"""

    id: str  # UUID
    timestamp: str  # ISO format
    workspace_path: str
    opx_content: str
    file_count: int
    success_count: int
    fail_count: int
    action_summary: List[str] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)


class IHistoryService(ABC):
    """
    Interface cho HistoryService quản lý lịch sử thao tác.
    """

    @abstractmethod
    def add_history_entry(
        self,
        workspace_path: str,
        opx_content: str,
        action_results: List[dict],
    ) -> Optional[HistoryEntry]:
        """Thêm entry mới vào lịch sử."""
        pass

    @abstractmethod
    def get_history_entries(self, limit: int = 50) -> List[HistoryEntry]:
        """Lấy danh sách entries."""
        pass

    @abstractmethod
    def get_entry_by_id(self, entry_id: str) -> Optional[HistoryEntry]:
        """Tìm entry theo ID."""
        pass

    @abstractmethod
    def delete_entry(self, entry_id: str) -> bool:
        """Xóa một entry."""
        pass

    @abstractmethod
    def clear_history(self) -> bool:
        """Xóa toàn bộ lịch sử."""
        pass

    @abstractmethod
    def get_history_stats(self) -> dict:
        """Lấy thống kê lịch sử."""
        pass
