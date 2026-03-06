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
        "application.services.workspace_index.collect_files_from_disk", mock_collect
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
async def test_start_session_error_handling(mcp_instance, monkeypatch):
    """Test start_session handles errors gracefully"""

    def mock_error(*args, **kwargs):
        raise Exception("Test error")

    monkeypatch.setattr(
        "application.services.workspace_index.collect_files_from_disk", mock_error
    )

    tool = get_tool(mcp_instance, "start_session")
    result = await tool(workspace_path="/tmp")

    assert "Error" in result
