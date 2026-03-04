"""
Selection Handler - Xu ly manage_selection tool.

Delegate logic CRUD cho SessionManager trong core.
"""

from pathlib import Path
from typing import List, Optional

from mcp_server.core.session_manager import SessionManager


def register_tools(mcp_instance) -> None:
    """Dang ky selection tools voi MCP server.

    Args:
        mcp_instance: FastMCP server instance.
    """

    # Ham manage_selection dung de quan ly danh sach cac file dang duoc chon de build prompt
    @mcp_instance.tool()
    def manage_selection(
        workspace_path: str,
        action: str = "get",
        paths: Optional[List[str]] = None,
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
            workspace_path: Absolute path to the workspace root directory.
            action: Action to perform - "get", "set", "add", or "clear".
            paths: List of relative file paths (required for "set" and "add" actions).
        """
        ws = Path(workspace_path).resolve()
        if not ws.is_dir():
            return f"Error: '{workspace_path}' is not a valid directory."

        session_file = ws / ".synapse" / "selection.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        if action == "get":
            return SessionManager.get_selection(session_file, ws)
        elif action == "set":
            return SessionManager.set_selection(session_file, ws, paths or [])
        elif action == "add":
            return SessionManager.add_selection(session_file, ws, paths or [])
        elif action == "clear":
            return SessionManager.clear_selection(session_file)
        else:
            return f"Error: Unknown action '{action}'. Use: get, set, add, clear."
