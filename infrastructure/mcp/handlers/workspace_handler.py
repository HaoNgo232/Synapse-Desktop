"""
Workspace Handler - Xu ly cac tool lien quan den workspace operations.

Bao gom: start_session. (list_files, list_directories da go bo - dung built-in list_dir/glob.)
"""

import os
from pathlib import Path
from typing import Annotated, Optional

from mcp.server.fastmcp import Context
from pydantic import Field

from infrastructure.mcp.core.constants import logger
from infrastructure.mcp.core.workspace_manager import WorkspaceManager
import asyncio


def _list_directories_impl(workspace_path: str, max_depth: int = 3) -> str:
    """Implementation cho list_directories, co the goi tu start_session."""
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    max_depth = min(max(1, max_depth), 10)

    SKIP_DIRS = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".tox",
        ".eggs",
        ".ruff_cache",
        ".next",
        ".nuxt",
    }

    lines: list[str] = [ws.name + "/"]

    def _walk(current: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            dirs = sorted(
                (
                    entry
                    for entry in os.scandir(current)
                    if entry.is_dir(follow_symlinks=False)
                    and entry.name not in SKIP_DIRS
                    and not entry.name.startswith(".")
                ),
                key=lambda e: e.name.lower(),
            )
        except PermissionError:
            return

        for i, d in enumerate(dirs):
            is_last = i == len(dirs) - 1
            connector = "--- " if is_last else "|-- "
            lines.append(f"{prefix}{connector}{d.name}/")
            new_prefix = prefix + ("    " if is_last else "|   ")
            _walk(Path(d.path), new_prefix, depth + 1)

    _walk(ws, "", 1)

    if len(lines) == 1:
        return f"{ws.name}/ (empty or all directories are ignored)"

    return "\n".join(lines)


def register_tools(mcp_instance) -> None:
    """Dang ky workspace tools voi MCP server."""

    @mcp_instance.tool()
    async def start_session(
        workspace_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to the workspace root directory. Auto-detected if omitted."
            ),
        ] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Start a new session by auto-discovering project structure, organization, and technical debt.

        Call this FIRST when starting work on a new codebase or task.
        Returns project summary, directory tree, and TODO/FIXME/HACK comments.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from infrastructure.mcp.handlers.structure_handler import (
                _get_project_structure,
            )
            from infrastructure.mcp.handlers.analysis_handler import _find_todos
            from application.services.workspace_index import collect_files_from_disk

            ws_str = str(ws)

            # Scan filesystem 1 lan duy nhat, sau do truyen cached_files
            # cho _get_project_structure va _find_todos de tranh scan lap
            cached_files = await asyncio.to_thread(
                collect_files_from_disk, ws, workspace_path=ws
            )

            structure = await asyncio.to_thread(
                _get_project_structure, ws_str, cached_files
            )
            tree = await asyncio.to_thread(_list_directories_impl, ws_str, 2)
            todos_result = await asyncio.to_thread(
                _find_todos, ws_str, True, cached_files
            )
            todos_preview = (
                todos_result
                if len(todos_result) < 800
                else todos_result[:800] + "\n... (truncated)"
            )

            return (
                f"{'=' * 60}\nSESSION INITIALIZED [OK]\n{'=' * 60}\n\n"
                f"{structure}\n\n{'=' * 60}\nDIRECTORY STRUCTURE\n{'=' * 60}\n"
                f"{tree}\n\n{'=' * 60}\nTECHNICAL DEBT\n{'=' * 60}\n"
                f"{todos_preview}\n\n{'=' * 60}\n"
                f"Next steps:\n  - Use get_codemap to explore specific files\n"
                f"  - Use read_file when you need implementation details\n"
                f"  - Use get_imports_graph to understand module coupling\n{'=' * 60}"
            )
        except Exception as e:
            logger.error("start_session error: %s", e)
            return f"Error initializing session: {e}"
