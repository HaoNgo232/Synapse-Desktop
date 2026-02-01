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
from core.utils.safe_timer import SafeTimer  # RACE CONDITION FIX


# ============================================
# GLOBAL CANCELLATION FLAG
# Giống isLoadingDirectory trong PasteMax
# RACE CONDITION FIX: Sử dụng threading.Lock để đảm bảo thread-safe
# ============================================
import threading as _token_threading

_token_counting_lock = _token_threading.Lock()
_is_counting_tokens = False


def is_counting_tokens() -> bool:
    """
    Check xem có đang counting tokens không.

    Thread-safe: Sử dụng lock để đọc giá trị.
    """
    with _token_counting_lock:
        return _is_counting_tokens


def stop_token_counting():
    """
    Dừng token counting ngay lập tức.

    Thread-safe: Sử dụng lock để set giá trị.
    """
    global _is_counting_tokens
    with _token_counting_lock:
        _is_counting_tokens = False


def start_token_counting():
    """
    Bắt đầu token counting.

    Thread-safe: Sử dụng lock để set giá trị.
    """
    global _is_counting_tokens
    with _token_counting_lock:
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
        
        # Race condition prevention
        self._update_lock = threading.Lock()
        self._pending_updates: Set[str] = set()
        self._update_timer: Optional[SafeTimer] = None  # RACE CONDITION FIX: Use SafeTimer
        self._is_disposed = False  # Disposal flag để prevent callbacks sau cleanup

    def clear_cache(self):
        """Xóa toàn bộ cache (khi reload tree)"""
        stop_token_counting()
        with self._lock:
            self._cache.clear()
            self._loading_paths.clear()
        with self._update_lock:
            self._pending_updates.clear()
            if self._update_timer:
                self._update_timer.cancel()
                self._update_timer = None

    def stop(self):
        """
        Stop processing và cleanup.
        
        RACE CONDITION FIX: Set disposal flag TRƯỚC khi cancel timers.
        """
        # Set disposal flag FIRST
        self._is_disposed = True
        
        stop_token_counting()
        self._loading_paths.clear()
        with self._update_lock:
            self._pending_updates.clear()
            if self._update_timer:
                self._update_timer.dispose()  # RACE CONDITION FIX: Use dispose instead of cancel
                self._update_timer = None

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
        Request tính token count cho file - prevent duplicate requests
        """
        with self._update_lock:
            if path in self._cache or path in self._pending_updates:
                return
            self._pending_updates.add(path)

        # Chỉ tính cho files
        if Path(path).is_dir():
            with self._update_lock:
                self._pending_updates.discard(path)
            return

        # Check cancellation - RACE CONDITION FIX: Sử dụng thread-safe function
        if not is_counting_tokens():
            with self._update_lock:
                self._pending_updates.discard(path)
            return

        try:
            tokens = count_tokens_for_file(Path(path))
            with self._lock:
                self._cache[path] = tokens
            with self._update_lock:
                self._pending_updates.discard(path)
                
            # Schedule UI update
            self._schedule_ui_update()
                
        except Exception:
            with self._lock:
                self._cache[path] = 0
            with self._update_lock:
                self._pending_updates.discard(path)

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
        # RACE CONDITION FIX: Sử dụng thread-safe function
        start_token_counting()

        # Collect all files
        files_to_count = []
        self._collect_files_to_count(tree, visible_only, visible_paths, files_to_count)

        # Count tokens sync với progress updates
        count = 0
        for path in files_to_count:
            # Check cancellation trước mỗi file - CRITICAL
            # RACE CONDITION FIX: Sử dụng thread-safe function
            if not is_counting_tokens():
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
        # Check cancellation - RACE CONDITION FIX: Sử dụng thread-safe function
        if not is_counting_tokens():
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
                # RACE CONDITION FIX: Sử dụng thread-safe function
                if not is_counting_tokens():
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
            
    def _schedule_ui_update(self):
        """Schedule a debounced UI update - RACE CONDITION SAFE"""
        with self._update_lock:
            if self._update_timer:
                self._update_timer.cancel()
            
            # RACE CONDITION FIX: Use SafeTimer instead of Timer
            self._update_timer = SafeTimer(
                interval=0.1,
                callback=self._do_ui_update,
                page=getattr(self, '_page', None),
                use_main_thread=True
            )
            self._update_timer.start()
    
    def _do_ui_update(self):
        """
        Actual UI update với disposal check.
        
        RACE CONDITION FIX: Check disposal trước khi gọi callback.
        Timer callback có thể chạy sau khi service đã cleanup.
        """
        # Skip nếu đã disposed
        if self._is_disposed:
            return
        
        if self.on_update:
            try:
                self.on_update()
            except Exception:
                pass  # Ignore errors - callback có thể fail safely
