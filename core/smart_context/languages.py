"""
Smart Context Languages - Tree-sitter Language Management

Module quản lý việc load và cache Tree-sitter language grammars.
Hỗ trợ Python và JavaScript (có thể mở rộng thêm).
"""

from typing import Optional, Dict
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language

# Cache các language đã load để tránh load lại nhiều lần
_language_cache: Dict[str, Language] = {}

# Map từ file extension sang Tree-sitter language
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    # Python
    "py": "python",
    "pyw": "python",
    # JavaScript / TypeScript
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    # TypeScript sẽ dùng JavaScript parser (syntax tương đương phần lớn)
    "ts": "javascript",
    "tsx": "javascript",
}


def get_language(extension: str) -> Optional[Language]:
    """
    Lấy Tree-sitter Language dựa trên file extension.

    Args:
        extension: File extension (không có dấu chấm), ví dụ: "py", "js"

    Returns:
        Language object hoặc None nếu không hỗ trợ
    """
    ext_lower = extension.lower()
    lang_name = EXTENSION_TO_LANGUAGE.get(ext_lower)

    if not lang_name:
        return None

    # Kiểm tra cache trước
    if lang_name in _language_cache:
        return _language_cache[lang_name]

    # Load language dựa trên tên
    language: Optional[Language] = None

    if lang_name == "python":
        language = Language(tspython.language())
    elif lang_name == "javascript":
        language = Language(tsjavascript.language())

    # Cache lại kết quả
    if language:
        _language_cache[lang_name] = language

    return language


def is_supported(extension: str) -> bool:
    """
    Kiểm tra xem file extension có được Smart Context hỗ trợ không.

    Args:
        extension: File extension (không có dấu chấm)

    Returns:
        True nếu hỗ trợ, False nếu không
    """
    return extension.lower() in EXTENSION_TO_LANGUAGE


def get_supported_extensions() -> list[str]:
    """
    Lấy danh sách các file extensions được hỗ trợ.

    Returns:
        List các extensions (không có dấu chấm)
    """
    return list(EXTENSION_TO_LANGUAGE.keys())
