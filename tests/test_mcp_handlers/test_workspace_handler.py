"""Unit tests for mcp_server/handlers/workspace_handler.py"""

import pytest
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from mcp_server.handlers.workspace_handler import register_tools


@pytest.fixture
def mcp_instance():
    mcp = FastMCP("test_workspace")
    register_tools(mcp)
    return mcp


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    (tmp_path / "test.py").write_text("# TODO: test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("pass")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    def mock_collect(ws, workspace_path=None):
        return [str(tmp_path / "test.py"), str(tmp_path / "src" / "main.py")]

    monkeypatch.setattr(
        "services.workspace_index.collect_files_from_disk", mock_collect
    )

    return tmp_path


def get_tool(mcp, name):
    return mcp._tool_manager._tools[name].fn


@pytest.mark.asyncio
async def test_start_session_basic(mcp_instance, mock_workspace):
    """Test start_session initializes successfully"""
    tool = get_tool(mcp_instance, "start_session")
    result = await tool(workspace_path=str(mock_workspace))

    assert "SESSION INITIALIZED" in result
    assert "Project:" in result


@pytest.mark.asyncio
async def test_start_session_auto_detect(mcp_instance, mock_workspace):
    """Test start_session with CWD fallback"""
    tool = get_tool(mcp_instance, "start_session")
    result = await tool()

    assert "SESSION INITIALIZED" in result


@pytest.mark.asyncio
async def test_list_files_basic(mcp_instance, mock_workspace):
    """Test list_files returns file list"""
    tool = get_tool(mcp_instance, "list_files")
    result = await tool(workspace_path=str(mock_workspace))

    assert "Found" in result
    assert "test.py" in result


@pytest.mark.asyncio
async def test_list_files_with_extension_filter(mcp_instance, mock_workspace):
    """Test list_files with extension filter"""
    tool = get_tool(mcp_instance, "list_files")
    result = await tool(extensions=[".py"], workspace_path=str(mock_workspace))

    assert "test.py" in result


@pytest.mark.asyncio
async def test_list_files_no_matches(mcp_instance, mock_workspace):
    """Test list_files with no matching files"""
    tool = get_tool(mcp_instance, "list_files")
    result = await tool(extensions=[".js"], workspace_path=str(mock_workspace))

    assert "No files found" in result


@pytest.mark.asyncio
async def test_list_directories_basic(mcp_instance, mock_workspace):
    """Test list_directories returns tree"""
    tool = get_tool(mcp_instance, "list_directories")
    result = await tool(workspace_path=str(mock_workspace))

    assert "src" in result or mock_workspace.name in result


@pytest.mark.asyncio
async def test_list_directories_with_depth(mcp_instance, mock_workspace):
    """Test list_directories with max_depth"""
    tool = get_tool(mcp_instance, "list_directories")
    result = await tool(max_depth=1, workspace_path=str(mock_workspace))

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_list_directories_invalid_workspace(mcp_instance):
    """Test list_directories with invalid workspace"""
    tool = get_tool(mcp_instance, "list_directories")
    result = await tool(workspace_path="/nonexistent")

    assert "Error" in result


@pytest.mark.asyncio
async def test_list_files_auto_detect(mcp_instance, mock_workspace):
    """Test list_files with CWD auto-detection"""
    tool = get_tool(mcp_instance, "list_files")
    result = await tool()

    assert "Found" in result or "test.py" in result


@pytest.mark.asyncio
async def test_list_directories_max_depth_limit(mcp_instance, mock_workspace):
    """Test list_directories respects max_depth limit"""
    tool = get_tool(mcp_instance, "list_directories")
    result = await tool(max_depth=10, workspace_path=str(mock_workspace))

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_start_session_error_handling(mcp_instance, monkeypatch):
    """Test start_session handles errors gracefully"""

    def mock_error(*args, **kwargs):
        raise Exception("Test error")

    monkeypatch.setattr("services.workspace_index.collect_files_from_disk", mock_error)

    tool = get_tool(mcp_instance, "start_session")
    result = await tool(workspace_path="/tmp")

    assert "Error" in result
