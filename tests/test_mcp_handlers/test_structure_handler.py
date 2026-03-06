"""Unit tests for mcp_server/handlers/structure_handler.py"""

import pytest
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from infrastructure.mcp.handlers.structure_handler import register_tools


@pytest.fixture
def mcp_instance():
    mcp = FastMCP("test_structure")
    register_tools(mcp)
    return mcp


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    (tmp_path / "test.py").write_text("pass")
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    def mock_collect(ws, workspace_path=None):
        return [str(tmp_path / "test.py")]

    monkeypatch.setattr(
        "application.services.workspace_index.collect_files_from_disk", mock_collect
    )

    return tmp_path


def get_tool(mcp, name):
    return mcp._tool_manager._tools[name].fn


@pytest.mark.asyncio
async def test_explain_architecture_basic(mcp_instance, mock_workspace):
    """Test explain_architecture returns analysis"""
    tool = get_tool(mcp_instance, "explain_architecture")
    result = await tool(workspace_path=str(mock_workspace))

    assert "Architecture" in result or "Module" in result


@pytest.mark.asyncio
async def test_explain_architecture_with_focus(mcp_instance, mock_workspace):
    """Test explain_architecture with focus directory"""
    (mock_workspace / "src").mkdir()
    (mock_workspace / "src" / "main.py").write_text("pass")

    tool = get_tool(mcp_instance, "explain_architecture")
    result = await tool(focus_directory="src", workspace_path=str(mock_workspace))

    assert "focus" in result.lower() or "src" in result


@pytest.mark.asyncio
async def test_explain_architecture_invalid_focus(mcp_instance, mock_workspace):
    """Test explain_architecture with invalid focus directory"""
    tool = get_tool(mcp_instance, "explain_architecture")
    result = await tool(
        focus_directory="../../../etc", workspace_path=str(mock_workspace)
    )

    assert "Error" in result or "Invalid" in result


@pytest.mark.asyncio
async def test_explain_architecture_with_entry_points(mcp_instance, mock_workspace):
    """Test explain_architecture detects entry points"""
    (mock_workspace / "main.py").write_text("def main(): pass")

    tool = get_tool(mcp_instance, "explain_architecture")
    result = await tool(workspace_path=str(mock_workspace))

    assert "Architecture" in result or "Entry" in result or "Module" in result
