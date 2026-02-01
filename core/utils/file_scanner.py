"""
File Scanner - File tree scanning với global cancellation

Simplified version - không dùng threading, chạy sync trong async context.
Dùng global cancellation flag giống isLoadingDirectory trong PasteMax.

Features:
- Global cancellation flag để stop ngay lập tức
- Throttled progress updates (200ms interval)
- Gitignore và default ignore patterns support
"""

import time
from pathlib import Path
from typing import Callable, Optional, List
from dataclasses import dataclass

import pathspec

from core.constants import EXTENDED_IGNORE_PATTERNS
from core.utils.file_utils import (
    TreeItem,
    is_system_path,
    _read_gitignore,
)


# ============================================
# GLOBAL CANCELLATION FLAG
# Giống isLoadingDirectory trong PasteMax
# RACE CONDITION FIX: Sử dụng threading.Lock để đảm bảo thread-safe
# ============================================
import threading

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

    Simplified version - sync scanning với global flag để cancel.
    """

    # Constants
    THROTTLE_INTERVAL_MS = 200  # 200ms giữa các progress updates

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

        Sử dụng global _is_scanning flag để cancel.

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
        spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns)

        try:
            # Scan với progress
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

    def _build_ignore_patterns(self, root_path: Path, config: ScanConfig) -> List[str]:
        """Build list các ignore patterns từ config."""
        patterns: List[str] = []

        # Always exclude VCS directories
        patterns.extend([".git", ".hg", ".svn"])

        # Default ignore patterns
        if config.use_default_ignores:
            patterns.extend(EXTENDED_IGNORE_PATTERNS)

        # User patterns
        if config.excluded_patterns:
            patterns.extend(config.excluded_patterns)

        # Gitignore patterns
        if config.use_gitignore:
            gitignore_patterns = _read_gitignore(root_path)
            patterns.extend(gitignore_patterns)

        return patterns

    def _scan_directory(
        self,
        current_path: Path,
        root_path: Path,
        spec: pathspec.PathSpec,
        progress_callback: Optional[ProgressCallback],
    ) -> TreeItem:
        """Scan một directory recursively với progress."""
        # RACE CONDITION FIX: Sử dụng thread-safe function thay vì đọc global trực tiếp

        # Check global cancellation flag - giống PasteMax
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

        # Update progress - directory count
        self._progress.directories += 1
        self._progress.current_path = str(current_path)

        # Throttled progress callback
        self._emit_progress(progress_callback)

        try:
            entries = list(current_path.iterdir())
        except PermissionError:
            return item
        except OSError:
            return item

        # Sort: directories first, then alphabetically
        entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

        # Separate files and directories
        directories = [e for e in entries if e.is_dir()]
        files = [e for e in entries if e.is_file()]

        # Process directories
        for entry in directories:
            # Check cancellation trước mỗi directory
            # RACE CONDITION FIX: Sử dụng thread-safe function
            if not is_scanning():
                break

            if is_system_path(entry):
                continue

            try:
                rel_path = entry.relative_to(root_path)
            except ValueError:
                continue

            rel_path_str = str(rel_path) + "/"

            if spec.match_file(rel_path_str):
                continue

            child = self._scan_directory(entry, root_path, spec, progress_callback)
            item.children.append(child)

        # Process files
        for entry in files:
            # Check cancellation trước mỗi batch files
            # RACE CONDITION FIX: Sử dụng thread-safe function
            if not is_scanning():
                break

            if is_system_path(entry):
                continue

            try:
                rel_path = entry.relative_to(root_path)
            except ValueError:
                continue

            rel_path_str = str(rel_path)

            if spec.match_file(rel_path_str):
                continue

            # Update progress - file count
            self._progress.files += 1

            item.children.append(
                TreeItem(label=entry.name, path=str(entry), is_dir=False)
            )

        # Emit final progress for this directory
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
