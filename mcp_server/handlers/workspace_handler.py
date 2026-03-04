"""
Workspace Handler - Xu ly cac tool lien quan den workspace operations.

Bao gom: start_session, list_files, list_directories.
"""

import os
from pathlib import Path
from typing import List, Optional

from mcp_server.core.constants import logger


def register_tools(mcp_instance) -> None:
    """Dang ky workspace tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    # Ham start_session giup tu dong discover cau truc du an, cac framework va technical debt
    @mcp_instance.tool()
    def start_session(workspace_path: str) -> str:
        """Start a new session by auto-discovering project structure, organization, and technical debt.

        WHY USE THIS OVER BUILT-IN: Combines 3 calls into one to give you an immediate high-level summary.
        However, you can also use your built-in tools recursively if you prefer.

        This is a convenience tool that runs the essential discovery sequence:
        1. get_project_structure - Understand scale, languages, frameworks
        2. list_directories - See folder organization
        3. find_todos - Check technical debt

        Call this FIRST when starting work on a new codebase or task.
        """
        ws = Path(workspace_path).resolve()
        if not ws.is_dir():
            return f"Error: '{workspace_path}' is not a valid directory."

        try:
            # Import cac tool cung level de goi truc tiep
            from mcp_server.handlers.structure_handler import (
                _get_project_structure,
            )
            from mcp_server.handlers.analysis_handler import _find_todos

            # 1. Project structure
            structure = _get_project_structure(workspace_path)

            # 2. Directory tree (depth 2 for quick overview)
            tree = _list_directories_impl(workspace_path, max_depth=2)

            # 3. Technical debt scan
            todos_result = _find_todos(workspace_path, include_hack=True)
            # Truncate if too long
            todos_preview = (
                todos_result
                if len(todos_result) < 800
                else todos_result[:800] + "\n... (truncated)"
            )

            return (
                f"{'=' * 60}\n"
                f"SESSION INITIALIZED [OK]\n"
                f"{'=' * 60}\n\n"
                f"{structure}\n\n"
                f"{'=' * 60}\n"
                f"DIRECTORY STRUCTURE\n"
                f"{'=' * 60}\n"
                f"{tree}\n\n"
                f"{'=' * 60}\n"
                f"TECHNICAL DEBT\n"
                f"{'=' * 60}\n"
                f"{todos_preview}\n\n"
                f"{'=' * 60}\n"
                f"Next steps:\n"
                f"  - Use get_codemap to explore specific files\n"
                f"  - Use read_file when you need implementation details\n"
                f"  - Use get_imports_graph to understand module coupling\n"
                f"{'=' * 60}"
            )
        except Exception as e:
            logger.error("start_session error: %s", e)
            return f"Error initializing session: {e}"

    # Ham list_files liet ke tat ca file trong workspace, co ho tro filter theo extension
    @mcp_instance.tool()
    def list_files(
        workspace_path: str,
        extensions: Optional[List[str]] = None,
    ) -> str:
        """List all files in the workspace, automatically respecting .gitignore and skipping hidden files.

        WHY USE THIS OVER BUILT-IN: Use YOUR BUILT-IN list_dir/ls for simple directories.
        Use this to get a flat list of ALL files recursively in the project, automatically
        respecting .gitignore, which is useful to feed into other tools.

        Returns one relative path per line. Use the `extensions` filter to narrow results
        (e.g., [".py", ".ts"] to find only Python and TypeScript files).

        When to use: You need to know exactly which files exist, find files by extension,
        or get a flat list to pass to other tools like read_file or get_codemap.

        Args:
            workspace_path: Absolute path to the workspace root directory.
            extensions: Optional list of extensions to filter by (e.g., [".py", ".js"]). None returns all files.
        """
        ws = Path(workspace_path).resolve()
        if not ws.is_dir():
            return f"Error: '{workspace_path}' is not a valid directory."

        try:
            from services.workspace_index import collect_files_from_disk

            all_files = collect_files_from_disk(ws, workspace_path=ws)

            # Loc theo extension neu co yeu cau
            if extensions:
                ext_set = {
                    e.lower() if e.startswith(".") else f".{e.lower()}"
                    for e in extensions
                }
                all_files = [f for f in all_files if Path(f).suffix.lower() in ext_set]

            # Chuyen thanh duong dan tuong doi
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

    # Ham list_directories hien thi cau truc thu muc duoi dang cay (nhu lenh tree)
    @mcp_instance.tool()
    def list_directories(
        workspace_path: str,
        max_depth: int = 3,
    ) -> str:
        """Show the directory tree structure of the workspace (similar to the `tree` command).

        WHY USE THIS OVER BUILT-IN: Use YOUR BUILT-IN list_dir/ls for simple exploration.
        Use this to see the overall shape of the project recursively up to max_depth.

        Quickly understand how a project is organized - folder hierarchy, module boundaries,
        and naming conventions - without listing every file.

        When to use: First step when exploring an unfamiliar codebase, or when you need to
        understand where specific modules/packages live before reading files.

        Args:
            workspace_path: Absolute path to the workspace root directory.
            max_depth: Maximum directory depth to display (default: 3, max: 10).
        """
        return _list_directories_impl(workspace_path, max_depth)


def _list_directories_impl(workspace_path: str, max_depth: int = 3) -> str:
    """Implementation cho list_directories, co the goi tu start_session.

    Args:
        workspace_path: Duong dan workspace.
        max_depth: Do sau toi da.

    Returns:
        Chuoi cay thu muc ASCII.
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        return f"Error: '{workspace_path}' is not a valid directory."

    max_depth = min(max(1, max_depth), 10)

    # Danh sach thu muc can bo qua
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
        """De quy duyet cay thu muc voi ASCII connectors. Dung os.scandir de tranh tao Path objects thua."""
        if depth > max_depth:
            return

        try:
            # Dung os.scandir thay vi iterdir() de tranh tao DirEntry objects thua
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
