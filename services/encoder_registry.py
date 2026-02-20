"""
Encoder Registry - Provider/Container cho TokenizationService.

Module nay la single access point cho TokenizationService instance.
Thay the cac global state cu, cung cap dependency injection cho
toan bo ung dung.

Functions:
- get_tokenization_service(): Lay TokenizationService singleton
- initialize_encoder(): Set model config cho service (goi khi app start)
- get_current_model(): Lay model ID tu settings
- get_tokenizer_repo(): Resolve tokenizer repo tu current model settings

Dependency flow:
    services.settings_manager -> encoder_registry -> TokenizationService -> core.encoders
"""

import threading
from typing import Optional

from services.interfaces.tokenization_service import ITokenizationService
from services.tokenization_service import TokenizationService

# TokenizationService singleton instance (thread-safe)
_service_instance: Optional[TokenizationService] = None
_service_lock = threading.Lock()


def get_tokenization_service() -> ITokenizationService:
    """
    Lay TokenizationService singleton instance.

    Thread-safe lazy initialization.
    Day la entry point chinh cho toan bo ung dung.

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
        from services.settings_manager import load_settings

        settings = load_settings()
        return settings.get("model_id", "").lower() if settings else ""
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
        from services.settings_manager import load_settings
        from config.model_config import get_model_by_id

        settings = load_settings()
        model_id = settings.get("model_id", "")

        model_config = get_model_by_id(model_id)
        if model_config:
            return model_config.tokenizer_repo

        return None
    except Exception:
        return None
