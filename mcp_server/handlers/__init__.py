"""
Handlers package - Chua cac handler modules cho MCP tools.

Moi handler module chiu trach nhiem cho mot nhom tools lien quan,
va expose function register_tools(mcp) de dang ky tools voi MCP server.
"""

from mcp_server.handlers.workspace_handler import register_tools as register_workspace
from mcp_server.handlers.file_handler import register_tools as register_file
from mcp_server.handlers.selection_handler import register_tools as register_selection
from mcp_server.handlers.token_handler import register_tools as register_token
from mcp_server.handlers.analysis_handler import register_tools as register_analysis
from mcp_server.handlers.structure_handler import register_tools as register_structure
from mcp_server.handlers.dependency_handler import register_tools as register_dependency
from mcp_server.handlers.git_handler import register_tools as register_git
from mcp_server.handlers.context_handler import register_tools as register_context
from mcp_server.handlers.workflow_handler import register_tools as register_workflow


def register_all_tools(mcp_instance) -> None:
    """Dang ky tat ca tools tu cac handler modules vao MCP server.

    Goi tung register_tools() tu moi handler module de dang ky
    cac @mcp.tool() functions.

    Args:
        mcp_instance: FastMCP server instance.
    """
    register_workspace(mcp_instance)
    register_file(mcp_instance)
    register_selection(mcp_instance)
    register_token(mcp_instance)
    register_analysis(mcp_instance)
    register_structure(mcp_instance)
    register_dependency(mcp_instance)
    register_git(mcp_instance)
    register_context(mcp_instance)
    register_workflow(mcp_instance)
