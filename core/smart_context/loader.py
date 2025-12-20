"""
Tree-sitter Language Loader

Module để load Tree-sitter Language objects với caching.
Sử dụng LanguageConfig từ config.py để xác định cách load.
"""

from typing import Optional
from tree_sitter import Language  # type: ignore

from core.smart_context.config import get_config_by_extension

# Cache đã load languages
_language_cache: dict[str, Language] = {}


def get_language(extension: str) -> Optional[Language]:
    """
    Lấy Tree-sitter Language object cho file extension.

    Load language từ config và cache kết quả để tránh load lại.

    Args:
        extension: File extension không có dấu chấm (e.g., 'py', 'ts')

    Returns:
        Tree-sitter Language object hoặc None nếu không hỗ trợ
    """
    config = get_config_by_extension(extension)
    if not config:
        return None

    # Check cache
    if config.name not in _language_cache:
        # Load và cache
        _language_cache[config.name] = config.loader()

    return _language_cache[config.name]


def get_query(extension: str) -> Optional[str]:
    """
    Lấy tree-sitter query string cho file extension.

    Args:
        extension: File extension không có dấu chấm

    Returns:
        Query string hoặc None nếu không hỗ trợ
    """
    config = get_config_by_extension(extension)
    if not config:
        return None
    return config.query


def clear_cache() -> None:
    """Clear language cache (useful for testing)."""
    _language_cache.clear()
