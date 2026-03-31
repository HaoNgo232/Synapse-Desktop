"""
Symbol Extractor - Extracts symbols from code using Tree-sitter Queries (SCM)
"""

from pathlib import Path
from typing import Optional, List, Set, Tuple
from tree_sitter import Parser, Node, Query, QueryCursor  # type: ignore

from domain.codemap.types import Symbol, SymbolKind
from domain.smart_context.loader import get_language


def extract_symbols(file_path: str, content: str) -> List[Symbol]:
    """
    Extracts all symbols using Tree-sitter Queries (SCM).
    Queries reside in domain/codemap/queries/ to ensure Domain-driven architecture.
    """
    suffix = Path(file_path).suffix
    if not suffix:
        return []

    ext = suffix.lstrip(".")
    language = get_language(ext)
    if not language:
        return []

    try:
        parser = Parser(language)
        tree = parser.parse(bytes(content, "utf-8"))
        if not tree or not tree.root_node:
            return []

        # 1. Load SCM Query from Domain folder
        query = _get_query_for_extension(ext, language)
        symbols: List[Symbol] = []
        lines = content.split("\n")

        # Mark Entry Point (Heuristic)
        if _is_likely_entry_point(file_path, content):
            symbols.append(
                Symbol(
                    name="[ENTRY POINT]",
                    kind=SymbolKind.MODULE,
                    file_path=file_path,
                    line_start=1,
                    line_end=1,
                    signature=f"FILE: {Path(file_path).name} (BOOTSTRAPPER)",
                    parent=None,
                )
            )

        if query:
            # 2. Execute Query
            cursor = QueryCursor(query)
            captures_dict = cursor.captures(tree.root_node)
            seen_defs: Set[Tuple[int, int, int]] = set()

            for tag_name, nodes in captures_dict.items():
                if "name.definition" not in tag_name:
                    continue

                kind = _tag_to_kind(tag_name, ext)
                for node in nodes:
                    pos = (node.start_point[0], node.end_point[0], node.start_point[1])
                    if pos in seen_defs:
                        continue

                    name = node.text.decode("utf-8") if node.text else None
                    if name:
                        parent = _find_parent_name(node, symbols)
                        symbol = Symbol(
                            name=name,
                            kind=kind,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            signature=_extract_signature(node, lines),
                            parent=parent,
                        )
                        symbols.append(symbol)
                        seen_defs.add(pos)

            symbols.sort(key=lambda s: s.line_start)

        return symbols

    except Exception:
        return []


# Global cache for compiled queries (Phase 5 Optimization)
_QUERY_CACHE: dict[str, Query] = {}


def _get_query_for_extension(ext: str, language) -> Optional[Query]:
    """Loads SCM Query from domain/codemap/queries/ with caching mechanism."""
    lang_map = {
        "py": "python",
        "ts": "typescript",
        "tsx": "tsx",
        "js": "javascript",
        "go": "go",
        "rs": "rust",
        "rb": "ruby",
        "cpp": "cpp",
        "c": "c",
        "cs": "c_sharp",
        "java": "java",
    }
    lang_name = lang_map.get(ext, ext)

    # Check cache first
    cache_key = f"{lang_name}:{id(language)}"
    if cache_key in _QUERY_CACHE:
        return _QUERY_CACHE[cache_key]

    # IMPORTANT: Path has been moved to domain/codemap/queries/
    query_path = Path("domain/codemap/queries") / f"{lang_name}-tags.scm"

    if query_path.exists():
        try:
            query = Query(language, query_path.read_text())
            _QUERY_CACHE[cache_key] = query
            return query
        except Exception:
            return None
    return None


def _tag_to_kind(tag: str, ext: str) -> SymbolKind:
    """Maps tag name to SymbolKind."""
    tag = tag.lower()
    if "class" in tag:
        return SymbolKind.CLASS
    if "interface" in tag:
        return SymbolKind.INTERFACE
    if "method" in tag:
        return SymbolKind.METHOD
    if "func" in tag:
        return SymbolKind.FUNCTION
    if "struct" in tag:
        return SymbolKind.STRUCT
    if "enum" in tag:
        return SymbolKind.ENUM
    if "module" in tag:
        return SymbolKind.MODULE
    if "type" in tag:
        if ext == "go":
            return SymbolKind.STRUCT
        return SymbolKind.TYPE
    return SymbolKind.VARIABLE


def _find_parent_name(node: Node, symbols: List[Symbol]) -> Optional[str]:
    """Finds the parent symbol."""
    curr = node.parent
    while curr:
        start, end = curr.start_point[0] + 1, curr.end_point[0] + 1
        for s in symbols:
            if s.line_start <= start and s.line_end >= end:
                if s.kind in [
                    SymbolKind.CLASS,
                    SymbolKind.MODULE,
                    SymbolKind.INTERFACE,
                    SymbolKind.STRUCT,
                ]:
                    return s.name
        curr = curr.parent
    return None


def _is_likely_entry_point(file_path: str, content: str) -> bool:
    """Identifies the Entry Point."""
    filename = Path(file_path).name.lower()
    entry_filenames = [
        "main.py",
        "app.py",
        "index.py",
        "manage.py",
        "server.py",
        "main.ts",
        "index.ts",
        "main.go",
    ]
    if filename in entry_filenames:
        return True
    if 'if __name__ == "__main__":' in content:
        return True
    if any(k in content for k in ["bootstrap(", "app.listen(", "FastAPI("]):
        return True
    return False


def _extract_signature(node: Node, lines: List[str]) -> Optional[str]:
    """Extracts signature including Docstring/Decorators."""
    def_node = node
    while def_node.parent and (
        "identifier" in def_node.type
        or "name" in def_node.type
        or "declarator" in def_node.type
    ):
        def_node = def_node.parent
    if def_node.parent and def_node.parent.type in [
        "type_spec",
        "method_declaration",
        "function_declaration",
    ]:
        def_node = def_node.parent
        if def_node.parent and def_node.parent.type == "type_declaration":
            def_node = def_node.parent

    start_row = def_node.start_point[0]
    if start_row >= len(lines):
        return node.text.decode("utf-8") if node.text else None
    main_line = lines[start_row].strip()

    decorators: List[str] = []
    curr = def_node.prev_sibling
    while curr and curr.type in ["decorator", "attribute"]:
        deco_text = curr.text.decode("utf-8").strip() if curr.text else ""
        if deco_text:
            decorators.insert(0, deco_text)
        curr = curr.prev_sibling

    description = ""
    comment_node = def_node.prev_sibling
    if decorators:
        first_deco = def_node.prev_sibling
        while first_deco and first_deco.type in ["decorator", "attribute"]:
            comment_node = first_deco.prev_sibling
            first_deco = first_deco.prev_sibling

    if comment_node and comment_node.type in [
        "comment",
        "line_comment",
        "block_comment",
    ]:
        description = _parse_doc_text(
            comment_node.text.decode("utf-8") if comment_node.text else ""
        )

    if not description:
        body_node = None
        for child in def_node.children:
            if child.type in [
                "block",
                "statement_block",
                "function_body",
                "class_body",
            ]:
                body_node = child
                break
        if body_node:
            for child in body_node.children:
                target = child
                if child.type == "expression_statement":
                    target = child.children[0]
                if target.type == "string":
                    description = _parse_doc_text(
                        target.text.decode("utf-8") if target.text else ""
                    )
                    break

    if main_line.endswith(":"):
        main_line = main_line[:-1]
    if main_line.endswith("{"):
        main_line = main_line[:-1].strip()

    final_sig = " ".join(decorators) + " " + main_line if decorators else main_line
    if description:
        limit = 500
        short_desc = (
            description[:limit] + "..." if len(description) > limit else description
        )
        final_sig += f"\n    /*\n     {short_desc}\n     */"
    return final_sig


def _parse_doc_text(raw_text: str) -> str:
    """Cleans up Docstring/JSDoc."""
    if not raw_text:
        return ""
    content = raw_text.strip().strip("*/'\"").strip()
    if not content:
        return ""
    lines = content.split("\n")
    actual_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("*"):
            stripped = stripped[1:].strip()
        if stripped.startswith("//"):
            stripped = stripped[2:].strip()
        if stripped:
            actual_lines.append(stripped)
        else:
            actual_lines.append("")
    return "\n     ".join(actual_lines).strip()
