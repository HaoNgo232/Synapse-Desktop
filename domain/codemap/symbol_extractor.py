"""
Symbol Extractor - Extract symbols từ code sử dụng Tree-sitter

Module này parse code và extract tất cả symbols (classes, functions, methods, variables)
với metadata (line numbers, signatures, parent).
"""

import os
from typing import Optional
from tree_sitter import Parser, Node  # type: ignore

from domain.codemap.types import Symbol, SymbolKind
from domain.smart_context.config import get_config_by_extension
from domain.smart_context.loader import get_language


def extract_symbols(file_path: str, content: str) -> list[Symbol]:
    """
    Extract tất cả symbols từ file content.

    Args:
        file_path: Đường dẫn file (để xác định ngôn ngữ)
        content: Nội dung raw của file

    Returns:
        List các Symbol objects

    Example:
        >>> symbols = extract_symbols("app.py", "class Foo:\\n    def bar(self): pass")
        >>> len(symbols)
        2
        >>> symbols[0].kind
        SymbolKind.CLASS
    """
    # Lấy file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lstrip(".")

    # Get language config
    config = get_config_by_extension(ext)
    if not config:
        return []

    language = get_language(ext)
    if not language:
        return []

    try:
        # Parse content
        parser = Parser(language)
        tree = parser.parse(bytes(content, "utf-8"))

        if not tree or not tree.root_node:
            return []

        # Extract symbols từ AST
        symbols: list[Symbol] = []
        lines = content.split("\n")
        _extract_symbols_recursive(
            tree.root_node, lines, file_path, symbols, parent=None
        )

        return symbols

    except Exception:
        return []


def _extract_symbols_recursive(
    node: Node,
    lines: list[str],
    file_path: str,
    symbols: list[Symbol],
    parent: Optional[str] = None,
) -> None:
    """
    Recursively extract symbols từ AST node.

    Args:
        node: Current AST node
        lines: Split file content into lines
        file_path: File path
        symbols: List để append symbols vào
        parent: Parent symbol name (for methods)
    """

    # Check node type và extract symbol
    symbol = _node_to_symbol(node, lines, file_path, parent)
    if symbol:
        symbols.append(symbol)
        # Nếu là class, set làm parent cho children
        if symbol.kind == SymbolKind.CLASS:
            parent = symbol.name

    # Recursively process children
    for child in node.children:
        _extract_symbols_recursive(child, lines, file_path, symbols, parent)


def _node_to_symbol(
    node: Node, lines: list[str], file_path: str, parent: Optional[str]
) -> Optional[Symbol]:
    """
    Convert AST node thành Symbol nếu match.

    Hỗ trợ: Python, JavaScript/TypeScript, Java, Rust.
    """
    node_type = node.type

    # Class / Interface / Struct / Enum (Common types)
    is_class = "class" in node_type and "definition" in node_type  # Python
    is_class_decl = node_type in [
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
    ]  # Java / TS
    is_rust_type = node_type in ["struct_item", "enum_item", "trait_item"]  # Rust

    if is_class or is_class_decl or is_rust_type:
        name = _extract_name(node, lines)
        if name:
            signature = _extract_signature(node, lines)
            kind = SymbolKind.CLASS
            if "interface" in node_type:
                kind = SymbolKind.INTERFACE
            elif "struct" in node_type:
                kind = SymbolKind.STRUCT
            elif "enum" in node_type:
                kind = SymbolKind.ENUM
            elif "trait" in node_type:
                kind = SymbolKind.TRAIT

            return Symbol(
                name=name,
                kind=kind,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=signature,
                parent=None,
            )

    # Function / Method (Common types)
    is_func = "function" in node_type and "definition" in node_type  # Python / TS
    is_java_method = node_type == "method_declaration"  # Java
    is_rust_fn = node_type == "function_item"  # Rust

    if is_func or is_java_method or is_rust_fn:
        name = _extract_name(node, lines)
        if name:
            signature = _extract_signature(node, lines)
            # Nếu có parent (chứa trong class/struct/impl) thì là Method
            kind = SymbolKind.METHOD if parent else SymbolKind.FUNCTION
            return Symbol(
                name=name,
                kind=kind,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=signature,
                parent=parent,
            )

    # Import statement
    if (
        "import" in node_type
        or "use_declaration" in node_type
        or "package_declaration" in node_type
    ):
        name = _extract_import_name(node, lines)
        if name:
            return Symbol(
                name=name,
                kind=SymbolKind.IMPORT,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=lines[node.start_point[0]].strip()
                if node.start_point[0] < len(lines)
                else None,
                parent=None,
            )

    # Variable / Constant assignment (top-level only)
    if not parent and (
        "variable" in node_type
        or "assignment" in node_type
        or "declaration" in node_type
    ):
        name = _extract_name(node, lines)
        if name and node.start_point[0] < len(lines):
            # Chỉ lấy top-level variables (Không thụt đầu dòng)
            line = lines[node.start_point[0]].strip()
            if line and not line.startswith((" ", "\t")):
                return Symbol(
                    name=name,
                    kind=SymbolKind.VARIABLE,
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=line[:100],
                    parent=None,
                )

    return None


def _extract_name(node: Node, lines: list[str]) -> Optional[str]:
    """
    Extract name từ definition node.

    Tìm child node có type chứa 'identifier' hoặc 'name'.
    """
    for child in node.children:
        if "identifier" in child.type or "name" in child.type:
            start_row = child.start_point[0]
            start_col = child.start_point[1]
            end_col = child.end_point[1]
            if start_row < len(lines):
                return lines[start_row][start_col:end_col]
    return None


def _extract_signature(node: Node, lines: list[str]) -> Optional[str]:
    """
    Extract signature từ definition node.

    Lấy dòng đầu tiên của definition (không có body).
    """
    start_row = node.start_point[0]
    if start_row >= len(lines):
        return None

    line = lines[start_row].strip()
    # Remove trailing colon (Python, TypeScript)
    if line.endswith(":"):
        line = line[:-1]
    # Remove trailing braces (C-style)
    if line.endswith("{"):
        line = line[:-1].strip()

    return line


def _extract_import_name(node: Node, lines: list[str]) -> Optional[str]:
    """
    Extract module name từ import statement.

    Hỗ trợ:
    - Python: import foo, from foo import bar
    - Rust: use std::collections::HashMap
    - Java: package com.example, import java.util.List
    """
    target_types = [
        "dotted_name",
        "module",
        "scoped_identifier",
        "use_list",
        "identifier",
        "package_name",
        "scoped_type_identifier",
    ]

    for child in node.children:
        if any(t in child.type for t in target_types):
            start_row = child.start_point[0]
            start_col = child.start_point[1]
            end_col = child.end_point[1]
            if start_row < len(lines):
                return lines[start_row][start_col:end_col]

    return None
