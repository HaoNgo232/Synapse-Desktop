from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GitDiffResult:
    """Kết quả diff làm việc (staged + unstaged)."""

    work_tree_diff: str = ""
    staged_diff: str = ""


@dataclass
class GitCommit:
    """Thông tin một commit."""

    hash: str
    date: str
    message: str
    files: List[str] = field(default_factory=list)


@dataclass
class GitLogResult:
    """Kết quả git log gần đây."""

    commits: List[GitCommit] = field(default_factory=list)
    log_content: str = ""
    commit_count: int = 0
    error: Optional[str] = None
