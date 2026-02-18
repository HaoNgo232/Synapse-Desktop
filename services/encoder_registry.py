"""
Encoder Registry - Config injection wrapper cho core/encoders.

Module nay bridge giua service layer (settings) va core layer (encoders).
Core layer khong biet ve settings -- module nay inject config vao.

Functions:
- initialize_encoder(): Set default encoder config cho core layer (goi khi app start)
- get_encoder(): Lay encoder singleton voi config tu settings
- get_tokenizer_repo(): Resolve tokenizer repo tu current model settings
- get_current_model(): Lay model ID tu settings

Dependency flow:
    services.settings_manager -> encoder_registry -> core.encoders
    (KHONG con: core.encoders -> services.settings_manager)
"""

from typing import Optional, Any

from core.encoders import _get_encoder


def initialize_encoder() -> None:
    """
    Initialize default encoder config cho core layer.

    Goi function nay khi app start hoac khi user doi model.
    Set tokenizer_repo vao core.tokenization.counter module.
    """
    repo = get_tokenizer_repo()
    import core.tokenization.counter as counter

    counter.set_default_encoder_config(tokenizer_repo=repo)


def get_current_model() -> str:
    """
    Lay model hien tai tu settings.

    Wrapper doc settings va tra ve model_id.
    Logic nay truoc day nam trong core/encoders.py (vi pham DIP).

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
    Logic nay truoc day nam trong core/encoders.py (vi pham DIP).

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


def get_encoder() -> Optional[Any]:
    """
    Lay encoder singleton voi config injection tu settings.

    Day la entry point chinh cho consumers can encoder.
    Tu dong resolve tokenizer_repo tu settings va inject vao core.

    Returns:
        Encoder instance hoac None
    """
    repo = get_tokenizer_repo()
    return _get_encoder(tokenizer_repo=repo)
