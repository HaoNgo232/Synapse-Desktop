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
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set

if TYPE_CHECKING:
    from infrastructure.filesystem.ignore_engine import IgnoreEngine

logger = logging.getLogger(__name__)


def build_search_index(
    workspace_path: Path,
    generation_check: Optional[Callable[[], bool]] = None,
    ignore_engine: Optional["IgnoreEngine"] = None,
) -> Dict[str, List[str]]:
    """
    Build flat search index tu workspace bang os.walk.

    Dung cung logic ignore voi file tree:
    pathspec (EXTENDED_IGNORE, excluded patterns, gitignore),
    is_binary_file, is_system_path.

    Args:
        workspace_path: Duong dan workspace root.
        generation_check: Optional callback to check if scan should abort.
        ignore_engine: Optional IgnoreEngine instance (for cache reuse).
        generation_check: Optional callback tra ve False neu index da stale
                          (vi du: user doi workspace giua luc build).
                          Neu None, khong check.

    Returns:
        Dict mapping filename_lower -> list of full paths.
        Vi du: {"main.py": ["/home/user/project/main.py"]}
    """
    from shared.constants import DIRECTORY_QUICK_SKIP
    from infrastructure.filesystem.file_utils import is_binary_file, is_system_path
    from infrastructure.filesystem.ignore_engine import IgnoreEngine
    from application.services.workspace_config import (
        get_excluded_patterns,
        get_use_gitignore,
    )

    # Dung workspace_path lam root (co resolve)
    root_path = workspace_path.resolve()
    excluded = get_excluded_patterns()

    # Dung IgnoreEngine instance (inject hoac tao moi)
    if ignore_engine is None:
        ignore_engine = IgnoreEngine()
    spec = ignore_engine.build_pathspec(
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


def search_in_index(index: Dict[str, List[str]], query: Optional[str]) -> List[str]:
    """
    Tim files theo query trong search index (case-insensitive substring).

    Ho tro 2 che do tim kiem:
    - Tim theo ten file (mac dinh): query la substring cua ten file
    - Tim theo noi dung file (prefix "code:"): quet noi dung cac file trong index

    Independent voi lazy loading — tim duoc ca files chua expand trong tree.

    Args:
        index: Search index tu build_search_index()
        query: Chuoi tim kiem (case-insensitive).
               Neu bat dau bang "code:", se tim trong noi dung file.

    Returns:
        Sorted list cac full paths matching query.
    """
    if not index:
        return []

    query_stripped = (query or "").strip()
    if not query_stripped:
        return []

    # Kiem tra prefix "code:" de chuyen sang che do tim kiem noi dung file
    CODE_PREFIX = "code:"
    if query_stripped.lower().startswith(CODE_PREFIX):
        content_query = query_stripped[len(CODE_PREFIX) :].strip()
        if not content_query:
            return []
        return _search_content_in_files(index, content_query)

    # Che do mac dinh: tim theo ten file (case-insensitive substring)
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
    """
    Tim kiem noi dung ben trong cac file da duoc index.

    Quet tung file trong flat index, doc noi dung va tim substring
    (case-insensitive). Bo qua cac file khong doc duoc (encoding loi,
    permission denied, file qua lon).

    Args:
        index: Search index tu build_search_index() (filename_lower -> [full_paths])
        content_query: Chuoi can tim trong noi dung file (chua strip, chua lower)

    Returns:
        Sorted list cac full paths chua noi dung matching query.
    """
    # Gioi han kich thuoc file de tranh doc file qua lon (2MB)
    MAX_CONTENT_SEARCH_SIZE = 2 * 1024 * 1024

    query_lower = content_query.lower()
    results: List[str] = []

    for _filename, paths in index.items():
        for full_path in paths:
            try:
                import os

                # Bo qua file qua lon de tranh block UI lau
                file_size = os.path.getsize(full_path)
                if file_size > MAX_CONTENT_SEARCH_SIZE:
                    continue

                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                if query_lower in content.lower():
                    results.append(full_path)
            except (OSError, PermissionError, UnicodeDecodeError):
                # Bo qua cac file khong doc duoc
                continue

    results.sort()
    return results


def collect_files_from_disk(
    folder: Path,
    workspace_path: Optional[Path] = None,
    ignore_engine: Optional["IgnoreEngine"] = None,
) -> List[str]:
    """
    Scan filesystem truc tiep de tim tat ca files trong folder.

    Dung cho folders chua lazy-loaded trong tree model.
    Respect excluded patterns, gitignore, va binary extensions.

    Args:
        folder: Thu muc can scan.
        workspace_path: Workspace root (bat buoc de ignore patterns
                        match dung relative path o moi level).
                        Raise ValueError neu None.
        ignore_engine: Optional IgnoreEngine instance (for cache reuse).

    Returns:
        List cac full paths (khong trung lap, da loc binary/ignored).
    """
    from infrastructure.filesystem.file_utils import is_binary_file, is_system_path
    from infrastructure.filesystem.ignore_engine import IgnoreEngine
    from application.services.workspace_config import (
        get_excluded_patterns,
        get_use_gitignore,
    )
    from shared.constants import DIRECTORY_QUICK_SKIP

    # workspace_path bat buoc - caller phai truyen
    if workspace_path is None:
        raise ValueError(
            "workspace_path is required for collect_files_from_disk. "
            "Caller must provide workspace root path."
        )
    root_path = workspace_path.resolve()

    excluded = get_excluded_patterns()

    # Dung IgnoreEngine instance (inject hoac tao moi)
    if ignore_engine is None:
        ignore_engine = IgnoreEngine()
    spec = ignore_engine.build_pathspec(
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
