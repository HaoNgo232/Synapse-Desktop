"""
Workspace Index - Filesystem scanning va search index KHONG phu thuoc Qt.

Module nay tach logic filesystem ra khoi file_tree_model.py:
- build_search_index(): Build flat search index qua os.walk
- search_in_index(): Tim files theo query (case-insensitive)
- collect_files_from_disk(): Scan folder de lay tat ca files (respect ignore rules)

Dependency flow:
    file_tree_model.py (Qt) --> workspace_index.py (pure data) --> core/ignore_engine.py

KHONG import bat ky module Qt nao.
"""

import os
import logging
import pathspec
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set

if TYPE_CHECKING:
    from infrastructure.filesystem.ignore_engine import IgnoreEngine

logger = logging.getLogger(__name__)


def _get_ignore_spec(
    workspace_path: Path, ignore_engine: "IgnoreEngine"
) -> pathspec.PathSpec:
    """Helper để lấy pathspec cho workspace."""
    from application.services.workspace_config import (
        get_excluded_patterns,
        get_use_gitignore,
    )

    excluded = get_excluded_patterns()
    return ignore_engine.build_pathspec(
        workspace_path,
        use_default_ignores=True,
        excluded_patterns=excluded if excluded else None,
        use_gitignore=get_use_gitignore(),
    )


def build_search_index(
    workspace_path: Path,
    generation_check: Optional[Callable[[], bool]] = None,
    ignore_engine: Optional["IgnoreEngine"] = None,
) -> Dict[str, List[str]]:
    """Build flat search index sử dụng scandir-rs (nếu có) hoặc os.walk."""
    from shared.constants import DIRECTORY_QUICK_SKIP
    from infrastructure.filesystem.file_utils import (
        is_binary_file,
        is_system_path_str,
        HAS_SCANDIR_RS,
    )

    scandir_rs = None
    if HAS_SCANDIR_RS:
        try:
            import scandir_rs
        except ImportError:
            HAS_SCANDIR_RS = False

    root_path = workspace_path.resolve()
    if ignore_engine is None:
        from infrastructure.filesystem.ignore_engine import IgnoreEngine

        ignore_engine = IgnoreEngine()

    spec = _get_ignore_spec(root_path, ignore_engine)
    root_path_str = str(root_path)
    if not root_path_str.endswith(os.path.sep):
        root_path_str += os.path.sep

    index: Dict[str, List[str]] = {}

    # Optimization: Sử dụng scandir_rs.Walk nếu có (nhanh hơn rất nhiều)
    walk_func = (
        getattr(scandir_rs, "Walk", None) if (HAS_SCANDIR_RS and scandir_rs) else None
    )

    if walk_func:
        try:
            # Walk returns flattened list of entries if no filter provided
            # return_type=2 means ReturnEntry
            results = walk_func(
                str(root_path),
                follow_links=True,
                include_dirs=False,  # Chỉ lấy files cho search index
                include_files=True,
                return_type=2,
            ).collect()

            # Optimization: Pre-build skip patterns with separators
            _sep = os.path.sep
            _skip_with_sep = {_sep + s + _sep for s in DIRECTORY_QUICK_SKIP}

            for entry in results:
                if generation_check and not generation_check():
                    return {}

                full_path: str = entry.path

                # Fast skip directory check using substring matching
                # Thêm separator ở đầu và cuối để match chính xác component
                check_path = _sep + full_path + _sep
                if any(s in check_path for s in _skip_with_sep):
                    continue

                # Skip system and binary files using strings to avoid Path() overhead in hot loop
                if is_system_path_str(full_path) or is_binary_file(full_path):
                    continue

                filename = os.path.basename(full_path)

                # Relative path calculation (fast)
                if full_path.startswith(root_path_str):
                    rel_path = full_path[len(root_path_str) :]
                else:
                    rel_path = filename

                if spec.match_file(rel_path):
                    continue

                key = filename.lower()
                if key not in index:
                    index[key] = []
                index[key].append(full_path)

            return index
        except Exception as e:
            logger.debug(f"Scandir-rs walk failed, falling back to os.walk: {e}")

    # Fallback to os.walk
    try:
        for dirpath, dirnames, filenames in os.walk(str(workspace_path)):
            if generation_check and not generation_check():
                return {}

            # Prune directories
            dirnames[:] = [d for d in dirnames if d not in DIRECTORY_QUICK_SKIP]

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)

                if is_system_path_str(full_path) or is_binary_file(full_path):
                    continue

                if full_path.startswith(root_path_str):
                    rel_path = full_path[len(root_path_str) :]
                else:
                    rel_path = filename

                if spec.match_file(rel_path):
                    continue

                key = filename.lower()
                if key not in index:
                    index[key] = []
                index[key].append(full_path)
    except Exception as e:
        logger.debug(f"Error building search index: {e}")

    return index


def search_in_index(index: Dict[str, List[str]], query: Optional[str]) -> List[str]:
    """Tìm files theo query trong search index (case-insensitive substring)."""
    if not index:
        return []

    query_stripped = (query or "").strip()
    if not query_stripped:
        return []

    # Check for "code:" prefix
    CODE_PREFIX = "code:"
    if query_stripped.lower().startswith(CODE_PREFIX):
        content_query = query_stripped[len(CODE_PREFIX) :].strip()
        if not content_query:
            return []
        return _search_content_in_files(index, content_query)

    query_lower = query_stripped.lower()
    results: List[str] = []
    for filename_lower, paths in index.items():
        if query_lower in filename_lower:
            results.extend(paths)

    results.sort()
    return results


def _search_content_in_files(
    index: Dict[str, List[str]], content_query: str
) -> List[str]:
    """Tìm kiếm nội dung trong các file đã được indexed."""
    MAX_CONTENT_SEARCH_SIZE = 2 * 1024 * 1024
    query_lower = content_query.lower()
    results: List[str] = []

    for paths in index.values():
        for full_path in paths:
            try:
                if os.path.getsize(full_path) > MAX_CONTENT_SEARCH_SIZE:
                    continue

                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                if query_lower in content.lower():
                    results.append(full_path)
            except (OSError, PermissionError, UnicodeDecodeError):
                continue

    results.sort()
    return results


def collect_files_from_disk(
    folder: Path,
    workspace_path: Optional[Path] = None,
    ignore_engine: Optional["IgnoreEngine"] = None,
) -> List[str]:
    """Scan filesystem trực tiếp để lấy tất cả files trong folder (lazy loading fallback)."""
    from shared.constants import DIRECTORY_QUICK_SKIP
    from infrastructure.filesystem.file_utils import (
        is_binary_file,
        is_system_path_str,
        HAS_SCANDIR_RS,
    )

    scandir_rs = None
    if HAS_SCANDIR_RS:
        try:
            import scandir_rs
        except ImportError:
            HAS_SCANDIR_RS = False

    if workspace_path is None:
        raise ValueError("workspace_path is required")

    root_path = workspace_path.resolve()
    if ignore_engine is None:
        from infrastructure.filesystem.ignore_engine import IgnoreEngine

        ignore_engine = IgnoreEngine()

    spec = _get_ignore_spec(root_path, ignore_engine)
    root_path_str = str(root_path)
    if not root_path_str.endswith(os.path.sep):
        root_path_str += os.path.sep

    result: List[str] = []
    seen: Set[str] = set()

    # Use scandir_rs if available
    walk_func = (
        getattr(scandir_rs, "Walk", None) if (HAS_SCANDIR_RS and scandir_rs) else None
    )
    if walk_func:
        try:
            entries = walk_func(
                str(folder),
                follow_links=True,
                include_dirs=False,
                include_files=True,
                return_type=2,
            ).collect()

            _sep = os.path.sep
            _skip_with_sep = {_sep + s + _sep for s in DIRECTORY_QUICK_SKIP}

            for entry in entries:
                full_path: str = entry.path

                # Fast skip directory check using substring matching instead of split()
                check_path = _sep + full_path + _sep
                if any(s in check_path for s in _skip_with_sep):
                    continue

                if is_system_path_str(full_path) or is_binary_file(full_path):
                    continue

                if full_path.startswith(root_path_str):
                    rel_path = full_path[len(root_path_str) :]
                else:
                    rel_path = os.path.basename(full_path)

                if spec.match_file(rel_path):
                    continue

                if full_path not in seen:
                    result.append(full_path)
                    seen.add(full_path)
            return result
        except Exception:
            pass

    # Fallback to os.walk
    try:
        _sep = os.path.sep
        _skip_with_sep = {_sep + s + _sep for s in DIRECTORY_QUICK_SKIP}

        for dirpath, dirnames, filenames in os.walk(str(folder)):
            dirnames[:] = [d for d in dirnames if d not in DIRECTORY_QUICK_SKIP]
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)

                # Fast skip directory check
                check_path = _sep + full_path + _sep
                if any(s in check_path for s in _skip_with_sep):
                    continue

                # Skip system and binary files using strings
                if is_system_path_str(full_path) or is_binary_file(full_path):
                    continue

                if full_path.startswith(root_path_str):
                    rel_path = full_path[len(root_path_str) :]
                else:
                    rel_path = filename

                if spec.match_file(rel_path):
                    continue

                if full_path not in seen:
                    result.append(full_path)
                    seen.add(full_path)
    except (PermissionError, OSError):
        pass

    return result
