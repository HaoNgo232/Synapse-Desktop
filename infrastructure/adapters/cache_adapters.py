"""
Cache Adapters - Wrap existing caches to implement ICacheable protocol.

Moi adapter wrap mot cache module cu the (TokenCache, security cache, etc.)
de CacheRegistry co the invalidate tat ca mot cach thong nhat.

Adapters duoc tu dong register vao cache_registry khi module nay duoc import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.filesystem.ignore_engine import IgnoreEngine
    from application.interfaces.tokenization_port import ITokenizationService

from infrastructure.adapters.cache_registry import cache_registry


class TokenCacheAdapter:
    """
    Adapter cho TokenizationService cache.

    Nhan ITokenizationService qua dependency injection thay vi dung singleton.
    Goi clear_cache() / clear_file_from_cache() tren instance.
    """

    def __init__(self, tokenization_service: "ITokenizationService") -> None:
        self._service = tokenization_service

    def invalidate_path(self, path: str) -> None:
        """Xoa token count cho file cu the."""
        self._service.clear_file_from_cache(path)

    def invalidate_all(self) -> None:
        """Xoa toan bo token cache."""
        self._service.clear_cache()

    def size(self) -> int:
        """Tra ve so entries hien co (dung internal cache neu co)."""
        svc = self._service
        if hasattr(svc, "_cache"):
            return len(svc._cache)
        return 0


class SecurityCacheAdapter:
    """Adapter cho core.security_check._security_scan_cache."""

    def invalidate_path(self, path: str) -> None:
        """Xoa security scan result cho file cu the."""
        from infrastructure.adapters.security_check import invalidate_security_cache

        invalidate_security_cache(path)

    def invalidate_all(self) -> None:
        """Xoa toan bo security scan cache."""
        from infrastructure.adapters.security_check import clear_security_cache

        clear_security_cache()

    def size(self) -> int:
        """Tra ve so entries hien co."""
        from infrastructure.adapters.security_check import get_security_cache_stats

        stats = get_security_cache_stats()
        return stats.get("size", 0) if isinstance(stats, dict) else 0


class IgnoreCacheAdapter:
    """Adapter cho core.ignore_engine (IgnoreEngine instance tu ServiceContainer)."""

    def __init__(self, ignore_engine: "IgnoreEngine") -> None:
        from domain.filesystem.ignore_engine import (
            IgnoreEngine as _IgnoreEngine,
        )

        self._engine: _IgnoreEngine = ignore_engine

    def invalidate_path(self, path: str) -> None:
        """
        Invalidate ignore cache khi .gitignore thay doi.

        Chi clear toan bo cache vi gitignore anh huong global,
        khong the invalidate tung file rieng le.
        """
        if ".gitignore" in path or ".git/info/exclude" in path:
            self._engine.clear_cache()

    def invalidate_all(self) -> None:
        """Xoa toan bo ignore cache."""
        self._engine.clear_cache()

    def size(self) -> int:
        """Tra ve tong so entries cua ca 2 caches."""
        return len(self._engine._gitignore_cache) + len(self._engine._pathspec_cache)


class RelationshipCacheAdapter:
    """
    Adapter cho core.smart_context.parser._RELATIONSHIPS_CACHE.

    Performance optimization: Chi invalidate khi source code files thay doi,
    bo qua text/config files de giam cache churn. Tim va xoa chi nhung entry
    thuoc ve file do thong qua prefix `{file_path}:`.
    """

    # Code extensions that affect relationships
    _CODE_EXTENSIONS = frozenset(
        {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".cs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
        }
    )

    def invalidate_path(self, path: str) -> None:
        """
        Xoa cache entries cua file tuong ung khi thay doi.

        Non-code files (txt, md, json, yaml) are ignored to reduce cache churn.
        """
        from pathlib import Path as _Path

        # Skip non-code files
        if _Path(path).suffix.lower() not in self._CODE_EXTENSIONS:
            return

        from domain.smart_context.parser import _RELATIONSHIPS_CACHE

        keys_to_remove = [
            k for k in _RELATIONSHIPS_CACHE.keys() if k.startswith(f"{path}:")
        ]
        for k in keys_to_remove:
            _RELATIONSHIPS_CACHE.pop(k, None)

    def invalidate_all(self) -> None:
        """Xoa toan bo relationship cache."""
        from domain.smart_context.parser import _RELATIONSHIPS_CACHE

        _RELATIONSHIPS_CACHE.clear()

    def size(self) -> int:
        """Tra ve so entries hien co."""
        from domain.smart_context.parser import _RELATIONSHIPS_CACHE

        return len(_RELATIONSHIPS_CACHE)


def register_all_caches(
    ignore_engine: "IgnoreEngine",
    tokenization_service: "ITokenizationService",
) -> None:
    """
    Dang ky tat ca cache adapters vao CacheRegistry.

    Goi ham nay 1 lan tai thoi diem app khoi dong.
    An toan khi goi nhieu lan (overwrite registrations cu).

    Args:
        ignore_engine: IgnoreEngine instance tu ServiceContainer.
        tokenization_service: ITokenizationService instance tu ServiceContainer.
    """
    cache_registry.register("token_cache", TokenCacheAdapter(tokenization_service))
    cache_registry.register("security_cache", SecurityCacheAdapter())
    cache_registry.register("ignore_cache", IgnoreCacheAdapter(ignore_engine))
    cache_registry.register("relationship_cache", RelationshipCacheAdapter())
