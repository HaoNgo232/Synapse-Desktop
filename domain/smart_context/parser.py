"""
Smart Context Parser - Tree-sitter Code Structure Extraction

Unified with Code Map Engine: Uses standardized Query-based (SCM) from Domain.
Provides high-precision multilingual code structure extraction for Smart Context.
"""

import logging
import os
import threading
from pathlib import Path
from typing import Optional, List

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
) -> Optional[str]:
    """
    Parses file content and extracts code structure (Hybrid Compressed Context).
    According to Opus 4.6 specification:
    Part 1: Project Dependency Graph (If requested/with workspace_root)
    Part 2: Compressed File Contents (Signatures, types, imports - bodies stripped)
    """
    from domain.codemap.symbol_extractor import extract_symbols
    from domain.codemap.relationship_extractor import extract_relationships
    from domain.codemap.types import RelationshipKind
    from domain.smart_context.config import is_supported
    from domain.smart_context.loader import get_language
    from domain.codemap.dependency_graph_generator import DependencyGraphGenerator
    from tree_sitter import Parser

    _, ext = os.path.splitext(file_path)
    ext = ext.lstrip(".")

    if not is_supported(ext):
        return None

    try:
        language = get_language(ext)
        if not language:
            logger.debug(f"Language loader failed for extension: {ext}")
            return None

        parser = Parser(language)
        tree = parser.parse(bytes(content, "utf-8"))

        # 1. Extract Symbols (Signatures)
        symbols = extract_symbols(file_path, content)
        # Don't return None immediately here; try to get at least imports

        # 2. Extract Imports
        relationships = extract_relationships(
            file_path,
            content,
            tree=tree,
            language=language,
            workspace_root=Path(workspace_root) if workspace_root else None,
        )
        imports = [r for r in relationships if r.kind == RelationshipKind.IMPORTS]

        # Get raw import lines from content
        lines = content.split("\n")
        import_lines = []
        seen_import_rows = set()
        for imp in imports:
            row = imp.source_line - 1
            if row < len(lines) and row not in seen_import_rows:
                import_lines.append(lines[row].strip())
                seen_import_rows.add(row)

        chunks: List[str] = []

        # Add imports to the beginning (if any)
        if import_lines:
            chunks.append("\n".join(import_lines))

        # 3. Add Symbol Signatures
        if symbols:
            for s in symbols:
                if s.name == "[ENTRY POINT]":
                    chunks.append(f"// {s.signature}")
                    continue
                # Signature extraction (already contains decorators/docstrings from SymbolExtractor)
                chunk = s.signature if s.signature else s.name
                chunks.append(chunk)
        elif not import_lines:
            # If both symbols and imports are missing, the file is either empty or structure parsing failed
            return f"// FILE: {file_path} (Empty or unextractable)"

        # Assemble Compressed Content
        compressed_content = f"\n{CHUNK_SEPARATOR}\n".join(chunks)

        # 4. Part 1: Dependency Graph (Only if requested and multiple files context is provided)
        if workspace_root and all_files_content:
            graph_gen = DependencyGraphGenerator(Path(workspace_root))
            graph_output = graph_gen.generate_graph(all_files_content)
            if graph_output:
                return f"{graph_output}\n\n{SECTION_SEPARATOR}\n\n{compressed_content}"

        return compressed_content

    except Exception as e:
        logger.error("smart_parse failed for %s: %s", file_path, e, exc_info=True)
        return None


def _build_relationships_section(
    file_path: str, content: str, tree=None, language=None
) -> Optional[str]:
    """Build relationships section."""
    content_key = str(hash(content))
    cached = _get_cached_relationships(file_path, content_key)
    if cached is not None:
        return cached if cached else None

    try:
        from domain.codemap.relationship_extractor import extract_relationships
        from domain.codemap.types import RelationshipKind

        relationships = extract_relationships(
            file_path, content, tree=tree, language=language
        )
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
