"""
Tests cho ServiceContainer - composition root pattern.

Verify:
1. Container tao dung cac service instances
2. reset_for_model_change() re-initialize encoder
3. get_health_report() tra ve cache stats
4. Container khong tao duplicate singletons

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
        from services.service_container import ServiceContainer
        from services.service_interfaces import IPromptBuilder

        container = ServiceContainer()
        assert isinstance(container.prompt_builder, IPromptBuilder)

    def test_creates_clipboard_service(self):
        """Container phai tao QtClipboardService instance."""
        from services.service_container import ServiceContainer
        from services.service_interfaces import IClipboardService

        container = ServiceContainer()
        assert isinstance(container.clipboard, IClipboardService)

    def test_references_existing_cache_registry_singleton(self):
        """Container phai dung cache_registry singleton, KHONG tao moi."""
        from services.service_container import ServiceContainer
        from services.cache_registry import cache_registry

        container = ServiceContainer()
        assert container.cache_registry is cache_registry

    def test_tokenization_property_delegates_to_registry(self):
        """Container.tokenization phai delegate sang encoder_registry."""
        from services.service_container import ServiceContainer
        from services.encoder_registry import get_tokenization_service

        container = ServiceContainer()
        # Cung instance vi deu goi get_tokenization_service()
        assert container.tokenization is get_tokenization_service()


class TestServiceContainerLifecycle:
    """Dam bao lifecycle methods hoat dong dung."""

    def test_reset_for_model_change_calls_initialize_encoder(self):
        """reset_for_model_change() phai goi initialize_encoder()."""
        from services.service_container import ServiceContainer

        container = ServiceContainer()

        with patch("services.service_container.initialize_encoder") as mock_init:
            container.reset_for_model_change()
            mock_init.assert_called_once()


class TestServiceContainerHealthReport:
    """Dam bao health report tra ve thong tin dung."""

    def test_health_report_contains_cache_stats(self):
        """get_health_report() phai tra ve cache_stats."""
        from services.service_container import ServiceContainer

        container = ServiceContainer()
        report = container.get_health_report()

        assert "cache_stats" in report
        assert isinstance(report["cache_stats"], dict)

    def test_health_report_contains_registered_names(self):
        """get_health_report() phai tra ve danh sach caches da dang ky."""
        from services.service_container import ServiceContainer

        container = ServiceContainer()
        report = container.get_health_report()

        assert "caches_registered" in report
        assert isinstance(report["caches_registered"], list)

    def test_health_report_handles_cache_error_gracefully(self):
        """get_health_report() khong crash khi cache loi."""
        from services.service_container import ServiceContainer

        container = ServiceContainer()

        # Mock cache_registry.get_stats to raise
        with patch.object(
            container.cache_registry, "get_stats", side_effect=RuntimeError("boom")
        ):
            report = container.get_health_report()

        assert "cache_error" in report
        assert "boom" in report["cache_error"]
