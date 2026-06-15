import abc
from pathlib import Path
from typing import Optional
from shared.types.git_types import GitDiffResult, GitLogResult

class IGitService(abc.ABC):
    @abc.abstractmethod
    def get_diffs(self, root_path: Path, base_ref: Optional[str] = None) -> Optional[GitDiffResult]:
        """Lay git diff cua repository."""
        pass

    @abc.abstractmethod
    def get_logs(self, root_path: Path, max_commits: int = 10) -> Optional[GitLogResult]:
        """Lay git log cua repository."""
        pass
