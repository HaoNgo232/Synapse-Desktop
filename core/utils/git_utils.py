"""
Git Utilities - Handle git operations (diff, log, status)
"""

import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List
import logging

# Configure logger
logger = logging.getLogger(__name__)


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


def is_git_installed() -> bool:
    """Check if git is installed and available in PATH."""
    return shutil.which("git") is not None


def is_git_repo(root_path: Path) -> bool:
    """
    Check if path is inside a git repository.
    Uses 'git rev-parse --is-inside-work-tree' for reliable check.
    """
    if not is_git_installed():
        return False

    try:
        result = subprocess.run(
            ["git", "-C", str(root_path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        return False


def get_git_diffs(root_path: Path) -> Optional[GitDiffResult]:
    """
    Get git diff for working tree and staged changes.
    Equivalent to Repomix getGitDiffs.
    """
    if not is_git_repo(root_path):
        return None

    try:
        # Working tree diff (unstaged)
        # --no-color is important to avoid ANSI codes in output
        work_tree = subprocess.run(
            ["git", "-C", str(root_path), "diff", "--no-color"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Staged diff
        staged = subprocess.run(
            ["git", "-C", str(root_path), "diff", "--staged", "--no-color"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        return GitDiffResult(
            work_tree_diff=work_tree.stdout or "", staged_diff=staged.stdout or ""
        )
    except subprocess.TimeoutExpired:
        logger.warning("Git diff timed out")
        return None
    except Exception as e:
        logger.error(f"Failed to get git diffs: {e}")
        return None


def get_git_logs(root_path: Path, max_commits: int = 10) -> Optional[GitLogResult]:
    """
    Get recent git log with changed files.
    Equivalent to Repomix getGitLogs, but properly parsing output.
    """
    if not is_git_repo(root_path):
        return None

    # Format: %x00 (separator) + %h (hash) | %ad (date) | %s (subject)
    # Using %x00 in format string lets git output NULL bytes
    sep = "\x00"
    fmt = "%x00%h|%ad|%s"

    try:
        # git log command
        cmd = [
            "git",
            "-C",
            str(root_path),
            "log",
            f"--pretty=format:{fmt}",
            "--date=iso",
            "--name-only",
            "-n",
            str(max_commits),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            return None

        raw_output = result.stdout
        commits = _parse_git_log(raw_output, sep)

        return GitLogResult(
            commits=commits,
            log_content=raw_output,  # Raw content might be useful for debugging
        )

    except Exception as e:
        logger.error(f"Failed to get git logs: {e}")
        return None


def _parse_git_log(raw_output: str, separator: str) -> List[GitCommit]:
    """
    Parse raw git log output into structured GitCommit objects.
    Logic ported from Repomix gitLogHandle.ts parseGitLog
    """
    if not raw_output.strip():
        return []

    commits: List[GitCommit] = []

    # Split by NULL separator -> list of commit blocks
    # Filter empty strings (first element might be empty due to leading separator)
    entries = [e for e in raw_output.split(separator) if e]

    for entry in entries:
        lines = [line.strip() for line in entry.splitlines() if line.strip()]
        if not lines:
            continue

        # First line contains: hash|date|subject
        header = lines[0]
        parts = header.split("|", 2)

        if len(parts) < 3:
            continue

        commit_hash, date, message = parts[0], parts[1], parts[2]

        # Remaining lines are file paths
        files = lines[1:]

        commits.append(
            GitCommit(hash=commit_hash, date=date, message=message, files=files)
        )

    return commits
