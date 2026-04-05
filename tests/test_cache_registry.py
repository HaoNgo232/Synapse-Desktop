"""
Tests cho CacheRegistry, ICacheable protocol, va cache adapters.

Verify:
1. ICacheable protocol enforcement
2. CacheRegistry register/unregister/invalidate
3. Cache adapters implement ICacheable correctly
4. invalidate_for_path va invalidate_for_workspace
5. Error isolation between caches
"""

import pytest
from unittest.mock import patch

from infrastructure.adapters.cache_protocol import ICacheable
from infrastructure.adapters.cache_registry import CacheRegistry, cache_registry
from infrastructure.adapters.cache_adapters import (
    TokenCacheAdapter,
    SecurityCacheAdapter,
    IgnoreCacheAdapter,
    RelationshipCacheAdapter,
    register_all_caches,
)


# ============================================================
# Helpers
# ============================================================


class FakeCache:
    """Fake cache implementing ICacheable for testing."""

    def __init__(self) -> None:
        self.invalidated_paths: list[str] = []
        self.all_invalidated: bool = False
        self._size: int = 10

    def invalidate_path(self, path: str) -> None:
        self.invalidated_paths.append(path)

    def invalidate_all(self) -> None:
        self.all_invalidated = True
        self.invalidated_paths.clear()

    def size(self) -> int:
        return self._size


class BrokenCache:
    """Cache that raises on every operation — for error isolation testing."""

    def invalidate_path(self, path: str) -> None:
        raise RuntimeError("boom")

    def invalidate_all(self) -> None:
        raise RuntimeError("boom")

    def size(self) -> int:
        raise RuntimeError("boom")


# ============================================================
# ICacheable Protocol Tests
# ============================================================


class TestICacheableProtocol:
    """Verify ICacheable structural subtyping."""

    def test_fake_cache_is_cacheable(self):
        """FakeCache hop le voi ICacheable protocol."""
        assert isinstance(FakeCache(), ICacheable)

    def test_broken_cache_is_cacheable(self):
        """BrokenCache cung hop le (miễn co dung methods)."""
        assert isinstance(BrokenCache(), ICacheable)

    def test_non_cacheable_rejected(self):
        """Object khong co dung methods thi khong hop le."""
        assert not isinstance(object(), ICacheable)
        assert not isinstance("string", ICacheable)


# ============================================================
# CacheRegistry Tests
# ============================================================


class TestCacheRegistry:
    """Test CacheRegistry core functionality."""

    def setup_method(self):
        """Tao registry moi cho moi test."""
        self.registry = CacheRegistry()

    def test_register_and_list(self):
        """Register cache va verify no duoc listed."""
        cache = FakeCache()
        self.registry.register("test", cache)
        assert "test" in self.registry.get_registered_names()

    def test_unregister(self):
        """Unregister cache da dang ky."""
        self.registry.register("test", FakeCache())
        self.registry.unregister("test")
        assert "test" not in self.registry.get_registered_names()

    def test_unregister_nonexistent(self):
        """Unregister cache khong ton tai khong loi."""
        self.registry.unregister("nonexistent")  # No error

    def test_invalidate_for_path(self):
        """invalidate_for_path goi invalidate_path tren tat ca caches."""
        c1, c2 = FakeCache(), FakeCache()
        self.registry.register("c1", c1)
        self.registry.register("c2", c2)

        self.registry.invalidate_for_path("/some/file.py")

        assert "/some/file.py" in c1.invalidated_paths
        assert "/some/file.py" in c2.invalidated_paths

    def test_invalidate_for_workspace(self):
        """invalidate_for_workspace goi invalidate_all tren tat ca caches."""
        c1, c2 = FakeCache(), FakeCache()
        self.registry.register("c1", c1)
        self.registry.register("c2", c2)

        self.registry.invalidate_for_workspace()

        assert c1.all_invalidated
        assert c2.all_invalidated

    def test_error_isolation_path(self):
        """1 cache loi khong anh huong cache khac khi invalidate_for_path."""
        broken = BrokenCache()
        good = FakeCache()
        self.registry.register("broken", broken)
        self.registry.register("good", good)

        self.registry.invalidate_for_path("/test.py")

        assert "/test.py" in good.invalidated_paths

    def test_error_isolation_workspace(self):
        """1 cache loi khong anh huong cache khac khi invalidate_for_workspace."""
        broken = BrokenCache()
        good = FakeCache()
        self.registry.register("broken", broken)
        self.registry.register("good", good)

        self.registry.invalidate_for_workspace()

        assert good.all_invalidated

    def test_get_stats(self):
        """get_stats tra ve size cua tung cache."""
        c1 = FakeCache()
        c1._size = 42
        c2 = FakeCache()
        c2._size = 7
        self.registry.register("c1", c1)
        self.registry.register("c2", c2)

        stats = self.registry.get_stats()
        assert stats["c1"] == 42
        assert stats["c2"] == 7

    def test_get_stats_error_returns_negative_one(self):
        """get_stats tra ve -1 cho cache bi loi."""
        self.registry.register("broken", BrokenCache())
        stats = self.registry.get_stats()
        assert stats["broken"] == -1

    def test_reset_for_testing(self):
        """_reset_for_testing xoa tat ca registrations."""
        self.registry.register("test", FakeCache())
        self.registry._reset_for_testing()
        assert len(self.registry.get_registered_names()) == 0


# ============================================================
# Cache Adapter Tests
# ============================================================


class TestTokenCacheAdapter:
    """Test TokenCacheAdapter wraps TokenizationService cache correctly."""

    def _make_adapter(self):
        """Helper tao adapter voi TokenizationService fresh."""
        from application.services.tokenization_service import TokenizationService

        return TokenCacheAdapter(TokenizationService())

    def test_implements_protocol(self):
        adapter = self._make_adapter()
        assert isinstance(adapter, ICacheable)

    def test_invalidate_path_clears_file(self, tmp_path):
        """invalidate_path goi clear_file_from_cache tren service."""
        from unittest.mock import patch
        from application.services.tokenization_service import TokenizationService

        svc = TokenizationService()
        adapter = TokenCacheAdapter(svc)
        with patch.object(svc, "clear_file_from_cache") as mock:
            adapter.invalidate_path("/test/file.py")
            mock.assert_called_once_with("/test/file.py")

    def test_invalidate_all_calls_clear(self):
        """invalidate_all goi clear_cache tren service."""
        from unittest.mock import patch
        from application.services.tokenization_service import TokenizationService

        svc = TokenizationService()
        adapter = TokenCacheAdapter(svc)
        with patch.object(svc, "clear_cache") as mock:
            adapter.invalidate_all()
            mock.assert_called_once()

    def test_size_returns_int(self):
        """size() tra ve int."""
        adapter = self._make_adapter()
        result = adapter.size()
        assert isinstance(result, int)


class TestSecurityCacheAdapter:
    """Test SecurityCacheAdapter wraps security cache correctly."""

    def test_implements_protocol(self):
        assert isinstance(SecurityCacheAdapter(), ICacheable)

    @patch("infrastructure.adapters.security_check.invalidate_security_cache")
    def test_invalidate_path(self, mock_invalidate):
        SecurityCacheAdapter().invalidate_path("/test.py")
        mock_invalidate.assert_called_once_with("/test.py")

    @patch("infrastructure.adapters.security_check.clear_security_cache")
    def test_invalidate_all(self, mock_clear):
        SecurityCacheAdapter().invalidate_all()
        mock_clear.assert_called_once()


class TestIgnoreCacheAdapter:
    """Test IgnoreCacheAdapter wraps ignore engine caches."""

    def _make_adapter(self):
        from domain.filesystem.ignore_engine import IgnoreEngine

        return IgnoreCacheAdapter(IgnoreEngine())

    def test_implements_protocol(self):
        assert isinstance(self._make_adapter(), ICacheable)

    def test_invalidate_path_gitignore_triggers_clear(self):
        from domain.filesystem.ignore_engine import IgnoreEngine

        engine = IgnoreEngine()
        adapter = IgnoreCacheAdapter(engine)
        # Ghi fake data vao cache truoc
        engine._gitignore_cache["dummy"] = (0.0, [])
        adapter.invalidate_path("/project/.gitignore")
        # Sau invalidate cache phai trong
        assert len(engine._gitignore_cache) == 0

    def test_invalidate_path_normal_file_no_clear(self):
        from domain.filesystem.ignore_engine import IgnoreEngine

        engine = IgnoreEngine()
        engine._gitignore_cache["dummy"] = (0.0, [])
        adapter = IgnoreCacheAdapter(engine)
        adapter.invalidate_path("/project/src/main.py")
        # Normal file: cache khong bi clear
        assert len(engine._gitignore_cache) == 1

    def test_invalidate_all(self):
        from domain.filesystem.ignore_engine import IgnoreEngine

        engine = IgnoreEngine()
        engine._gitignore_cache["dummy"] = (0.0, [])
        adapter = IgnoreCacheAdapter(engine)
        adapter.invalidate_all()
        assert len(engine._gitignore_cache) == 0


class TestRelationshipCacheAdapter:
    """Test RelationshipCacheAdapter wraps parser cache."""

    def test_implements_protocol(self):
        assert isinstance(RelationshipCacheAdapter(), ICacheable)


# ============================================================
# Integration: register_all_caches
# ============================================================


class TestRegisterAllCaches:
    """Test register_all_caches dang ky tat ca adapters."""

    def setup_method(self):
        cache_registry._reset_for_testing()

    def teardown_method(self):
        cache_registry._reset_for_testing()

    def test_registers_all_four_caches(self):
        from domain.filesystem.ignore_engine import IgnoreEngine
        from application.services.tokenization_service import TokenizationService

        register_all_caches(
            ignore_engine=IgnoreEngine(),
            tokenization_service=TokenizationService(),
        )
        names = cache_registry.get_registered_names()
        assert "token_cache" in names
        assert "security_cache" in names
        assert "ignore_cache" in names
        assert "relationship_cache" in names

    def test_idempotent(self):
        from domain.filesystem.ignore_engine import IgnoreEngine
        from application.services.tokenization_service import TokenizationService

        kwargs = dict(
            ignore_engine=IgnoreEngine(),
            tokenization_service=TokenizationService(),
        )
        register_all_caches(**kwargs)
        register_all_caches(**kwargs)  # Goi lai khong loi
        assert len(cache_registry.get_registered_names()) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
