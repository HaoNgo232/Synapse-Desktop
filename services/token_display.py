"""
Token Display Service - Quan ly va cache token counts cho files.

Phien ban Signal-based - khong con phu thuoc vao UI framework.
TokenDisplayService ke thua QObject de co the emit signals.
UI layers lang nghe signals nay thay vi duoc truyen callback.

Features:
- Cache token counts de tranh tinh toan lai
- Global cancellation flag (tu core.tokenization.cancellation)
- Aggregate tokens cho folders
- Qt Signals cho thread-safe UI updates (khong can UI page reference)
"""

from pathlib import Path
from typing import Dict, Set, Optional, List
from collections import OrderedDict
import threading
import time

from PySide6.QtCore import QObject, Signal

from core.utils.file_utils import TreeItem
from services.encoder_registry import get_tokenization_service

# Cancellation flag - import tu core layer (fix circular dependency)
# Re-export de backward compat (main_window.py, tests import tu day)
from core.tokenization.cancellation import (  # noqa: F401
    is_counting_tokens,
    start_token_counting,
    stop_token_counting,
)


class TokenDisplayService(QObject):
    """
    Service quan ly token display cho file tree.

    Phien ban SIGNAL-BASED - emit Qt signals thay vi goi UI callback truc tiep.
    Giup tach biet hoan toan tầng Service khoi tầng UI.

    CACH SU DUNG:
        service = TokenDisplayService()
        # UI layer tu ket noi signal:
        service.cache_updated.connect(my_widget.on_token_cache_updated)

    PERFORMANCE OPTIMIZATIONS:
    - Priority queue: count visible/selected files first
    - Smarter batching with size-aware scheduling
    - Incremental cache updates
    - Folder token cache: cache tong tokens cho folders de tranh tinh lai
    """

    # Signal emit khi token cache duoc update (de UI refresh)
    # Khong can truyen tham so - UI tu doc tu get_token_count()
    cache_updated = Signal()

    # Config
    MAX_CACHE_SIZE = 10000  # Maximum cache entries
    PROGRESS_INTERVAL = 10  # Update progress moi N files (reduced for responsiveness)

    # Size thresholds for smart scheduling
    SMALL_FILE_THRESHOLD = 10000  # bytes - count immediately
    LARGE_FILE_THRESHOLD = 100000  # bytes - defer to background

    def __init__(self, parent: Optional[QObject] = None):
        """
        Khoi tao TokenDisplayService.

        Args:
            parent: QObject parent (tuy chon, de quan ly lifecycle)
        """
        super().__init__(parent)

        # Cache: path -> token count
        self._cache: Dict[str, int] = {}
        self._lock = threading.Lock()

        # Folder token cache: folder_path -> (total_tokens, is_complete, file_count)
        # Giup tranh tinh toan lai tong tokens cho folders moi lan render
        # Using OrderedDict for explicit LRU behavior
        self._folder_cache: OrderedDict[str, tuple[int, bool, int]] = OrderedDict()
        self._folder_cache_lock = threading.Lock()
        self._MAX_FOLDER_CACHE_SIZE = 2000  # Prevent unbounded growth

        # Tracking loading state
        self._loading_paths: Set[str] = set()

        # Race condition prevention
        self._update_lock = threading.Lock()
        self._pending_updates: Set[str] = set()
        self._is_disposed = False  # Disposal flag de prevent callbacks sau cleanup

        # Track all deferred timers de cancel khi stop
        self._deferred_threads: List[threading.Timer] = []
        self._deferred_threads_lock = threading.Lock()

    def clear_cache(self):
        """Xoa toan bo cache (khi reload tree)."""
        from core.logging_config import log_debug

        log_debug("[TokenDisplayService] clear_cache() called")

        # Stop global counting flag FIRST
        stop_token_counting()

        # Cancel ALL deferred timers IMMEDIATELY
        self._cancel_all_deferred_timers()

        with self._lock:
            self._cache.clear()
            self._loading_paths.clear()

        # Clear folder cache
        with self._folder_cache_lock:
            self._folder_cache.clear()

        with self._update_lock:
            self._pending_updates.clear()

        log_debug("[TokenDisplayService] clear_cache() complete")

    def stop(self):
        """
        Stop processing va cleanup IMMEDIATELY.

        Set disposal flag TRUOC khi cancel timers.
        Cancel ALL deferred timers de dam bao khong co background work con chay.
        """
        from core.logging_config import log_debug

        log_debug("[TokenDisplayService] stop() called - cancelling all operations")

        # Set disposal flag FIRST - causes all callbacks to exit early
        self._is_disposed = True

        # Stop global token counting flag IMMEDIATELY
        stop_token_counting()

        # Cancel ALL deferred timers - CRITICAL for folder switch
        self._cancel_all_deferred_timers()

        # Clear all state
        self._loading_paths.clear()
        with self._update_lock:
            self._pending_updates.clear()

        # Also clear cache to prevent stale data
        with self._lock:
            self._cache.clear()

        log_debug("[TokenDisplayService] stop() complete")

    def _cancel_all_deferred_timers(self):
        """
        Cancel tat ca deferred timers dang pending.

        CRITICAL: Goi method nay khi switch folder hoac stop service
        de dam bao khong co background token counting con chay.
        """
        from core.logging_config import log_debug

        with self._deferred_threads_lock:
            timer_count = len(self._deferred_threads)
            if timer_count > 0:
                log_debug(
                    f"[TokenDisplayService] Cancelling {timer_count} deferred timers"
                )

            for timer in self._deferred_threads:
                try:
                    timer.cancel()
                except Exception:
                    pass
            self._deferred_threads.clear()

    def cleanup_stale_entries(self, valid_paths: set):
        """Xoa cac cache entries khong con ton tai trong tree."""
        with self._lock:
            stale_keys = [k for k in self._cache.keys() if k not in valid_paths]
            for key in stale_keys:
                del self._cache[key]

    def get_token_count(self, path: str) -> Optional[int]:
        """Lay token count tu cache. Returns None neu chua duoc tinh."""
        with self._lock:
            return self._cache.get(path)

    def get_token_display(self, path: str) -> str:
        """Lay string hien thi token count. Returns empty string neu chua co."""
        with self._lock:
            count = self._cache.get(path)
            if count is None:
                if path in self._loading_paths:
                    return "..."
                return ""
            return self._format_tokens(count)

    def is_loading(self, path: str) -> bool:
        """Check xem path dang duoc load khong."""
        return path in self._loading_paths

    def request_token_count(self, path: str):
        """
        Request tinh token count cho file - prevent duplicate requests.

        Sau khi tinh xong, se emit cache_updated signal de UI tu refresh.
        """
        with self._update_lock:
            if path in self._cache or path in self._pending_updates:
                return
            self._pending_updates.add(path)

        # Chi tinh cho files
        if Path(path).is_dir():
            with self._update_lock:
                self._pending_updates.discard(path)
            return

        # Check cancellation
        if not is_counting_tokens():
            with self._update_lock:
                self._pending_updates.discard(path)
            return

        try:
            tokens = get_tokenization_service().count_tokens_for_file(Path(path))
            with self._lock:
                self._cache[path] = tokens
            with self._update_lock:
                self._pending_updates.discard(path)

            # Invalidate folder cache vi file token da thay doi
            self.invalidate_folder_cache(path)

            # Emit signal de UI tu update (thread-safe qua Qt signal mechanism)
            if not self._is_disposed:
                from core.utils.qt_utils import run_on_main_thread

                run_on_main_thread(
                    lambda: self.cache_updated.emit() if not self._is_disposed else None
                )

        except Exception as e:
            from core.logging_config import log_debug

            log_debug(f"[TokenDisplayService] Failed to count tokens for {path}: {e}")
            with self._lock:
                self._cache[path] = 0
            with self._update_lock:
                self._pending_updates.discard(path)

    def request_tokens_for_tree(
        self,
        tree: TreeItem,
        visible_only: bool = True,
        visible_paths: Optional[set] = None,
        max_immediate: int = 30,
    ):
        """
        Request token counts cho toan bo tree.

        Toi uu:
        - Prioritize small files for immediate counting
        - Large files deferred to background
        - Selected/visible files get priority

        Args:
            tree: Root TreeItem
            visible_only: Chi count visible files
            visible_paths: Set paths dang visible
            max_immediate: So files count ngay (default 30)
        """
        # Bat dau token counting (set flag = True)
        start_token_counting()

        # Check if disposed hoac co van de
        if self._is_disposed:
            return

        # Collect all files
        files_to_count: List[str] = []
        self._collect_files_to_count(tree, visible_only, visible_paths, files_to_count)

        if not is_counting_tokens():
            return

        # Smart prioritization: sort by file size (small first)
        def get_file_priority(path: str) -> tuple:
            """Return (priority_score, path) for sorting."""
            try:
                size = Path(path).stat().st_size
                # Small files first, then by path for consistency
                return (0 if size < self.SMALL_FILE_THRESHOLD else 1, size, path)
            except OSError:
                return (2, 0, path)  # Errors last

        # Sort files by priority
        files_to_count.sort(key=get_file_priority)

        # Split based on size-aware threshold
        immediate_files: List[str] = []
        deferred_files: List[str] = []

        for path in files_to_count:
            if len(immediate_files) >= max_immediate:
                deferred_files.append(path)
            else:
                try:
                    size = Path(path).stat().st_size
                    if (
                        size < self.LARGE_FILE_THRESHOLD
                        and len(immediate_files) < max_immediate
                    ):
                        immediate_files.append(path)
                    else:
                        deferred_files.append(path)
                except OSError:
                    deferred_files.append(path)

        # Count immediate files PARALLEL - su dung ThreadPoolExecutor + mmap
        # AN TOAN: count_tokens_batch_parallel() da xu ly race condition
        if immediate_files and is_counting_tokens():
            from core.logging_config import log_info

            # PERFORMANCE TRACKING
            start_time = time.perf_counter()
            log_info(
                f"[TokenCounter] START counting {len(immediate_files)} files (parallel)"
            )

            # Convert to Path list
            immediate_paths = [Path(p) for p in immediate_files]

            # Parallel counting - nhanh hon 3-4x
            service = get_tokenization_service()
            results = service.count_tokens_batch_parallel(
                immediate_paths, max_workers=4
            )

            # PERFORMANCE TRACKING
            elapsed = time.perf_counter() - start_time
            total_tokens = sum(results.values()) if results else 0
            log_info(
                f"[TokenCounter] COMPLETE: {len(results)} files, {total_tokens:,} tokens in {elapsed:.3f}s ({len(results) / elapsed:.1f} files/sec)"
            )

            # Update cache MOT LAN (batch update, khong lock tung file)
            if results and is_counting_tokens():
                with self._lock:
                    self._cache.update(results)

                # Emit signal de UI refresh (thread-safe qua Qt queued connection)
                if not self._is_disposed:
                    self.cache_updated.emit()

        # Schedule deferred files counting if any and not cancelled
        if deferred_files and is_counting_tokens():
            self._schedule_deferred_counting(deferred_files)

    def _schedule_deferred_counting(self, files: list):
        """
        Schedule counting cho deferred files.

        Count tung batch nho voi delay de khong block UI.

        FOLDER SWITCH FIX: Track all timers de cancel khi switch folder.
        Su dung threading.Timer thay vi SafeTimer de giam phu thuoc vao UI.
        """
        from core.logging_config import log_debug

        # Early exit checks
        if not files:
            return
        if not is_counting_tokens():
            log_debug(
                "[TokenDisplayService] _schedule_deferred_counting skipped - not counting"
            )
            return
        if self._is_disposed:
            log_debug(
                "[TokenDisplayService] _schedule_deferred_counting skipped - disposed"
            )
            return

        # PERFORMANCE: Batch size va delay cho project lon (700+ files)
        BATCH_SIZE = 100  # Giam so lan schedule
        BATCH_DELAY = 0.5  # 500ms between batches

        def count_batch(batch_files):
            """Dem tokens cho mot batch files."""
            from core.logging_config import log_debug

            # Check cancellation FIRST
            if not is_counting_tokens() or self._is_disposed:
                log_debug("[TokenDisplayService] count_batch cancelled at start")
                return

            for path in batch_files:
                if not is_counting_tokens() or self._is_disposed:
                    log_debug("[TokenDisplayService] count_batch cancelled mid-batch")
                    return

                with self._lock:
                    if path in self._cache:
                        continue

                try:
                    tokens = get_tokenization_service().count_tokens_for_file(
                        Path(path)
                    )
                    with self._lock:
                        self._cache[path] = tokens
                except Exception as e:
                    from core.logging_config import log_debug

                    log_debug(
                        f"[TokenDisplayService] Deferred count failed for {path}: {e}"
                    )
                    with self._lock:
                        self._cache[path] = 0

            # Emit signal sau khi batch hoan thanh
            if not self._is_disposed and is_counting_tokens():
                self.cache_updated.emit()

        # Clear old deferred timers before scheduling new ones
        self._cancel_all_deferred_timers()

        # Check cancellation again after clearing
        if not is_counting_tokens() or self._is_disposed:
            return

        # Process in batches - check cancellation before each batch
        for i in range(0, len(files), BATCH_SIZE):
            if not is_counting_tokens() or self._is_disposed:
                log_debug(
                    f"[TokenDisplayService] batch scheduling cancelled at batch {i}"
                )
                return

            batch = files[i : i + BATCH_SIZE]
            delay = BATCH_DELAY * (i // BATCH_SIZE + 1)

            # Su dung threading.Timer thay vi SafeTimer de giam phu thuoc vao UI page
            def create_batch_callback(batch_data):
                """Tao closure cho moi batch de tranh late binding bug."""
                return lambda: count_batch(batch_data)

            timer = threading.Timer(delay, create_batch_callback(batch))
            timer.daemon = True  # Daemon thread - tu dong ket thuc khi app dong

            # Track timer de cancel later
            with self._deferred_threads_lock:
                if self._is_disposed:
                    timer.cancel()
                    return
                self._deferred_threads.append(timer)

            timer.start()

    def _collect_files_to_count(
        self,
        item: TreeItem,
        visible_only: bool,
        visible_paths: Optional[set],
        result: list,
    ):
        """Recursive collect files can tinh token."""
        if not is_counting_tokens():
            return

        # Skip neu visible_only va item khong visible
        if visible_only and visible_paths and item.path not in visible_paths:
            return

        if not item.is_dir:
            # La file - add to list
            with self._lock:
                cached = item.path in self._cache

            if not cached:
                result.append(item.path)
        else:
            # La folder - recurse vao children
            for child in item.children:
                if not is_counting_tokens():
                    break
                self._collect_files_to_count(child, visible_only, visible_paths, result)

    def _cleanup_cache_if_needed(self):
        """Remove oldest cache entries neu cache qua lon."""
        with self._lock:
            if len(self._cache) > self.MAX_CACHE_SIZE:
                remove_count = len(self._cache) // 5
                keys_to_remove = list(self._cache.keys())[:remove_count]
                for key in keys_to_remove:
                    del self._cache[key]

    def get_folder_tokens(self, folder_path: str, tree: TreeItem) -> Optional[int]:
        """
        Tinh tong tokens cua folder tu cache.

        Return partial sum ngay ca khi chua cache het de hien thi cho user.
        """
        folder_item = self._find_item_by_path(tree, folder_path)
        if not folder_item:
            return None

        total = 0
        file_paths = self._get_all_file_paths(folder_item)

        if not file_paths:
            return None

        with self._lock:
            for file_path in file_paths:
                if file_path in self._cache:
                    total += self._cache[file_path]

        return total if total > 0 else None

    def get_folder_tokens_status(
        self, folder_path: str, tree: TreeItem
    ) -> tuple[int, bool]:
        """
        Lay token count va status complete cua folder.

        OPTIMIZED: Su dung folder cache de tranh tinh toan lai.
        Cache duoc invalidate khi file cache thay doi.

        Returns:
            Tuple (total_tokens, is_complete)
            - total_tokens: Tong so tokens da cache (co the la partial)
            - is_complete: True neu tat ca files trong folder da duoc cache
        """
        # Check folder cache first
        with self._folder_cache_lock:
            if folder_path in self._folder_cache:
                total, is_complete, _ = self._folder_cache[folder_path]
                # Move to end for LRU (most recently used)
                self._folder_cache.move_to_end(folder_path)
                return (total, is_complete)

        # Cache miss - calculate
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

        # Cache the result (with eviction if over limit)
        with self._folder_cache_lock:
            if len(self._folder_cache) >= self._MAX_FOLDER_CACHE_SIZE:
                # Evict oldest 25% of entries
                evict_count = self._MAX_FOLDER_CACHE_SIZE // 4
                keys_to_evict = list(self._folder_cache.keys())[:evict_count]
                for k in keys_to_evict:
                    del self._folder_cache[k]

            self._folder_cache[folder_path] = (total, all_cached, len(file_paths))

        return (total, all_cached)

    def invalidate_folder_cache(self, file_path: str):
        """
        Invalidate folder cache khi mot file duoc update.

        Xoa cache cua tat ca folders chua file nay.

        Args:
            file_path: Path cua file vua duoc update
        """
        with self._folder_cache_lock:
            folders_to_remove = []
            for folder_path in self._folder_cache:
                if file_path.startswith(folder_path + "/") or file_path.startswith(
                    folder_path + "\\"
                ):
                    folders_to_remove.append(folder_path)

            for folder in folders_to_remove:
                del self._folder_cache[folder]

    def _get_all_file_paths(self, item: TreeItem) -> list:
        """Lay tat ca file paths trong item."""
        paths = []
        if not item.is_dir:
            paths.append(item.path)
        for child in item.children:
            paths.extend(self._get_all_file_paths(child))
        return paths

    def _find_item_by_path(
        self, item: TreeItem, target_path: str
    ) -> Optional[TreeItem]:
        """Tim TreeItem theo path."""
        if item.path == target_path:
            return item
        for child in item.children:
            found = self._find_item_by_path(child, target_path)
            if found:
                return found
        return None

    @staticmethod
    def _format_tokens(count: int) -> str:
        """Format token count cho display."""
        if count < 1000:
            return str(count)
        elif count < 10000:
            return f"{count / 1000:.1f}k"
        else:
            return f"{count // 1000}k"
