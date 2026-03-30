"""
Smart Context Parser - Tree-sitter Code Structure Extraction

Hợp nhất với Code Map Engine: Sử dụng Query-based (SCM) chuẩn hóa từ Domain.
Cung cấp khả năng trích xuất cấu trúc code đa ngôn ngữ chính xác cao cho Smart Context.
"""

import logging
import os
import threading
from typing import Optional, List

logger = logging.getLogger(__name__)

# Chunk separator giống Repomix
CHUNK_SEPARATOR = "⋮----"

# LRU Cache cho relationships
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
    file_path: str, content: str, include_relationships: bool = False
) -> Optional[str]:
    """
    Parse file content và trích xuất cấu trúc code (Smart Context).
    SỬ DỤNG CHUNG ENGINE VỚI CODE MAP ĐỂ ĐẠT ĐỘ CHÍNH XÁC CAO NHẤT.
    """
    # Tránh Circular Import bằng cách import local
    from domain.codemap.symbol_extractor import extract_symbols
    from domain.smart_context.config import is_supported

    _, ext = os.path.splitext(file_path)
    ext = ext.lstrip(".")

    if not is_supported(ext):
        return None

    try:
        # Sử dụng Code Map Engine
        symbols = extract_symbols(file_path, content)
        if not symbols:
            return None

        chunks: List[str] = []
        for s in symbols:
            if s.name == "📍 [ENTRY POINT]":
                chunks.append(f"// {s.signature}")
                continue

            # Format Smart Context tinh gọn
            kind_prefix = f"[{s.kind.name}] " if s.kind.name != "VARIABLE" else ""
            prefix = f"{s.parent} > " if s.parent else ""
            line_info = f" (L{s.line_start}-{s.line_end})"

            chunk = f"{kind_prefix}{prefix}{s.signature}{line_info}"
            chunks.append(chunk)

        result = f"\n{CHUNK_SEPARATOR}\n".join(chunks)

        if include_relationships:
            relationships_section = _build_relationships_section(file_path, content)
            if relationships_section:
                result += f"\n\n{relationships_section}"

        return result

    except Exception as e:
        logger.debug("smart_parse failed: %s", e)
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
