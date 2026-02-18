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
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def build_search_index(
    workspace_path: Path,
    generation_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, List[str]]:
    """
    Build flat search index tu workspace bang os.walk.

    Dung cung logic ignore voi file tree:
    pathspec (EXTENDED_IGNORE, excluded patterns, gitignore),
    is_binary_file, is_system_path.

    Args:
        workspace_path: Duong dan workspace root.
        generation_check: Optional callback tra ve False neu index da stale
                          (vi du: user doi workspace giua luc build).
                          Neu None, khong check.

    Returns:
        Dict mapping filename_lower -> list of full paths.
        Vi du: {"main.py": ["/home/user/project/main.py"]}
    """
    from core.constants import DIRECTORY_QUICK_SKIP
    from core.utils.file_utils import is_binary_file, is_system_path
    from core.ignore_engine import build_pathspec, find_git_root
    from services.workspace_config import (
        get_excluded_patterns,
        get_use_gitignore,
    )

    # Tim git root tu workspace
    root_path = find_git_root(workspace_path)
    excluded = get_excluded_patterns()

    # Delegate cho ignore_engine (single source of truth)
    spec = build_pathspec(
        root_path,
        use_default_ignores=True,
        excluded_patterns=excluded if excluded else None,
        use_gitignore=get_use_gitignore(),
    )
    root_path_str = str(root_path)

    index: Dict[str, List[str]] = {}  # filename_lower -> [full_paths]

    try:
        for dirpath, dirnames, filenames in os.walk(str(workspace_path)):
            # Check xem index con fresh khong
            if generation_check is not None and not generation_check():
                return {}

            # Prune ignored dirs IN-PLACE — os.walk se KHONG enter vao
            dirnames[:] = sorted(d for d in dirnames if d not in DIRECTORY_QUICK_SKIP)

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                entry = Path(full_path)

                # Skip system files va binary files
                if is_system_path(entry) or is_binary_file(entry):
                    continue

                # Check pathspec (gitignore, excluded patterns)
                try:
                    rel_path_str = os.path.relpath(full_path, root_path_str)
                except ValueError:
                    rel_path_str = filename

                if spec.match_file(rel_path_str):
                    continue

                # Them vao index
                key = filename.lower()
                if key not in index:
                    index[key] = []
                index[key].append(full_path)
    except Exception as e:
        logger.debug(f"Error building search index for {workspace_path}: {e}")

    return index


def search_in_index(index: Dict[str, List[str]], query: str) -> List[str]:
    """
    Tim files theo query trong search index (case-insensitive substring).

    Independent voi lazy loading — tim duoc ca files chua expand trong tree.

    Args:
        index: Search index tu build_search_index()
        query: Chuoi tim kiem (case-insensitive)

    Returns:
        Sorted list cac full paths matching query.
    """
    if not index:
        return []

    query_lower = (query or "").lower().strip()
    if not query_lower:
        return []

    results: List[str] = []
    for filename_lower, paths in index.items():
        if query_lower in filename_lower:
            results.extend(paths)

    results.sort()
    return results


def collect_files_from_disk(
    folder: Path,
    workspace_path: Optional[Path] = None,
) -> List[str]:
    """
    Scan filesystem truc tiep de tim tat ca files trong folder.

    Dung cho folders chua lazy-loaded trong tree model.
    Respect excluded patterns, gitignore, va binary extensions.

    Args:
        folder: Thu muc can scan.
        workspace_path: Workspace root (de resolve git root chinh xac).
                        Neu None, dung folder lam root.

    Returns:
        List cac full paths (khong trung lap, da loc binary/ignored).
    """
    from core.utils.file_utils import is_binary_file, is_system_path
    from core.ignore_engine import build_pathspec, find_git_root
    from services.workspace_config import get_excluded_patterns, get_use_gitignore
    from core.constants import DIRECTORY_QUICK_SKIP

    # Tim git root
    root_path = find_git_root(folder)

    # Fallback to workspace root neu co
    if workspace_path and workspace_path != root_path:
        ws_root = find_git_root(workspace_path)
        if ws_root != workspace_path:
            root_path = ws_root

    excluded = get_excluded_patterns()

    # Delegate cho ignore_engine (single source of truth)
    spec = build_pathspec(
        root_path,
        use_default_ignores=True,
        excluded_patterns=excluded if excluded else None,
        use_gitignore=get_use_gitignore(),
    )

    root_path_str = str(root_path)
    result: List[str] = []
    seen: Set[str] = set()

    try:
        for dirpath, dirnames, filenames in os.walk(str(folder)):
            # Prune ignored directories IN-PLACE — tranh traverse node_modules (100K+ files)
            dirnames[:] = sorted(d for d in dirnames if d not in DIRECTORY_QUICK_SKIP)

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                entry = Path(full_path)

                # Skip system files va binary files
                if is_system_path(entry) or is_binary_file(entry):
                    continue

                # Check pathspec (gitignore, excluded patterns)
                try:
                    rel_path_str = os.path.relpath(full_path, root_path_str)
                except ValueError:
                    rel_path_str = filename

                if spec.match_file(rel_path_str):
                    continue

                if full_path not in seen:
                    result.append(full_path)
                    seen.add(full_path)
    except (PermissionError, OSError) as e:
        logger.debug(f"Error scanning {folder}: {e}")

    return result
