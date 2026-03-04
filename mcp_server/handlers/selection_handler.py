"""
Selection Handler - Xu ly manage_selection tool.

Quan ly danh sach file duoc chon (ticked) trong Synapse session.
"""

import asyncio
import json
import fcntl
from pathlib import Path
from typing import List, Optional, Callable

from mcp.server.fastmcp import Context

from mcp_server.core.constants import logger
from mcp_server.core.workspace_manager import WorkspaceManager


def _locked_read_modify_write(
    session_file: Path, modifier_fn: Callable[[list[str]], list[str]]
) -> list[str]:
    """Read the selection JSON, pass it to modifier_fn, write back, all under cross-process lock."""
    # Ensure file exists so we can open it in r+
    if not session_file.exists():
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps({"selected_files": []}))

    with open(session_file, "r+", encoding="utf-8") as f:
        # Cross-process exclusive lock
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            try:
                data = json.load(f)
                current_selection = data.get("selected_files", [])
            except (json.JSONDecodeError, OSError):
                current_selection = []

            new_selection = modifier_fn(current_selection)

            # Write back
            f.seek(0)
            json.dump({"selected_files": new_selection}, f, indent=2)
            f.write("\n")
            f.truncate()

            return new_selection
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def register_tools(mcp_instance) -> None:
    """Dang ky selection tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    @mcp_instance.tool()
    async def manage_selection(
        action: str = "get",
        paths: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Manage the list of currently selected (ticked) files in the Synapse session.

        WHY USE THIS OVER BUILT-IN: When building prompts across multiple tool calls, this lets you
        incrementally add/remove files to a selection, then pass them all to build_prompt
        at once. Useful for complex multi-step context curation.

        This controls which files are included when building prompts. Use it to
        curate the exact set of files that should be part of the AI context.

        Actions:
          "get"   - Return the current selection list.
          "set"   - Replace the entire selection with the provided paths.
          "add"   - Add paths to the existing selection (skips duplicates).
          "clear" - Remove all files from the selection.

        When to use: Before calling build_prompt, use "set" or "add" to choose the
        right files. Use "get" to check what's currently selected. Use "clear" to
        start fresh.

        Args:
            action: Action to perform - "get", "set", "add", or "clear".
            paths: List of relative file paths (required for "set" and "add" actions).
            workspace_path: Absolute path to workspace root. Auto-detected if omitted.
        """
        try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        session_file = WorkspaceManager.get_session_file(ws)

        # BUG #1 FIX: Offload file read to background thread
        # BUG #2 FIX: Use cross-process file lock via _locked_read_modify_write

        if action == "get":
            current_selection = []
            if session_file.exists():
                try:
                    raw_text = await asyncio.to_thread(
                        session_file.read_text, encoding="utf-8"
                    )
                    data = json.loads(raw_text)
                    current_selection = data.get("selected_files", [])
                except (OSError, json.JSONDecodeError) as e:
                    logger.warning("Failed to load selection: %s", e)

            if not current_selection:
                return "No files currently selected."
            return f"Selected files ({len(current_selection)}):\n" + "\n".join(
                f"  {p}" for p in current_selection
            )

        elif action == "clear":

            def clear_modifier(_: list[str]) -> list[str]:
                return []

            await asyncio.to_thread(
                _locked_read_modify_write, session_file, clear_modifier
            )
            return "Selection cleared."

        elif action in ("set", "add"):
            if not paths:
                return f"Error: 'paths' parameter required for action '{action}'."

            # Validate paths
            for rp in paths:
                fp = (ws / rp).resolve()
                if not fp.is_relative_to(ws):
                    return f"Error: Path traversal detected for: {rp}"
                if not fp.is_file():
                    return f"Error: File not found: {rp}"

            if action == "set":

                def set_modifier(_: list[str]) -> list[str]:
                    # Type hint ensures we satisfy the callable requirement
                    return paths if paths is not None else []

                new_selection = await asyncio.to_thread(
                    _locked_read_modify_write, session_file, set_modifier
                )
            else:  # add

                def add_modifier(current: list[str]) -> list[str]:
                    existing_set = set(current)
                    safe_paths = paths if paths is not None else []
                    return current + [p for p in safe_paths if p not in existing_set]

                new_selection = await asyncio.to_thread(
                    _locked_read_modify_write, session_file, add_modifier
                )

            return f"Selection updated: {len(new_selection)} files selected."

        else:
            return f"Error: Invalid action '{action}'. Use: get, set, add, or clear."
