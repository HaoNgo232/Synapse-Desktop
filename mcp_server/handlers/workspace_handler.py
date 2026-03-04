"""
Workspace Handler - Xu ly cac tool lien quan den workspace operations.

Bao gom: start_session, list_files, list_directories.
"""

import os
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import Context

from mcp_server.core.constants import logger
from mcp_server.core.workspace_manager import WorkspaceManager


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
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Start a new session by auto-discovering project structure, organization, and technical debt.

        WHY USE THIS OVER BUILT-IN: Combines 3 calls into one.
        Call this FIRST when starting work on a new codebase or task.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from mcp_server.handlers.structure_handler import _get_project_structure
            from mcp_server.handlers.analysis_handler import _find_todos

            ws_str = str(ws)
            structure = _get_project_structure(ws_str)
            tree = _list_directories_impl(ws_str, max_depth=2)
            todos_result = _find_todos(ws_str, include_hack=True)
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

    @mcp_instance.tool()
    async def list_files(
        extensions: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """List all files in the workspace, automatically respecting .gitignore.

        WHY USE THIS OVER BUILT-IN: Use YOUR BUILT-IN list_dir/ls for simple directories.
        Use this to get a flat list of ALL files recursively.

        Args:
            extensions: Optional list of extensions to filter by (e.g., [".py", ".js"]).
            workspace_path: Absolute path to workspace root. Auto-detected if omitted.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        try:
            from services.workspace_index import collect_files_from_disk

            all_files = collect_files_from_disk(ws, workspace_path=ws)

            if extensions:
                ext_set = {
                    e.lower() if e.startswith(".") else f".{e.lower()}"
                    for e in extensions
                }
                all_files = [f for f in all_files if Path(f).suffix.lower() in ext_set]

            result_lines = []
            for f in sorted(all_files):
                try:
                    rel = os.path.relpath(f, ws)
                    result_lines.append(rel)
                except ValueError:
                    result_lines.append(f)

            if not result_lines:
                return "No files found matching the criteria."

            return f"Found {len(result_lines)} files:\n" + "\n".join(result_lines)

        except Exception as e:
            logger.error("list_files error: %s", e)
            return f"Error listing files: {e}"

    @mcp_instance.tool()
    async def list_directories(
        max_depth: int = 3,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Show the directory tree structure of the workspace.

        WHY USE THIS OVER BUILT-IN: Use YOUR BUILT-IN list_dir/ls for simple exploration.
        Use this to see the overall shape of the project recursively.

        Args:
            max_depth: Maximum directory depth to display (default: 3, max: 10).
            workspace_path: Absolute path to workspace root. Auto-detected if omitted.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        return _list_directories_impl(str(ws), max_depth)
