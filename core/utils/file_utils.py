"""
File System Utilities - File tree scanning voi gitignore support

Su dung pathspec thay vi ignore library.
Ignore/gitignore logic duoc delegate cho core.ignore_engine (single source of truth).
"""

import platform
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import pathspec
from core.constants import (
    BINARY_EXTENSIONS,
    DIRECTORY_QUICK_SKIP,
)

# Delegate tat ca ignore logic cho ignore_engine
from core.ignore_engine import (
    build_pathspec,
    read_gitignore,
    find_git_root,
    clear_cache as _clear_ignore_cache,
)

# === Backward-compatible re-exports ===
# Cac module khac (file_scanner, file_tree_model) import truc tiep tu file_utils.
# Giu lai re-exports de khong break import paths.
_read_gitignore = read_gitignore
_find_git_root = find_git_root


@dataclass
class TreeItem:
    """
    Mot item trong file tree (file hoac folder).
    Tuong duong VscodeTreeItem trong TypeScript.

    is_loaded: True nếu children đã được scan (cho lazy loading).
               False = folder chưa được scan, children = []
    """

    label: str  # Ten hien thi (filename/dirname)
    path: str  # Duong dan tuyet doi
    is_dir: bool = False
    children: list["TreeItem"] = field(default_factory=list)
    is_loaded: bool = True  # True = đã scan, False = chưa scan (lazy)


def is_binary_file(file_path: Path) -> bool:
    """
    Check if file is binary using extension, magic bytes, and null byte detection.
    Returns True if file is binary (image, video, audio, executable, etc.)

    OPTIMIZED: Check extension first (no I/O), then magic bytes if needed.
    """
    # 1. Check extension first (FAST - no I/O)
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    # 2. Check if file exists and has content
    if not file_path.is_file():
        return False

    try:
        file_size = file_path.stat().st_size
        if file_size == 0:
            return False

        # 3. For files without extension or unknown extension, check content
        # Only read first 8KB to minimize I/O
        chunk_size = min(8192, file_size)
        with open(file_path, "rb") as f:
            chunk = f.read(chunk_size)

        # 4. Check for null bytes first (FAST)
        if b"\x00" in chunk:
            return True

        # 5. Check magic bytes with filetype library (SLOWER)
        import filetype

        kind = filetype.guess(file_path)
        if kind is not None:
            return True

    except Exception:
        pass

    return False


def is_binary_by_extension(file_path: Path) -> bool:
    """
    Check if file is binary based on extension (legacy function).
    Use is_binary_file() for more accurate detection.
    """
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

    # Delegate cho ignore_engine (single source of truth)
    spec = build_pathspec(
        root_path,
        use_default_ignores=use_default_ignores,
        excluded_patterns=excluded_patterns,
        use_gitignore=use_gitignore,
    )

    # Build tree recursively
    return _build_tree(root_path, root_path, spec)


def scan_directory_shallow(
    root_path: Path,
    depth: int = 1,
    excluded_patterns: Optional[list[str]] = None,
    use_gitignore: bool = True,
    use_default_ignores: bool = True,
) -> TreeItem:
    """
    Scan directory CHI den depth cap (cho lazy loading).

    depth=1: Chi scan immediate children, khong de quy vao folders.
              Folders se co is_loaded=False.
    depth=2: Scan 2 levels, etc.

    Args:
        root_path: Thu muc goc can scan
        depth: So cap can scan (1 = chi immediate children)
        excluded_patterns: Patterns de exclude
        use_gitignore: Co doc .gitignore khong
        use_default_ignores: Co dung EXTENDED_IGNORE_PATTERNS khong

    Returns:
        TreeItem root voi children chi scan den depth cap
    """
    root_path = root_path.resolve()

    # Delegate cho ignore_engine (single source of truth)
    spec = build_pathspec(
        root_path,
        use_default_ignores=use_default_ignores,
        excluded_patterns=excluded_patterns,
        use_gitignore=use_gitignore,
    )

    # Build tree voi depth limit
    # current_depth=1 vi root la level 1, children la level 2
    return _build_tree_shallow(
        root_path, root_path, spec, current_depth=1, max_depth=depth
    )


def _build_tree_shallow(
    current_path: Path,
    root_path: Path,
    spec: pathspec.PathSpec,
    current_depth: int,
    max_depth: int,
) -> TreeItem:
    """Build tree structure với depth limit (cho lazy loading)"""
    item = TreeItem(
        label=current_path.name or str(current_path),
        path=str(current_path),
        is_dir=current_path.is_dir(),
        is_loaded=True,  # Root luôn loaded
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
        # Check system path first
        if is_system_path(entry):
            continue

        # Get relative path for ignore matching
        try:
            rel_path = entry.relative_to(root_path)
        except ValueError:
            continue

        rel_path_str = str(rel_path)
        if entry.is_dir():
            rel_path_str += "/"

        # Check if should be ignored
        if spec.match_file(rel_path_str):
            continue

        # Xử lý directories
        if entry.is_dir():
            if current_depth < max_depth:
                # Còn trong depth limit → recurse
                child = _build_tree_shallow(
                    entry, root_path, spec, current_depth + 1, max_depth
                )
                item.children.append(child)
            else:
                # Vượt depth limit → tạo placeholder với is_loaded=False
                child = TreeItem(
                    label=entry.name,
                    path=str(entry),
                    is_dir=True,
                    children=[],
                    is_loaded=False,  # Chưa scan children
                )
                item.children.append(child)
        else:
            # Files luôn được thêm
            item.children.append(
                TreeItem(
                    label=entry.name, path=str(entry), is_dir=False, is_loaded=True
                )
            )

    return item


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


# === Backward-compatible wrappers ===
# Cac functions da chuyen sang core.ignore_engine.
# Giu lai wrappers de khong break existing imports.


def clear_gitignore_cache():
    """Clear the gitignore pattern cache. Delegate cho ignore_engine."""
    _clear_ignore_cache()


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


# _find_git_root da chuyen sang core.ignore_engine.find_git_root
# Re-export o dong dau file de backward compat


def load_folder_children(
    folder_item: TreeItem,
    excluded_patterns: Optional[list[str]] = None,
    use_gitignore: bool = True,
    use_default_ignores: bool = True,
) -> None:
    """
    Load children cho folder chua duoc scan (is_loaded=False).
    Ham nay MUTATE folder_item.children va set is_loaded=True.

    Dung khi user click checkbox hoac expand folder lan dau.

    Args:
        folder_item: TreeItem folder can load children
        excluded_patterns: Patterns de exclude
        use_gitignore: Co doc .gitignore khong
        use_default_ignores: Co dung EXTENDED_IGNORE_PATTERNS khong
    """
    if not folder_item.is_dir:
        return  # Khong phai folder

    if folder_item.is_loaded:
        return  # Da loaded roi

    folder_path = Path(folder_item.path)

    # Tim git root de match ignore patterns dung
    root_path = find_git_root(folder_path)

    # Delegate cho ignore_engine (single source of truth)
    spec = build_pathspec(
        root_path,
        use_default_ignores=use_default_ignores,
        excluded_patterns=excluded_patterns,
        use_gitignore=use_gitignore,
    )

    # Scan children
    try:
        entries = list(folder_path.iterdir())
    except PermissionError:
        folder_item.is_loaded = True
        return

    # Sort: directories first, then alphabetically
    entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

    for entry in entries:
        # Check system path
        if is_system_path(entry):
            continue

        # IGNORE MATCHING: Check both relative path AND entry name
        # Vì patterns như "node_modules" cần match cả khi ở subfolder
        entry_name = entry.name

        # Quick check cho common ignore directories
        # Dùng shared DIRECTORY_QUICK_SKIP - bao gồm tất cả ngôn ngữ/framework
        if entry_name in DIRECTORY_QUICK_SKIP:
            continue

        # Check với spec cho các patterns khác
        try:
            rel_path = entry.relative_to(root_path)
            rel_path_str = str(rel_path)
        except ValueError:
            rel_path_str = entry_name

        if entry.is_dir():
            rel_path_str += "/"
            # Cũng check entry name với trailing slash
            if spec.match_file(entry_name + "/"):
                continue

        # Check if should be ignored
        if spec.match_file(rel_path_str):
            continue

        # Add child
        if entry.is_dir():
            child = TreeItem(
                label=entry.name,
                path=str(entry),
                is_dir=True,
                children=[],
                is_loaded=False,  # Children chưa scan
            )
            folder_item.children.append(child)
        else:
            child = TreeItem(
                label=entry.name,
                path=str(entry),
                is_dir=False,
                is_loaded=True,
            )
            folder_item.children.append(child)

    # Mark as loaded
    folder_item.is_loaded = True
