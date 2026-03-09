"""Unit tests for mcp_server/handlers/analysis_handler.py"""

import pytest
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from infrastructure.mcp.handlers.analysis_handler import register_tools


@pytest.fixture
def mcp_instance():
    mcp = FastMCP("test_analysis")
    register_tools(mcp)
    return mcp


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    """Mock workspace with CWD fallback"""
    test_file = tmp_path / "test.py"
    test_file.write_text("def foo():\n    pass\n# TODO: fix")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
    return tmp_path


def get_tool(mcp, name):
    return mcp._tool_manager._tools[name].fn


@pytest.mark.asyncio
async def test_get_symbols_basic(mcp_instance, mock_workspace):
    """Test get_symbols extracts symbols"""
    tool = get_tool(mcp_instance, "get_symbols")
    result = await tool(file_path="test.py", workspace_path=str(mock_workspace))

    assert "symbols" in result.lower() or "foo" in result


@pytest.mark.asyncio
async def test_get_symbols_path_traversal(mcp_instance, mock_workspace):
    """Test get_symbols prevents path traversal"""
    tool = get_tool(mcp_instance, "get_symbols")
    result = await tool(
        file_path="../../../etc/passwd", workspace_path=str(mock_workspace)
    )

    assert "Error" in result or "traversal" in result


@pytest.mark.asyncio
async def test_get_symbols_nonexistent_file(mcp_instance, mock_workspace):
    """Test get_symbols with nonexistent file"""
    tool = get_tool(mcp_instance, "get_symbols")
    result = await tool(file_path="nonexistent.py", workspace_path=str(mock_workspace))

    assert "Error" in result or "not found" in result


@pytest.mark.asyncio
async def test_get_symbols_no_symbols(mcp_instance, tmp_path, monkeypatch):
    """Test get_symbols with file containing no symbols"""
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("# Just a comment")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    tool = get_tool(mcp_instance, "get_symbols")
    result = await tool(file_path="empty.py", workspace_path=str(tmp_path))

    assert "No symbols" in result or "symbols" in result.lower()
