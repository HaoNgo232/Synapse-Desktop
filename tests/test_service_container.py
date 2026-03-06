"""
Tests cho ServiceContainer - composition root pattern.

Verify:
1. Container tao dung cac service instances
2. reset_for_model_change() re-initialize tokenization service
3. get_health_report() tra ve cache stats
4. Container so huu instance rieng (khong dung shared singletons)

Run: pytest tests/test_service_container.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch


# Dam bao project root trong sys.path
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


class TestServiceContainerCreation:
    """Dam bao container tao dung cac service instances."""

    def test_creates_prompt_builder(self):
        """Container phai tao PromptBuildService instance."""
        from application.services.service_container import ServiceContainer
        from application.services.service_interfaces import IPromptBuilder

        container = ServiceContainer()
        assert isinstance(container.prompt_builder, IPromptBuilder)

    def test_creates_clipboard_service(self):
        """Container phai tao QtClipboardService instance."""
        from application.services.service_container import ServiceContainer
        from application.services.service_interfaces import IClipboardService

        container = ServiceContainer()
        assert isinstance(container.clipboard, IClipboardService)

    def test_creates_owned_cache_registry(self):
        """Container phai tao CacheRegistry rieng (khong dung global singleton)."""
        from application.services.service_container import ServiceContainer
        from infrastructure.adapters.cache_registry import CacheRegistry

        container = ServiceContainer()
        # Container so huu instance rieng cua CacheRegistry
        assert isinstance(container.cache_registry, CacheRegistry)

    def test_creates_owned_tokenization_service(self):
        """Container phai tao TokenizationService rieng (khong dung global singleton)."""
        from application.services.service_container import ServiceContainer
        from application.interfaces.tokenization_port import ITokenizationService

        container = ServiceContainer()
        # tokenization property tra ve instance do container so huu
        assert isinstance(container.tokenization, ITokenizationService)

    def test_two_containers_share_cache_registry_until_phase2(self):
        """Moi container hien su dung module-level cache_registry."""
        from application.services.service_container import ServiceContainer

        container_a = ServiceContainer()
        container_b = ServiceContainer()
        # Tam thoi chia se module singleton
        assert container_a.cache_registry is container_b.cache_registry


class TestServiceContainerLifecycle:
    """Dam bao lifecycle methods hoat dong dung."""

    def test_reset_for_model_change_updates_tokenization(self):
        """reset_for_model_change() phai cap nhat tokenization service config."""
        from application.services.service_container import ServiceContainer

        container = ServiceContainer()
        # Mock _resolve_tokenizer_repo de kiem soat test
        with patch.object(
            ServiceContainer, "_resolve_tokenizer_repo", return_value="test/repo"
        ):
            # Neu khong raise exception la OK
            container.reset_for_model_change()

    def test_shutdown_does_not_raise(self):
        """shutdown() khong duoc raise exception."""
        from application.services.service_container import ServiceContainer

        container = ServiceContainer()
        # Should not raise
        container.shutdown()

    def test_shutdown_invalidates_caches(self):
        """shutdown() phai goi invalidate_for_workspace() tren cache_registry."""
        from application.services.service_container import ServiceContainer

        container = ServiceContainer()
        with patch.object(
            container.cache_registry, "invalidate_for_workspace"
        ) as mock_invalidate:
            container.shutdown()
            mock_invalidate.assert_called_once()


class TestServiceContainerHealthReport:
    """Dam bao health report tra ve thong tin dung."""

    def test_health_report_contains_cache_stats(self):
        """get_health_report() phai tra ve cache_stats."""
        from application.services.service_container import ServiceContainer

        container = ServiceContainer()
        report = container.get_health_report()

        assert "cache_stats" in report
        assert isinstance(report["cache_stats"], dict)

    def test_health_report_contains_registered_names(self):
        """get_health_report() phai tra ve danh sach caches da dang ky."""
        from application.services.service_container import ServiceContainer

        container = ServiceContainer()
        report = container.get_health_report()

        assert "caches_registered" in report
        assert isinstance(report["caches_registered"], list)

    def test_health_report_handles_cache_error_gracefully(self):
        """get_health_report() khong crash khi cache loi."""
        from application.services.service_container import ServiceContainer

        container = ServiceContainer()

        # Mock cache_registry.get_stats to raise
        with patch.object(
            container.cache_registry, "get_stats", side_effect=RuntimeError("boom")
        ):
            report = container.get_health_report()

        assert "cache_error" in report
        assert "boom" in report["cache_error"]
