"""
Token Display Service - Quan ly va cache token counts cho files

Tach ra theo SOLID:
- Single Responsibility: Chi xu ly token counting va caching
- Open/Closed: De dang extend them caching strategies
- Interface Segregation: Chi expose methods can thiet
"""

from pathlib import Path
from typing import Dict, Optional, Callable, Set
from dataclasses import dataclass
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from core.token_counter import count_tokens_for_file
from core.file_utils import TreeItem


@dataclass
class TokenInfo:
    """Thong tin token cua file/folder"""

    tokens: int
    is_cached: bool = False
    is_loading: bool = False


class TokenDisplayService:
    """
    Service quan ly token display cho file tree.

    Features:
    - Cache token counts de tranh tinh toan lai
    - Background loading de khong block UI (với ThreadPoolExecutor)
    - Aggregate tokens cho folders
    - Auto cleanup stale cache entries
    """

    # Config - optimized for performance
    BATCH_SIZE = 50  # Process 50 files per batch (increased from 20)
    MAX_WORKERS = 6  # Thread pool size (increased from 4)
    MAX_CACHE_SIZE = 10000  # Maximum cache entries (increased from 5000)
    UPDATE_THROTTLE_MS = 100  # Minimum time between UI updates

    def __init__(self, on_update: Optional[Callable[[], None]] = None):
        """
        Args:
            on_update: Callback khi token cache duoc update (de refresh UI)
        """
        self.on_update = on_update

        # Cache: path -> token count
        self._cache: Dict[str, int] = {}

        # Tracking loading state
        self._loading_paths: Set[str] = set()

        # Background loading queue
        self._pending_paths: list = []
        self._is_processing = False

        # Thread safety lock
        self._lock = Lock()

        # Thread pool for parallel processing
        self._executor: Optional[ThreadPoolExecutor] = None
        
        # Throttling for UI updates
        self._last_update_time: float = 0

    def clear_cache(self):
        """Xoa toan bo cache (khi reload tree)"""
        with self._lock:
            self._cache.clear()
            self._loading_paths.clear()
            self._pending_paths.clear()
            # Signal background thread to stop immediately
            self._is_processing = False
            # Clear any remaining items to prevent stale processing
            self._pending_paths = []

    def stop(self):
        """Stop background processing gracefully"""
        with self._lock:
            self._is_processing = False
            self._pending_paths.clear()

        # Shutdown executor if exists
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

    def cleanup_stale_entries(self, valid_paths: set):
        """
        Xóa các cache entries không còn tồn tại trong tree.

        Args:
            valid_paths: Set các paths hiện tại trong tree
        """
        with self._lock:
            stale_keys = [k for k in self._cache.keys() if k not in valid_paths]
            for key in stale_keys:
                del self._cache[key]

    def get_token_count(self, path: str) -> Optional[int]:
        """
        Lay token count tu cache.
        Returns None neu chua duoc tinh.
        """
        with self._lock:
            return self._cache.get(path)

    def get_token_display(self, path: str) -> str:
        """
        Lay string hien thi token count.
        Returns empty string neu chua co.
        """
        count = self._cache.get(path)
        if count is None:
            if path in self._loading_paths:
                return "..."
            return ""
        return self._format_tokens(count)

    def is_loading(self, path: str) -> bool:
        """Check xem path dang duoc load khong"""
        with self._lock:
            return path in self._loading_paths

    def request_token_count(self, path: str):
        """
        Request tinh token count cho file (async).
        Neu da co trong cache thi khong lam gi.
        """
        if path in self._cache or path in self._loading_paths:
            return

        # Chi tinh cho files, khong tinh cho folders
        if Path(path).is_dir():
            return

        with self._lock:
            if path in self._cache or path in self._loading_paths:
                return

            self._pending_paths.append(path)
            self._loading_paths.add(path)

            # Start background processing neu chua chay
            if not self._is_processing:
                self._start_background_processing()

    def request_tokens_for_tree(
        self,
        tree: TreeItem,
        visible_only: bool = True,
        visible_paths: Optional[set] = None,
    ):
        """
        Request token counts cho toan bo tree.

        Args:
            tree: Root TreeItem
            visible_only: Chi tinh cho files dang hien thi
            visible_paths: Set cac paths dang hien thi (neu visible_only=True)
        """
        self._collect_files_to_count(tree, visible_only, visible_paths)

        with self._lock:
            if self._pending_paths and not self._is_processing:
                self._start_background_processing()

    def _collect_files_to_count(
        self, item: TreeItem, visible_only: bool, visible_paths: Optional[set]
    ):
        """Recursive collect files can tinh token"""
        # Skip neu visible_only va item khong visible
        if visible_only and visible_paths and item.path not in visible_paths:
            return

        if not item.is_dir:
            # La file - request token count
            with self._lock:
                if (
                    item.path not in self._cache
                    and item.path not in self._loading_paths
                ):
                    self._pending_paths.append(item.path)
                    self._loading_paths.add(item.path)
        else:
            # La folder - recurse vao children
            for child in item.children:
                self._collect_files_to_count(child, visible_only, visible_paths)

    def _start_background_processing(self):
        """Start background thread de tinh tokens"""
        self._is_processing = True
        thread = Thread(target=self._process_pending, daemon=True)
        thread.start()

    def _process_pending(self):
        """Process pending paths trong background với batch processing và ThreadPoolExecutor"""
        # Initialize executor if needed
        if not self._executor:
            self._executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)

        while True:
            # Get batch of paths to process
            batch: list = []
            with self._lock:
                if not self._pending_paths:
                    self._is_processing = False
                    break

                # Take up to BATCH_SIZE items
                batch_size = min(self.BATCH_SIZE, len(self._pending_paths))
                batch = self._pending_paths[:batch_size]
                self._pending_paths = self._pending_paths[batch_size:]

            if not batch:
                break

            # Process batch in parallel
            try:
                futures = {
                    self._executor.submit(self._count_file_tokens, path): path
                    for path in batch
                }

                for future in as_completed(futures, timeout=30):
                    path = futures[future]
                    try:
                        tokens = future.result()
                        with self._lock:
                            self._cache[path] = tokens
                            self._loading_paths.discard(path)
                    except Exception:
                        with self._lock:
                            self._cache[path] = 0
                            self._loading_paths.discard(path)

            except Exception:
                # Timeout or other error - mark all as 0
                with self._lock:
                    for path in batch:
                        if path not in self._cache:
                            self._cache[path] = 0
                        self._loading_paths.discard(path)

            # Notify UI after each batch (throttled)
            current_time = time.time() * 1000  # ms
            if self.on_update and (current_time - self._last_update_time) >= self.UPDATE_THROTTLE_MS:
                try:
                    self.on_update()
                    self._last_update_time = current_time
                except Exception:
                    pass

            # Small delay between batches
            time.sleep(0.005)  # Reduced from 0.01 for faster processing

            # Cleanup cache if too large
            self._cleanup_cache_if_needed()

        # Final update
        if self.on_update:
            try:
                self.on_update()
            except Exception:
                pass

    def _count_file_tokens(self, path: str) -> int:
        """Count tokens for a single file (called from thread pool)"""
        try:
            return count_tokens_for_file(Path(path))
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

    def get_folder_tokens(self, folder_path: str, tree: TreeItem) -> Optional[int]:
        """
        Tinh tong tokens cua folder tu cache.
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
    def _format_tokens(count: int) -> str:
        """Format token count cho display"""
        if count < 1000:
            return str(count)
        elif count < 10000:
            return f"{count / 1000:.1f}k"
        else:
            return f"{count // 1000}k"
