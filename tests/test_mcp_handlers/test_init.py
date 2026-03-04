"""Unit tests for mcp_server/handlers/__init__.py"""

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server.handlers import register_all_tools


@pytest.fixture
def mcp_instance():
    return FastMCP("test_init")


def test_register_all_tools(mcp_instance):
    """Test register_all_tools registers all tools"""
    register_all_tools(mcp_instance)

    # Check that tools are registered
    tools = mcp_instance._tool_manager._tools

    # Should have tools from all handlers
    assert len(tools) > 0

    # Check for key tools from each handler
    expected_tools = [
        "find_references",
        "get_codemap",
        "get_imports_graph",
        "read_file_range",
        "diff_summary",
        "manage_selection",
        "get_project_structure",
        "estimate_tokens",
        "rp_build",
        "start_session",
    ]

    for tool_name in expected_tools:
        assert tool_name in tools, f"Tool {tool_name} not registered"


def test_register_all_tools_idempotent(mcp_instance):
    """Test register_all_tools can be called multiple times"""
    register_all_tools(mcp_instance)
    initial_count = len(mcp_instance._tool_manager._tools)

    register_all_tools(mcp_instance)
    final_count = len(mcp_instance._tool_manager._tools)

    # Should not duplicate tools
    assert initial_count == final_count
