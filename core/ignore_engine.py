"""
Ignore Engine - Single source of truth cho tat ca logic ignore/gitignore.

Thay the cac doan code bi trung lap o:
- core/utils/file_utils.py (scan_directory, scan_directory_shallow, load_folder_children)
- core/utils/file_scanner.py (FileScanner._build_ignore_patterns)
- components/file_tree_model.py (_collect_files_from_disk, _build_search_index_async)

Cung cap:
- build_ignore_patterns(): Tap hop patterns tu VCS + default + user + gitignore
- build_pathspec(): Tao pathspec.PathSpec tu patterns (co cache)
- read_gitignore(): Doc .gitignore, .git/info/exclude, global gitignore (co cache)
- find_git_root(): Tim git root directory tu mot path bat ky
- clear_cache(): Xoa tat ca cache

SOLID: Single Responsibility - chi lo viec quyet dinh "file/folder nay co bi ignore khong"
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pathspec

from core.constants import EXTENDED_IGNORE_PATTERNS

# === Cache ===
# Cache cho gitignore patterns: root_path -> (mtime, patterns)
_gitignore_cache: Dict[str, Tuple[float, list]] = {}

# Cache cho PathSpec objects: cache_key -> (mtime, PathSpec)
_pathspec_cache: Dict[str, Tuple[float, pathspec.PathSpec]] = {}


# === Cac VCS directories luon bi exclude ===
VCS_DIRS = [".git", ".hg", ".svn"]


def build_ignore_patterns(
    root_path: Path,
    *,
    use_default_ignores: bool = True,
    excluded_patterns: Optional[List[str]] = None,
    use_gitignore: bool = True,
) -> List[str]:
    """
    Tap hop tat ca ignore patterns tu nhieu nguon.

    Thu tu uu tien: VCS > Default (EXTENDED_IGNORE) > User > Gitignore.
    User patterns co the override default patterns.

    Args:
        root_path: Thu muc goc cua workspace/project
        use_default_ignores: Co dung EXTENDED_IGNORE_PATTERNS khong (default: True)
        excluded_patterns: Danh sach patterns tu user (gitignore format)
        use_gitignore: Co doc .gitignore khong (default: True)

    Returns:
        List cac ignore patterns (gitignore format)
    """
    patterns: List[str] = []

    # 1. Luon exclude VCS directories
    patterns.extend(VCS_DIRS)

    # 2. Default ignore patterns (port tu Repomix)
    # Bao gom: node_modules, __pycache__, .venv, Cargo.lock, etc.
    if use_default_ignores:
        patterns.extend(EXTENDED_IGNORE_PATTERNS)

    # 3. User-defined patterns (co the override default)
    if excluded_patterns:
        patterns.extend(excluded_patterns)

    # 4. Gitignore patterns (.gitignore + .git/info/exclude + global)
    if use_gitignore:
        gitignore_pats = read_gitignore(root_path)
        patterns.extend(gitignore_pats)

    return patterns


def build_pathspec(
    root_path: Path,
    *,
    use_default_ignores: bool = True,
    excluded_patterns: Optional[List[str]] = None,
    use_gitignore: bool = True,
) -> pathspec.PathSpec:
    """
    Tao pathspec.PathSpec tu tat ca ignore patterns (co cache).

    Wrapper convenience: goi build_ignore_patterns() roi tao PathSpec.
    Su dung cache de tranh tao lai PathSpec khi patterns khong doi.

    Args:
        root_path: Thu muc goc cua workspace/project
        use_default_ignores: Co dung EXTENDED_IGNORE_PATTERNS khong
        excluded_patterns: Danh sach patterns tu user
        use_gitignore: Co doc .gitignore khong

    Returns:
        pathspec.PathSpec object de match files/folders
    """
    patterns = build_ignore_patterns(
        root_path,
        use_default_ignores=use_default_ignores,
        excluded_patterns=excluded_patterns,
        use_gitignore=use_gitignore,
    )
    return get_cached_pathspec(root_path, patterns)


def get_cached_pathspec(root_path: Path, patterns: List[str]) -> pathspec.PathSpec:
    """
    Cache PathSpec object, invalidate khi .gitignore thay doi hoac patterns thay doi.

    Cache key bao gom ca root_path va patterns hash de dam bao:
    - Khac patterns -> khac PathSpec (tranh cache collision)
    - Patterns giong nhau + gitignore unchanged -> reuse cache

    Args:
        root_path: Root path cua workspace
        patterns: List patterns de build PathSpec

    Returns:
        Cached hoac newly created PathSpec object
    """
    # Include patterns hash trong cache key de tranh collision
    patterns_hash = hash(tuple(patterns))
    cache_key = f"{root_path}:{patterns_hash}"
    gitignore_mtime = _get_gitignore_mtime(root_path)

    if cache_key in _pathspec_cache:
        cached_mtime, cached_spec = _pathspec_cache[cache_key]
        if cached_mtime == gitignore_mtime:
            return cached_spec

    # Tao PathSpec moi va cache
    spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    _pathspec_cache[cache_key] = (gitignore_mtime, spec)
    return spec


def read_gitignore(root_path: Path) -> List[str]:
    """
    Doc .gitignore va .git/info/exclude va global gitignore.

    Su dung cache dua tren .gitignore mtime de tranh doc lai file.

    Sources (theo thu tu):
    1. root_path/.gitignore
    2. root_path/.git/info/exclude
    3. Global gitignore (~/.config/git/ignore hoac ~/.gitignore_global)

    Args:
        root_path: Thu muc goc chua .gitignore

    Returns:
        List cac gitignore patterns (raw lines tu file)
    """
    global _gitignore_cache

    gitignore_path = root_path / ".gitignore"
    cache_key = str(root_path)

    # Kiem tra cache validity
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

    patterns: List[str] = []
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

    # 3) Global gitignore (kiem tra cac vi tri pho bien)
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


def find_git_root(start_path: Path) -> Path:
    """
    Tim git root directory bang cach traverse len parent directories.

    Args:
        start_path: Thu muc bat dau tim

    Returns:
        Path den git root, hoac start_path neu khong tim thay .git
    """
    root_path = start_path
    while root_path.parent != root_path:
        if (root_path / ".git").exists():
            break
        root_path = root_path.parent
    return root_path


def clear_cache() -> None:
    """Xoa tat ca cache (gitignore patterns va PathSpec objects)."""
    global _gitignore_cache, _pathspec_cache
    _gitignore_cache.clear()
    _pathspec_cache.clear()


def _get_gitignore_mtime(root_path: Path) -> float:
    """Lay modification time cua .gitignore file."""
    gitignore_file = root_path / ".gitignore"
    if gitignore_file.exists():
        return gitignore_file.stat().st_mtime
    return 0.0
