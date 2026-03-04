"""Unit tests for mcp_server/handlers/structure_handler.py"""

import pytest
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from mcp_server.handlers.structure_handler import register_tools


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
        "services.workspace_index.collect_files_from_disk", mock_collect
    )

    return tmp_path


def get_tool(mcp, name):
    return mcp._tool_manager._tools[name].fn


@pytest.mark.asyncio
async def test_get_project_structure_basic(mcp_instance, mock_workspace):
    """Test get_project_structure returns summary"""
    tool = get_tool(mcp_instance, "get_project_structure")
    result = await tool(workspace_path=str(mock_workspace))

    assert "Project:" in result
    assert "Total files" in result


@pytest.mark.asyncio
async def test_get_project_structure_detects_framework(mcp_instance, mock_workspace):
    """Test get_project_structure detects Node.js"""
    tool = get_tool(mcp_instance, "get_project_structure")
    result = await tool(workspace_path=str(mock_workspace))

    assert "Node.js" in result or "Frameworks" in result


@pytest.mark.asyncio
async def test_get_project_structure_invalid_workspace(mcp_instance):
    """Test get_project_structure with invalid workspace"""
    tool = get_tool(mcp_instance, "get_project_structure")
    result = await tool(workspace_path="/nonexistent")

    assert "Error" in result


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
async def test_get_project_structure_empty_workspace(
    mcp_instance, tmp_path, monkeypatch
):
    """Test get_project_structure with empty workspace"""
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    def mock_collect(ws, workspace_path=None):
        return []

    monkeypatch.setattr(
        "services.workspace_index.collect_files_from_disk", mock_collect
    )

    tool = get_tool(mcp_instance, "get_project_structure")
    result = await tool(workspace_path=str(tmp_path))

    assert "No files found" in result or "empty" in result


@pytest.mark.asyncio
async def test_explain_architecture_with_entry_points(mcp_instance, mock_workspace):
    """Test explain_architecture detects entry points"""
    (mock_workspace / "main.py").write_text("def main(): pass")

    tool = get_tool(mcp_instance, "explain_architecture")
    result = await tool(workspace_path=str(mock_workspace))

    assert "Architecture" in result or "Entry" in result or "Module" in result


@pytest.mark.asyncio
async def test_get_project_structure_with_multiple_frameworks(
    mcp_instance, mock_workspace
):
    """Test get_project_structure detects multiple frameworks"""
    (mock_workspace / "requirements.txt").write_text("django")
    (mock_workspace / "manage.py").write_text("# Django")

    tool = get_tool(mcp_instance, "get_project_structure")
    result = await tool(workspace_path=str(mock_workspace))

    assert "Python" in result or "Django" in result or "Frameworks" in result
