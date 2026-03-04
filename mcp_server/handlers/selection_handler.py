"""
Selection Handler - Xu ly manage_selection tool.

Quan ly danh sach file duoc chon (ticked) trong Synapse session.
"""

import asyncio
import json
from typing import List, Optional

from mcp.server.fastmcp import Context

from mcp_server.core.constants import logger
from mcp_server.core.workspace_manager import WorkspaceManager

# Lock de serialize read-modify-write tren session file,
# tranh TOCTOU race condition khi concurrent add/set actions
_selection_lock = asyncio.Lock()


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

        # Serialize read-modify-write de tranh TOCTOU race condition
        async with _selection_lock:
            # Load current selection
            current_selection: list[str] = []
            if session_file.exists():
                try:
                    data = json.loads(session_file.read_text(encoding="utf-8"))
                    current_selection = data.get("selected_files", [])
                except (OSError, json.JSONDecodeError) as e:
                    logger.warning("Failed to load selection: %s", e)

            if action == "get":
                if not current_selection:
                    return "No files currently selected."
                return f"Selected files ({len(current_selection)}):\n" + "\n".join(
                    f"  {p}" for p in current_selection
                )

            elif action == "clear":
                session_file.write_text(
                    json.dumps({"selected_files": []}, indent=2), encoding="utf-8"
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
                    new_selection = paths
                else:  # add
                    existing_set = set(current_selection)
                    new_selection = current_selection + [
                        p for p in paths if p not in existing_set
                    ]

                session_file.write_text(
                    json.dumps({"selected_files": new_selection}, indent=2),
                    encoding="utf-8",
                )
                return f"Selection updated: {len(new_selection)} files selected."

            else:
                return (
                    f"Error: Invalid action '{action}'. Use: get, set, add, or clear."
                )
