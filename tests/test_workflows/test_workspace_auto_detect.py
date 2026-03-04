import pytest
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from mcp_server.handlers.workspace_handler import register_tools as _reg_ws
from mcp_server.handlers.analysis_handler import register_tools as _reg_analysis
from mcp_server.handlers.structure_handler import register_tools as _reg_struct
from mcp_server.handlers.git_handler import register_tools as _reg_git
from mcp_server.handlers.workflow_handler import register_tools as _reg_workflow

# Setup a mock MCP instance
_test_mcp = FastMCP("test_auto_detect")
_reg_ws(_test_mcp)
_reg_analysis(_test_mcp)
_reg_struct(_test_mcp)
_reg_git(_test_mcp)
_reg_workflow(_test_mcp)


def get_tool(name):
    return _test_mcp._tool_manager._tools[name].fn


@pytest.fixture
def in_temp_dir(tmp_path, monkeypatch):
    """Fixture to run a test inside a temporary directory (mocking CWD)."""
    # Create a dummy file to make it look like a project
    (tmp_path / "dummy.py").write_text("print('hello')")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(os, "getcwd", lambda: str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_start_session_auto_detect(in_temp_dir):
    """Verify start_session falls back to CWD."""
    start_session = get_tool("start_session")
    # No workspace_path provided
    result = await start_session()
    assert "SESSION INITIALIZED" in result
    # It should have detected the temp dir as workspace
    assert str(in_temp_dir.name) in result


@pytest.mark.asyncio
async def test_get_project_structure_auto_detect(in_temp_dir):
    """Verify get_project_structure falls back to CWD."""
    get_project_structure = get_tool("get_project_structure")
    result = await get_project_structure()
    assert "Project:" in result
    assert str(in_temp_dir.name) in result
    assert ".py" in result


@pytest.mark.asyncio
async def test_find_todos_auto_detect(in_temp_dir):
    """Verify find_todos falls back to CWD."""
    find_todos = get_tool("find_todos")
    (in_temp_dir / "todo.py").write_text("# TODO: fix me")
    result = await find_todos()
    assert "TODO" in result
    assert "fix me" in result


@pytest.mark.asyncio
async def test_rp_build_auto_detect(in_temp_dir):
    """Verify rp_build falls back to CWD."""
    rp_build = get_tool("rp_build")
    # This might fail if it can't find any scope, but it shouldn't raise ValueError for path
    result = await rp_build(task_description="test task")
    assert "Error" not in result or "No files detected" in result
    assert "ValueError" not in result  # Ensure it didn't crash on path resolution
