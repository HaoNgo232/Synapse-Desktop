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

# Các loại node type cần capture cho Python (FALLBACK ONLY)
PYTHON_CAPTURE_TYPES = {
    "class_definition",
    "function_definition",
    "decorated_definition",
    "import_statement",
    "import_from_statement",
}

# Các loại node type cần capture cho JavaScript/TypeScript (FALLBACK ONLY)
JAVASCRIPT_CAPTURE_TYPES = {
    "class_declaration",
    "function_declaration",
    "arrow_function",
    "method_definition",
    "import_statement",
    "export_statement",
    "lexical_declaration",  # const, let declarations
}

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
                # Query parsing failed, fallback to node-type based
                pass

        # FALLBACK: Use old node-type based parsing (backward compatibility)
        config = get_config_by_extension(ext)
        if config and config.name == "python":
            capture_types = PYTHON_CAPTURE_TYPES
        else:
            # JavaScript và TypeScript dùng JS capture types
            capture_types = JAVASCRIPT_CAPTURE_TYPES

        # Thu thập các chunks
        chunks = _extract_chunks(tree.root_node, content, capture_types)

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
# Cac functions nay chi duoc su dung khi query-based parsing fails


def _extract_chunks(node: Node, content: str, capture_types: set[str]) -> list[str]:
    """
    Đệ quy duyệt AST và trích xuất các chunks phù hợp.

    FALLBACK ONLY: Used when query-based parsing fails.

    Args:
        node: Node hiện tại trong AST
        content: Nội dung raw của file
        capture_types: Set các node types cần capture

    Returns:
        List các code chunks đã extract
    """
    chunks: list[str] = []

    # Kiểm tra node hiện tại có phải loại cần capture không
    if node.type in capture_types:
        chunk = _extract_signature(node, content)
        if chunk:
            chunks.append(chunk)
        # Không đệ quy vào children của node đã capture
        return chunks

    # Đệ quy vào children
    for child in node.children:
        chunks.extend(_extract_chunks(child, content, capture_types))

    return chunks


def _extract_signature(node: Node, content: str) -> Optional[str]:
    """
    Trích xuất signature (header + docstring) từ một node.

    FALLBACK ONLY: Used when query-based parsing fails.

    Args:
        node: Node cần extract
        content: Nội dung raw của file

    Returns:
        String signature hoặc None
    """
    lines = content.split("\n")

    # Lấy dòng bắt đầu và kết thúc của node
    start_line = node.start_point[0]
    end_line = node.end_point[0]

    # Với import statements: lấy toàn bộ
    if node.type in ("import_statement", "import_from_statement"):
        return "\n".join(lines[start_line : end_line + 1])

    # Với decorated definitions (Python): tìm decorator và function bên trong
    if node.type == "decorated_definition":
        result_lines = []
        for child in node.children:
            if child.type == "decorator":
                result_lines.append(lines[child.start_point[0]])
            elif child.type in ("function_definition", "class_definition"):
                sig = _extract_signature(child, content)
                if sig:
                    result_lines.append(sig)
        return "\n".join(result_lines) if result_lines else None

    # Với function/class: lấy signature (dòng đầu) + docstring
    result_lines = []

    # Dòng đầu tiên là signature
    result_lines.append(lines[start_line])

    # Tìm docstring
    for child in node.children:
        if child.type == "expression_statement":
            for subchild in child.children:
                if subchild.type == "string":
                    docstring_lines = lines[
                        subchild.start_point[0] : subchild.end_point[0] + 1
                    ]
                    result_lines.extend(["    " + line for line in docstring_lines])
                    break
            break

    # Thêm "..." để indicate body is omitted
    result_lines.append("    ...")

    return "\n".join(result_lines)
