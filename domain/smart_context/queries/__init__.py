"""
Central Registry cho Tree-sitter Queries (SCM) của toàn bộ hệ thống Synapse.
Load từ domain/codemap/queries/ để đảm bảo Single Source of Truth.
"""

from pathlib import Path


def _load_query(lang: str) -> str:
    # Aider/Synapse pattern: {lang}-tags.scm
    query_path = Path("domain/codemap/queries") / f"{lang}-tags.scm"
    if query_path.exists():
        return query_path.read_text()
    return ""


# Cung cấp mapping constants cho Smart Context Config (Backward Compatibility + Unity)
QUERY_PYTHON = _load_query("python")
QUERY_JAVASCRIPT = _load_query("javascript")
QUERY_TYPESCRIPT = _load_query("typescript")
QUERY_RUST = _load_query("rust")
QUERY_GO = _load_query("go")
QUERY_JAVA = _load_query("java")
QUERY_CSHARP = _load_query("c_sharp")
QUERY_C = _load_query("c")
QUERY_CPP = _load_query("cpp")
QUERY_RUBY = _load_query("ruby")
QUERY_PHP = _load_query("php")
QUERY_SWIFT = _load_query("swift")
QUERY_CSS = _load_query("css")
QUERY_SOLIDITY = _load_query("solidity")
