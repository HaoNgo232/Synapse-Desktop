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
from core.constants import BINARY_EXTENSIONS, DIRECTORY_QUICK_SKIP, EXTENDED_IGNORE_PATTERNS

# Cache for gitignore patterns: root_path -> (mtime, patterns)
_gitignore_cache: Dict[str, Tuple[float, list]] = {}

# Cache for PathSpec objects: root_path -> (mtime, PathSpec)
_pathspec_cache: Dict[str, Tuple[float, pathspec.PathSpec]] = {}


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
        with open(file_path, 'rb') as f:
            chunk = f.read(chunk_size)
        
        # 4. Check for null bytes first (FAST)
        if b'\x00' in chunk:
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


def scan_directory_shallow(
    root_path: Path,
    depth: int = 1,
    excluded_patterns: Optional[list[str]] = None,
    use_gitignore: bool = True,
    use_default_ignores: bool = True,
) -> TreeItem:
    """
    Scan directory CHỈ đến depth cấp (cho lazy loading).
    
    depth=1: Chỉ scan immediate children, không đệ quy vào folders.
             Folders sẽ có is_loaded=False.
    depth=2: Scan 2 levels, etc.
    
    Args:
        root_path: Thư mục gốc cần scan
        depth: Số cấp cần scan (1 = chỉ immediate children)
        excluded_patterns: Patterns để exclude
        use_gitignore: Có đọc .gitignore không
        use_default_ignores: Có dùng EXTENDED_IGNORE_PATTERNS không
    
    Returns:
        TreeItem root với children chỉ scan đến depth cấp
    """
    root_path = root_path.resolve()

    # Build ignore spec (giống scan_directory)
    ignore_patterns: list[str] = []
    ignore_patterns.extend([".git", ".hg", ".svn"])
    
    if use_default_ignores:
        ignore_patterns.extend(EXTENDED_IGNORE_PATTERNS)
    
    if excluded_patterns:
        ignore_patterns.extend(excluded_patterns)
    
    if use_gitignore:
        gitignore_patterns = _read_gitignore(root_path)
        ignore_patterns.extend(gitignore_patterns)
    
    spec = pathspec.PathSpec.from_lines("gitwildmatch", list(ignore_patterns))
    
    # Build tree với depth limit
    # current_depth=1 vì root là level 1, children là level 2
    return _build_tree_shallow(root_path, root_path, spec, current_depth=1, max_depth=depth)


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
                child = _build_tree_shallow(entry, root_path, spec, current_depth + 1, max_depth)
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
                TreeItem(label=entry.name, path=str(entry), is_dir=False, is_loaded=True)
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
    global _gitignore_cache, _pathspec_cache
    _gitignore_cache.clear()
    _pathspec_cache.clear()


def _get_gitignore_mtime(root_path: Path) -> float:
    """Get modification time of .gitignore file"""
    gitignore_file = root_path / ".gitignore"
    if gitignore_file.exists():
        return gitignore_file.stat().st_mtime
    return 0.0


def get_cached_pathspec(root_path: Path, patterns: list) -> pathspec.PathSpec:
    """
    Cache PathSpec object, invalidate khi .gitignore hoặc patterns thay đổi.
    
    Cache key bao gồm cả root_path và patterns hash để đảm bảo:
    - Khác patterns → khác PathSpec (tránh cache collision)
    - Patterns giống nhau + gitignore unchanged → reuse cache
    
    Args:
        root_path: Root path của workspace
        patterns: List patterns để build PathSpec
        
    Returns:
        Cached hoặc newly created PathSpec object
    """
    # Include patterns hash trong cache key để tránh collision
    # khi patterns thay đổi nhưng gitignore mtime vẫn giữ nguyên
    patterns_hash = hash(tuple(patterns))
    cache_key = f"{root_path}:{patterns_hash}"
    gitignore_mtime = _get_gitignore_mtime(root_path)

    if cache_key in _pathspec_cache:
        cached_mtime, cached_spec = _pathspec_cache[cache_key]
        if cached_mtime == gitignore_mtime:
            return cached_spec

    # Create new PathSpec and cache it
    spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    _pathspec_cache[cache_key] = (gitignore_mtime, spec)
    return spec


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


def load_folder_children(
    folder_item: TreeItem,
    excluded_patterns: Optional[list[str]] = None,
    use_gitignore: bool = True,
    use_default_ignores: bool = True,
) -> None:
    """
    Load children cho folder chưa được scan (is_loaded=False).
    Hàm này MUTATE folder_item.children và set is_loaded=True.
    
    Dùng khi user click checkbox hoặc expand folder lần đầu.
    
    Args:
        folder_item: TreeItem folder cần load children
        excluded_patterns: Patterns để exclude
        use_gitignore: Có đọc .gitignore không
        use_default_ignores: Có dùng EXTENDED_IGNORE_PATTERNS không
    """
    if not folder_item.is_dir:
        return  # Không phải folder
    
    if folder_item.is_loaded:
        return  # Đã loaded rồi
    
    folder_path = Path(folder_item.path)
    
    # Build ignore spec
    ignore_patterns: list[str] = []
    ignore_patterns.extend([".git", ".hg", ".svn"])
    
    if use_default_ignores:
        ignore_patterns.extend(EXTENDED_IGNORE_PATTERNS)
    
    if excluded_patterns:
        ignore_patterns.extend(excluded_patterns)
    
    if use_gitignore:
        # Tìm root path để đọc .gitignore
        # Giả sử .gitignore ở parent directories
        root_path = folder_path
        while root_path.parent != root_path:
            if (root_path / ".git").exists():
                break
            root_path = root_path.parent
        
        gitignore_patterns = _read_gitignore(root_path)
        ignore_patterns.extend(gitignore_patterns)
    else:
        # Default root path for caching
        root_path = folder_path
        while root_path.parent != root_path:
            if (root_path / ".git").exists():
                break
            root_path = root_path.parent
    
    # Use cached PathSpec instead of creating new one each time
    spec = get_cached_pathspec(root_path, list(ignore_patterns))
    
    # Scan children
    try:
        entries = list(folder_path.iterdir())
    except PermissionError:
        folder_item.is_loaded = True
        return
    
    # Sort: directories first, then alphabetically
    entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
    
    # Get root path for relative path calculation
    root_path = folder_path
    while root_path.parent != root_path:
        if (root_path / ".git").exists():
            break
        root_path = root_path.parent
    
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

