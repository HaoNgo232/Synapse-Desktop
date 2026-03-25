"""
Model Configuration - Backward compatibility shim.

File này đã được chuyển sang application/config/model_config.py.
Import từ application/config/model_config để tuân theo Clean Architecture.
"""

from application.config.model_config import (
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
