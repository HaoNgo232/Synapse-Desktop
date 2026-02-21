"""
CacheRegistry - Diem trung tam de invalidate tat ca caches trong ung dung.

Thay vi moi module tu goi invalidate tung cache rieng le,
CacheRegistry cung cap mot API duy nhat:
- invalidate_for_path(path): Goi khi file thay doi
- invalidate_for_workspace(): Goi khi workspace thay doi
- get_stats(): Lay thong ke cache cho monitoring

Su dung:
    from services.cache_registry import cache_registry
    cache_registry.register("token_cache", token_cache_adapter)
    cache_registry.invalidate_for_path("/path/to/changed_file.py")
"""

import logging
import threading

from services.cache_protocol import ICacheable

logger = logging.getLogger(__name__)


class CacheRegistry:
    """
    Registry trung tam cho tat ca caches.

    Thread-safe. Su dung module-level singleton pattern voi
    _reset_for_testing() helper de ho tro unit tests.
    """

    def __init__(self) -> None:
        self._caches: dict[str, ICacheable] = {}
        self._lock = threading.Lock()

    def register(self, name: str, cache: ICacheable) -> None:
        """
        Dang ky mot cache de quan ly.

        Args:
            name: Ten dinh danh cho cache (vd: "token_cache")
            cache: Instance implement ICacheable protocol
        """
        with self._lock:
            self._caches[name] = cache

    def unregister(self, name: str) -> None:
        """
        Huy dang ky cache.

        Args:
            name: Ten cache can huy
        """
        with self._lock:
            self._caches.pop(name, None)

    def invalidate_for_path(self, path: str) -> None:
        """
        Invalidate tat ca caches cho mot file path cu the.

        Goi khi FileWatcher phat hien file thay doi hoac bi xoa.
        An toan: exceptions tu tung cache khong anh huong cac cache khac.

        Args:
            path: Duong dan tuyet doi cua file da thay doi
        """
        with self._lock:
            caches = list(self._caches.items())

        for name, cache in caches:
            try:
                cache.invalidate_path(path)
            except Exception as e:
                # Log loi de debug, nhung khong de 1 cache loi lam hong toan bo flow
                logger.warning(
                    "Failed to invalidate cache '%s' for path '%s': %s",
                    name,
                    path,
                    e,
                )

    def invalidate_for_workspace(self) -> None:
        """
        Xoa toan bo tat ca caches.

        Goi khi workspace thay doi hoac user reset settings.
        An toan: exceptions tu tung cache khong anh huong cac cache khac.
        """
        with self._lock:
            caches = list(self._caches.items())

        for name, cache in caches:
            try:
                cache.invalidate_all()
            except Exception as e:
                logger.warning(
                    "Failed to invalidate_all for cache '%s': %s",
                    name,
                    e,
                )

    def get_stats(self) -> dict[str, int]:
        """
        Tra ve thong ke so entries cua tung cache.

        Returns:
            Dict mapping cache_name -> so entries
        """
        with self._lock:
            caches = list(self._caches.items())

        stats: dict[str, int] = {}
        for name, cache in caches:
            try:
                stats[name] = cache.size()
            except Exception:
                stats[name] = -1
        return stats

    def get_registered_names(self) -> list[str]:
        """Tra ve danh sach ten cac cache da dang ky."""
        with self._lock:
            return list(self._caches.keys())

    def _reset_for_testing(self) -> None:
        """
        Xoa tat ca registrations. CHI SU DUNG TRONG TESTS.

        Helper cho unit tests de reset state giua cac test cases.
        """
        with self._lock:
            self._caches.clear()


# Module-level singleton instance
cache_registry = CacheRegistry()
