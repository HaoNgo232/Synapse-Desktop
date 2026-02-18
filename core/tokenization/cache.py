"""
Token cache voi LRU eviction va mtime-based invalidation.

Thread-safe OrderedDict cache:
- Key: file path string
- Value: (mtime, token_count)
- Eviction: Khi dat MAX_CACHE_SIZE, xoa entries cu nhat (FIFO)
- Invalidation: Khi file thay doi (mtime khac), cache miss
"""

import threading
from collections import OrderedDict
from typing import Optional, Tuple

# Maximum so entries trong cache
MAX_CACHE_SIZE = 2000


class TokenCache:
    """
    LRU cache cho token counts, thread-safe.

    Su dung OrderedDict de track thu tu truy cap.
    Mtime-based invalidation: cache entry chi valid
    khi file khong bi thay doi ke tu lan cache cuoi.
    """

    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        """
        Khoi tao cache voi max size.

        Args:
            max_size: So luong entries toi da truoc khi evict
        """
        self._store: OrderedDict[str, Tuple[float, int]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size

    def get(self, path: str, mtime: float) -> Optional[int]:
        """
        Lay token count tu cache neu mtime khop.

        Thread-safe. Move entry to end (LRU).

        Args:
            path: File path string
            mtime: Modification time hien tai cua file

        Returns:
            Token count neu cache hit, None neu miss hoac stale
        """
        with self._lock:
            cached = self._store.get(path)
            if cached is not None:
                cached_mtime, cached_count = cached
                if cached_mtime == mtime:
                    # LRU: move to end
                    self._store.move_to_end(path)
                    return cached_count
            return None

    def get_no_move(self, path: str, mtime: float) -> Optional[int]:
        """
        Lay token count tu cache KHONG move (cho parallel workers).

        Tranh lock contention khi nhieu workers cung doc.

        Args:
            path: File path string
            mtime: Modification time hien tai

        Returns:
            Token count neu cache hit, None neu miss
        """
        with self._lock:
            cached = self._store.get(path)
            if cached is not None:
                cached_mtime, cached_count = cached
                if cached_mtime == mtime:
                    return cached_count
            return None

    def put(self, path: str, mtime: float, count: int) -> None:
        """
        Luu token count vao cache voi LRU eviction.

        Thread-safe. Tu dong evict entries cu khi dat max_size.

        Args:
            path: File path string
            mtime: Modification time cua file
            count: So luong tokens
        """
        with self._lock:
            # Evict oldest entries neu can
            while len(self._store) >= self._max_size:
                self._store.popitem(last=False)
            self._store[path] = (mtime, count)

    def put_batch(self, entries: dict[str, Tuple[float, int]]) -> None:
        """
        Luu nhieu entries cung luc (cho batch processing).

        Thread-safe. Giam lock contention so voi put() tung entry.

        Args:
            entries: Dict mapping path -> (mtime, count)
        """
        with self._lock:
            for path, (mtime, count) in entries.items():
                while len(self._store) >= self._max_size:
                    self._store.popitem(last=False)
                self._store[path] = (mtime, count)

    def clear(self) -> None:
        """Xoa toan bo cache. Thread-safe."""
        with self._lock:
            self._store.clear()

    def clear_file(self, path: str) -> None:
        """
        Xoa cache entry cho mot file cu the.

        Goi khi file watcher phat hien file thay doi.

        Args:
            path: File path can xoa
        """
        with self._lock:
            self._store.pop(path, None)

    def __len__(self) -> int:
        """Tra ve so luong entries trong cache."""
        with self._lock:
            return len(self._store)


# Singleton instance - dung chung boi counter.py va batch.py
token_cache = TokenCache()
