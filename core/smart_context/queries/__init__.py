"""
Smart Context Queries Package

Export tất cả tree-sitter queries cho các ngôn ngữ được hỗ trợ.
Mỗi query trong file riêng để dễ maintain và extend.
"""

from core.smart_context.queries.python import QUERY as QUERY_PYTHON
from core.smart_context.queries.javascript import QUERY as QUERY_JAVASCRIPT
from core.smart_context.queries.typescript import QUERY as QUERY_TYPESCRIPT
from core.smart_context.queries.rust import QUERY as QUERY_RUST
from core.smart_context.queries.go import QUERY as QUERY_GO
from core.smart_context.queries.java import QUERY as QUERY_JAVA
from core.smart_context.queries.c_sharp import QUERY as QUERY_CSHARP
from core.smart_context.queries.c import QUERY as QUERY_C
from core.smart_context.queries.cpp import QUERY as QUERY_CPP

__all__ = [
    "QUERY_PYTHON",
    "QUERY_JAVASCRIPT",
    "QUERY_TYPESCRIPT",
    "QUERY_RUST",
    "QUERY_GO",
    "QUERY_JAVA",
    "QUERY_CSHARP",
    "QUERY_C",
    "QUERY_CPP",
]
