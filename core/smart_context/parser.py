"""
Smart Context Parser - Tree-sitter Code Structure Extraction

Module chính để parse code và trích xuất cấu trúc (classes, functions, docstrings).
Sử dụng Tree-sitter để phân tích code theo ngôn ngữ.

Refactored to use modular config and loader.
"""

import os
import threading
from typing import Optional
from tree_sitter import Parser, Node, Language, Tree  # type: ignore

from core.smart_context.config import is_supported, get_config_by_extension
from core.smart_context.loader import get_language, get_query

# Chunk separator giống Repomix
CHUNK_SEPARATOR = "⋮----"

# LRU Cache cho relationships
# Default 128 files - sufficient for most projects
# For large projects (50k+ files), consider increasing via environment variable
# Set SYNAPSE_RELATIONSHIP_CACHE_SIZE to override (e.g., 8192 or 16384)

_CACHE_MAX_SIZE = int(os.environ.get("SYNAPSE_RELATIONSHIP_CACHE_SIZE", "128"))
_RELATIONSHIPS_CACHE: dict[str, str] = {}
_CACHE_LOCK = threading.Lock()


def _get_cache_key(file_path: str, content_hash: str) -> str:
    """Tạo cache key từ file_path và content_hash."""
    return f"{file_path}:{content_hash}"


def _get_cached_relationships(file_path: str, content_hash: str) -> str | None:
    """
    Lấy cached relationships section.

    Returns:
        Cached string nếu có, None nếu cache miss
        "" (empty string) nếu cached result là 'no relationships'
    """
    with _CACHE_LOCK:
        key = _get_cache_key(file_path, content_hash)
        return _RELATIONSHIPS_CACHE.get(key)


def _cache_relationships(file_path: str, content_hash: str, result: str | None) -> None:
    """
    Cache relationships section.

    Args:
        result: Relationships section string, hoặc "" nếu không có relationships
    """
    with _CACHE_LOCK:
        # Evict oldest entries nếu cache đầy
        if len(_RELATIONSHIPS_CACHE) >= _CACHE_MAX_SIZE:
            # Remove 25% oldest entries (simple LRU approximation)
            keys_to_remove = list(_RELATIONSHIPS_CACHE.keys())[: _CACHE_MAX_SIZE // 4]
            for k in keys_to_remove:
                _RELATIONSHIPS_CACHE.pop(k, None)  # safe if already deleted

        key = _get_cache_key(file_path, content_hash)
        _RELATIONSHIPS_CACHE[key] = result if result else ""


def smart_parse(
    file_path: str, content: str, include_relationships: bool = False
) -> Optional[str]:
    """
    Parse file content và trích xuất cấu trúc code (Smart Context).

    Strategy:
    1. Try query-based parsing first (better quality, from Repomix)
    2. Fallback to node-type based parsing if query fails
    3. Fallback to None if both fail
    4. Optionally append relationships section (CodeMaps)

    Args:
        file_path: Đường dẫn file (để xác định ngôn ngữ)
        content: Nội dung raw của file
        include_relationships: Nếu True, append relationships section (default: False)

    Returns:
        String chứa các code chunks (signatures, docstrings) và relationships (nếu enabled)
        hoặc None nếu không hỗ trợ

    BACKWARD COMPATIBILITY:
    - API signature không đổi (include_relationships default=False)
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
                    # Append relationships section nếu enabled (reuse tree)
                    if include_relationships:
                        relationships_section = _build_relationships_section(
                            file_path, content, tree=tree, language=language
                        )
                        if relationships_section:
                            result += f"\n\n{relationships_section}"
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
        result = f"\n{CHUNK_SEPARATOR}\n".join(chunks)

        # Append relationships section nếu enabled (reuse tree)
        if include_relationships:
            relationships_section = _build_relationships_section(
                file_path, content, tree=tree, language=language
            )
            if relationships_section:
                result += f"\n\n{relationships_section}"

        return result

    except Exception:
        # Nếu có lỗi parse, trả về None
        return None


def _build_relationships_section(
    file_path: str, content: str, tree=None, language=None
) -> Optional[str]:
    """
    Build relationships section cho Smart Context output.

    Extract và format relationships (function calls, class inheritance)
    thành markdown section.

    Args:
        file_path: Đường dẫn file
        content: Nội dung file
        tree: Pre-parsed AST tree (optional, để reuse - PERFORMANCE)
        language: Pre-loaded language (optional)

    Returns:
        Formatted relationships section hoặc None nếu không có relationships

    OPTIMIZATIONS:
    - Truyền tree để tránh double parsing (~50% faster)
    - LRU cache để tránh re-extract (~O(1) cho repeated calls)

    CACHE KEY DESIGN:
    - Uses hash(content) for cache invalidation
    - hash() is fast (O(1) after first call, cached by CPython)
    - Birthday collision probability is negligible for typical use
    - NOTE: hash() is randomized per-process (PYTHONHASHSEED), so cache
      cannot be persisted to disk or shared between processes
    """
    # Use Python's built-in hash (cached, O(1), no allocation)
    content_key = str(hash(content))

    # Check cache
    cached = _get_cached_relationships(file_path, content_key)
    if cached is not None:
        return cached if cached else None  # "" means no relationships

    try:
        from core.codemaps.relationship_extractor import extract_relationships
        from core.codemaps.types import RelationshipKind

        # Extract relationships (reuse tree nếu có)
        relationships = extract_relationships(
            file_path, content, tree=tree, language=language
        )

        if not relationships:
            _cache_relationships(file_path, content_key, "")  # Cache empty result
            return None

        # Group by kind
        calls = [r for r in relationships if r.kind == RelationshipKind.CALLS]
        inherits = [r for r in relationships if r.kind == RelationshipKind.INHERITS]
        imports = [r for r in relationships if r.kind == RelationshipKind.IMPORTS]

        # Build section
        lines = ["## Relationships"]

        if calls:
            lines.append("\n### Function Calls")
            for rel in calls[:20]:  # Limit to 20 để tránh quá dài
                lines.append(
                    f"- `{rel.source}` calls `{rel.target}` (line {rel.source_line})"
                )

        if inherits:
            lines.append("\n### Class Inheritance")
            for rel in inherits:
                lines.append(
                    f"- `{rel.source}` inherits from `{rel.target}` (line {rel.source_line})"
                )

        if imports:
            lines.append("\n### Imports")
            for rel in imports[:15]:  # Limit to 15
                lines.append(f"- Imports `{rel.target}` (line {rel.source_line})")

        result = "\n".join(lines)
        _cache_relationships(file_path, content_key, result)  # Cache result
        return result

    except Exception as e:
        # Debug: log exception để biết tại sao relationships không được append
        import traceback

        print(f"[DEBUG] _build_relationships_section failed: {e}")
        traceback.print_exc()
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
