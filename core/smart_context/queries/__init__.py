"""
Smart Context Queries Package

Export tất cả tree-sitter queries cho các ngôn ngữ được hỗ trợ.
Mỗi query trong file riêng để dễ maintain và extend.
"""

# Phase 1: Foundation
from core.smart_context.queries.python import QUERY as QUERY_PYTHON
from core.smart_context.queries.javascript import QUERY as QUERY_JAVASCRIPT
from core.smart_context.queries.typescript import QUERY as QUERY_TYPESCRIPT

# Phase 2: Developer Tools
from core.smart_context.queries.rust import QUERY as QUERY_RUST
from core.smart_context.queries.go import QUERY as QUERY_GO

# Phase 3: Enterprise
from core.smart_context.queries.java import QUERY as QUERY_JAVA
from core.smart_context.queries.c_sharp import QUERY as QUERY_CSHARP
from core.smart_context.queries.c import QUERY as QUERY_C
from core.smart_context.queries.cpp import QUERY as QUERY_CPP

# Phase 4: Web & Scripting
from core.smart_context.queries.ruby import QUERY as QUERY_RUBY
from core.smart_context.queries.php import QUERY as QUERY_PHP
from core.smart_context.queries.swift import QUERY as QUERY_SWIFT

__all__ = [
    # Phase 1
    "QUERY_PYTHON",
    "QUERY_JAVASCRIPT",
    "QUERY_TYPESCRIPT",
    # Phase 2
    "QUERY_RUST",
    "QUERY_GO",
    # Phase 3
    "QUERY_JAVA",
    "QUERY_CSHARP",
    "QUERY_C",
    "QUERY_CPP",
    # Phase 4
    "QUERY_RUBY",
    "QUERY_PHP",
    "QUERY_SWIFT",
]
