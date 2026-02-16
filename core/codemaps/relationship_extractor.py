"""
Relationship Extractor - Extract relationships từ code

Module này parse code và extract relationships:
- Function calls (CALLS)
- Class inheritance (INHERITS)
- Imports (IMPORTS) - reuse từ dependency_resolver
"""

import os
from pathlib import Path
from typing import Optional, Set
from tree_sitter import Parser, Language, Query, QueryCursor  # type: ignore

from core.codemaps.types import Relationship, RelationshipKind
from core.smart_context.config import get_config_by_extension
from core.smart_context.loader import get_language
from core.codemaps.queries import (
    QUERY_PYTHON_CALLS,
    QUERY_PYTHON_INHERITANCE,
    QUERY_JS_CALLS,
    QUERY_JS_INHERITANCE,
    QUERY_JS_IMPORTS,
    QUERY_GO_CALLS,
    QUERY_RUST_CALLS,
    QUERY_RUST_INHERITANCE,
)
from core.dependency_resolver import DependencyResolver


def extract_relationships(
    file_path: str,
    content: str,
    known_symbols: Optional[Set[str]] = None,
    tree=None,
    language: Optional[Language] = None,
) -> list[Relationship]:
    """
    Extract tất cả relationships từ file content.

    Args:
        file_path: Đường dẫn file (để xác định ngôn ngữ)
        content: Nội dung raw của file
        known_symbols: Set các symbol names trong workspace (optional)
        tree: Pre-parsed AST tree (optional, để reuse từ smart_parse)
        language: Pre-loaded language (optional, để reuse)

    Returns:
        List các Relationship objects

    PERFORMANCE: Nếu tree được truyền vào, skip parsing -> ~50% faster
    """
    # Lấy file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lstrip(".")

    # Get language config
    config = get_config_by_extension(ext)
    if not config:
        return []

    # Reuse language nếu được truyền vào
    if language is None:
        language = get_language(ext)
    if not language:
        return []

    try:
        # Reuse tree nếu được truyền vào (OPTIMIZATION)
        if tree is None:
            parser = Parser(language)
            tree = parser.parse(bytes(content, "utf-8"))

        if not tree or not tree.root_node:
            return []

        relationships: list[Relationship] = []

        # Extract function calls
        calls = _extract_calls(language, tree, content, ext, file_path)
        relationships.extend(calls)

        # Extract class inheritance
        inheritance = _extract_inheritance(language, tree, content, ext, file_path)
        relationships.extend(inheritance)

        # Extract imports (currently for JS/TS)
        imports = _extract_imports(language, tree, content, ext, file_path)
        relationships.extend(imports)

        # Filter by known_symbols nếu có
        if known_symbols:
            relationships = [
                r for r in relationships if r.target in known_symbols or "." in r.target
            ]

        return relationships

    except Exception as e:
        from core.logging_config import log_debug

        log_debug(f"[RelationshipExtractor] Failed for {file_path}: {e}")
        return []


def _extract_calls(
    language: Language, tree, content: str, ext: str, file_path: str
) -> list[Relationship]:
    """
    Extract function/method calls từ AST.

    Returns:
        List Relationship với kind=CALLS
    """
    # Select query based on language
    query_map = {
        "py": QUERY_PYTHON_CALLS,
        "pyw": QUERY_PYTHON_CALLS,
        "js": QUERY_JS_CALLS,
        "jsx": QUERY_JS_CALLS,
        "ts": QUERY_JS_CALLS,
        "tsx": QUERY_JS_CALLS,
        "go": QUERY_GO_CALLS,
        "rs": QUERY_RUST_CALLS,
    }

    query_string = query_map.get(ext)
    if not query_string:
        return []

    try:
        query = Query(language, query_string)
        query_cursor = QueryCursor(query)
        captures = query_cursor.captures(tree.root_node)

        relationships: list[Relationship] = []
        lines = content.split("\n")

        # OPTIMIZATION: Build function boundaries map once
        boundaries_map = _build_function_boundaries_map(tree.root_node, lines)

        for capture_name, nodes in captures.items():
            for node in nodes:
                # Extract function/method name
                start_row = node.start_point[0]
                start_col = node.start_point[1]
                end_col = node.end_point[1]

                if start_row >= len(lines):
                    continue

                target_name = lines[start_row][start_col:end_col]

                # Determine source using fast lookup (O(n) instead of O(n*tree_depth))
                source = _find_enclosing_function_fast(start_row, boundaries_map)
                if not source:
                    source = file_path  # Fallback to file-level

                relationships.append(
                    Relationship(
                        source=source,
                        target=target_name,
                        kind=RelationshipKind.CALLS,
                        source_line=start_row + 1,
                    )
                )

        return relationships

    except Exception:
        return []


def _extract_inheritance(
    language: Language, tree, content: str, ext: str, file_path: str
) -> list[Relationship]:
    """
    Extract class inheritance từ AST.

    Returns:
        List Relationship với kind=INHERITS
    """
    # JS/TS: handle directly from AST to support member-expression heritage
    if ext in {"js", "jsx", "ts", "tsx", "mjs", "cjs", "mts", "cts"}:
        return _extract_js_ts_inheritance(tree)

    # Select query based on language
    query_map = {
        "py": QUERY_PYTHON_INHERITANCE,
        "pyw": QUERY_PYTHON_INHERITANCE,
        "js": QUERY_JS_INHERITANCE,
        "jsx": QUERY_JS_INHERITANCE,
        "ts": QUERY_JS_INHERITANCE,
        "tsx": QUERY_JS_INHERITANCE,
        "rs": QUERY_RUST_INHERITANCE,
    }

    query_string = query_map.get(ext)
    if not query_string:
        return []

    try:
        query = Query(language, query_string)
        query_cursor = QueryCursor(query)
        captures = query_cursor.captures(tree.root_node)

        relationships: list[Relationship] = []
        lines = content.split("\n")

        # Group captures by class
        class_bases: dict[str, list[tuple[str, int]]] = {}

        for capture_name, nodes in captures.items():
            for node in nodes:
                start_row = node.start_point[0]
                start_col = node.start_point[1]
                end_col = node.end_point[1]

                if start_row >= len(lines):
                    continue

                name = lines[start_row][start_col:end_col]

                if "class.name" in capture_name:
                    if name not in class_bases:
                        class_bases[name] = []
                elif (
                    "class.base" in capture_name
                    or "class.base_attr" in capture_name
                    or "impl.trait" in capture_name
                ):
                    # Find corresponding class name
                    for class_name in class_bases.keys():
                        class_bases[class_name].append((name, start_row + 1))

        # Convert to Relationship objects
        for class_name, bases in class_bases.items():
            for base_name, line in bases:
                relationships.append(
                    Relationship(
                        source=class_name,
                        target=base_name,
                        kind=RelationshipKind.INHERITS,
                        source_line=line,
                    )
                )

        return relationships

    except Exception:
        return []


def _extract_js_ts_inheritance(tree) -> list[Relationship]:
    """Extract inheritance for JS/TS class declarations from AST nodes."""
    relationships: list[Relationship] = []

    def _walk(node) -> None:
        if node.type == "class_declaration":
            class_name = None
            base_name = None

            for child in node.children:
                if child.type == "identifier" and class_name is None:
                    class_name = child.text.decode("utf-8") if child.text else None
                elif child.type == "class_heritage":
                    for heritage_child in child.children:
                        if heritage_child.type in {"identifier", "member_expression"}:
                            base_name = (
                                heritage_child.text.decode("utf-8")
                                if heritage_child.text
                                else None
                            )
                            break

            if class_name and base_name:
                relationships.append(
                    Relationship(
                        source=class_name,
                        target=base_name,
                        kind=RelationshipKind.INHERITS,
                        source_line=node.start_point[0] + 1,
                    )
                )

        for child in node.children:
            _walk(child)

    _walk(tree.root_node)
    return relationships


def _extract_imports(
    language: Language, tree, content: str, ext: str, file_path: str
) -> list[Relationship]:
    """Extract imports for JS/TS and resolve to workspace-relative modules when possible."""
    if ext not in {"js", "jsx", "ts", "tsx", "mjs", "cjs", "mts", "cts"}:
        return []

    try:
        query = Query(language, QUERY_JS_IMPORTS)
        query_cursor = QueryCursor(query)
        captures = query_cursor.captures(tree.root_node)

        source_path = os.path.abspath(file_path)
        source_dir = os.path.dirname(source_path)
        resolver = DependencyResolver(Path(source_dir))

        relationships: list[Relationship] = []
        seen: set[tuple[str, int]] = set()
        lines = content.split("\n")

        for _capture_name, nodes in captures.items():
            for node in nodes:
                start_row = node.start_point[0]
                start_col = node.start_point[1]
                end_col = node.end_point[1]

                if start_row >= len(lines):
                    continue

                raw_import = lines[start_row][start_col:end_col].strip().strip("\"'")
                if not raw_import:
                    continue

                # Try resolve via resolver. If unresolved, keep raw module path.
                target = raw_import
                resolved = resolver.resolve_js_import(raw_import, Path(source_dir))
                if resolved:
                    try:
                        target = str(resolved.resolve())
                    except Exception:
                        target = str(resolved)

                key = (target, start_row + 1)
                if key in seen:
                    continue
                seen.add(key)

                relationships.append(
                    Relationship(
                        source=source_path,
                        target=target,
                        kind=RelationshipKind.IMPORTS,
                        source_line=start_row + 1,
                    )
                )

        return relationships
    except Exception:
        return []


def _build_function_boundaries_map(
    root_node, lines: list[str]
) -> list[tuple[int, int, str]]:
    """
    Build map of function boundaries một lần để lookup via binary search.

    Returns:
        List of (start_line, end_line, function_name) tuples, sorted by start_line ASC

    PERFORMANCE: Build map 1 lần thay vì traverse tree mỗi lần tìm enclosing function.
    Sorted ASC by start_line to enable bisect-based O(log n) lookup.
    """
    boundaries: list[tuple[int, int, str]] = []

    def traverse(node):
        # Check if this node is a function/method definition
        if "function" in node.type and "definition" in node.type:
            # Extract function name
            func_name = None
            for child in node.children:
                if "identifier" in child.type or "name" in child.type:
                    start_row = child.start_point[0]
                    start_col = child.start_point[1]
                    end_col = child.end_point[1]
                    if start_row < len(lines):
                        func_name = lines[start_row][start_col:end_col]
                        break

            if func_name:
                boundaries.append((node.start_point[0], node.end_point[0], func_name))

        # Recursively process children
        for child in node.children:
            traverse(child)

    traverse(root_node)
    # Sort by start_line ASC to enable bisect binary search
    return sorted(boundaries, key=lambda x: x[0])


def _find_enclosing_function_fast(
    target_line: int, boundaries_map: list[tuple[int, int, str]]
) -> Optional[str]:
    """
    Tìm enclosing function sử dụng binary search + backward scan.

    Algorithm:
    1. bisect_right tìm insertion point cho target_line → O(log n)
    2. Scan ngược từ insertion point tìm innermost function chứa target_line
       → O(k) với k = số nested levels (thường 1-3, rất nhỏ)

    Complexity:
    - Average case: O(log n) — bisect dominates, backward scan chỉ vài bước
    - Worst case: O(n) — khi tất cả functions đều nested (rất hiếm)
    - Nhanh hơn linear scan đáng kể cho files có nhiều functions (>50)

    Args:
        target_line: Line number của target node (0-indexed)
        boundaries_map: Pre-built function boundaries, PHẢI sorted by start_line ASC

    Returns:
        Function name hoặc None
    """
    from bisect import bisect_right

    if not boundaries_map:
        return None

    # bisect_right: tìm index sao cho tất cả entries trước nó có start_line <= target_line
    # Dùng tuple comparison: (target_line + 1,) > (target_line, ...) luôn đúng
    # nên bisect_right cho ta vị trí ngay sau entry cuối cùng có start_line <= target_line
    idx = bisect_right(boundaries_map, (target_line,))

    # Scan ngược từ idx-1 để tìm innermost enclosing function
    # Innermost = function có start_line lớn nhất mà vẫn chứa target_line
    # Vì sorted ASC, entry gần idx nhất là innermost candidate
    best_name: Optional[str] = None

    for i in range(idx - 1, -1, -1):
        start_line, end_line, func_name = boundaries_map[i]

        if start_line > target_line:
            continue  # Shouldn't happen due to bisect, but safety check

        if start_line <= target_line <= end_line:
            # Found enclosing function. Vì ta scan từ cao → thấp start_line,
            # match đầu tiên là innermost (start_line lớn nhất)
            return func_name

        # Optimization: nếu end_line < target_line VÀ ta đã rời khỏi vùng
        # có thể chứa target, các entries trước đó cũng không thể chứa
        # (trừ khi có outer function bao quanh). Tiếp tục scan để tìm outer.
        # Nhưng nếu đã tìm được best_name, có thể break sớm hơn.

    return best_name


def _find_enclosing_function(root_node, target_node, lines: list[str]) -> Optional[str]:
    """
    Tìm function/method chứa target_node.

    DEPRECATED: Sử dụng _find_enclosing_function_fast với boundaries map để performance tốt hơn.

    Returns:
        Function/method name hoặc None
    """

    def traverse(node, target):
        # Check if this node is a function/method definition
        if "function" in node.type and "definition" in node.type:
            # Check if target is inside this function
            if (
                node.start_point[0] <= target.start_point[0] <= node.end_point[0]
                and node.start_point[0] <= target.end_point[0] <= node.end_point[0]
            ):
                # Extract function name
                for child in node.children:
                    if "identifier" in child.type or "name" in child.type:
                        start_row = child.start_point[0]
                        start_col = child.start_point[1]
                        end_col = child.end_point[1]
                        if start_row < len(lines):
                            return lines[start_row][start_col:end_col]

        # Recursively search children
        for child in node.children:
            result = traverse(child, target)
            if result:
                return result

        return None

    return traverse(root_node, target_node)
