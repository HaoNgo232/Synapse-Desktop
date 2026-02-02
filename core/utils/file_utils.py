"""
File System Utilities - File tree scanning voi gitignore support

Su dung pathspec thay vi ignore library.
"""

import os
import platform
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
import pathspec
from core.constants import BINARY_EXTENSIONS, EXTENDED_IGNORE_PATTERNS

# Cache for gitignore patterns: root_path -> (mtime, patterns)
_gitignore_cache: Dict[str, Tuple[float, list]] = {}


@dataclass
class TreeItem:
    """
    Mot item trong file tree (file hoac folder).
    Tuong duong VscodeTreeItem trong TypeScript.
    """

    label: str  # Ten hien thi (filename/dirname)
    path: str  # Duong dan tuyet doi
    is_dir: bool = False
    children: list["TreeItem"] = field(default_factory=list)


def is_binary_by_extension(file_path: Path) -> bool:
    """Check if file is binary based on extension"""
    return file_path.suffix.lower() in BINARY_EXTENSIONS


def is_system_path(file_path: Path) -> bool:
    """
    Check if path is an OS system path that should be excluded.
    Supports: Windows, macOS, Linux
    """
    system = platform.system()
    name = file_path.name
    path_str = str(file_path)

    if system == "Windows":
        # Check reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
        if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", name, re.IGNORECASE):
            return True
        # Check system folders
        lower_path = path_str.lower()
        if "\\windows\\" in lower_path or "\\system32\\" in lower_path:
            return True

    elif system == "Darwin":  # macOS
        # Common macOS system files/folders
        if name in (".DS_Store", ".Trashes", ".fseventsd") or name.startswith(
            ".Spotlight-"
        ):
            return True

    elif system == "Linux":
        # Critical Linux system directories
        # Chi check neu scan tu root hoac cac thu muc nay nam trong project
        if path_str.startswith(("/proc/", "/sys/", "/dev/")):
            return True

    return False


def scan_directory(
    root_path: Path,
    excluded_patterns: Optional[list[str]] = None,
    use_gitignore: bool = True,
    use_default_ignores: bool = True,
) -> TreeItem:
    """
    Scan mot directory va tra ve tree structure.

    Chuc nang:
    - Duyet tat ca files/folders trong thu muc goc
    - Tu dong ignore cac patterns mac dinh (node_modules, __pycache__, etc.)
    - Ho tro .gitignore va user-defined patterns

    Args:
        root_path: Thu muc goc can scan
        excluded_patterns: Danh sach patterns de exclude (giong gitignore format)
        use_gitignore: Co doc .gitignore khong (default: True)
        use_default_ignores: Co su dung EXTENDED_IGNORE_PATTERNS khong (default: True)
                            Tat tinh nang nay neu muon scan TAT CA files

    Returns:
        TreeItem root chua toan bo cay thu muc
    """
    root_path = root_path.resolve()

    # Build ignore spec
    ignore_patterns: list[str] = []

    # Always exclude version control directories
    # Luon loai bo cac thu muc version control bat ke cau hinh
    ignore_patterns.extend([".git", ".hg", ".svn"])

    # Thu tu uu tien: VCS > Default > User > Gitignore
    # User patterns co the override default patterns

    # Extended default ignore patterns (port tu Repomix)
    # Bao gom: node_modules, __pycache__, .venv, Cargo.lock, etc.
    if use_default_ignores:
        ignore_patterns.extend(EXTENDED_IGNORE_PATTERNS)

    # Add user-defined patterns (co the override default)
    if excluded_patterns:
        ignore_patterns.extend(excluded_patterns)

    # Read .gitignore if enabled
    if use_gitignore:
        gitignore_patterns = _read_gitignore(root_path)
        ignore_patterns.extend(gitignore_patterns)

    # Create pathspec matcher
    spec = pathspec.PathSpec.from_lines("gitwildmatch", list(ignore_patterns))

    # Build tree recursively
    return _build_tree(root_path, root_path, spec)


def _build_tree(
    current_path: Path, root_path: Path, spec: pathspec.PathSpec
) -> TreeItem:
    """Build tree structure recursively"""
    item = TreeItem(
        label=current_path.name or str(current_path),
        path=str(current_path),
        is_dir=current_path.is_dir(),
    )

    if not current_path.is_dir():
        return item

    try:
        entries = list(current_path.iterdir())
    except PermissionError:
        return item

    # Sort: directories first, then alphabetically
    entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

    for entry in entries:
        # Check system path first (fast exclude)
        if is_system_path(entry):
            continue

        # Get relative path for ignore matching
        try:
            rel_path = entry.relative_to(root_path)
        except ValueError:
            continue

        rel_path_str = str(rel_path)

        # Add trailing slash for directories (pathspec expects this)
        if entry.is_dir():
            rel_path_str += "/"

        # Check if should be ignored
        if spec.match_file(rel_path_str):
            continue

        # Recurse for directories
        if entry.is_dir():
            child = _build_tree(entry, root_path, spec)
            item.children.append(child)
        else:
            item.children.append(
                TreeItem(label=entry.name, path=str(entry), is_dir=False)
            )

    return item


def _read_gitignore(root_path: Path) -> list[str]:
    """
    Doc .gitignore va .git/info/exclude.
    Logic tuong tu TypeScript nhung don gian hoa.
    Uses caching based on .gitignore mtime.
    """
    global _gitignore_cache

    gitignore_path = root_path / ".gitignore"
    cache_key = str(root_path)

    # Check cache validity
    if cache_key in _gitignore_cache:
        cached_mtime, cached_patterns = _gitignore_cache[cache_key]
        try:
            current_mtime = (
                gitignore_path.stat().st_mtime if gitignore_path.exists() else 0
            )
            if current_mtime == cached_mtime:
                return cached_patterns.copy()
        except OSError:
            pass

    patterns: list[str] = []
    gitignore_mtime = 0.0

    # 1) Project .gitignore
    if gitignore_path.exists():
        try:
            gitignore_mtime = gitignore_path.stat().st_mtime
            content = gitignore_path.read_text(encoding="utf-8", errors="replace")
            patterns.extend(content.splitlines())
        except (OSError, IOError):
            pass

    # 2) .git/info/exclude
    exclude_path = root_path / ".git" / "info" / "exclude"
    if exclude_path.exists():
        try:
            content = exclude_path.read_text(encoding="utf-8", errors="replace")
            patterns.extend(content.splitlines())
        except (OSError, IOError):
            pass

    # 3) Global gitignore (simplified - just check common locations)
    home = Path.home()
    global_ignore_candidates = [
        home / ".config" / "git" / "ignore",
        home / ".gitignore_global",
        home / ".gitignore",
    ]

    for candidate in global_ignore_candidates:
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8", errors="replace")
                patterns.extend(content.splitlines())
                break  # Chi doc mot file
            except (OSError, IOError):
                pass

    # Update cache
    _gitignore_cache[cache_key] = (gitignore_mtime, patterns.copy())

    return patterns


def clear_gitignore_cache():
    """Clear the gitignore pattern cache"""
    global _gitignore_cache
    _gitignore_cache.clear()


def flatten_tree_files(tree: TreeItem) -> list[Path]:
    """
    Flatten tree thanh list cac file paths (khong bao gom directories).
    Huu ich khi can list tat ca files de dem token.
    """
    files: list[Path] = []

    def _walk(item: TreeItem):
        if not item.is_dir:
            files.append(Path(item.path))
        for child in item.children:
            _walk(child)

    _walk(tree)
    return files


def get_selected_file_paths(tree: TreeItem, selected_paths: set[str]) -> list[Path]:
    """
    Loc ra cac file paths duoc chon tu set cac duong dan.

    Args:
        tree: TreeItem root
        selected_paths: Set cac duong dan duoc tick

    Returns:
        List cac Path objects cho files duoc chon (chi files, khong co dirs)
    """
    result: list[Path] = []

    def _walk(item: TreeItem):
        if item.path in selected_paths:
            if not item.is_dir:
                result.append(Path(item.path))
            else:
                # Neu chon folder thi lay tat ca files trong do
                for f in flatten_tree_files(item):
                    result.append(f)
        else:
            # Van can check children vi co the chon file trong folder chua duoc chon
            for child in item.children:
                _walk(child)

    _walk(tree)
    return result
