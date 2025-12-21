"""
Smart Context Parser - Tree-sitter Code Structure Extraction

Module chính để parse code và trích xuất cấu trúc (classes, functions, docstrings).
Sử dụng Tree-sitter để phân tích code theo ngôn ngữ.

Refactored to use modular config and loader.
"""

import os
from typing import Optional
from tree_sitter import Parser, Node, Language, Tree  # type: ignore

from core.smart_context.config import is_supported, get_config_by_extension
from core.smart_context.loader import get_language, get_query

# Chunk separator giống Repomix
CHUNK_SEPARATOR = "⋮----"


def smart_parse(file_path: str, content: str) -> Optional[str]:
    """
    Parse file content và trích xuất cấu trúc code (Smart Context).

    Strategy:
    1. Try query-based parsing first (better quality, from Repomix)
    2. Fallback to node-type based parsing if query fails
    3. Fallback to None if both fail

    Args:
        file_path: Đường dẫn file (để xác định ngôn ngữ)
        content: Nội dung raw của file

    Returns:
        String chứa các code chunks (signatures, docstrings) hoặc None nếu không hỗ trợ

    BACKWARD COMPATIBILITY:
    - API signature không đổi
    - Nếu query-based fails → fallback to old node-type logic
    """
    # Lấy file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lstrip(".")

    if not is_supported(ext):
        return None

    language = get_language(ext)
    if not language:
        return None

    try:
        # Tạo parser và parse content
        parser = Parser(language)
        tree = parser.parse(bytes(content, "utf-8"))

        if not tree or not tree.root_node:
            return None

        # Try query-based parsing first (improved quality)
        query_string = get_query(ext)
        if query_string:
            try:
                result = _parse_with_query(language, tree, content, query_string, ext)
                if result:
                    return result
            except Exception:
                # Query parsing failed, fallback below
                pass

        # FALLBACK: Use simple node-based extraction with DefaultParseStrategy
        # This catches cases where query parsing fails or no query exists
        chunks = _extract_chunks_simple(tree.root_node, content)

        if not chunks:
            return None

        # Nối các chunks với separator
        return f"\n{CHUNK_SEPARATOR}\n".join(chunks)

    except Exception:
        # Nếu có lỗi parse, trả về None
        return None


def _parse_with_query(
    language: Language, tree: Tree, content: str, query_string: str, ext: str
) -> Optional[str]:
    """
    Parse using tree-sitter query with Strategy pattern (ported from Repomix).

    Uses language-specific ParseStrategy for smart extraction.

    Args:
        language: Tree-sitter Language object
        tree: Parsed tree
        content: File content as string
        query_string: Tree-sitter query string
        ext: File extension (to select strategy)

    Returns:
        Formatted string with code chunks or None if fails
    """
    try:
        from tree_sitter import Query, QueryCursor  # type: ignore
        from core.smart_context.strategies import get_strategy
        from core.smart_context.chunk_utils import (
            filter_duplicated_chunks,
            merge_adjacent_chunks,
        )

        query = Query(language, query_string)
        query_cursor = QueryCursor(query)
        captures = query_cursor.captures(tree.root_node)

        if not captures:
            return None

        # Get language config to determine strategy
        config = get_config_by_extension(ext)
        lang_name = config.name if config else "default"
        strategy = get_strategy(lang_name)

        lines = content.split("\n")
        captured_chunks: list[dict] = []
        processed_chunks: set[str] = set()

        # Iterate over captures dict
        for capture_name, nodes in captures.items():
            # Only process definition nodes (classes, functions, etc.)
            if not capture_name.startswith("definition."):
                continue

            for node in nodes:
                start_row = node.start_point[0]
                end_row = node.end_point[0]

                # Use strategy to extract chunk
                chunk = strategy.parse_capture(
                    capture_name, lines, start_row, end_row, processed_chunks
                )

                if chunk:
                    captured_chunks.append(
                        {
                            "content": chunk.strip(),
                            "start_row": start_row,
                            "end_row": end_row,
                        }
                    )

        if not captured_chunks:
            return None

        # Post-processing
        filtered = filter_duplicated_chunks(captured_chunks)
        merged = merge_adjacent_chunks(filtered)

        return "\n" + f"\n{CHUNK_SEPARATOR}\n".join(c["content"] for c in merged)

    except Exception:
        return None


# ==================== FALLBACK FUNCTIONS (Backward Compatibility) ====================
# Functions nay duoc su dung khi query-based parsing fails hoac khong co query


def _extract_chunks_simple(node: Node, content: str) -> list[str]:
    """
    Simple fallback extraction - lay dong dau tien cua moi function/class definition.
    Duoc su dung khi query-based parsing fails.

    Args:
        node: Root node cua AST
        content: Noi dung raw cua file

    Returns:
        List cac code chunks
    """
    chunks: list[str] = []
    lines = content.split("\n")
    processed: set[str] = set()

    def traverse(n: Node) -> None:
        """Duyet AST de tim definitions."""
        # Check common definition node types across languages
        if any(
            keyword in n.type
            for keyword in [
                "function",
                "method",
                "class",
                "interface",
                "struct",
                "enum",
                "type_alias",
                "import",
            ]
        ):
            if n.start_point[0] < len(lines):
                # Chi lay dong dau tien
                chunk = lines[n.start_point[0]].strip()
                if chunk and chunk not in processed:
                    chunks.append(chunk)
                    processed.add(chunk)
            # Khong duyet vao children cua definition node
            return

        # Duyet recursively vao children
        for child in n.children:
            traverse(child)

    traverse(node)
    return chunks
