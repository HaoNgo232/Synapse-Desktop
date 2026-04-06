from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List


from domain.git.models import GitDiffResult, GitLogResult


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
    def get_diff_result(
        self, workspace: Path, base_ref: Optional[str] = None
    ) -> Optional[GitDiffResult]:
        """Lấy kết quả diff dưới dạng cấu trúc GitDiffResult."""
        pass

    @abstractmethod
    def get_log_result(
        self, workspace: Path, max_commits: int = 10
    ) -> Optional[GitLogResult]:
        """Lấy kết quả git log dưới dạng cấu trúc GitLogResult."""
        pass

    @abstractmethod
    def get_changed_files(self, workspace: Path) -> List[str]:
        """Lấy danh sách các tập tin đã thay đổi."""
        pass
