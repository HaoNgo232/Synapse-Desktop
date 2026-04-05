"""
File Scanner - File tree scanning với global cancellation

PERFORMANCE: Sử dụng scandir-rs (Rust) thay vì os.scandir khi có thể.
- Linux: 3-11x nhanh hơn
- Windows: 6-70x nhanh hơn
Fallback về os.scandir nếu scandir-rs không được cài đặt.

Features:
- Global cancellation flag để stop ngay lập tức
- Throttled progress updates (200ms interval)
- Gitignore và default ignore patterns support
"""

import os
import time
from pathlib import Path
from typing import Callable, Optional, List, Any, Tuple
from dataclasses import dataclass

import pathspec
from collections import OrderedDict

from domain.filesystem.ignore_engine import IgnoreEngine
from infrastructure.filesystem.file_utils import (
    TreeItem,
    is_system_path,
    is_binary_file,
)
from shared.constants import DIRECTORY_QUICK_SKIP

# Try import scandir_rs (Rust-based)
# WARNING: We intentionally disable scandir_rs because its Walk generator
# does NOT support dynamic directory pruning (like os.walk's dirs.remove()).
# This causes it to unconditionally crawl massive ignored folders (like node_modules, .git, .venv),
# leading to catastrophic performance degradation on real-world projects.
HAS_SCANDIR_RS = False
RustWalk: Any = None


# ============================================
# GLOBAL CANCELLATION FLAG
# Giống isLoadingDirectory trong PasteMax
# RACE CONDITION FIX: Sử dụng threading.Lock để đảm bảo thread-safe
# ============================================
import threading  # noqa: E402

_scanning_lock = threading.Lock()
_is_scanning = False
_scan_generation = 0  # Monotonically increasing generation counter


def is_scanning() -> bool:
    """
    Check xem có đang scanning không.

    Thread-safe: Sử dụng lock để đọc giá trị.
    """
    with _scanning_lock:
        return _is_scanning


def start_scanning() -> int:
    """
    Bắt đầu scanning session.

    Thread-safe: Sử dụng lock để set giá trị.

    Returns:
        Generation number cho scan session nay.
        Truyen generation vao is_scanning_valid() de kiem tra
        scan nay co con hop le khong.
    """
    global _is_scanning, _scan_generation
    with _scanning_lock:
        _is_scanning = True
        _scan_generation += 1
        return _scan_generation


def stop_scanning():
    """
    Dừng scanning ngay lập tức.

    Thread-safe: Sử dụng lock để set giá trị.
    """
    global _is_scanning
    with _scanning_lock:
        _is_scanning = False


def is_scanning_valid(generation: int) -> bool:
    """
    Check xem scan session voi generation nay con hop le khong.

    Returns False neu:
    - Scanning da bi stop (is_scanning = False)
    - Mot scan session MOI da duoc start (generation khac)

    Args:
        generation: Generation number nhan duoc tu start_scanning()
    """
    with _scanning_lock:
        return _is_scanning and _scan_generation == generation


@dataclass
class ScanProgress:
    """
    Progress information during directory scanning.

    Attributes:
        directories: Số directories đã scan
        files: Số files đã tìm thấy
        current_path: Path đang được scan
    """

    directories: int = 0
    files: int = 0
    current_path: str = ""


@dataclass
class ScanConfig:
    """
    Configuration cho file scanner.

    Attributes:
        excluded_patterns: List patterns để exclude
        use_gitignore: Có đọc .gitignore không
        use_default_ignores: Có dùng default ignore patterns không
    """

    excluded_patterns: Optional[List[str]] = None
    use_gitignore: bool = True
    use_default_ignores: bool = True


# Type alias cho progress callback
ProgressCallback = Callable[[ScanProgress], None]


class LRUSpecCache:
    """
    Cache giới hạn kích thước sử dụng chiến lược Least Recently Used.
    Giúp tránh memory leak khi scan monorepo cực lớn.
    """

    def __init__(self, maxsize=1000):
        self._cache: OrderedDict[Path, list] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key, default=None):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return default

    def __setitem__(self, key, value):
        self._cache[key] = value
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def __contains__(self, key):
        return key in self._cache


class FileScanner:
    """
    File scanner với global cancellation và progress callbacks.

    Supports two modes:
    - Full scan: Recursive scan toàn bộ tree (default)
    - Lazy scan: Chỉ scan level đầu, lazy load children khi expand
    """

    # Constants
    THROTTLE_INTERVAL_MS = 200  # 200ms giữa các progress updates

    # Lazy scan config
    LAZY_SCAN_THRESHOLD = 1000  # Files threshold to suggest lazy mode

    def __init__(self, ignore_engine: "IgnoreEngine"):
        self.ignore_engine = ignore_engine
        self._last_progress_time: float = 0
        self._progress: ScanProgress = ScanProgress()

    def scan(
        self,
        root_path: Path,
        config: Optional[ScanConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> TreeItem:
        """
        Scan directory với progress updates.

        PERFORMANCE: Sử dụng scandir-rs (Rust) khi có thể, fallback về os.scandir.

        Args:
            root_path: Directory root để scan
            config: Scan configuration (optional)
            progress_callback: Callback được gọi khi có progress update

        Returns:
            TreeItem root chứa toàn bộ cây thư mục
        """
        # RACE CONDITION FIX: Sử dụng thread-safe function
        start_scanning()

        if config is None:
            config = ScanConfig()

        root_path = root_path.resolve()

        # Reset progress
        self._progress = ScanProgress()
        self._last_progress_time = 0

        # Build initial ignore patterns (root + default + user)
        ignore_patterns = self._build_ignore_patterns(root_path, config)
        # Spec stack: list of (PathSpec, base_path)
        # base_path is the directory where the .gitignore was found
        root_spec = pathspec.PathSpec.from_lines("gitignore", tuple(ignore_patterns))  # type: ignore[arg-type]
        spec_stack = [(root_spec, root_path)]

        try:
            # Ưu tiên dùng Rust scanner nếu có
            if HAS_SCANDIR_RS:
                return self._scan_with_rust(
                    root_path,
                    spec_stack,
                    progress_callback,
                )
            else:
                # Fallback về Python scanner
                return self._scan_directory(
                    root_path,
                    root_path,
                    spec_stack,
                    progress_callback,
                )
        finally:
            # Không reset _is_scanning ở đây
            # để caller có thể check trạng thái
            pass

    def _scan_with_rust(
        self,
        root_path: Path,
        spec_stack: List[Tuple[pathspec.PathSpec, Path]],
        progress_callback: Optional[ProgressCallback],
    ) -> TreeItem:
        """
        Scan sử dụng scandir-rs (Rust) - nhanh hơn 3-11x so với Python.
        """
        from shared.logging_config import log_info

        if not HAS_SCANDIR_RS or RustWalk is None:
            return self._scan_directory(
                root_path, root_path, spec_stack, progress_callback
            )

        log_info("[FileScanner] Using scandir-rs (Rust) for fast scanning")

        root_path_str = str(root_path)

        # Root item
        root_item = TreeItem(
            label=root_path.name or root_path_str,
            path=root_path_str,
            is_dir=True,
        )

        # Dict để build tree structure: Path -> TreeItem
        path_to_item: dict[Path, TreeItem] = {root_path: root_item}
        # Cache lưu trữ active_stack cho từng directory - Sử dụng LRU để tránh memory leak
        path_to_spec_stack: LRUSpecCache = LRUSpecCache(maxsize=2000)
        path_to_spec_stack[root_path] = spec_stack

        try:
            # Dùng Walk từ scandir-rs - tương tự os.walk() nhưng nhanh hơn nhiều
            for rel_dirpath, dirs, files in RustWalk(root_path_str):
                if not is_scanning():
                    break

                abs_dirpath = os.path.join(root_path_str, rel_dirpath)
                current_dir = Path(abs_dirpath)

                # Get parent item
                parent_item = path_to_item.get(current_dir)
                if parent_item is None:
                    continue

                if current_dir != root_path:
                    # Kế thừa spec stack từ thư mục cha
                    parent_dir = current_dir.parent
                    parent_stack = path_to_spec_stack.get(parent_dir, spec_stack)
                    active_stack = (
                        list(parent_stack) if parent_stack else spec_stack.copy()
                    )

                    # Cập nhật nếu có thêm .gitignore ở hiện tại
                    if (current_dir / ".gitignore").exists():
                        pats = self.ignore_engine.read_gitignore(current_dir)
                        if pats:
                            s = pathspec.PathSpec.from_lines("gitignore", tuple(pats))  # type: ignore[arg-type]
                            active_stack.append((s, current_dir))

                    # Cache cho các thư mục con
                    path_to_spec_stack[current_dir] = active_stack
                else:
                    active_stack = spec_stack

                # Process directories
                for dir_name in sorted(dirs, key=str.lower):
                    if not is_scanning():
                        break
                    abs_dir_path = os.path.join(abs_dirpath, dir_name)
                    dir_obj = Path(abs_dir_path)

                    if is_system_path(dir_obj):
                        continue

                    # Check ignore patterns against the stack
                    is_ignored = False
                    for s, base in active_stack:
                        try:
                            rel_to_base = dir_obj.relative_to(base)
                            rel_path_str = str(rel_to_base) + "/"
                            if s.match_file(rel_path_str):
                                is_ignored = True
                                break
                        except ValueError:
                            continue

                    if is_ignored:
                        continue

                    child = TreeItem(label=dir_name, path=abs_dir_path, is_dir=True)
                    parent_item.children.append(child)
                    path_to_item[dir_obj] = child

                # Process files
                for file_name in sorted(files, key=str.lower):
                    if not is_scanning():
                        break
                    abs_file_path = os.path.join(abs_dirpath, file_name)
                    file_obj = Path(abs_file_path)

                    if is_system_path(file_obj) or is_binary_file(file_obj):
                        continue

                    # Check ignore patterns against the stack
                    is_ignored = False
                    for s, base in active_stack:
                        try:
                            rel_to_base = file_obj.relative_to(base)
                            rel_path_str = str(rel_to_base)
                            if s.match_file(rel_path_str):
                                is_ignored = True
                                break
                        except ValueError:
                            continue

                    if is_ignored:
                        continue

                    self._progress.files += 1
                    parent_item.children.append(
                        TreeItem(label=file_name, path=abs_file_path, is_dir=False)
                    )

            self._emit_progress(progress_callback, force=True)

        except Exception as e:
            from shared.logging_config import log_error

            log_error(f"[FileScanner] Rust scanner error: {e}, falling back to Python")
            return self._scan_directory(
                root_path, root_path, spec_stack, progress_callback
            )

        return root_item

    def _build_ignore_patterns(self, root_path: Path, config: ScanConfig) -> List[str]:
        """Build list cac ignore patterns tu config. Delegate cho ignore_engine."""
        return self.ignore_engine.build_ignore_patterns(
            root_path,
            use_default_ignores=config.use_default_ignores,
            excluded_patterns=config.excluded_patterns,
            use_gitignore=config.use_gitignore,
        )

    def _scan_directory(
        self,
        current_path: Path,
        root_path: Path,
        spec_stack: List[Tuple[pathspec.PathSpec, Path]],
        progress_callback: Optional[ProgressCallback],
    ) -> TreeItem:
        """Scan một directory recursively với progress - optimized version."""
        # Check global cancellation flag
        if not is_scanning():
            return TreeItem(
                label=current_path.name or str(current_path),
                path=str(current_path),
                is_dir=True,
            )

        item = TreeItem(
            label=current_path.name or str(current_path),
            path=str(current_path),
            is_dir=current_path.is_dir(),
        )

        if not current_path.is_dir():
            return item

        # Update progress
        self._progress.directories += 1
        self._progress.current_path = str(current_path)
        self._emit_progress(progress_callback)

        try:
            # Use scandir for better performance than iterdir
            with os.scandir(current_path) as entries_iter:
                # Separate dirs and files in single pass
                directories: List[os.DirEntry] = []
                files: List[os.DirEntry] = []

                for entry in entries_iter:
                    if not is_scanning():
                        break
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            directories.append(entry)
                        elif entry.is_file(follow_symlinks=False):
                            files.append(entry)
                    except OSError:
                        continue

        except (PermissionError, OSError):
            return item

        if not is_scanning():
            return item

        # Sort: alphabetically (is_dir separation already done)
        directories.sort(key=lambda e: e.name.lower())
        files.sort(key=lambda e: e.name.lower())

        # Process directories
        for entry in directories:
            if not is_scanning():
                break

            entry_path = Path(entry.path)

            if is_system_path(entry_path) or entry.name in DIRECTORY_QUICK_SKIP:
                continue

            try:
                rel_path = entry_path.relative_to(root_path)
            except ValueError:
                continue

            rel_path_str = str(rel_path) + "/"

            # ========= FIX: Kiểm tra directory có bị ignore không =========
            is_ignored = False
            for s, base in spec_stack:
                try:
                    rel_to_base = entry_path.relative_to(base)
                    rel_to_base_str = str(rel_to_base) + "/"
                    if s.match_file(rel_to_base_str):
                        is_ignored = True
                        break
                except ValueError:
                    continue

            if is_ignored:
                continue
            # ===============================================================

            # Check for nested .gitignore
            new_spec_stack = spec_stack.copy()
            if (entry_path / ".gitignore").exists():
                nested_patterns = self.ignore_engine.read_gitignore(entry_path)
                if nested_patterns:
                    nested_spec = pathspec.PathSpec.from_lines(
                        "gitignore",
                        nested_patterns,  # type: ignore
                    )
                    new_spec_stack.append((nested_spec, entry_path))

            child = self._scan_directory(
                entry_path, root_path, new_spec_stack, progress_callback
            )
            item.children.append(child)

        # Process files in batches for better cancellation responsiveness
        BATCH_SIZE = 50
        file_count = 0

        for entry in files:
            if file_count % BATCH_SIZE == 0 and not is_scanning():
                break

            entry_path = Path(entry.path)

            if is_system_path(entry_path):
                continue

            # Skip binary files (check magic bytes)
            if is_binary_file(entry_path):
                continue

            try:
                rel_path = entry_path.relative_to(root_path)
            except ValueError:
                continue

            # Check ignore patterns against the stack
            is_ignored = False
            for s, base in spec_stack:
                try:
                    rel_to_base = entry_path.relative_to(base)
                    rel_path_str = str(rel_to_base)
                    if s.match_file(rel_path_str):
                        is_ignored = True
                        break
                except ValueError:
                    continue

            if is_ignored:
                continue

            self._progress.files += 1
            file_count += 1

            item.children.append(
                TreeItem(label=entry.name, path=str(entry_path), is_dir=False)
            )

        # Emit final progress
        self._emit_progress(progress_callback, force=True)

        return item

    def _emit_progress(
        self,
        callback: Optional[ProgressCallback],
        force: bool = False,
    ) -> None:
        """
        Emit progress với throttling.

        Args:
            callback: Progress callback function
            force: Bỏ qua throttle và emit ngay
        """
        if not callback:
            return

        current_time = time.time() * 1000  # Convert to ms
        time_since_last = current_time - self._last_progress_time

        if force or time_since_last >= self.THROTTLE_INTERVAL_MS:
            self._last_progress_time = current_time
            # Copy progress để an toàn
            progress_copy = ScanProgress(
                directories=self._progress.directories,
                files=self._progress.files,
                current_path=self._progress.current_path,
            )

            try:
                callback(progress_copy)
            except Exception:
                pass  # Ignore callback errors


def scan_single_level(
    directory_path: Path,
    root_path: Path,
    spec_stack: List[Tuple[pathspec.PathSpec, Path]],
) -> TreeItem:
    """
    Scan chỉ một level của directory (không recursive).

    Dùng cho lazy loading - scan children khi user expand folder.

    Args:
        directory_path: Directory cần scan
        root_path: Root workspace path (để match ignore patterns)
        spec_stack: PathSpec stack cho ignore matching
    """
    if not is_scanning():
        return TreeItem(
            label=directory_path.name or str(directory_path),
            path=str(directory_path),
            is_dir=True,
        )

    item = TreeItem(
        label=directory_path.name or str(directory_path),
        path=str(directory_path),
        is_dir=True,
    )

    try:
        entries = list(directory_path.iterdir())
    except (PermissionError, OSError):
        return item

    entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

    for entry in entries:
        if not is_scanning():
            break

        if is_system_path(entry):
            continue

        try:
            entry.relative_to(root_path)
        except ValueError:
            continue

        # Check ignore patterns against the stack
        is_ignored = False
        for s, base in spec_stack:
            try:
                rel_to_base = entry.relative_to(base)
                rel_path_str = str(rel_to_base)
                if entry.is_dir():
                    rel_path_str += "/"
                if s.match_file(rel_path_str):
                    is_ignored = True
                    break
            except ValueError:
                continue

        if is_ignored:
            continue

        if entry.is_dir():
            # Tạo placeholder - sẽ load children khi expand
            child = TreeItem(
                label=entry.name,
                path=str(entry),
                is_dir=True,
                children=[],  # Empty - will lazy load
            )
            # Mark as not loaded yet
            child._lazy_loaded = False  # type: ignore
        else:
            child = TreeItem(
                label=entry.name,
                path=str(entry),
                is_dir=False,
            )

        item.children.append(child)

    return item


def scan_directory_lazy(
    directory_path: Path,
    root_path: Path,
    excluded_patterns: Optional[List[str]] = None,
    use_gitignore: bool = True,
    use_default_ignores: bool = True,
) -> TreeItem:
    """
    Lazy scan một directory (chỉ 1 level).

    Gọi function này khi user expand folder để load children on-demand.

    Args:
        directory_path: Directory cần scan
        root_path: Root workspace path
        excluded_patterns: Patterns để exclude
        use_gitignore: Có dùng .gitignore không
        use_default_ignores: Có dùng default ignores không

    Returns:
        TreeItem với immediate children only
    """
    config = ScanConfig(
        excluded_patterns=excluded_patterns,
        use_gitignore=use_gitignore,
        use_default_ignores=use_default_ignores,
    )

    scanner = FileScanner(
        ignore_engine=IgnoreEngine()
    )  # NOTE: Should pass in ignore_engine instance from caller

    # Build initial ignore spec
    ignore_patterns = scanner._build_ignore_patterns(root_path, config)
    root_spec = pathspec.PathSpec.from_lines("gitignore", tuple(ignore_patterns))  # type: ignore[arg-type]
    spec_stack = [(root_spec, root_path)]

    start_scanning()
    try:
        return scan_single_level(directory_path, root_path, spec_stack)
    finally:
        pass  # Don't stop scanning - caller manages this


# Convenience function
def scan_directory(
    root_path: Path,
    ignore_engine: IgnoreEngine,
    excluded_patterns: Optional[List[str]] = None,
    use_gitignore: bool = True,
    use_default_ignores: bool = True,
    progress_callback: Optional[ProgressCallback] = None,
) -> TreeItem:
    """
    Scan directory với progress callbacks.

    Sử dụng global cancellation flag. Gọi stop_scanning() để cancel.

    Args:
        root_path: Directory root để scan
        excluded_patterns: List patterns để exclude
        use_gitignore: Có đọc .gitignore không
        use_default_ignores: Có dùng default ignore patterns không
        progress_callback: Callback được gọi khi có progress update

    Returns:
        TreeItem root chứa toàn bộ cây thư mục
    """
    config = ScanConfig(
        excluded_patterns=excluded_patterns,
        use_gitignore=use_gitignore,
        use_default_ignores=use_default_ignores,
    )

    scanner = FileScanner(ignore_engine=ignore_engine)
    return scanner.scan(
        root_path,
        config=config,
        progress_callback=progress_callback,
    )
