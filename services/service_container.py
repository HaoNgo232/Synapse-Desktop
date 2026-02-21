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
- KHONG thay the cac global accessor hien co (get_tokenization_service(), cache_registry)
- Chi wrap chung lai de cung cap single point of control
- Cac module khac van co the import truc tiep ma khong bi anh huong
"""

import logging
from typing import Any

from services.prompt_build_service import PromptBuildService, QtClipboardService
from services.cache_registry import cache_registry
from services.encoder_registry import get_tokenization_service, initialize_encoder
from services.service_interfaces import IPromptBuilder, IClipboardService
from services.interfaces.tokenization_service import ITokenizationService

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Composition root - single point of control cho service lifecycle.

    So huu: PromptBuildService, QtClipboardService
    Tham chieu: cache_registry (module singleton), encoder_registry (module singleton)

    Thread Safety: Khoi tao PHAI thuc hien tren main thread.
    Cac services ben trong deu thread-safe.
    """

    def __init__(self) -> None:
        """Khoi tao tat ca services tai composition root."""
        # Services do container so huu truc tiep
        self.prompt_builder: IPromptBuilder = PromptBuildService()
        self.clipboard: IClipboardService = QtClipboardService()

        # Tham chieu den cac singleton hien co (KHONG tao instance moi)
        self.cache_registry = cache_registry

        logger.info("ServiceContainer initialized")

    @property
    def tokenization(self) -> ITokenizationService:
        """
        Tra ve TokenizationService hien tai.

        Delegate sang encoder_registry singleton de dam bao
        moi noi trong app dung cung instance.
        """
        return get_tokenization_service()

    def reset_for_model_change(self) -> None:
        """
        Re-initialize services khi user doi model.

        Goi method nay thay vi goi initialize_encoder() truc tiep
        de tap trung lifecycle management tai mot diem.
        """
        initialize_encoder()
        logger.info("ServiceContainer: model change reset completed")

    def get_health_report(self) -> dict[str, Any]:
        """
        Tra ve health report cua tat ca services.

        Huu ich cho monitoring va debugging.

        Returns:
            Dict chua cache stats va danh sach caches da dang ky
        """
        report: dict[str, Any] = {}
        try:
            report["cache_stats"] = self.cache_registry.get_stats()
            report["caches_registered"] = self.cache_registry.get_registered_names()
        except Exception as e:
            logger.warning("Failed to get cache health: %s", e)
            report["cache_error"] = str(e)

        return report
