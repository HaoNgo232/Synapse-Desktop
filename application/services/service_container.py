"""
ServiceContainer - Composition root cho toan bo application services.

Tap trung viec khoi tao va quan ly lifecycle cua cac services
tai mot diem duy nhat, thay vi trai rac o nhieu files.

Su dung:
    container = ServiceContainer()
    view = ContextViewQt(
        get_workspace=...,
        prompt_builder=container.prompt_builder,
        clipboard_service=container.clipboard,
    )

Design decisions:
- Container SO HUU truc tiep TokenizationService (khong dung global singleton)
- encoder_registry.get_tokenization_service() hien van hoat dong de tuong thich
  nguoc nhung delegate sang container neu co the
- Cac module can TokenizationService nen nhan qua constructor, khong global import
"""

import logging
from typing import Any

from application.services.prompt_build_service import PromptBuildService
from infrastructure.adapters.clipboard_service import QtClipboardService
from infrastructure.adapters.cache_registry import CacheRegistry
from application.services.tokenization_service import TokenizationService
from application.services.service_interfaces import IPromptBuilder, IClipboardService
from application.interfaces.tokenization_port import ITokenizationService
from infrastructure.filesystem.ignore_engine import IgnoreEngine
from application.services.graph_service import GraphService

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Composition root - single point of control cho service lifecycle.

    So huu: PromptBuildService, QtClipboardService, TokenizationService, CacheRegistry, IgnoreEngine
    Khong con dung module-level singletons (encoder_registry, cache_registry).

    Thread Safety: Khoi tao PHAI thuc hien tren main thread.
    Cac services ben trong deu thread-safe.
    """

    def __init__(self) -> None:
        """Khoi tao tat ca services tai composition root."""
        # IgnoreEngine - quan ly tat ca logic ignore/gitignore
        # Khoi tao tai day de tranh module-level state
        self.ignore_engine: IgnoreEngine = IgnoreEngine()

        # GraphService - quan ly RelationshipGraph o application layer
        # Inject IgnoreEngine de ton trong cac exclude patterns khi scan files
        self.graph_service: GraphService = GraphService(
            ignore_engine=self.ignore_engine
        )

        # TokenizationService - khoi tao noi bo thay vi dung global singleton
        # Lay tokenizer_repo tu settings hien tai
        from infrastructure.adapters.encoder_registry import get_tokenizer_repo

        _repo = get_tokenizer_repo()
        self._tokenization_service: TokenizationService = TokenizationService(
            tokenizer_repo=_repo
        )

        # Services do container so huu truc tiep (inject dependencies)
        self.prompt_builder: IPromptBuilder = PromptBuildService(
            tokenization_service=self._tokenization_service,
            graph_service=self.graph_service,
        )
        self.clipboard: IClipboardService = QtClipboardService()

        # CacheRegistry - tam thoi giu lai module singleton o day cho den khi Phase 2 migration
        from infrastructure.adapters.cache_registry import (
            cache_registry as _module_registry,
        )

        self.cache_registry: CacheRegistry = _module_registry

        logger.info("ServiceContainer initialized with owned services")

    @property
    def tokenization(self) -> ITokenizationService:
        """
        Tra ve TokenizationService hien tai.

        Tra ve instance do CONTAINER so huu, khong phai global singleton.
        """
        return self._tokenization_service

    def reset_for_model_change(self) -> None:
        """
        Re-initialize TokenizationService khi user doi model.

        Goi method nay thay vi goi initialize_encoder() truc tiep
        de tap trung lifecycle management tai mot diem.
        """
        repo = self._resolve_tokenizer_repo()
        self._tokenization_service.set_model_config(tokenizer_repo=repo)
        logger.info("ServiceContainer: model change reset completed (repo=%s)", repo)

    def shutdown(self) -> None:
        """
        Cleanup all owned services.

        Call from MainWindow.closeEvent() to ensure graceful shutdown.
        Invalidates all caches and releases resources.
        """
        try:
            self.cache_registry.invalidate_for_workspace()
        except Exception as e:
            logger.warning("Failed to invalidate caches during shutdown: %s", e)

        try:
            self.graph_service.invalidate()
        except Exception as e:
            logger.warning("Failed to invalidate graph service during shutdown: %s", e)

        logger.info("ServiceContainer shut down")

    def get_health_report(self) -> dict[str, Any]:
        """
        Return a health report of all services.

        Useful for monitoring and debugging.

        Returns:
            Dict chua cache stats va list of registered caches
        """
        report: dict[str, Any] = {}
        try:
            report["cache_stats"] = self.cache_registry.get_stats()
            report["caches_registered"] = self.cache_registry.get_registered_names()
        except Exception as e:
            logger.warning("Failed to get cache health: %s", e)
            report["cache_error"] = str(e)

        return report

    @staticmethod
    def _resolve_tokenizer_repo() -> "str | None":
        """
        Lay Hugging Face tokenizer repo tu settings hien tai.

        Tra ve None neu khong co model duoc cau hinh hoac gap loi.
        """
        try:
            from infrastructure.persistence.settings_manager import load_app_settings
            from presentation.config.model_config import get_model_by_id

            settings = load_app_settings()
            model_id = settings.model_id
            model_config = get_model_by_id(model_id)
            if model_config:
                return model_config.tokenizer_repo
            return None
        except Exception:
            return None
