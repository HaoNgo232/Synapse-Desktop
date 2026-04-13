"""
Tests cho mcp_server/handlers/ - Kiem tra tool registration.

Dam bao tat ca handlers dang ky dung so luong tools
voi ten chinh xac khi goi register_all_tools().
"""

from mcp.server.fastmcp import FastMCP

from infrastructure.mcp.handlers import register_all_tools
from infrastructure.mcp.handlers.analysis_handler import register_tools as reg_analysis
from infrastructure.mcp.handlers.context_handler import register_tools as reg_context
from infrastructure.mcp.handlers.dependency_handler import (
    register_tools as reg_dependency,
)
from infrastructure.mcp.handlers.file_handler import register_tools as reg_file
from infrastructure.mcp.handlers.git_handler import register_tools as reg_git
from infrastructure.mcp.handlers.selection_handler import (
    register_tools as reg_selection,
)
from infrastructure.mcp.handlers.structure_handler import (
    register_tools as reg_structure,
)
from infrastructure.mcp.handlers.token_handler import register_tools as reg_token
from infrastructure.mcp.handlers.workflow_handler import register_tools as reg_workflow
from infrastructure.mcp.handlers.workspace_handler import (
    register_tools as reg_workspace,
)


def _get_tool_names(register_fn):
    """Helper: dang ky tools vao MCP instance va tra ve danh sach ten tools."""
    mcp = FastMCP("test")
    register_fn(mcp)
    return {tool.name for tool in mcp._tool_manager.list_tools()}


class TestIndividualHandlerRegistration:
    """Kiem tra tung handler dang ky dung so luong va ten tools."""

    def test_workspace_handler_tools(self):
        """workspace_handler dang ky 1 tool."""
        names = _get_tool_names(reg_workspace)
        assert "start_session" in names
        assert len(names) == 1

    def test_file_handler_tools(self):
        """file_handler hien tai khong dang ky tool nao."""
        names = _get_tool_names(reg_file)
        assert len(names) == 0

    def test_selection_handler_tools(self):
        """selection_handler dang ky 1 tool."""
        names = _get_tool_names(reg_selection)
        assert "manage_selection" in names
        assert len(names) == 1

    def test_token_handler_tools(self):
        """token_handler dang ky 1 tool."""
        names = _get_tool_names(reg_token)
        assert "estimate_tokens" in names
        assert len(names) == 1

    def test_analysis_handler_tools(self):
        """analysis_handler dang ky 1 tool (get_symbols)."""
        names = _get_tool_names(reg_analysis)
        assert "get_symbols" in names
        assert len(names) == 1

    def test_structure_handler_tools(self):
        """structure_handler dang ky 1 tool."""
        names = _get_tool_names(reg_structure)
        assert "explain_architecture" in names
        assert len(names) == 1

    def test_dependency_handler_tools(self):
        """dependency_handler dang ky 3 tools."""
        names = _get_tool_names(reg_dependency)
        assert "get_imports_graph" in names
        assert "get_related_tests" in names
        assert "blast_radius" in names
        assert len(names) == 3

    def test_git_handler_tools(self):
        """git_handler hien tai khong dang ky tool nao."""
        names = _get_tool_names(reg_git)
        assert len(names) == 0

    def test_context_handler_tools(self):
        """context_handler dang ky 3 tools."""
        names = _get_tool_names(reg_context)
        assert "get_codemap" in names
        assert "batch_codemap" in names
        assert "build_prompt" in names
        assert len(names) == 3

    def test_workflow_handler_tools(self):
        """workflow_handler dang ky 9 tools."""
        names = _get_tool_names(reg_workflow)
        assert "rp_build" in names
        assert "rp_review" in names
        assert "rp_refactor" in names
        assert "rp_investigate" in names
        assert "rp_test" in names
        assert "rp_design" in names
        assert "manage_memory" in names
        assert "get_contract_pack" in names
        assert "detect_design_drift" in names
        assert "list_workflow_plugins" in names
        assert "run_workflow_plugin" in names
        assert len(names) == 11


class TestRegisterAllTools:
    """Kiem tra register_all_tools dang ky mode selection-only."""

    def test_total_tool_count(self):
        """Tong so tools aggregate chi con 1 (manage_selection)."""
        mcp = FastMCP("test_all")
        register_all_tools(mcp)
        tools = list(mcp._tool_manager.list_tools())
        assert len(tools) == 1

    def test_no_duplicate_tool_names(self):
        """Khong co tool nao bi trung ten."""
        mcp = FastMCP("test_all")
        register_all_tools(mcp)
        tools = list(mcp._tool_manager.list_tools())
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), f"Duplicate tools: {names}"

    def test_all_expected_tools_present(self):
        """Chi tool selection duoc dang ky o aggregate entrypoint."""
        mcp = FastMCP("test_all")
        register_all_tools(mcp)
        names = {t.name for t in mcp._tool_manager.list_tools()}

        expected_tools = {
            # selection_handler
            "manage_selection",
        }

        missing = expected_tools - names
        extra = names - expected_tools
        assert not missing, f"Missing tools: {missing}"
        assert not extra, f"Extra unexpected tools: {extra}"
