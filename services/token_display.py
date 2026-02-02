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
from typing import Dict, Callable, Set, Optional, List
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
        
        # Track all deferred timers để cancel khi stop
        self._deferred_timers: List[SafeTimer] = []
        self._deferred_timers_lock = threading.Lock()

    def clear_cache(self):
        """Xóa toàn bộ cache (khi reload tree)"""
        from core.logging_config import log_debug
        log_debug("[TokenDisplayService] clear_cache() called")
        
        # Stop global counting flag FIRST
        stop_token_counting()
        
        # Cancel ALL deferred timers IMMEDIATELY
        self._cancel_all_deferred_timers()
        
        with self._lock:
            self._cache.clear()
            self._loading_paths.clear()
        with self._update_lock:
            self._pending_updates.clear()
            if self._update_timer:
                try:
                    self._update_timer.dispose()
                except Exception:
                    pass
                self._update_timer = None
        
        log_debug("[TokenDisplayService] clear_cache() complete")

    def stop(self):
        """
        Stop processing và cleanup IMMEDIATELY.
        
        RACE CONDITION FIX: Set disposal flag TRƯỚC khi cancel timers.
        Cancel ALL deferred timers để đảm bảo không có background work còn chạy.
        """
        from core.logging_config import log_debug
        log_debug("[TokenDisplayService] stop() called - cancelling all operations")
        
        # Set disposal flag FIRST - this causes all callbacks to exit early
        self._is_disposed = True
        
        # Stop global token counting flag IMMEDIATELY
        stop_token_counting()
        
        # Cancel ALL deferred timers - CRITICAL for folder switch
        self._cancel_all_deferred_timers()
        
        # Clear all state
        self._loading_paths.clear()
        with self._update_lock:
            self._pending_updates.clear()
            if self._update_timer:
                try:
                    self._update_timer.dispose()
                except Exception:
                    pass
                self._update_timer = None
        
        # Also clear cache to prevent stale data
        with self._lock:
            self._cache.clear()
        
        log_debug("[TokenDisplayService] stop() complete")

    def _cancel_all_deferred_timers(self):
        """
        Cancel tất cả deferred timers đang pending.
        
        CRITICAL: Gọi method này khi switch folder hoặc stop service
        để đảm bảo không có background token counting còn chạy.
        """
        from core.logging_config import log_debug
        
        with self._deferred_timers_lock:
            timer_count = len(self._deferred_timers)
            if timer_count > 0:
                log_debug(f"[TokenDisplayService] Cancelling {timer_count} deferred timers")
            
            for timer in self._deferred_timers:
                try:
                    timer.dispose()
                except Exception:
                    pass
            self._deferred_timers.clear()

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
        max_immediate: int = 20,  # Reduced from 50 for faster UI response
    ):
        """
        Request token counts cho toàn bộ tree.
        
        Tối ưu: Chỉ count ngay lập tức cho max_immediate files đầu tiên.
        Files còn lại sẽ được count incrementally khi UI idle.
        
        PERFORMANCE FIX: Reduced max_immediate to 20 for faster initial UI response.
        
        Args:
            tree: Root TreeItem
            page: Flet page
            visible_only: Chỉ count visible files
            visible_paths: Set paths đang visible
            max_immediate: Số files count ngay (default 20)
        """
        # Check if already cancelled before starting
        if not is_counting_tokens():
            return
            
        # RACE CONDITION FIX: Sử dụng thread-safe function
        start_token_counting()
        self._page = page  # Store for UI updates

        # Collect all files
        files_to_count = []
        self._collect_files_to_count(tree, visible_only, visible_paths, files_to_count)
        
        # Check cancellation after collecting files
        if not is_counting_tokens():
            return
        
        # Split into immediate và deferred
        immediate_files = files_to_count[:max_immediate]
        deferred_files = files_to_count[max_immediate:]

        # Count immediate files sync - with frequent cancellation checks
        count = 0
        for path in immediate_files:
            # Check cancellation trước mỗi file - CRITICAL
            if not is_counting_tokens():
                return  # Exit immediately

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

            # Progress update mỗi 10 files (reduced from 20 for more responsive UI)
            if count % 10 == 0:
                # Check cancellation before UI update
                if not is_counting_tokens():
                    return
                if self.on_update:
                    try:
                        self.on_update()
                    except Exception:
                        pass

        # Final update for immediate files
        if is_counting_tokens() and self.on_update:
            try:
                self.on_update()
            except Exception:
                pass
        
        # Schedule deferred files counting if any and not cancelled
        if deferred_files and is_counting_tokens():
            self._schedule_deferred_counting(deferred_files)
    
    def _schedule_deferred_counting(self, files: list):
        """
        Schedule counting cho deferred files.
        
        Count từng batch nhỏ với delay để không block UI.
        
        PERFORMANCE FIX: Smaller batches and more frequent cancellation checks.
        FOLDER SWITCH FIX: Track all timers để cancel khi switch folder.
        """
        from core.logging_config import log_debug
        
        # Early exit checks
        if not files:
            return
        if not is_counting_tokens():
            log_debug("[TokenDisplayService] _schedule_deferred_counting skipped - not counting")
            return
        if self._is_disposed:
            log_debug("[TokenDisplayService] _schedule_deferred_counting skipped - disposed")
            return
        
        BATCH_SIZE = 5  # Very small batches for responsive cancellation
        BATCH_DELAY = 0.05  # 50ms between batches
        
        def count_batch(batch_files):
            # Check cancellation FIRST - before doing ANY work
            if not is_counting_tokens() or self._is_disposed:
                log_debug("[TokenDisplayService] count_batch cancelled at start")
                return
            
            for path in batch_files:
                # Check cancellation for EACH file - CRITICAL
                if not is_counting_tokens() or self._is_disposed:
                    log_debug("[TokenDisplayService] count_batch cancelled mid-batch")
                    return  # Exit immediately
                
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
            
            # Update UI after batch only if not cancelled
            if is_counting_tokens() and self.on_update and not self._is_disposed:
                try:
                    self.on_update()
                except Exception:
                    pass
        
        # Clear old deferred timers before scheduling new ones
        self._cancel_all_deferred_timers()
        
        # Check cancellation again after clearing
        if not is_counting_tokens() or self._is_disposed:
            return
        
        # Process in batches - check cancellation before each batch
        for i in range(0, len(files), BATCH_SIZE):
            # Check cancellation before scheduling each batch
            if not is_counting_tokens() or self._is_disposed:
                log_debug(f"[TokenDisplayService] batch scheduling cancelled at batch {i}")
                return
            
            batch = files[i:i + BATCH_SIZE]
            
            # Use SafeTimer for thread-safe deferred execution
            def create_batch_callback(batch_data):
                return lambda: count_batch(batch_data)
            
            timer = SafeTimer(
                interval=BATCH_DELAY * (i // BATCH_SIZE + 1),
                callback=create_batch_callback(batch),
                page=self._page,
                use_main_thread=False,  # Count in background
            )
            
            # Track timer để cancel later
            with self._deferred_timers_lock:
                # Final check before adding
                if self._is_disposed:
                    timer.dispose()
                    return
                self._deferred_timers.append(timer)
            
            timer.start()

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
