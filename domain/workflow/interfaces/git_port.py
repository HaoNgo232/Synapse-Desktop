import abc
from pathlib import Path
from typing import Optional, List
from shared.types.git_types import GitDiffResult, GitLogResult, DiffOnlyResult


class IGitService(abc.ABC):
    @abc.abstractmethod
    def get_diffs(
        self, root_path: Path, base_ref: Optional[str] = None
    ) -> Optional[GitDiffResult]:
        """Lay git diff cua repository."""
        pass

    @abc.abstractmethod
    def get_logs(
        self, root_path: Path, max_commits: int = 10
    ) -> Optional[GitLogResult]:
        """Lay git log cua repository."""
        pass

    @abc.abstractmethod
    def get_diff_only(
        self,
        root_path: Path,
        num_commits: int = 0,
        include_staged: bool = True,
        include_unstaged: bool = True,
    ) -> DiffOnlyResult:
        """Lay git diff rut gon cho Copy Diff Only."""
        pass

    @abc.abstractmethod
    def filter_diff_by_files(self, diff_content: str, files: List[str]) -> str:
        """Loc noi dung diff chi giu lai cac file trong danh sach."""
        pass

    @abc.abstractmethod
    def extract_changed_files_from_diff(self, diff_content: str) -> List[str]:
        """Trich xuat danh sach file thay doi tu noi dung diff."""
        pass

    @abc.abstractmethod
    def build_diff_prompt(
        self,
        diff_result: DiffOnlyResult,
        instructions: str,
        include_changed_content: bool,
        include_tree_structure: bool,
        workspace_root: Optional[Path] = None,
        use_relative_paths: bool = False,
        include_related_files: bool = False,
        related_depth: int = 1,
        related_max_files: int = 20,
        output_format: str = "xml",
    ) -> str:
        """Build prompt from diff result for Copy Diff Only."""
        pass
