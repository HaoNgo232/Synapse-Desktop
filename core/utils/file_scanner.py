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
from typing import Callable, Optional, List, Any
from dataclasses import dataclass

import pathspec

from core.ignore_engine import build_ignore_patterns
from core.utils.file_utils import (
    TreeItem,
    is_system_path,
    is_binary_file,
)

# Try import scandir_rs (Rust-based, much faster)
# Some environments do not expose typed symbols for scandir_rs.Walk,
# so resolve dynamically to keep runtime behavior and satisfy static analysis.
RustWalk: Any = None
try:
    import scandir_rs

    RustWalk = getattr(scandir_rs, "Walk", None)
    HAS_SCANDIR_RS = callable(RustWalk)
except ImportError:
    HAS_SCANDIR_RS = False


# ============================================
# GLOBAL CANCELLATION FLAG
# Giống isLoadingDirectory trong PasteMax
# RACE CONDITION FIX: Sử dụng threading.Lock để đảm bảo thread-safe
# ============================================
import threading  # noqa: E402

_scanning_lock = threading.Lock()
_is_scanning = False


def is_scanning() -> bool:
    """
    Check xem có đang scanning không.

    Thread-safe: Sử dụng lock để đọc giá trị.
    """
    with _scanning_lock:
        return _is_scanning


def start_scanning():
    """
    Bắt đầu scanning session.

    Thread-safe: Sử dụng lock để set giá trị.
    """
    global _is_scanning
    with _scanning_lock:
        _is_scanning = True


def stop_scanning():
    """
    Dừng scanning ngay lập tức.

    Thread-safe: Sử dụng lock để set giá trị.
    """
    global _is_scanning
    with _scanning_lock:
        _is_scanning = False


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

    def __init__(self):
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

        # Build ignore spec
        ignore_patterns = self._build_ignore_patterns(root_path, config)
        spec = pathspec.PathSpec.from_lines("gitignore", tuple(ignore_patterns))  # type: ignore[arg-type]

        try:
            # Ưu tiên dùng Rust scanner nếu có
            if HAS_SCANDIR_RS:
                return self._scan_with_rust(
                    root_path,
                    spec,
                    progress_callback,
                )
            else:
                # Fallback về Python scanner
                return self._scan_directory(
                    root_path,
                    root_path,
                    spec,
                    progress_callback,
                )
        finally:
            # Không reset _is_scanning ở đây
            # để caller có thể check trạng thái
            pass

    def _scan_with_rust(
        self,
        root_path: Path,
        spec: pathspec.PathSpec,
        progress_callback: Optional[ProgressCallback],
    ) -> TreeItem:
        """
        Scan sử dụng scandir-rs (Rust) - nhanh hơn 3-11x so với Python.

        Rust scanner chạy trong background thread và release GIL,
        cho phép Python code khác chạy song song.

        NOTE: RustWalk trả về relative paths, không phải absolute paths!
        """
        from core.logging_config import log_info

        if not HAS_SCANDIR_RS or RustWalk is None:
            return self._scan_directory(root_path, root_path, spec, progress_callback)

        log_info("[FileScanner] Using scandir-rs (Rust) for fast scanning")

        root_path_str = str(root_path)

        # Root item
        root_item = TreeItem(
            label=root_path.name or root_path_str,
            path=root_path_str,
            is_dir=True,
        )

        # Dict để build tree structure: absolute path -> TreeItem
        path_to_item: dict[str, TreeItem] = {root_path_str: root_item}

        try:
            # Dùng Walk từ scandir-rs - tương tự os.walk() nhưng nhanh hơn nhiều
            # NOTE: RustWalk trả về (rel_dirpath, dirs, files) với rel_dirpath là relative path
            for rel_dirpath, dirs, files in RustWalk(root_path_str):
                if not is_scanning():
                    break

                # Convert relative path to absolute path
                # RustWalk: '' = root, 'subdir' = subdir, etc.
                if rel_dirpath == "" or rel_dirpath == ".":
                    abs_dirpath = root_path_str
                else:
                    abs_dirpath = os.path.join(root_path_str, rel_dirpath)

                # Update progress
                self._progress.directories += 1
                self._progress.current_path = abs_dirpath
                self._emit_progress(progress_callback)

                # Get parent item
                parent_item = path_to_item.get(abs_dirpath)
                if parent_item is None:
                    # Parent không có trong tree - có thể bị ignore
                    continue

                # Sort dirs và files
                dirs_sorted = sorted(dirs, key=str.lower)
                files_sorted = sorted(files, key=str.lower)

                # Process directories
                for dir_name in dirs_sorted:
                    if not is_scanning():
                        break

                    abs_dir_path = os.path.join(abs_dirpath, dir_name)

                    # Check system path
                    if is_system_path(Path(abs_dir_path)):
                        continue

                    # Check ignore patterns using relative path
                    try:
                        rel_path = Path(abs_dir_path).relative_to(root_path)
                        rel_path_str = str(rel_path) + "/"
                        if spec.match_file(rel_path_str):
                            continue
                    except ValueError:
                        continue

                    child = TreeItem(label=dir_name, path=abs_dir_path, is_dir=True)
                    parent_item.children.append(child)
                    path_to_item[abs_dir_path] = child

                # Process files
                for file_name in files_sorted:
                    if not is_scanning():
                        break

                    abs_file_path = os.path.join(abs_dirpath, file_name)

                    # Check system path
                    if is_system_path(Path(abs_file_path)):
                        continue

                    # Check ignore patterns
                    try:
                        rel_path = Path(abs_file_path).relative_to(root_path)
                        rel_path_str = str(rel_path)
                        if spec.match_file(rel_path_str):
                            continue
                    except ValueError:
                        continue

                    self._progress.files += 1
                    parent_item.children.append(
                        TreeItem(label=file_name, path=abs_file_path, is_dir=False)
                    )

            # Final progress
            self._emit_progress(progress_callback, force=True)

        except Exception as e:
            from core.logging_config import log_error

            log_error(f"[FileScanner] Rust scanner error: {e}, falling back to Python")
            # Fallback nếu Rust scanner lỗi
            return self._scan_directory(root_path, root_path, spec, progress_callback)

        return root_item

    def _build_ignore_patterns(self, root_path: Path, config: ScanConfig) -> List[str]:
        """Build list cac ignore patterns tu config. Delegate cho ignore_engine."""
        return build_ignore_patterns(
            root_path,
            use_default_ignores=config.use_default_ignores,
            excluded_patterns=config.excluded_patterns,
            use_gitignore=config.use_gitignore,
        )

    def _scan_directory(
        self,
        current_path: Path,
        root_path: Path,
        spec: pathspec.PathSpec,
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

            if is_system_path(entry_path):
                continue

            try:
                rel_path = entry_path.relative_to(root_path)
            except ValueError:
                continue

            rel_path_str = str(rel_path) + "/"

            if spec.match_file(rel_path_str):
                continue

            child = self._scan_directory(entry_path, root_path, spec, progress_callback)
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

            rel_path_str = str(rel_path)

            if spec.match_file(rel_path_str):
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
    spec: pathspec.PathSpec,
) -> TreeItem:
    """
    Scan chỉ một level của directory (không recursive).

    Dùng cho lazy loading - scan children khi user expand folder.

    Args:
        directory_path: Directory cần scan
        root_path: Root workspace path (để match ignore patterns)
        spec: PathSpec cho ignore matching

    Returns:
        TreeItem với children là placeholder nếu có subdirs
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
            rel_path = entry.relative_to(root_path)
        except ValueError:
            continue

        rel_path_str = str(rel_path)
        if entry.is_dir():
            rel_path_str += "/"

        if spec.match_file(rel_path_str):
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

    scanner = FileScanner()

    # Build ignore spec
    ignore_patterns = scanner._build_ignore_patterns(root_path, config)
    spec = pathspec.PathSpec.from_lines("gitignore", tuple(ignore_patterns))  # type: ignore[arg-type]

    start_scanning()
    try:
        return scan_single_level(directory_path, root_path, spec)
    finally:
        pass  # Don't stop scanning - caller manages this


# Convenience function
def scan_directory(
    root_path: Path,
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

    scanner = FileScanner()
    return scanner.scan(
        root_path,
        config=config,
        progress_callback=progress_callback,
    )
