from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class GitDiffResult:
    work_tree_diff: str = ""
    staged_diff: str = ""

@dataclass
class GitCommit:
    hash: str
    date: str
    message: str
    files: List[str] = field(default_factory=list)

@dataclass
class GitLogResult:
    commits: List[GitCommit] = field(default_factory=list)
    log_content: str = ""
    commit_count: int = 0
    error: Optional[str] = None
