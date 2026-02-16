"""
CodeMaps - Code Structure Analysis and Relationship Extraction

Module này phân tích cấu trúc code và extract relationships sử dụng Tree-sitter.

Public API:
    - extract_symbols: Extract symbols từ file
    - extract_relationships: Extract relationships từ file
    - build_codemap: Build CodeMap cho file hoặc workspace
"""

from core.codemaps.types import (
    Symbol,
    Relationship,
    CodeMap,
    SymbolKind,
    RelationshipKind,
)
from core.codemaps.symbol_extractor import extract_symbols
from core.codemaps.relationship_extractor import extract_relationships
from core.codemaps.graph_builder import CodeMapBuilder

__all__ = [
    "Symbol",
    "Relationship",
    "CodeMap",
    "SymbolKind",
    "RelationshipKind",
    "extract_symbols",
    "extract_relationships",
    "CodeMapBuilder",
]
