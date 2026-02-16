"""
Line Count Display Service - Quan ly va cache line counts cho files

Tach ra theo SOLID principles:
- Single Responsibility: Chi xu ly line counting va caching
- Open/Closed: De dang extend them caching strategies
- Interface Segregation: Chi expose methods can thiet

Line counting logic port tu Repomix:
- Empty file: 0 lines
- Count newlines: content.count('\n')
- If ends with \n: newline_count
- Else: newline_count + 1
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass
from threading import Lock

from core.utils.file_utils import TreeItem


@dataclass
class LineInfo:
    """Thong tin line count cua file/folder"""

    lines: int
    is_cached: bool = False


class LineCountService:
    """
    Service quan ly line count display cho file tree.

    Features:
    - Cache line counts de tranh tinh toan lai
    - Synchronous counting (line counting rat nhanh, khong can threading)
    - Aggregate lines cho folders
    - Auto cleanup stale cache entries

    Note: Khac voi TokenDisplayService, service nay don gian hon vi:
    - Line counting nhanh hon nhieu so voi token counting
    - Khong can background threading
    - Chi can simple cache
    """

    # Config
    MAX_CACHE_SIZE = 10000  # Maximum cache entries

    def __init__(self, on_update: Optional[Callable[[], None]] = None):
        """
        Args:
            on_update: Callback khi line cache duoc update (de refresh UI)
        """
        self.on_update = on_update

        # Cache: path -> line count
        self._cache: Dict[str, int] = {}

        # Thread safety lock
        self._lock = Lock()

    def clear_cache(self):
        """Xoa toan bo cache (khi reload tree)"""
        with self._lock:
            self._cache.clear()

    def cleanup_stale_entries(self, valid_paths: Set[str]):
        """
        Xoa cac cache entries khong con ton tai trong tree.

        Args:
            valid_paths: Set cac paths hien tai trong tree
        """
        with self._lock:
            stale_keys = [k for k in self._cache.keys() if k not in valid_paths]
            for key in stale_keys:
                del self._cache[key]

    def get_line_count(self, path: str) -> Optional[int]:
        """
        Lay line count tu cache.
        Returns None neu chua duoc tinh.
        """
        with self._lock:
            return self._cache.get(path)

    def get_line_display(self, path: str) -> str:
        """
        Lay string hien thi line count.
        Returns empty string neu chua co.
        """
        count = self._cache.get(path)
        if count is None:
            return ""
        return self._format_lines(count)

    def request_line_count(self, path: str):
        """
        Request tinh line count cho file (synchronous).
        Neu da co trong cache thi khong lam gi.
        """
        if path in self._cache:
            return

        # Chi tinh cho files, khong tinh cho folders
        if Path(path).is_dir():
            return

        with self._lock:
            # Double-check trong lock
            if path in self._cache:
                return

            # Tinh line count
            lines = self._count_file_lines(path)
            self._cache[path] = lines

        # Cleanup cache if needed
        self._cleanup_cache_if_needed()

        # Notify UI
        if self.on_update:
            try:
                self.on_update()
            except Exception as e:
                from core.logging_config import log_error

                log_error(f"Failed to notify UI update: {e}")

    def request_lines_for_tree(
        self,
        tree: TreeItem,
        visible_only: bool = True,
        visible_paths: Optional[Set[str]] = None,
        max_immediate: int = 100,
    ):
        """
        Request line counts cho toan bo tree.

        PERFORMANCE: Giới hạn số files count ngay để tránh block UI.

        Args:
            tree: Root TreeItem
            visible_only: Chi tinh cho files dang hien thi
            visible_paths: Set cac paths dang hien thi (neu visible_only=True)
            max_immediate: Max files to count immediately (default 100)
        """
        # Collect files to count
        files_to_count: List[str] = []
        self._collect_files_to_count_list(
            tree, visible_only, visible_paths, files_to_count
        )

        # Count immediate batch (won't block too much)
        immediate = files_to_count[:max_immediate]
        for path in immediate:
            self.request_line_count(path)

        # Schedule deferred counting for remaining files
        remaining = files_to_count[max_immediate:]
        if remaining:
            self._schedule_deferred_line_counting(remaining)

    def _collect_files_to_count_list(
        self,
        item: TreeItem,
        visible_only: bool,
        visible_paths: Optional[Set[str]],
        result: List[str],
    ):
        """Collect files into list for batch processing"""
        if visible_only and visible_paths and item.path not in visible_paths:
            return

        if not item.is_dir:
            if item.path not in self._cache:
                result.append(item.path)
        else:
            for child in item.children:
                self._collect_files_to_count_list(
                    child, visible_only, visible_paths, result
                )

    def _schedule_deferred_line_counting(self, files: List[str]):
        """Schedule line counting for remaining files in background"""
        import threading

        BATCH_SIZE = 100  # Tăng batch size
        BATCH_DELAY = 0.3  # 300ms - tăng delay để giảm UI pressure

        def count_batch(batch):
            for path in batch:
                self.request_line_count(path)

        for i in range(0, len(files), BATCH_SIZE):
            batch = files[i : i + BATCH_SIZE]
            delay = BATCH_DELAY * (i // BATCH_SIZE + 1)
            timer = threading.Timer(delay, count_batch, args=[batch])
            timer.daemon = True
            timer.start()

    def _collect_files_to_count(
        self, item: TreeItem, visible_only: bool, visible_paths: Optional[Set[str]]
    ):
        """Recursive collect files can tinh line count"""
        # Skip neu visible_only va item khong visible
        if visible_only and visible_paths and item.path not in visible_paths:
            return

        if not item.is_dir:
            # La file - request line count
            self.request_line_count(item.path)
        else:
            # La folder - recurse vao children
            for child in item.children:
                self._collect_files_to_count(child, visible_only, visible_paths)

    def _count_file_lines(self, path: str) -> int:
        """
        Count lines cho mot file - optimized version.

        Uses mmap for large files to avoid loading entire content into memory.
        Falls back to regular read for small files.

        Logic:
        - Empty file: 0 lines
        - Count newlines
        - If ends with newline: newline_count
        - Else: newline_count + 1
        """

        try:
            file_path = Path(path)
            file_size = file_path.stat().st_size

            # Empty file
            if file_size == 0:
                return 0

            # For large files (>1MB), use mmap for memory efficiency
            if file_size > 1024 * 1024:
                return self._count_lines_mmap(file_path)

            # For small files, read directly (faster due to less overhead)
            return self._count_lines_direct(file_path)

        except Exception as e:
            from core.logging_config import log_debug

            log_debug(f"Failed to count lines for {path}: {e}")
            return 0

    def _count_lines_mmap(self, file_path: Path) -> int:
        """Count lines using memory-mapped file (efficient for large files)."""
        import mmap

        try:
            with open(file_path, "rb") as f:
                # Memory map the file
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    newline_count = 0
                    # Count newlines in chunks
                    chunk_size = 1024 * 1024  # 1MB chunks
                    pos = 0
                    file_size = mm.size()

                    while pos < file_size:
                        end = min(pos + chunk_size, file_size)
                        chunk = mm[pos:end]
                        newline_count += chunk.count(b"\n")
                        pos = end

                    # Check if ends with newline
                    ends_with_newline = mm[-1:] == b"\n" if file_size > 0 else False

                    return newline_count if ends_with_newline else newline_count + 1
        except Exception:
            # Fallback to direct read
            return self._count_lines_direct(file_path)

    def _count_lines_direct(self, file_path: Path) -> int:
        """Count lines by reading file directly (efficient for small files)."""
        try:
            # Try reading as binary first (fastest)
            content_bytes = file_path.read_bytes()

            # Check for null bytes (binary file indicator)
            if b"\x00" in content_bytes[:1000]:
                # Binary file - just count newlines
                newline_count = content_bytes.count(b"\n")
                return (
                    newline_count
                    if content_bytes.endswith(b"\n")
                    else newline_count + 1
                )

            # Text file - decode and count
            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content = content_bytes.decode("latin-1")
                except UnicodeDecodeError:
                    # Fallback to binary count
                    newline_count = content_bytes.count(b"\n")
                    return (
                        newline_count
                        if content_bytes.endswith(b"\n")
                        else newline_count + 1
                    )

            if len(content) == 0:
                return 0

            newline_count = content.count("\n")
            return newline_count if content.endswith("\n") else newline_count + 1

        except Exception:
            return 0

    def _cleanup_cache_if_needed(self):
        """Remove oldest cache entries if cache is too large"""
        with self._lock:
            if len(self._cache) > self.MAX_CACHE_SIZE:
                # Remove 20% of oldest entries
                # Since dict maintains insertion order in Python 3.7+
                remove_count = len(self._cache) // 5
                keys_to_remove = list(self._cache.keys())[:remove_count]
                for key in keys_to_remove:
                    del self._cache[key]

    def get_folder_lines(self, folder_path: str, tree: TreeItem) -> Optional[int]:
        """
        Tinh tong lines cua folder tu cache.

        UPDATED: Return partial sum ngay ca khi chua cache het.
        Returns None chi khi chua co bat ky file nao duoc cache.
        """
        folder_item = self._find_item_by_path(tree, folder_path)
        if not folder_item:
            return None

        total = 0
        file_paths = self._get_all_file_paths(folder_item)

        # Neu khong co files, return None
        if not file_paths:
            return None

        with self._lock:
            for file_path in file_paths:
                if file_path in self._cache:
                    total += self._cache[file_path]

        # Return partial sum, chi return None neu chua co file nao duoc cache
        return total if total > 0 else None

    def get_folder_lines_status(
        self, folder_path: str, tree: TreeItem
    ) -> tuple[int, bool]:
        """
        Lay line count va status complete cua folder.

        Returns:
            Tuple (total_lines, is_complete)
            - total_lines: Tong so lines da cache (co the la partial)
            - is_complete: True neu tat ca files trong folder da duoc cache
        """
        folder_item = self._find_item_by_path(tree, folder_path)
        if not folder_item:
            return (0, True)

        total = 0
        all_cached = True
        file_paths = self._get_all_file_paths(folder_item)

        if not file_paths:
            return (0, True)

        with self._lock:
            for file_path in file_paths:
                if file_path in self._cache:
                    total += self._cache[file_path]
                else:
                    all_cached = False

        return (total, all_cached)

    def _get_all_file_paths(self, item: TreeItem) -> list:
        """Lay tat ca file paths trong item"""
        paths = []
        if not item.is_dir:
            paths.append(item.path)
        for child in item.children:
            paths.extend(self._get_all_file_paths(child))
        return paths

    def _find_item_by_path(
        self, item: TreeItem, target_path: str
    ) -> Optional[TreeItem]:
        """Tim TreeItem theo path"""
        if item.path == target_path:
            return item
        for child in item.children:
            found = self._find_item_by_path(child, target_path)
            if found:
                return found
        return None

    @staticmethod
    def _format_lines(count: int) -> str:
        """Format line count cho display"""
        if count < 1000:
            return str(count)
        elif count < 10000:
            return f"{count / 1000:.1f}k"
        else:
            return f"{count // 1000}k"
