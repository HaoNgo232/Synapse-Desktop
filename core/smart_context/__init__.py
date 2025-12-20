"""
Smart Context Package - Tree-sitter based code structure extraction.

Cung cấp khả năng trích xuất "tinh hoa" của source code (signatures, docstrings)
thay vì raw text đầy đủ, giúp tiết kiệm tokens khi gửi context cho LLMs.
"""

from core.smart_context.parser import smart_parse
from core.smart_context.languages import is_supported, get_supported_extensions

__all__ = ["smart_parse", "is_supported", "get_supported_extensions"]
