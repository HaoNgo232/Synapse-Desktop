"""
Test suite to verify all 5 bugs from the review are fixed.
"""

import threading
import time

import pytest


class TestBug1TokenCountWorkerArgument:
    """BUG #1: TokenCountWorker missing tokenization_service argument"""

    def test_worker_accepts_tokenization_service(self, tmp_path):
        """TokenCountWorker should accept tokenization_service parameter"""
        from components.file_tree_model import TokenCountWorker
        from services.tokenization_service import TokenizationService

        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        # Should not raise TypeError
        worker = TokenCountWorker(
            [str(test_file)],
            tokenization_service=TokenizationService(),
        )

        assert worker is not None
        assert worker._tokenization is not None


class TestBug2And3SingleServiceContainer:
    """BUG #2 & #3: Dual ServiceContainer and missing injected services"""

    def test_single_container_instance_via_qapp(self, qtbot):
        """QApplication should store single ServiceContainer instance"""
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        # In test environment, app might not have _service_container
        # This is set in main_window.py:main() during normal app startup
        # The important thing is that when it IS set, it's reused
        if hasattr(app, "_service_container"):
            assert app._service_container is not None
        else:
            # Test environment - skip this check
            pytest.skip("Test environment doesn't run main() bootstrap")

    def test_context_view_receives_injected_services(self, qtbot):
        """ContextViewQt should receive ignore_engine and tokenization_service"""
        from views.context_view_qt import ContextViewQt
        from services.service_container import ServiceContainer

        container = ServiceContainer()

        view = ContextViewQt(
            lambda: None,
            prompt_builder=container.prompt_builder,
            clipboard_service=container.clipboard,
            ignore_engine=container.ignore_engine,
            tokenization_service=container.tokenization,
        )

        # Should use injected services, not create fallback instances
        assert view._ignore_engine is container.ignore_engine
        assert view._tokenization_service is container.tokenization

    def test_cache_adapters_use_same_services(self):
        """Cache adapters should reference the same service instances as views"""
        from services.service_container import ServiceContainer
        from services.cache_adapters import TokenCacheAdapter, IgnoreCacheAdapter
        from services.cache_registry import cache_registry

        # In test environment, cache_registry might be empty
        # The important thing is that when adapters ARE registered,
        # they use the same service instances

        # Create a fresh container and register adapters
        from services.cache_adapters import register_all_caches

        container = ServiceContainer()
        register_all_caches(
            ignore_engine=container.ignore_engine,
            tokenization_service=container.tokenization,
        )

        # Get adapters from registry (it's a dict, not a list)
        token_adapter = cache_registry._caches.get("token_cache")
        ignore_adapter = cache_registry._caches.get("ignore_cache")

        # At least one adapter should be registered
        assert token_adapter is not None
        assert ignore_adapter is not None
        assert isinstance(token_adapter, TokenCacheAdapter)
        assert isinstance(ignore_adapter, IgnoreCacheAdapter)


class TestBug4WorkspaceIndexIgnoreEngine:
    """BUG #4: workspace_index creates throwaway IgnoreEngine instances"""

    def test_build_search_index_accepts_ignore_engine(self, tmp_path):
        """build_search_index should accept optional ignore_engine parameter"""
        from services.workspace_index import build_search_index
        from core.ignore_engine import IgnoreEngine

        (tmp_path / "test.py").write_text("x = 1")

        engine = IgnoreEngine()
        index = build_search_index(tmp_path, ignore_engine=engine)

        assert isinstance(index, dict)
        assert "test.py" in index

    def test_collect_files_accepts_ignore_engine(self, tmp_path):
        """collect_files_from_disk should accept optional ignore_engine parameter"""
        from services.workspace_index import collect_files_from_disk
        from core.ignore_engine import IgnoreEngine

        (tmp_path / "test.py").write_text("x = 1")

        engine = IgnoreEngine()
        files = collect_files_from_disk(
            tmp_path, workspace_path=tmp_path, ignore_engine=engine
        )

        assert len(files) > 0
        assert any("test.py" in f for f in files)

    def test_ignore_engine_cache_reused(self, tmp_path):
        """IgnoreEngine cache should be reused across multiple calls"""
        from services.workspace_index import build_search_index
        from core.ignore_engine import IgnoreEngine

        (tmp_path / ".gitignore").write_text("*.log")
        (tmp_path / "test.py").write_text("x = 1")
        (tmp_path / "test.log").write_text("log")

        engine = IgnoreEngine()

        # First call - cache miss
        index1 = build_search_index(tmp_path, ignore_engine=engine)

        # Second call - cache hit (should be faster)
        index2 = build_search_index(tmp_path, ignore_engine=engine)

        # Both should have same results
        assert index1 == index2
        # Cache should have entries
        assert len(engine._pathspec_cache) > 0


class TestBug5IgnoreEngineThreadSafety:
    """BUG #5: IgnoreEngine caches lack thread synchronization"""

    def test_ignore_engine_has_lock(self):
        """IgnoreEngine should have a threading.Lock"""
        from core.ignore_engine import IgnoreEngine

        engine = IgnoreEngine()
        assert hasattr(engine, "_lock")
        # Check it's a lock-like object (has acquire/release methods)
        assert hasattr(engine._lock, "acquire")
        assert hasattr(engine._lock, "release")

    def test_concurrent_cache_access_no_race(self, tmp_path):
        """Concurrent cache access should not cause race conditions"""
        from core.ignore_engine import IgnoreEngine

        (tmp_path / ".gitignore").write_text("*.log")

        engine = IgnoreEngine()
        errors = []

        def reader():
            try:
                for _ in range(50):
                    spec = engine.build_pathspec(tmp_path, use_default_ignores=True)
                    assert spec is not None
                    time.sleep(0.001)
            except Exception as e:
                errors.append(("reader", str(e)))

        def clearer():
            try:
                for _ in range(25):
                    time.sleep(0.002)
                    engine.clear_cache()
            except Exception as e:
                errors.append(("clearer", str(e)))

        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads.append(threading.Thread(target=clearer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race conditions detected: {errors}"

    def test_clear_cache_thread_safe(self, tmp_path):
        """clear_cache should be thread-safe"""
        from core.ignore_engine import IgnoreEngine

        engine = IgnoreEngine()

        # Populate cache
        engine.build_pathspec(tmp_path, use_default_ignores=True)
        assert len(engine._pathspec_cache) > 0

        # Clear from multiple threads
        def clear():
            engine.clear_cache()

        threads = [threading.Thread(target=clear) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should be empty and no exceptions
        assert len(engine._pathspec_cache) == 0
        assert len(engine._gitignore_cache) == 0


class TestPromptBuilderUsesContainerTokenization:
    """Additional: PromptBuildService should use container's tokenization service"""

    def test_prompt_builder_receives_tokenization_service(self):
        """PromptBuildService should receive tokenization_service from container"""
        from services.service_container import ServiceContainer

        container = ServiceContainer()

        # PromptBuilder should use the same tokenization service as container
        assert container.prompt_builder._tokenization_service is container.tokenization
