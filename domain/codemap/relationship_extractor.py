"""
Relationship Extractor - Extracts relationships from code

This module parses code and extracts relationships:
- Function calls (CALLS)
- Class inheritance (INHERITS)
- Imports (IMPORTS) - reused from dependency_resolver
"""

import os
from pathlib import Path
from typing import Optional, Set
from tree_sitter import Parser, Language, Query, QueryCursor  # type: ignore

from domain.codemap.types import Relationship, RelationshipKind
from domain.smart_context.config import get_config_by_extension
from domain.smart_context.loader import get_language
from domain.codemap.queries import (
    QUERY_PYTHON_CALLS,
    QUERY_PYTHON_INHERITANCE,
    QUERY_JS_CALLS,
    QUERY_JS_INHERITANCE,
    QUERY_GO_CALLS,
    QUERY_RUST_CALLS,
    QUERY_RUST_INHERITANCE,
)
from domain.codemap.dependency_resolver import DependencyResolver


def extract_relationships(
    file_path: str,
    content: str,
    known_symbols: Optional[Set[str]] = None,
    tree=None,
    language: Optional[Language] = None,
    workspace_root: Optional[Path] = None,
) -> list[Relationship]:
    """
    Extracts all relationships from file content.

    Args:
        file_path: File path (to determine language)
        content: Raw content of the file
        known_symbols: Set of symbol names in workspace (optional)
        tree: Pre-parsed AST tree (optional, reuse from smart_parse)
        language: Pre-loaded language (optional, reuse)

    Returns:
        List of Relationship objects

    PERFORMANCE: If tree is provided, skip parsing -> ~50% faster
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

        # Split lines once and pass to all extractors (OPTIMIZATION)
        lines = content.split("\n")

        # Extract function calls
        calls = _extract_calls(language, tree, lines, ext, file_path)
        relationships.extend(calls)

        # Extract class inheritance
        inheritance = _extract_inheritance(language, tree, lines, ext, file_path)
        relationships.extend(inheritance)

        # Extract imports (resolve to workspace-relative modules)
        imports = _extract_imports(
            language, tree, lines, ext, file_path, workspace_root=workspace_root
        )
        relationships.extend(imports)

        # Filter by known_symbols nếu có
        if known_symbols:
            relationships = [
                r for r in relationships if r.target in known_symbols or "." in r.target
            ]

        return relationships

    except Exception as e:
        from shared.logging_config import log_debug

        log_debug(f"[RelationshipExtractor] Failed for {file_path}: {e}")
        return []


def _extract_calls(
    language: Language, tree, lines: list[str], ext: str, file_path: str
) -> list[Relationship]:
    """
    Extracts function/method calls from AST.

    Args:
        lines: Pre-split lines from content (OPTIMIZATION)

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
    language: Language, tree, lines: list[str], ext: str, file_path: str
) -> list[Relationship]:
    """
    Extracts class inheritance from AST.

    Args:
        lines: Pre-split lines from content (OPTIMIZATION)

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

        # Flatten and sort captures by document order to match class with its bases
        flat_captures = []
        for capture_name, nodes in captures.items():
            for node in nodes:
                flat_captures.append((node, capture_name))
        flat_captures.sort(key=lambda x: (x[0].start_point[0], x[0].start_point[1]))

        # Group captures by class
        class_bases: dict[str, list[tuple[str, int]]] = {}
        current_class: Optional[str] = None

        for node, capture_name in flat_captures:
            start_row = node.start_point[0]
            start_col = node.start_point[1]
            end_col = node.end_point[1]

            if start_row >= len(lines):
                continue

            name = lines[start_row][start_col:end_col]

            if "class.name" in capture_name:
                current_class = name
                if name not in class_bases:
                    class_bases[name] = []
            elif current_class and (
                "class.base" in capture_name
                or "class.base_attr" in capture_name
                or "impl.trait" in capture_name
            ):
                class_bases[current_class].append((name, start_row + 1))

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
    language: Language,
    tree,
    lines: list[str],
    ext: str,
    file_path: str,
    workspace_root: Optional[Path] = None,
) -> list[Relationship]:
    """
    Extract imports for JS/TS and resolve to workspace-relative modules when possible.

    Args:
        lines: Pre-split lines from content (OPTIMIZATION)
    """
    source_path = os.path.abspath(file_path)
    source_dir = os.path.dirname(source_path)

    # Use workspace_root if available, fallback to source_dir
    root = workspace_root if workspace_root else Path(source_dir)
    resolver = DependencyResolver(root)

    # Build file index if workspace_root is provided to enable reliable resolution
    if workspace_root:
        resolver.build_file_index_from_disk(workspace_root)

    lang_name = resolver._get_lang_name(ext)
    if not lang_name:
        return []

    try:
        from domain.codemap.dependency_resolver import IMPORT_QUERIES

        query_string = IMPORT_QUERIES.get(lang_name, "")
        if not query_string:
            return []

        query = Query(language, query_string)
        query_cursor = QueryCursor(query)
        captures = query_cursor.captures(tree.root_node)

        relationships: list[Relationship] = []
        seen: set[tuple[str, int]] = set()

        for capture_name, nodes in captures.items():
            for node in nodes:
                # Extract row from the first node (if nodes is a list)
                # Our query usually only captures 1 node for 1 capture name
                start_row = node.start_point[0]
                start_col = node.start_point[1]
                end_col = node.end_point[1]

                if start_row >= len(lines):
                    continue

                raw_import = lines[start_row][start_col:end_col].strip().strip("\"'")
                # Remove < > in C++ includes
                if raw_import.startswith("<") and raw_import.endswith(">"):
                    raw_import = raw_import[1:-1]

                if not raw_import:
                    continue

                # JS/TS specific: resolution might be needed for file-to-file
                target = raw_import
                if lang_name in {"javascript", "typescript"}:
                    resolved = resolver.resolve_js_import(raw_import, Path(source_dir))
                    if resolved:
                        try:
                            target = str(resolved.resolve())
                        except Exception:
                            target = str(resolved)
                elif lang_name == "python":
                    resolved = resolver._resolve_python_import(
                        raw_import, Path(source_dir)
                    )
                    if resolved:
                        try:
                            target = str(resolved.resolve())
                        except Exception:
                            target = str(resolved)
                elif lang_name == "go":
                    # Go imports in AST include quotes, strip them for the target path
                    target = raw_import.strip('"')
                else:
                    pass

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
    Builds a map of function boundaries once for lookup via binary search.

    Returns:
        List of (start_line, end_line, function_name) tuples, sorted by start_line ASC

    PERFORMANCE: Build map once instead of traversing the tree each time to find enclosing function.
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
    Finds enclosing function using binary search + backward scan.

    Algorithm:
    1. bisect_right finds insertion point for target_line → O(log n)
    2. Backward scan from insertion point to find the innermost function containing target_line
       → O(k) where k = number of nested levels (usually 1-3, very small)

    Complexity:
    - Average case: O(log n) — bisect dominates, backward scan only a few steps
    - Worst case: O(n) — when all functions are nested (very rare)
    - Significantly faster than linear scan for files with many functions (>50)

    Args:
        target_line: Line number of target node (0-indexed)
        boundaries_map: Pre-built function boundaries, MUST BE sorted by start_line ASC

    Returns:
        Function name or None
    """
    from bisect import bisect_right

    if not boundaries_map:
        return None

    # bisect_right: find index such that all entries before it have start_line <= target_line
    # Use key function to only compare start_line (first element of the tuple)
    idx = bisect_right(boundaries_map, target_line, key=lambda x: x[0])

    # Backward scan from idx-1 to find the innermost enclosing function
    # Innermost = function with the largest start_line that still contains target_line
    # Since sorted ASC, entry closest to idx is the innermost candidate
    best_name: Optional[str] = None

    for i in range(idx - 1, -1, -1):
        start_line, end_line, func_name = boundaries_map[i]

        if start_line > target_line:
            continue  # Shouldn't happen due to bisect, but safety check

        if start_line <= target_line <= end_line:
            # Found enclosing function. Since we scan from high → low start_line,
            # the first match is the innermost (highest start_line)
            return func_name

        # Optimization: if end_line < target_line AND we have left the area
        # that could contain target, previous entries cannot contain it either
        # (unless there is an outer function wrapping around). Continue scanning for outer.
        # But if best_name is already found, we could break earlier.

    return best_name


def _find_enclosing_function(root_node, target_node, lines: list[str]) -> Optional[str]:
    """
    Finds the function/method containing target_node.

    DEPRECATED: Use _find_enclosing_function_fast with boundaries map for better performance.

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
