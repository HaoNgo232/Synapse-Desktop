from typing import Protocol, Optional, List, runtime_checkable
from pathlib import Path
import pathspec

@runtime_checkable
class IIgnoreEngine(Protocol):
    def build_pathspec(
        self,
        root_path: Path,
        use_default_ignores: bool = True,
        excluded_patterns: Optional[List[str]] = None,
        use_gitignore: bool = True,
    ) -> pathspec.PathSpec:
        ...

    def read_gitignore(self, path: Path) -> List[str]:
        ...

    def find_git_root(self, path: Path) -> Optional[Path]:
        ...

    def clear_cache(self) -> None:
        ...
