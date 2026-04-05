"""
File Collector - Domain logic for traversing and collecting files from disk.
Respects ignore patterns and OS system guards.
"""

import os
from pathlib import Path
from typing import List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from domain.filesystem.ignore_engine import IgnoreEngine


def collect_files_from_disk(
    folder: Path,
    workspace_path: Optional[Path] = None,
    ignore_engine: Optional["IgnoreEngine"] = None,
) -> List[str]:
    """Scan filesystem trực tiếp để lấy tất cả files trong folder (lazy loading fallback)."""
    from shared.constants import DIRECTORY_QUICK_SKIP
    from shared.utils.filesystem import is_binary_file, is_system_path_str

    if workspace_path is None:
        raise ValueError("workspace_path is required")

    root_path = workspace_path.resolve()
    if ignore_engine is None:
        from domain.filesystem.ignore_engine import IgnoreEngine

        ignore_engine = IgnoreEngine()

    from application.services.workspace_config import (
        get_excluded_patterns,
        get_use_gitignore,
    )

    excluded = get_excluded_patterns()
    spec = ignore_engine.build_pathspec(
        root_path,
        use_default_ignores=True,
        excluded_patterns=excluded if excluded else None,
        use_gitignore=get_use_gitignore(),
    )

    result: List[str] = []
    seen: Set[str] = set()

    _sep = os.path.sep
    _skip_with_sep = {_sep + s + _sep for s in DIRECTORY_QUICK_SKIP}
    root_path_str = str(root_path)
    if not root_path_str.endswith(_sep):
        root_path_str += _sep

    try:
        for dirpath, dirnames, filenames in os.walk(str(folder)):
            dirnames[:] = [d for d in dirnames if d not in DIRECTORY_QUICK_SKIP]
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)

                if full_path.startswith(root_path_str):
                    rel_path = full_path[len(root_path_str) :]
                else:
                    rel_path = filename

                if any(s in (_sep + rel_path + _sep) for s in _skip_with_sep):
                    continue

                if is_system_path_str(full_path) or is_binary_file(full_path):
                    continue

                if spec.match_file(rel_path):
                    continue

                if full_path not in seen:
                    result.append(full_path)
                    seen.add(full_path)
    except (PermissionError, OSError):
        pass

    return result
