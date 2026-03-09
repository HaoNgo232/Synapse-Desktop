"""
Handlers package - Chua cac handler modules cho MCP tools.

Moi handler module chiu trach nhiem cho mot nhom tools lien quan,
va expose function register_tools(mcp) de dang ky tools voi MCP server.

Removed handlers (deprecated, no longer register any tools):
- file_handler: get_file_metrics removed — use read_file + line count
- git_handler: diff_summary removed — use git diff command directly
"""

from infrastructure.mcp.handlers.workspace_handler import (
    register_tools as register_workspace,
)
from infrastructure.mcp.handlers.selection_handler import (
    register_tools as register_selection,
)
from infrastructure.mcp.handlers.token_handler import register_tools as register_token
from infrastructure.mcp.handlers.analysis_handler import (
    register_tools as register_analysis,
)
from infrastructure.mcp.handlers.structure_handler import (
    register_tools as register_structure,
)
from infrastructure.mcp.handlers.dependency_handler import (
    register_tools as register_dependency,
)
from infrastructure.mcp.handlers.context_handler import (
    register_tools as register_context,
)
from infrastructure.mcp.handlers.workflow_handler import (
    register_tools as register_workflow,
)


def register_all_tools(mcp_instance) -> None:
    """Dang ky tat ca tools tu cac handler modules vao MCP server.

    Goi tung register_tools() tu moi handler module de dang ky
    cac @mcp.tool() functions.

    Args:
        mcp_instance: FastMCP server instance.
    """
    register_workspace(mcp_instance)
    register_selection(mcp_instance)
    register_token(mcp_instance)
    register_analysis(mcp_instance)
    register_structure(mcp_instance)
    register_dependency(mcp_instance)
    register_context(mcp_instance)
    register_workflow(mcp_instance)
