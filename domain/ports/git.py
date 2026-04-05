from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List


class IGitRepository(ABC):
    """
    Interface cho các thao tác với kho lưu trữ Git.
    """

    @abstractmethod
    def get_current_branch(self, workspace: Path) -> Optional[str]:
        """Lấy tên nhánh hiện tại của Git repository."""
        pass

    @abstractmethod
    def is_repo(self, path: Path) -> bool:
        """Kiểm tra đường dẫn có phải là một kho lưu trữ Git không."""
        pass

    @abstractmethod
    def get_diff(self, workspace: Path) -> str:
        """Lấy sự biệt biệt của mã nguồn (git diff)."""
        pass

    @abstractmethod
    def get_changed_files(self, workspace: Path) -> List[str]:
        """Lấy danh sách các tập tin đã thay đổi."""
        pass
