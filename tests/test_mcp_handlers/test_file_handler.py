"""Unit tests for mcp_server/handlers/file_handler.py"""

import pytest
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from mcp_server.handlers.file_handler import register_tools


@pytest.fixture
def mcp_instance():
    mcp = FastMCP("test_file")
    register_tools(mcp)
    return mcp


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    test_file = tmp_path / "test.py"
    test_file.write_text("line1\nline2\nline3\nline4\nline5")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
    return tmp_path


def get_tool(mcp, name):
    return mcp._tool_manager._tools[name].fn


@pytest.mark.asyncio
async def test_read_file_range_full(mcp_instance, mock_workspace):
    """Test read_file_range reads full file"""
    tool = get_tool(mcp_instance, "read_file_range")
    result = await tool(relative_path="test.py", workspace_path=str(mock_workspace))

    assert "line1" in result and "line5" in result


@pytest.mark.asyncio
async def test_read_file_range_partial(mcp_instance, mock_workspace):
    """Test read_file_range with line range"""
    tool = get_tool(mcp_instance, "read_file_range")
    result = await tool(
        relative_path="test.py",
        start_line=2,
        end_line=3,
        workspace_path=str(mock_workspace),
    )

    assert "line2" in result and "line3" in result
    assert "line1" not in result or "Showing lines" in result


@pytest.mark.asyncio
async def test_read_file_range_path_traversal(mcp_instance, mock_workspace):
    """Test read_file_range prevents path traversal"""
    tool = get_tool(mcp_instance, "read_file_range")
    result = await tool(
        relative_path="../../../etc/passwd", workspace_path=str(mock_workspace)
    )

    assert "Error" in result


@pytest.mark.asyncio
async def test_read_file_range_nonexistent(mcp_instance, mock_workspace):
    """Test read_file_range with nonexistent file"""
    tool = get_tool(mcp_instance, "read_file_range")
    result = await tool(
        relative_path="nonexistent.py", workspace_path=str(mock_workspace)
    )

    assert "Error" in result or "not found" in result


@pytest.mark.asyncio
async def test_get_file_metrics_basic(mcp_instance, mock_workspace):
    """Test get_file_metrics returns metrics"""
    tool = get_tool(mcp_instance, "get_file_metrics")
    result = await tool(file_path="test.py", workspace_path=str(mock_workspace))

    assert "Total lines" in result
    assert "5" in result


@pytest.mark.asyncio
async def test_get_file_metrics_path_traversal(mcp_instance, mock_workspace):
    """Test get_file_metrics prevents path traversal"""
    tool = get_tool(mcp_instance, "get_file_metrics")
    result = await tool(
        file_path="../../../etc/passwd", workspace_path=str(mock_workspace)
    )

    assert "Error" in result


@pytest.mark.asyncio
async def test_read_file_range_out_of_bounds(mcp_instance, mock_workspace):
    """Test read_file_range with out of bounds line numbers"""
    tool = get_tool(mcp_instance, "read_file_range")
    result = await tool(
        relative_path="test.py",
        start_line=100,
        end_line=200,
        workspace_path=str(mock_workspace),
    )

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_file_metrics_with_todos(mcp_instance, tmp_path, monkeypatch):
    """Test get_file_metrics counts TODO comments"""
    todo_file = tmp_path / "todos.py"
    todo_file.write_text("# TODO: fix\n# FIXME: bug\n# HACK: temp\ndef foo(): pass")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    tool = get_tool(mcp_instance, "get_file_metrics")
    result = await tool(file_path="todos.py", workspace_path=str(tmp_path))

    assert "TODO" in result and "FIXME" in result
