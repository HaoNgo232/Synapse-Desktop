"""
Smart Context Parser - Tree-sitter Code Structure Extraction

Unified with Code Map Engine: Uses standardized Query-based (SCM) from Domain.
Provides high-precision multilingual code structure extraction for Smart Context.
"""

import logging
import os
import threading
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Chunk separator as per Opus 4.6 specification
CHUNK_SEPARATOR = "⋮----"
SECTION_SEPARATOR = "⋮----"  # Used for both Part 1 and Part 2 separation

# LRU Cache for relationships
_CACHE_MAX_SIZE = int(os.environ.get("SYNAPSE_RELATIONSHIP_CACHE_SIZE", "128"))
_RELATIONSHIPS_CACHE: dict[str, str] = {}
_CACHE_LOCK = threading.Lock()


def _get_cache_key(file_path: str, content_hash: str) -> str:
    return f"{file_path}:{content_hash}"


def _get_cached_relationships(file_path: str, content_hash: str) -> Optional[str]:
    with _CACHE_LOCK:
        key = _get_cache_key(file_path, content_hash)
        return _RELATIONSHIPS_CACHE.get(key)


def _cache_relationships(
    file_path: str, content_hash: str, result: Optional[str]
) -> None:
    with _CACHE_LOCK:
        if len(_RELATIONSHIPS_CACHE) >= _CACHE_MAX_SIZE:
            keys_to_remove = list(_RELATIONSHIPS_CACHE.keys())[: _CACHE_MAX_SIZE // 4]
            for k in keys_to_remove:
                _RELATIONSHIPS_CACHE.pop(k, None)
        key = _get_cache_key(file_path, content_hash)
        _RELATIONSHIPS_CACHE[key] = result if result else ""


def smart_parse(
    file_path: str,
    content: str,
    include_relationships: bool = False,
    workspace_root: Optional[str] = None,
    all_files_content: Optional[dict[str, str]] = None,
    resolver: Optional[Any] = None,  # NEW: hỗ trợ inject resolver
) -> Optional[str]:
    """
    Parses file content and extracts code structure (Hybrid Compressed Context).
    According to Opus 4.6 specification:
    Part 1: Project Dependency Graph (If requested/with workspace_root)
    Part 2: Compressed File Contents (Signatures, types, imports - bodies stripped)
    """
    from domain.ports.registry import DomainRegistry
    from domain.smart_context.config import is_supported
    from domain.codemap.dependency_graph_generator import DependencyGraphGenerator

    _, ext = os.path.splitext(file_path)
    ext = ext.lstrip(".")

    if not is_supported(ext):
        return None

    try:
        # Extract via the centralized port DTO
        info = DomainRegistry.code_intelligence().parse_file(Path(file_path), content)

        # Assemble Compressed Content with Intelligent Separator
        compressed_content = ""
        last_line = -1

        # Add Symbol Signatures (Imports first)
        if info.imports:
            compressed_content += "\n".join(info.imports)
            last_line = -1

        if info.symbols:
            for s in info.symbols:
                if s.name == "[ENTRY POINT]":
                    if compressed_content:
                        compressed_content += f"\n{CHUNK_SEPARATOR}\n"
                    compressed_content += f"// {s.signature}"
                    last_line = s.line_end
                    continue

                # Check for gap between symbols to insert separator
                if last_line != -1 and s.line_start > last_line + 1:
                    if not compressed_content.endswith(f"{CHUNK_SEPARATOR}\n"):
                        compressed_content += f"\n{CHUNK_SEPARATOR}\n"
                elif compressed_content and not compressed_content.endswith("\n"):
                    compressed_content += "\n"

                # Indentation based on nesting
                indent = "  " if s.parent else ""

                # Signature extraction (already contains decorators/docstrings from SymbolExtractor)
                sig = s.signature if s.signature else s.name

                # Thêm indent cho từng dòng của signature (nếu đa dòng)
                indented_sig = "\n".join(
                    [indent + line_text for line_text in sig.split("\n")]
                )
                compressed_content += indented_sig
                last_line = s.line_end

        # Build and Append Relationships Section if requested
        if include_relationships:
            rel_section = _build_relationships_section(
                file_path, content, info=info
            )
            if rel_section:
                compressed_content += f"\n\n{rel_section}"

        # Part 1: Dependency Graph (Only if requested and multiple files context is provided)
        if workspace_root and all_files_content:
            # Inject resolver để tránh rebuild index (Full Directory Walk)
            graph_gen = DependencyGraphGenerator(
                Path(workspace_root), resolver=resolver
            )
            graph_output = graph_gen.generate_graph(all_files_content)
            if graph_output:
                return f"{graph_output}\n\n{SECTION_SEPARATOR}\n\n{compressed_content}"

        return compressed_content

    except Exception as e:
        logger.error("smart_parse failed for %s: %s", file_path, e, exc_info=True)
        return None


def _extract_import_texts(tree: Any, content: str) -> list[str]:
    """
    Trích xuất toàn bộ text của các import statements từ AST.

    Khác với cách cũ (dùng Relationship.source_line để lấy 1 dòng),
    hàm này walk trực tiếp AST tree để lấy node.text - đảm bảo lấy đủ
    toàn bộ multi-line imports như:
        from PySide6.QtWidgets import (
            QWidget,
            QVBoxLayout,
        )

    Args:
        tree: Tree-sitter parse tree
        content: Raw file content (dùng để fallback nếu node.text là None)

    Returns:
        Danh sách import text strings, theo thứ tự xuất hiện trong file.
    """
    # Node types cần lấy text (Python, JS/TS, Go, Rust, Java, C#...)
    IMPORT_NODE_TYPES = {
        # Python
        "import_statement",
        "import_from_statement",
        # JS/TS
        "import_declaration",
        "import_statement",
        # Go
        "import_declaration",
        "import_spec",
        # Rust
        "use_declaration",
        # Java
        "import_declaration",
        # C#
        "using_directive",
        # C/C++
        "preproc_include",
        # Ruby
        "require",
    }

    if not tree or not tree.root_node:
        return []

    lines = content.split("\n")
    import_texts: list[str] = []
    seen_positions: set[tuple[int, int]] = set()

    def walk(node: Any) -> None:
        if node.type in IMPORT_NODE_TYPES:
            pos = (node.start_point[0], node.end_point[0])
            if pos not in seen_positions:
                seen_positions.add(pos)
                # Lấy text trực tiếp từ node (bao gồm toàn bộ multi-line)
                if node.text is not None:
                    text = node.text.decode("utf-8", errors="replace").strip()
                else:
                    # Fallback: cắt từ raw content theo row/col
                    start_row, start_col = node.start_point
                    end_row, end_col = node.end_point
                    if start_row == end_row:
                        line_bytes = lines[start_row].encode("utf-8")
                        text = (
                            line_bytes[start_col:end_col]
                            .decode("utf-8", errors="replace")
                            .strip()
                        )
                    else:
                        node_lines = []
                        for r in range(start_row, end_row + 1):
                            if r >= len(lines):
                                break
                            line = lines[r]
                            if r == start_row:
                                node_lines.append(line[start_col:])
                            elif r == end_row:
                                node_lines.append(line[:end_col])
                            else:
                                node_lines.append(line)
                        text = "\n".join(node_lines).strip()

                if text:
                    import_texts.append(text)
            # Không đi sâu vào con của import node (tránh duplicate)
            return

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return import_texts


def _build_relationships_section(
    file_path: str, content: str, tree=None, language=None, info=None
) -> Optional[str]:
    """Build relationships section."""
    content_key = str(hash(content))
    cached = _get_cached_relationships(file_path, content_key)
    if cached is not None:
        return cached if cached else None

    try:
        from domain.codemap.types import RelationshipKind

        if info is not None:
            relationships = info.relationships
        else:
            from domain.codemap.relationship_extractor import extract_relationships
            from domain.smart_context.loader import get_language
            from tree_sitter import Parser
            import os

            _, ext = os.path.splitext(file_path)
            ext = ext.lstrip(".")
            language = get_language(ext)
            if language:
                try:
                    parser = Parser(language)
                    tree = parser.parse(bytes(content, "utf-8"))
                    relationships = extract_relationships(
                        file_path, content, tree=tree, language=language
                    )
                except Exception:
                    relationships = []
            else:
                relationships = []

        if not relationships:
            _cache_relationships(file_path, content_key, "")
            return None

        calls = [r for r in relationships if r.kind == RelationshipKind.CALLS]
        inherits = [r for r in relationships if r.kind == RelationshipKind.INHERITS]
        imports = [r for r in relationships if r.kind == RelationshipKind.IMPORTS]

        lines = ["## Relationships"]
        if calls:
            lines.append("\n### Function Calls")
            for rel in calls[:20]:
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
            for rel in imports[:15]:
                lines.append(f"- Imports `{rel.target}` (line {rel.source_line})")

        result = "\n".join(lines)
        _cache_relationships(file_path, content_key, result)
        return result
    except Exception as e:
        logger.debug("_build_relationships_section failed: %s", e)
        return None

