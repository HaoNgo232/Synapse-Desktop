"""
Smart Context Parser - Tree-sitter Code Structure Extraction

Module chính để parse code và trích xuất cấu trúc (classes, functions, docstrings).
Sử dụng Tree-sitter để phân tích code theo ngôn ngữ.
"""

import os
from typing import Optional
from tree_sitter import Parser, Node

from core.smart_context.languages import get_language, is_supported

# Các loại node type cần capture cho Python
PYTHON_CAPTURE_TYPES = {
    "class_definition",
    "function_definition",
    "decorated_definition",
    "import_statement",
    "import_from_statement",
}

# Các loại node type cần capture cho JavaScript/TypeScript
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

    Args:
        file_path: Đường dẫn file (để xác định ngôn ngữ)
        content: Nội dung raw của file

    Returns:
        String chứa các code chunks (signatures, docstrings) hoặc None nếu không hỗ trợ
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

        # Xác định capture types dựa trên ngôn ngữ
        if ext in ("py", "pyw"):
            capture_types = PYTHON_CAPTURE_TYPES
        else:
            capture_types = JAVASCRIPT_CAPTURE_TYPES

        # Thu thập các chunks
        chunks = _extract_chunks(tree.root_node, content, capture_types)

        if not chunks:
            return None

        # Nối các chunks với separator
        return f"\n{CHUNK_SEPARATOR}\n".join(chunks)

    except Exception:
        # Nếu có lỗi parse, trả về None (không fallback)
        return None


def _extract_chunks(node: Node, content: str, capture_types: set[str]) -> list[str]:
    """
    Đệ quy duyệt AST và trích xuất các chunks phù hợp.

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
        # (tránh duplicate nested functions/classes)
        return chunks

    # Đệ quy vào children
    for child in node.children:
        chunks.extend(_extract_chunks(child, content, capture_types))

    return chunks


def _extract_signature(node: Node, content: str) -> Optional[str]:
    """
    Trích xuất signature (header + docstring) từ một node.

    Với function/class: lấy dòng đầu (signature) + docstring nếu có.
    Với import: lấy nguyên dòng import.

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
        # Lấy tất cả decorators và function signature
        result_lines = []
        for child in node.children:
            if child.type == "decorator":
                # Decorator thường 1 dòng
                result_lines.append(lines[child.start_point[0]])
            elif child.type in ("function_definition", "class_definition"):
                # Lấy signature và docstring của function/class bên trong
                sig = _extract_signature(child, content)
                if sig:
                    result_lines.append(sig)
        return "\n".join(result_lines) if result_lines else None

    # Với function/class: lấy signature (dòng đầu) + docstring
    result_lines = []

    # Dòng đầu tiên là signature (def foo(...): hoặc class Foo:)
    result_lines.append(lines[start_line])

    # Tìm docstring (thường là child đầu tiên loại string/expression_statement)
    for child in node.children:
        # Python: docstring là expression_statement chứa string
        if child.type == "expression_statement":
            for subchild in child.children:
                if subchild.type == "string":
                    docstring_lines = lines[
                        subchild.start_point[0] : subchild.end_point[0] + 1
                    ]
                    result_lines.extend(["    " + line for line in docstring_lines])
                    break
            break
        # JS/TS: comment trước có thể là JSDoc (đơn giản hoá, bỏ qua cho MVP)

    # Thêm "..." để indicate body is omitted
    result_lines.append("    ...")

    return "\n".join(result_lines)
