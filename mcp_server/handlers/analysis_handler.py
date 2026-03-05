"""
Analysis Handler - Xu ly cac tool phan tich code.

Bao gom: find_references, find_todos, get_symbols.
"""

import os
import re
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import Context

from mcp_server.core.constants import (
    INLINE_COMMENT_RE,
    STRING_LITERAL_RE,
    logger,
)
from mcp_server.core.workspace_manager import WorkspaceManager
import asyncio


def _find_references(
    ws: Path, symbol_name: str, file_extensions: Optional[List[str]]
) -> str:
    """Internal implementation cho find_references, dung asyncio.to_thread."""
    from services.workspace_index import collect_files_from_disk

    all_files = collect_files_from_disk(ws, workspace_path=ws)
    if file_extensions:
        ext_set = {e if e.startswith(".") else f".{e}" for e in file_extensions}
        all_files = [f for f in all_files if Path(f).suffix.lower() in ext_set]

    references: list[tuple[str, int, str]] = []
    pattern = rf"\b{re.escape(symbol_name)}\b"

    for file_path in all_files:
        try:
            fp = Path(file_path)
            content = fp.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith(("#", "//", "/*", "*")):
                    continue
                cleaned = STRING_LITERAL_RE.sub("", line)
                cleaned = INLINE_COMMENT_RE.sub("", cleaned)
                if re.search(pattern, cleaned):
                    rel_path = os.path.relpath(file_path, ws)
                    snippet = line.strip()[:80]
                    references.append((rel_path, i, snippet))
        except (OSError, UnicodeDecodeError):
            continue

    if not references:
        return f"No references found for: {symbol_name}"

    by_file: dict[str, list[tuple[int, str]]] = {}
    for file, line, snippet in references:
        if file not in by_file:
            by_file[file] = []
        by_file[file].append((line, snippet))

    result = [f"Found {len(references)} references in {len(by_file)} files:\n"]
    for file in sorted(by_file.keys()):
        result.append(f"\n{file}:")
        for line, snippet in by_file[file][:5]:
            result.append(f"  Line {line}: {snippet}")
        if len(by_file[file]) > 5:
            result.append(f"  ... +{len(by_file[file]) - 5} more")

    return "\n".join(result)


def _find_todos(workspace_path: str, include_hack: bool = True) -> str:
    """Internal implementation cho find_todos, co the goi tu start_session."""
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    try:
        from services.workspace_index import collect_files_from_disk

        all_files = collect_files_from_disk(ws, workspace_path=ws)
        code_exts = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".go",
            ".rs",
            ".java",
            ".c",
            ".cpp",
            ".h",
        }
        all_files = [f for f in all_files if Path(f).suffix.lower() in code_exts]

        todos: list[tuple[str, int, str, str]] = []

        for file_path in all_files:
            try:
                fp = Path(file_path)
                content = fp.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()

                for i, line in enumerate(lines, start=1):
                    comment_type = None
                    if re.search(r"\bTODO\b", line, re.IGNORECASE):
                        comment_type = "TODO"
                    elif re.search(r"\bFIXME\b", line, re.IGNORECASE):
                        comment_type = "FIXME"
                    elif include_hack and re.search(r"\bHACK\b", line, re.IGNORECASE):
                        comment_type = "HACK"

                    if comment_type:
                        rel_path = os.path.relpath(file_path, ws)
                        snippet = line.strip()[:100]
                        todos.append((rel_path, i, comment_type, snippet))
            except (OSError, UnicodeDecodeError):
                continue

        if not todos:
            return "No TODO/FIXME/HACK comments found in project."

        by_type: dict[str, list[tuple[str, int, str]]] = {
            "TODO": [],
            "FIXME": [],
            "HACK": [],
        }
        for file, line, ctype, snippet in todos:
            by_type[ctype].append((file, line, snippet))

        result = [f"Found {len(todos)} comments:\n"]
        for ctype in ["FIXME", "TODO", "HACK"]:
            items = by_type[ctype]
            if not items:
                continue
            result.append(f"\n{ctype} ({len(items)}):")
            for file, line, snippet in items[:20]:
                result.append(f"  {file}:{line} - {snippet}")
            if len(items) > 20:
                result.append(f"  ... +{len(items) - 20} more")

        return "\n".join(result)
    except Exception as e:
        logger.error("find_todos error: %s", e)
        return f"Error: {e}"


def register_tools(mcp_instance) -> None:
    """Dang ky analysis tools voi MCP server."""

    @mcp_instance.tool()
    async def find_references(
        symbol_name: str,
        file_extensions: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Find all locations where a symbol is used (AST + regex).

        Args:
            symbol_name: Name of symbol to find references for.
            file_extensions: Optional filter (e.g., [".py"]).
            workspace_path: Absolute path to workspace root.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            return await asyncio.to_thread(
                _find_references, ws, symbol_name, file_extensions
            )
        except Exception as e:
            logger.error("find_references error: %s", e)
            return f"Error: {e}"

    @mcp_instance.tool()
    async def find_todos(
        include_hack: bool = True,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Scan project for TODO/FIXME/HACK comments.

        Args:
            include_hack: Whether to include HACK comments.
            workspace_path: Absolute path to workspace root.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        return await asyncio.to_thread(_find_todos, str(ws), include_hack)

    @mcp_instance.tool()
    async def get_symbols(
        file_path: str,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Get list of symbols (functions, classes, methods) in a file as JSON.

        Args:
            file_path: Relative path to the file.
            workspace_path: Absolute path to workspace root.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        fp = (ws / file_path).resolve()

        if not fp.is_relative_to(ws):
            return "Error: Path traversal detected."
        if not fp.is_file():
            return f"Error: File not found: {file_path}"

        try:
            from core.codemaps.symbol_extractor import extract_symbols
            import json

            def _get_symbols_impl():
                content = fp.read_text(encoding="utf-8", errors="replace")
                return extract_symbols(str(fp), content)

            symbols = await asyncio.to_thread(_get_symbols_impl)

            if not symbols:
                return f"No symbols found in {file_path}"

            symbols_data = []
            for sym in symbols:
                symbols_data.append(
                    {
                        "name": sym.name,
                        "kind": sym.kind.value,
                        "line_start": sym.line_start,
                        "line_end": sym.line_end,
                        "signature": sym.signature,
                        "parent": sym.parent,
                    }
                )

            by_kind = {}
            for sym in symbols:
                kind = sym.kind.value
                by_kind[kind] = by_kind.get(kind, 0) + 1

            summary = f"Found {len(symbols)} symbols in {file_path}:\n"
            for kind, count in sorted(by_kind.items()):
                summary += f"  {kind}: {count}\n"

            return summary + "\n" + json.dumps(symbols_data, indent=2)

        except Exception as e:
            logger.error("get_symbols error: %s", e)
            return f"Error: {e}"
