"""
File System Utilities - File tree scanning voi gitignore support

Su dung pathspec thay vi ignore library.
Ignore/gitignore logic duoc delegate cho core.ignore_engine (single source of truth).
"""

import os
import platform
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import pathspec
from shared.constants import (
    BINARY_EXTENSIONS,
)

from domain.filesystem.ignore_engine import IgnoreEngine

HAS_SCANDIR_RS = False
try:
    # import scandir_rs

    HAS_SCANDIR_RS = False  # Tắt do Walk không hỗ trợ pruning
except ImportError:
    pass

if HAS_SCANDIR_RS:
    try:
        from shared.logging_config import log_info

        log_info("[file_utils] scandir-rs available")
    except ImportError:  # In scripts, shared.logging_config might not be setup
        pass

# Pre-compile regex for is_system_path (module-level optimization)
_WINDOWS_RESERVED_PATTERN = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", re.IGNORECASE
)

# Optimization: Module-level constants (tạo 1 lần duy nhất)
_TEXT_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".sh",
        ".sql",
        ".mod",
        ".sum",
        ".toml",
        ".cfg",
        ".ini",
        ".env",
        ".jsx",
        ".tsx",
        ".vue",
        ".svelte",
        ".scss",
        ".less",
        ".graphql",
        ".proto",
        ".tf",
        ".dockerfile",
    }
)


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


def is_binary_file(path_or_str: Path | str) -> bool:
    """
    Check xem một file có phải là binary không.
    Hàm này hỗ trợ cả Path object và string path để tối ưu hiệu năng trong vòng lặp lớn.

    Optimization:
    1. Kiểm tra extension trước (fast whitelist/blacklist)
    2. Chỉ đọc nội dung nếu extension không xác định.
    """
    from shared.constants import BINARY_EXTENSIONS

    # Convert to string for suffix check
    path_str = str(path_or_str)
    _, ext = os.path.splitext(path_str)
    ext = ext.lower()

    # 1. Fast check by extension
    if ext in BINARY_EXTENSIONS:
        return True

    # Whitelist các extension text phổ biến để skip I/O
    if ext in _TEXT_EXTENSIONS:
        return False

    # 2. Fallback to magic bytes check
    try:
        # Kiểm tra file size trước, file cực lớn (>5MB) mà không có extension
        # text thì khả năng cao là binary (ví dụ dump file).
        if os.path.getsize(path_str) > 5 * 1024 * 1024:
            return True

        with open(path_str, "rb") as f:
            chunk = f.read(1024)
            # Nếu chứa null byte thì khả năng cao là binary
            return b"\x00" in chunk
    except (PermissionError, OSError):
        return False


def is_binary_by_extension(file_path: Path) -> bool:
    """
    Check if file is binary based on extension (legacy function).
    Use is_binary_file() for more accurate detection.
    """
    return file_path.suffix.lower() in BINARY_EXTENSIONS


def is_system_path_str(path_str: str) -> bool:
    """
    Version nhanh của is_system_path nhận input là string.
    Dùng để tối ưu trong các vòng lặp quét hàng chục nghìn file.
    """
    system = platform.system()
    name = os.path.basename(path_str)

    if system == "Windows":
        # Check reserved names using pre-compiled regex
        if _WINDOWS_RESERVED_PATTERN.match(name):
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
        if path_str.startswith(("/proc/", "/sys/", "/dev/")):
            return True

    return False


def is_system_path(file_path: Path) -> bool:
    """
    Check if path is an OS system path that should be excluded.
    Supports: Windows, macOS, Linux
    """
    return is_system_path_str(str(file_path))


def scan_directory(
    root_path: Path,
    ignore_engine: IgnoreEngine,
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
    spec = ignore_engine.build_pathspec(
        root_path,
        use_default_ignores=use_default_ignores,
        excluded_patterns=excluded_patterns,
        use_gitignore=use_gitignore,
    )

    # Initial spec stack
    spec_stack = [(spec, root_path)]

    # Build tree recursively
    return _build_tree(root_path, root_path, spec_stack, ignore_engine)


def scan_directory_shallow(
    root_path: Path,
    ignore_engine: IgnoreEngine,
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
    spec = ignore_engine.build_pathspec(
        root_path,
        use_default_ignores=use_default_ignores,
        excluded_patterns=excluded_patterns,
        use_gitignore=use_gitignore,
    )

    # Initial spec stack
    spec_stack = [(spec, root_path)]

    # Build tree voi depth limit
    # current_depth=1 vi root la level 1, children la level 2
    return _build_tree_shallow(
        root_path,
        root_path,
        spec_stack,
        current_depth=1,
        max_depth=depth,
        engine=ignore_engine,
    )


def _build_tree_shallow(
    current_path: Path,
    root_path: Path,
    spec_stack: List[Tuple[pathspec.PathSpec, Path]],
    current_depth: int,
    max_depth: int,
    engine: IgnoreEngine,
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
        # Sử dụng os.scandir thay vì Path.iterdir để tránh hàng loạt lời gọi stat()
        # os.scandir trả về DirEntry object chứa sẵn info về is_dir/is_file.
        # Rất quan trọng cho ổ đĩa mạng hoặc ổ đĩa chậm.
        entries = list(os.scandir(str(current_path)))
    except (PermissionError, OSError):
        return item

    # Sort: directories first, then alphabetically
    # DirEntry don't have is_dir method in older versions, use is_dir() - it's cached from scandir.
    entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

    # Optimization: Pre-calculate base strings
    spec_stack_with_strs = []
    for s, base in spec_stack:
        base_str = str(base)
        if not base_str.endswith(os.path.sep):
            base_str += os.path.sep
        spec_stack_with_strs.append((s, base_str))

    for entry in entries:
        # DirEntry behavior
        entry_path_str = entry.path
        entry_name = entry.name
        is_dir = entry.is_dir()

        # Check system path first (fast exclude)
        if is_system_path_str(entry_path_str):
            continue

        # Check against spec stack using string operations
        is_ignored = False
        for s, base_str in spec_stack_with_strs:
            if entry_path_str.startswith(base_str):
                # Extract relative path
                rel_path = entry_path_str[len(base_str) :]
                if is_dir and not rel_path.endswith("/"):
                    rel_path += "/"

                if s.match_file(rel_path):
                    is_ignored = True
                    break

        if is_ignored:
            continue

        # Convert to Path object only once if needed for downstream tools
        # For small project root, this overhead is negligible compared to stat() calls.
        p_obj = Path(entry_path_str)

        # optimization: Only lookup .gitignore if we are planning to recurse
        if is_dir and current_depth < max_depth:
            # Check for nested .gitignore
            gitignore_path = os.path.join(entry_path_str, ".gitignore")
            if os.path.exists(gitignore_path):
                pats = engine.read_gitignore(p_obj)
                if pats:
                    new_spec = engine.build_pathspec(
                        p_obj,
                        use_default_ignores=False,
                        excluded_patterns=pats,
                        use_gitignore=False,
                    )
                    next_spec_stack = spec_stack + [(new_spec, p_obj)]
                else:
                    next_spec_stack = spec_stack
            else:
                next_spec_stack = spec_stack

            # recurse
            child = _build_tree_shallow(
                p_obj,
                root_path,
                next_spec_stack,
                current_depth + 1,
                max_depth,
                engine,
            )
            item.children.append(child)
        elif is_dir:
            # Placeholder cho thu muc chua load
            child = TreeItem(
                label=entry_name,
                path=entry_path_str,
                is_dir=True,
                is_loaded=False,
            )
            item.children.append(child)
        else:
            # Files
            item.children.append(
                TreeItem(
                    label=entry_name,
                    path=entry_path_str,
                    is_dir=False,
                    is_loaded=True,
                )
            )

    return item


def _build_tree(
    current_path: Path,
    root_path: Path,
    spec_stack: List[Tuple[pathspec.PathSpec, Path]],
    engine: IgnoreEngine,
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

        # Check check against spec stack
        is_ignored = False
        for s, base in spec_stack:
            try:
                rel_to_base = entry.relative_to(base)
                rel_to_base_str = str(rel_to_base)
                if entry.is_dir():
                    rel_to_base_str += "/"
                if s.match_file(rel_to_base_str):
                    is_ignored = True
                    break
            except ValueError:
                continue

        if is_ignored:
            continue

        # Recurse for directories
        if entry.is_dir():
            # Check for nested .gitignore
            new_spec_stack = spec_stack.copy()
            if (entry / ".gitignore").exists():
                pats = engine.read_gitignore(entry)
                if pats:
                    new_spec = engine.build_pathspec(
                        entry,
                        use_default_ignores=False,
                        excluded_patterns=pats,
                        use_gitignore=False,
                    )
                    new_spec_stack.append((new_spec, entry))

            child = _build_tree(entry, root_path, new_spec_stack, engine)
            item.children.append(child)
        else:
            item.children.append(
                TreeItem(label=entry.name, path=str(entry), is_dir=False)
            )

    return item


# === Backward-compatible wrappers ===
# Cac functions da chuyen sang core.ignore_engine.
# Giu lai wrappers de khong break existing imports.


def clear_gitignore_cache(ignore_engine: IgnoreEngine):
    """Clear the gitignore pattern cache. Delegate cho ignore_engine."""
    ignore_engine.clear_cache()


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
        Sorted for deterministic ordering.
    """
    result_set: set[Path] = set()  # Use set to avoid duplicates

    def _walk(item: TreeItem):
        if item.path in selected_paths:
            if not item.is_dir:
                result_set.add(Path(item.path))
            else:
                # Neu chon folder thi lay tat ca files trong do
                for f in flatten_tree_files(item):
                    result_set.add(f)
        else:
            # Van can check children vi co the chon file trong folder chua duoc chon
            for child in item.children:
                _walk(child)

    _walk(tree)
    return sorted(result_set)  # Sort for deterministic ordering


def load_folder_children(
    folder_item: TreeItem,
    ignore_engine: IgnoreEngine,
    excluded_patterns: Optional[list[str]] = None,
    use_gitignore: bool = True,
    use_default_ignores: bool = True,
    *,
    workspace_root: Optional[Path] = None,
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
        workspace_root: Root workspace path (bat buoc de ignore patterns
                        match dung relative path o moi level).
                        Raise ValueError neu None.
    """
    if not folder_item.is_dir:
        return  # Khong phai folder

    if folder_item.is_loaded:
        return  # Da loaded roi

    folder_path = Path(folder_item.path)

    # workspace_root bat buoc - caller phai truyen
    if workspace_root is None:
        raise ValueError(
            "workspace_root is required for load_folder_children. "
            "Caller must provide workspace root path."
        )
    root_path = workspace_root.resolve()

    # Initial spec
    spec = ignore_engine.build_pathspec(
        root_path,
        use_default_ignores=use_default_ignores,
        excluded_patterns=excluded_patterns,
        use_gitignore=use_gitignore,
    )
    spec_stack = [(spec, root_path)]

    # Build spec stack by looking up path
    if folder_path != root_path:
        try:
            rel_parts = folder_path.relative_to(root_path).parts
            check_path = root_path
            for part in rel_parts:
                check_path = check_path / part
                if (check_path / ".gitignore").exists() and check_path != root_path:
                    pats = ignore_engine.read_gitignore(check_path)
                    if pats:
                        s = pathspec.PathSpec.from_lines("gitignore", tuple(pats))  # type: ignore
                        spec_stack.append((s, check_path))
        except ValueError:
            pass

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

        # Check against spec stack
        is_ignored = False
        for s, base in spec_stack:
            try:
                rel_to_base = entry.relative_to(base)
                rel_to_base_str = str(rel_to_base)
                if entry.is_dir():
                    rel_to_base_str += "/"
                if s.match_file(rel_to_base_str):
                    is_ignored = True
                    break
            except ValueError:
                continue

        if is_ignored:
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
