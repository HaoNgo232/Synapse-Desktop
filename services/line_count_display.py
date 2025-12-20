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
from typing import Dict, Optional, Set, Callable
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
            except Exception:
                pass

    def request_lines_for_tree(
        self,
        tree: TreeItem,
        visible_only: bool = True,
        visible_paths: Optional[Set[str]] = None,
    ):
        """
        Request line counts cho toan bo tree.

        Args:
            tree: Root TreeItem
            visible_only: Chi tinh cho files dang hien thi
            visible_paths: Set cac paths dang hien thi (neu visible_only=True)
        """
        self._collect_files_to_count(tree, visible_only, visible_paths)

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
        Count lines cho mot file (port tu Repomix logic).

        Logic:
        - Empty file: 0 lines
        - Count newlines
        - If ends with newline: newline_count
        - Else: newline_count + 1
        """
        try:
            file_path = Path(path)

            # Read file content
            # Try multiple encodings
            content = None
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    content = file_path.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                # Binary file or unknown encoding - try reading as binary
                try:
                    content_bytes = file_path.read_bytes()
                    # Count newlines in binary
                    newline_count = content_bytes.count(b"\n")
                    return (
                        newline_count
                        if content_bytes.endswith(b"\n")
                        else newline_count + 1
                    )
                except Exception:
                    return 0

            # Empty file
            if len(content) == 0:
                return 0

            # Count newlines
            newline_count = content.count("\n")

            # Return based on whether content ends with newline
            return newline_count if content.endswith("\n") else newline_count + 1

        except Exception:
            # File read error - return 0
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
        Returns None neu chua tinh xong het.
        """
        folder_item = self._find_item_by_path(tree, folder_path)
        if not folder_item:
            return None

        total = 0
        all_cached = True

        for file_path in self._get_all_file_paths(folder_item):
            with self._lock:
                if file_path in self._cache:
                    total += self._cache[file_path]
                else:
                    all_cached = False
                    break

        return total if all_cached else None

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
