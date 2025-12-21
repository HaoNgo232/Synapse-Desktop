"""
Token Display Service - Quản lý và cache token counts cho files

Phiên bản Sync - Đơn giản nhất, giống PasteMax.
Không dùng threading hay async để tránh race conditions.

Features:
- Cache token counts để tránh tính toán lại
- Global cancellation flag để cancel ngay lập tức
- Aggregate tokens cho folders
"""

from pathlib import Path
from typing import Dict, Callable, Set, Optional
import threading

from core.utils.file_utils import TreeItem
from core.token_counter import count_tokens_for_file


# ============================================
# GLOBAL CANCELLATION FLAG
# Giống isLoadingDirectory trong PasteMax
# ============================================
_is_counting_tokens = False


def is_counting_tokens() -> bool:
    """Check xem có đang counting tokens không"""
    return _is_counting_tokens


def stop_token_counting():
    """Dừng token counting ngay lập tức"""
    global _is_counting_tokens
    _is_counting_tokens = False


def start_token_counting():
    """Bắt đầu token counting"""
    global _is_counting_tokens
    _is_counting_tokens = True


class TokenDisplayService:
    """
    Service quản lý token display cho file tree.

    Phiên bản SYNC - đơn giản nhất, không race condition.
    Token counting chạy synchronous với global flag để cancel.
    """

    # Config
    MAX_CACHE_SIZE = 10000  # Maximum cache entries
    PROGRESS_INTERVAL = 20  # Update progress mỗi N files

    def __init__(self, on_update: Optional[Callable[[], None]] = None):
        """
        Args:
            on_update: Callback khi token cache được update (để refresh UI)
        """
        self.on_update = on_update

        # Cache: path -> token count
        self._cache: Dict[str, int] = {}
        self._lock = threading.Lock()

        # Tracking loading state
        self._loading_paths: Set[str] = set()

    def clear_cache(self):
        """Xóa toàn bộ cache (khi reload tree)"""
        stop_token_counting()
        with self._lock:
            self._cache.clear()
            self._loading_paths.clear()

    def stop(self):
        """Stop processing"""
        stop_token_counting()
        self._loading_paths.clear()

    def cleanup_stale_entries(self, valid_paths: set):
        """Xóa các cache entries không còn tồn tại trong tree."""
        with self._lock:
            stale_keys = [k for k in self._cache.keys() if k not in valid_paths]
            for key in stale_keys:
                del self._cache[key]

    def get_token_count(self, path: str) -> Optional[int]:
        """Lấy token count từ cache. Returns None nếu chưa được tính."""
        with self._lock:
            return self._cache.get(path)

    def get_token_display(self, path: str) -> str:
        """Lấy string hiển thị token count. Returns empty string nếu chưa có."""
        with self._lock:
            count = self._cache.get(path)
            if count is None:
                if path in self._loading_paths:
                    return "..."
                return ""
            return self._format_tokens(count)

    def is_loading(self, path: str) -> bool:
        """Check xem path đang được load không"""
        return path in self._loading_paths

    def request_token_count(self, path: str, page=None):
        """
        Request tính token count cho file (SYNC).
        Tính ngay lập tức và cache kết quả.
        """
        with self._lock:
            if path in self._cache:
                return

        # Chỉ tính cho files
        if Path(path).is_dir():
            return

        # Check cancellation
        if not _is_counting_tokens:
            return

        try:
            tokens = count_tokens_for_file(Path(path))
            with self._lock:
                self._cache[path] = tokens
        except Exception:
            with self._lock:
                self._cache[path] = 0

    def request_tokens_for_tree(
        self,
        tree: TreeItem,
        page=None,
        visible_only: bool = True,
        visible_paths: Optional[set] = None,
    ):
        """
        Request token counts cho toàn bộ tree.
        Chạy SYNC với global cancellation flag.
        """
        global _is_counting_tokens
        _is_counting_tokens = True

        # Collect all files
        files_to_count = []
        self._collect_files_to_count(tree, visible_only, visible_paths, files_to_count)

        # Count tokens sync với progress updates
        count = 0
        for path in files_to_count:
            # Check cancellation trước mỗi file - CRITICAL
            if not _is_counting_tokens:
                break

            with self._lock:
                if path in self._cache:
                    continue

            try:
                tokens = count_tokens_for_file(Path(path))
                with self._lock:
                    self._cache[path] = tokens
            except Exception:
                with self._lock:
                    self._cache[path] = 0

            count += 1

            # Progress update mỗi N files
            if count % self.PROGRESS_INTERVAL == 0:
                if self.on_update:
                    try:
                        self.on_update()
                    except Exception:
                        pass

        # Final update
        if self.on_update:
            try:
                self.on_update()
            except Exception:
                pass

    def _collect_files_to_count(
        self,
        item: TreeItem,
        visible_only: bool,
        visible_paths: Optional[set],
        result: list,
    ):
        """Recursive collect files cần tính token"""
        # Check cancellation
        if not _is_counting_tokens:
            return

        # Skip nếu visible_only và item không visible
        if visible_only and visible_paths and item.path not in visible_paths:
            return

        if not item.is_dir:
            # Là file - add to list
            with self._lock:
                cached = item.path in self._cache

            if not cached:
                result.append(item.path)
        else:
            # Là folder - recurse vào children
            for child in item.children:
                if not _is_counting_tokens:
                    break
                self._collect_files_to_count(child, visible_only, visible_paths, result)

    def _cleanup_cache_if_needed(self):
        """Remove oldest cache entries nếu cache quá lớn"""
        with self._lock:
            if len(self._cache) > self.MAX_CACHE_SIZE:
                remove_count = len(self._cache) // 5
                keys_to_remove = list(self._cache.keys())[:remove_count]
                for key in keys_to_remove:
                    del self._cache[key]

    def get_folder_tokens(self, folder_path: str, tree: TreeItem) -> Optional[int]:
        """Tính tổng tokens của folder từ cache."""
        folder_item = self._find_item_by_path(tree, folder_path)
        if not folder_item:
            return None

        total = 0
        all_cached = True

        file_paths = self._get_all_file_paths(folder_item)

        with self._lock:
            for file_path in file_paths:
                if file_path in self._cache:
                    total += self._cache[file_path]
                else:
                    all_cached = False
                    break

        return total if all_cached else None

    def _get_all_file_paths(self, item: TreeItem) -> list:
        """Lấy tất cả file paths trong item"""
        paths = []
        if not item.is_dir:
            paths.append(item.path)
        for child in item.children:
            paths.extend(self._get_all_file_paths(child))
        return paths

    def _find_item_by_path(
        self, item: TreeItem, target_path: str
    ) -> Optional[TreeItem]:
        """Tìm TreeItem theo path"""
        if item.path == target_path:
            return item
        for child in item.children:
            found = self._find_item_by_path(child, target_path)
            if found:
                return found
        return None

    @staticmethod
    def _format_tokens(count: int) -> str:
        """Format token count cho display"""
        if count < 1000:
            return str(count)
        elif count < 10000:
            return f"{count / 1000:.1f}k"
        else:
            return f"{count // 1000}k"
