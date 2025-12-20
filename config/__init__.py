"""
Config Package - Chứa các constants và cấu hình của ứng dụng

Bao gồm:
- model_config: Định nghĩa các LLM models và context limits
"""

from config.model_config import (
    ModelConfig,
    MODEL_CONFIGS,
    DEFAULT_MODEL_ID,
    get_model_by_id,
    get_model_options,
)

__all__ = [
    "ModelConfig",
    "MODEL_CONFIGS",
    "DEFAULT_MODEL_ID",
    "get_model_by_id",
    "get_model_options",
]
