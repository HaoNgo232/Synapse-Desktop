"""Handlers package - Selection-only registration entrypoint.

Core logic cua cac handler khac van duoc giu nguyen trong codebase,
nhung MCP aggregate registration hien tai chi expose tool selection.
"""

from infrastructure.mcp.handlers.selection_handler import (
    register_tools as register_selection,
)


def register_all_tools(mcp_instance: object) -> None:
    """Dang ky tools vao MCP server (hien tai: chi selection tool).

    Args:
        mcp_instance: FastMCP server instance.
    """
    register_selection(mcp_instance)
