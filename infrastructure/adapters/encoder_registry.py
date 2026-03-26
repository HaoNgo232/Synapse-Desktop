"""
Encoder Registry - Provider cho TokenizationService.

DEPRECATED: Module nay giu lai de backward compatibility.
Cach dung MOI: truyen TokenizationService qua ServiceContainer.

Functions:
- get_tokenization_service(): Lay TokenizationService singleton (deprecated, dung ServiceContainer)
- initialize_encoder(): Cap nhat encoder config (deprecated, dung container.reset_for_model_change())
- get_current_model(): Lay model ID tu settings
- get_tokenizer_repo(): Resolve tokenizer repo tu current model settings

Dependency flow:
    services.settings_manager -> encoder_registry -> TokenizationService -> core.encoders
"""

import threading
from typing import Optional

from application.interfaces.tokenization_port import ITokenizationService
from application.services.tokenization_service import TokenizationService

# TokenizationService singleton instance (thread-safe) - backward compat
# Preference: Su dung ServiceContainer.tokenization thay the
_service_instance: Optional[TokenizationService] = None
_service_lock = threading.Lock()


def get_tokenization_service() -> ITokenizationService:
    """
    Lay TokenizationService singleton instance.

    Thread-safe lazy initialization.
    Day la entry point chinh cho cac code chua duoc chuyen sang
    ServiceContainer injection.

    Returns:
        ITokenizationService instance
    """
    global _service_instance
    if _service_instance is not None:
        return _service_instance

    with _service_lock:
        if _service_instance is None:
            repo = get_tokenizer_repo()
            _service_instance = TokenizationService(tokenizer_repo=repo)
        return _service_instance


def initialize_encoder() -> None:
    """
    Initialize hoac update encoder config cho TokenizationService.

    Goi function nay khi app start hoac khi user doi model.
    Se update tokenizer_repo trong service instance.

    NOTE: Neu dang dung ServiceContainer, hay goi container.reset_for_model_change()
    thay the de dam bao nhat quan.
    """
    repo = get_tokenizer_repo()
    service = get_tokenization_service()
    service.set_model_config(tokenizer_repo=repo)


def get_current_model() -> str:
    """
    Lay model hien tai tu settings.

    Returns:
        Model ID (vd: "claude-sonnet-4.5", "gpt-4o")
    """
    try:
        from infrastructure.persistence.settings_manager import load_app_settings

        settings = load_app_settings()
        return settings.model_id.lower() if settings.model_id else ""
    except Exception:
        return ""


def get_tokenizer_repo() -> Optional[str]:
    """
    Lay Hugging Face tokenizer repo cho model hien tai.

    Doc model_id tu settings, tra cuu tokenizer_repo tu model_config.

    Returns:
        Tokenizer repo (vd: "Xenova/claude-tokenizer") hoac None
    """
    try:
        from infrastructure.persistence.settings_manager import load_app_settings
        from application.config.model_config import get_model_by_id

        settings = load_app_settings()
        model_id = settings.model_id

        model_config = get_model_by_id(model_id)
        if model_config:
            return model_config.tokenizer_repo

        return None
    except Exception:
        return None
