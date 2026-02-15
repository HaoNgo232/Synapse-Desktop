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
    commit_count: int = 0
    error: Optional[str] = None


@dataclass
class DiffOnlyResult:
    """Kết quả cho Copy Diff Only feature"""
    diff_content: str
    files_changed: int
    insertions: int
    deletions: int
    commits_included: int
    changed_files: List[str] = field(default_factory=list)  # List of changed file paths
    error: Optional[str] = None


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


def get_diff_only(
    workspace_path: Path,
    num_commits: int = 1,
    include_staged: bool = True,
    include_unstaged: bool = True,
) -> DiffOnlyResult:
    """
    Lấy chỉ git diff - không bao gồm source code đầy đủ.
    
    Mục đích: Cho AI review các thay đổi gần đây mà không cần context toàn bộ project.
    
    Args:
        workspace_path: Path đến workspace
        num_commits: Số commits gần nhất cần include (0 = chỉ uncommitted changes)
        include_staged: Bao gồm staged changes
        include_unstaged: Bao gồm unstaged changes
    
    Returns:
        DiffOnlyResult với diff content và statistics
    """
    if not is_git_repo(workspace_path):
        return DiffOnlyResult(
            diff_content="",
            files_changed=0,
            insertions=0,
            deletions=0,
            commits_included=0,
            error="Not a git repository"
        )
    
    diff_parts: list[str] = []
    changed_files: list[str] = []  # Track changed file paths
    total_files = 0
    total_insertions = 0
    total_deletions = 0
    
    try:
        # 1. Uncommitted changes (staged + unstaged)
        if include_unstaged:
            # Unstaged changes (working tree vs index)
            result = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                unstaged_diff = subprocess.run(
                    ["git", "diff"],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if unstaged_diff.stdout.strip():
                    diff_parts.append("# Unstaged Changes (Working Tree)\n")
                    diff_parts.append(unstaged_diff.stdout)
                    # Parse stats
                    stats = _parse_diff_stats(result.stdout)
                    total_files += stats[0]
                    total_insertions += stats[1]
                    total_deletions += stats[2]
                    # Collect changed files
                    changed_files.extend(_extract_changed_files(result.stdout))
        
        if include_staged:
            # Staged changes (index vs HEAD)
            result = subprocess.run(
                ["git", "diff", "--cached", "--stat"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                staged_diff = subprocess.run(
                    ["git", "diff", "--cached"],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if staged_diff.stdout.strip():
                    diff_parts.append("\n# Staged Changes (Ready to Commit)\n")
                    diff_parts.append(staged_diff.stdout)
                    stats = _parse_diff_stats(result.stdout)
                    total_files += stats[0]
                    total_insertions += stats[1]
                    total_deletions += stats[2]
                    # Collect changed files
                    changed_files.extend(_extract_changed_files(result.stdout))
        
        # 2. Recent commits diff
        commits_included = 0
        if num_commits > 0:
            # Get diff of last N commits
            result = subprocess.run(
                ["git", "log", f"-{num_commits}", "--oneline"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                commit_lines = result.stdout.strip().split("\n")
                commits_included = len(commit_lines)
                
                # Get combined diff
                diff_result = subprocess.run(
                    ["git", "diff", f"HEAD~{num_commits}..HEAD"],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if diff_result.returncode == 0 and diff_result.stdout.strip():
                    diff_parts.append(f"\n# Recent Commits ({commits_included} commits)\n")
                    diff_parts.append("# Commits:\n")
                    for line in commit_lines:
                        diff_parts.append(f"#   {line}\n")
                    diff_parts.append("\n")
                    diff_parts.append(diff_result.stdout)
                    
                    # Get stats
                    stat_result = subprocess.run(
                        ["git", "diff", "--stat", f"HEAD~{num_commits}..HEAD"],
                        cwd=workspace_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if stat_result.returncode == 0:
                        stats = _parse_diff_stats(stat_result.stdout)
                        total_files += stats[0]
                        total_insertions += stats[1]
                        total_deletions += stats[2]
                        # Collect changed files from commits
                        changed_files.extend(_extract_changed_files(stat_result.stdout))
        
        diff_content = "".join(diff_parts)
        
        # Deduplicate changed files while preserving order
        seen = set()
        unique_files = []
        for f in changed_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)
        
        return DiffOnlyResult(
            diff_content=diff_content,
            files_changed=total_files,
            insertions=total_insertions,
            deletions=total_deletions,
            commits_included=commits_included,
            changed_files=unique_files,
            error=None
        )
        
    except subprocess.TimeoutExpired:
        return DiffOnlyResult(
            diff_content="",
            files_changed=0,
            insertions=0,
            deletions=0,
            commits_included=0,
            error="Git command timed out"
        )
    except Exception as e:
        return DiffOnlyResult(
            diff_content="",
            files_changed=0,
            insertions=0,
            deletions=0,
            commits_included=0,
            error=str(e)
        )


def _parse_diff_stats(stat_output: str) -> tuple[int, int, int]:
    """
    Parse git diff --stat output để lấy files changed, insertions, deletions.
    
    Returns:
        (files_changed, insertions, deletions)
    """
    import re
    
    # Last line format: "X files changed, Y insertions(+), Z deletions(-)"
    lines = stat_output.strip().split("\n")
    if not lines:
        return (0, 0, 0)
    
    last_line = lines[-1]
    
    files = 0
    insertions = 0
    deletions = 0
    
    # Parse files changed
    files_match = re.search(r"(\d+) files? changed", last_line)
    if files_match:
        files = int(files_match.group(1))
    
    # Parse insertions
    ins_match = re.search(r"(\d+) insertions?\(\+\)", last_line)
    if ins_match:
        insertions = int(ins_match.group(1))
    
    # Parse deletions
    del_match = re.search(r"(\d+) deletions?\(-\)", last_line)
    if del_match:
        deletions = int(del_match.group(1))
    
    return (files, insertions, deletions)


def _extract_changed_files(stat_output: str) -> list[str]:
    """
    Extract danh sách file paths từ git diff --stat output.
    
    Format của mỗi dòng: " path/to/file.py | N +++ --"
    
    Args:
        stat_output: Output từ git diff --stat
    
    Returns:
        List các file paths đã thay đổi
    """
    files = []
    lines = stat_output.strip().split("\n")
    
    for line in lines:
        # Skip summary line (cuối cùng chứa "files changed")
        if "changed" in line and ("insertion" in line or "deletion" in line):
            continue
        
        # Format: " path/to/file | stats"
        if "|" in line:
            file_part = line.split("|")[0].strip()
            if file_part:
                # Handle renamed files: "old_name => new_name"
                if "=>" in file_part:
                    # Lấy new name
                    parts = file_part.split("=>")
                    if len(parts) == 2:
                        file_part = parts[1].strip()
                        # Handle path prefix: "{dir/}old => new"
                        if "{" in parts[0]:
                            prefix = parts[0].split("{")[0]
                            file_part = prefix + file_part.rstrip("}")
                files.append(file_part)
    
    return files


def build_diff_only_prompt(
    diff_result: DiffOnlyResult,
    instructions: str,
    include_changed_content: bool,
    include_tree_structure: bool,
) -> str:
    """
    Build prompt from diff result for Copy Diff Only feature.
    
    Args:
        diff_result: DiffOnlyResult from get_diff_only()
        instructions: User instructions text
        include_changed_content: Include full content of changed files
        include_tree_structure: Include changed file tree structure
    
    Returns:
        Formatted prompt string
    """
    parts = [
        "<diff_context>",
        f"Files changed: {diff_result.files_changed}",
        f"Lines: +{diff_result.insertions} / -{diff_result.deletions}",
    ]
    if diff_result.commits_included > 0:
        parts.append(f"Commits included: {diff_result.commits_included}")
    parts.extend(["</diff_context>", ""])

    if include_tree_structure and diff_result.changed_files:
        tree_str = _build_tree_from_paths(diff_result.changed_files[:50])
        parts.extend(["<project_structure>", tree_str, "</project_structure>", ""])

    parts.extend(["<git_diff>", diff_result.diff_content, "</git_diff>"])

    if include_changed_content and diff_result.changed_files:
        parts.extend(["", "<changed_files_content>"])
        for file_path in diff_result.changed_files[:20]:
            full_path = Path(file_path)
            if full_path.exists() and full_path.is_file():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    if len(content) <= 50000:
                        from core.utils.language_utils import get_language_from_path
                        lang = get_language_from_path(str(full_path))
                        parts.extend([
                            f'<file path="{file_path}">',
                            f"```{lang}",
                            content,
                            "```",
                            "</file>",
                        ])
                except Exception:
                    pass
        parts.append("</changed_files_content>")

    if instructions and instructions.strip():
        parts.extend(["", "<user_instructions>", instructions.strip(), "</user_instructions>"])

    return "\n".join(parts)


def _build_tree_from_paths(file_paths: List[str]) -> str:
    """Build tree hierarchy string from a list of file paths."""
    tree_dict: dict = {}
    for file_path in file_paths:
        path_parts = file_path.replace("\\", "/").split("/")
        current = tree_dict
        for i, part in enumerate(path_parts):
            if i == len(path_parts) - 1:
                current[part] = None  # file
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

    lines: list = []
    _render_tree_dict(tree_dict, lines, prefix="")
    return "\n".join(lines)


def _render_tree_dict(tree_dict: dict, lines: list, prefix: str = "") -> None:
    """Render tree dict dùng ├──/└──/│ giống _build_tree_string trong prompt_generator."""
    # Sắp xếp: folders trước, files sau (giống scan_directory)
    items = sorted(tree_dict.items(), key=lambda x: (x[1] is None, x[0]))
    for i, (name, children) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        if children is None:
            # File — thêm marker [modified]
            lines.append(f"{prefix}{connector}{name} [modified]")
        else:
            # Folder
            lines.append(f"{prefix}{connector}{name}/")
            # Prefix cho children: "    " nếu là item cuối, "│   " nếu còn item khác
            new_prefix = prefix + ("    " if is_last else "│   ")
            _render_tree_dict(children, lines, new_prefix)
