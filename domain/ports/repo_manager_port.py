from dataclasses import dataclass
from typing import Optional, List, Callable, Protocol, runtime_checkable
from pathlib import Path
from datetime import datetime


@dataclass
class RemoteRepoInfo:
    owner: str
    repo: str
    ref: Optional[str] = None
    original_url: str = ""


@dataclass
class CloneProgress:
    status: str
    percentage: Optional[int] = None


@dataclass
class CachedRepo:
    name: str
    path: Path
    size_bytes: int = 0
    last_modified: Optional[datetime] = None
    repo_info: Optional[RemoteRepoInfo] = None


ProgressCallback = Callable[[CloneProgress], None]


@runtime_checkable
class IRepoManager(Protocol):
    def clone_repo(
        self,
        url: str,
        on_progress: Optional[ProgressCallback] = None,
        timeout: Optional[int] = None,
        force_reclone: bool = False,
    ) -> Path: ...

    def get_cached_repos(self) -> List[CachedRepo]: ...

    def delete_repo(self, repo_name: str) -> bool: ...

    def clear_cache(self) -> int: ...

    def get_cache_size(self) -> int: ...

    def format_size(self, size_bytes: int) -> str: ...

    def is_dirty(self, repo_path: Path) -> bool: ...

    def stash_changes(self, repo_path: Path) -> bool: ...

    def discard_changes(self, repo_path: Path) -> bool: ...
