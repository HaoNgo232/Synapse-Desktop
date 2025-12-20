"""
Smart Context Module - Public API

Cung cấp Smart Context extraction cho các ngôn ngữ lập trình.
Sử dụng Tree-sitter để parse và trích xuất cấu trúc code.

Supported Languages:
- Python (.py, .pyw)
- JavaScript (.js, .jsx, .mjs, .cjs)
- TypeScript (.ts, .tsx, .mts, .cts)
- Rust (.rs)
- Go (.go)
- Java (.java)
- C# (.cs)
- C (.c, .h)
- C++ (.cpp, .hpp, .cc, .cxx)
"""

from core.smart_context.parser import smart_parse
from core.smart_context.config import (
    get_supported_extensions,
    get_config_by_extension,
    is_supported,
    LanguageConfig,
    LANGUAGE_CONFIGS,
)
from core.smart_context.loader import get_language, get_query

__all__ = [
    # Main API
    "smart_parse",
    # Config functions
    "get_supported_extensions",
    "get_config_by_extension",
    "is_supported",
    "LanguageConfig",
    "LANGUAGE_CONFIGS",
    # Loader functions
    "get_language",
    "get_query",
]
