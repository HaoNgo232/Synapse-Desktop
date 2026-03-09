"""
CodeMaps - Code Structure Analysis and Relationship Extraction

Module này phân tích cấu trúc code và extract relationships sử dụng Tree-sitter.

Public API:
    - extract_symbols: Extract symbols từ file
    - extract_relationships: Extract relationships từ file
    - build_codemap: Build CodeMap cho file hoặc workspace
    - WorkspaceSummary: Canonical workspace summary dataclass
    - build_canonical_summary: Single entry point cho workspace structure
    - get_summary_as_text: Render WorkspaceSummary to text
"""

from domain.codemap.types import (
    Symbol,
    Relationship,
    CodeMap,
    SymbolKind,
    RelationshipKind,
)
from domain.codemap.symbol_extractor import extract_symbols
from domain.codemap.relationship_extractor import extract_relationships
from domain.codemap.graph_builder import CodeMapBuilder
from domain.codemap.canonical_structure import (
    WorkspaceSummary,
    build_canonical_summary,
    get_summary_as_text,
)

__all__ = [
    "Symbol",
    "Relationship",
    "CodeMap",
    "SymbolKind",
    "RelationshipKind",
    "extract_symbols",
    "extract_relationships",
    "CodeMapBuilder",
    "WorkspaceSummary",
    "build_canonical_summary",
    "get_summary_as_text",
]
