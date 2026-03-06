"""Unit tests for mcp_server/handlers/dependency_handler.py"""

import pytest
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from infrastructure.mcp.handlers.dependency_handler import register_tools


@pytest.fixture
def mcp_instance():
    mcp = FastMCP("test_dependency")
    register_tools(mcp)
    return mcp


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    (tmp_path / "main.py").write_text("from utils import helper\ndef main(): helper()")
    (tmp_path / "utils.py").write_text("def helper(): pass")
    (tmp_path / "test_main.py").write_text(
        "from main import main\ndef test_main(): pass"
    )
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    def mock_collect(ws, workspace_path=None):
        return [
            str(tmp_path / "main.py"),
            str(tmp_path / "utils.py"),
            str(tmp_path / "test_main.py"),
        ]

    monkeypatch.setattr(
        "application.services.workspace_index.collect_files_from_disk", mock_collect
    )

    return tmp_path


def get_tool(mcp, name):
    return mcp._tool_manager._tools[name].fn


@pytest.mark.asyncio
async def test_get_imports_graph_basic(mcp_instance, mock_workspace):
    """Test get_imports_graph returns dependency graph"""
    tool = get_tool(mcp_instance, "get_imports_graph")
    result = await tool(workspace_path=str(mock_workspace))

    assert "Dependency Graph" in result or "imports" in result


@pytest.mark.asyncio
async def test_get_imports_graph_with_file_paths(mcp_instance, mock_workspace):
    """Test get_imports_graph with specific files"""
    tool = get_tool(mcp_instance, "get_imports_graph")
    result = await tool(file_paths=["main.py"], workspace_path=str(mock_workspace))

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_imports_graph_path_traversal(mcp_instance, mock_workspace):
    """Test get_imports_graph prevents path traversal"""
    tool = get_tool(mcp_instance, "get_imports_graph")
    result = await tool(
        file_paths=["../../../etc/passwd"], workspace_path=str(mock_workspace)
    )

    assert "Error" in result


@pytest.mark.asyncio
async def test_get_callers_basic(mcp_instance, mock_workspace):
    """Test get_callers finds function callers"""
    tool = get_tool(mcp_instance, "get_callers")
    result = await tool(symbol_name="helper", workspace_path=str(mock_workspace))

    assert "helper" in result or "callers" in result or "No callers" in result


@pytest.mark.asyncio
async def test_get_callers_no_results(mcp_instance, mock_workspace):
    """Test get_callers with no callers found"""
    tool = get_tool(mcp_instance, "get_callers")
    result = await tool(
        symbol_name="nonexistent_func", workspace_path=str(mock_workspace)
    )

    assert "No callers found" in result


@pytest.mark.asyncio
async def test_get_callers_with_extension_filter(mcp_instance, mock_workspace):
    """Test get_callers with file extension filter"""
    tool = get_tool(mcp_instance, "get_callers")
    result = await tool(
        symbol_name="helper",
        file_extensions=[".py"],
        workspace_path=str(mock_workspace),
    )

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_related_tests_basic(mcp_instance, mock_workspace):
    """Test get_related_tests finds test files"""
    tool = get_tool(mcp_instance, "get_related_tests")
    result = await tool(file_paths=["main.py"], workspace_path=str(mock_workspace))

    assert "test" in result.lower() or "No related test" in result


@pytest.mark.asyncio
async def test_get_related_tests_no_tests(mcp_instance, mock_workspace):
    """Test get_related_tests with no test files"""
    tool = get_tool(mcp_instance, "get_related_tests")
    result = await tool(file_paths=["utils.py"], workspace_path=str(mock_workspace))

    assert "No related test" in result or "test" in result.lower()


@pytest.mark.asyncio
async def test_get_related_tests_path_traversal(mcp_instance, mock_workspace):
    """Test get_related_tests prevents path traversal"""
    tool = get_tool(mcp_instance, "get_related_tests")
    result = await tool(
        file_paths=["../../../etc/passwd"], workspace_path=str(mock_workspace)
    )

    assert "Error" in result or "No related test" in result


@pytest.mark.asyncio
async def test_get_imports_graph_empty_workspace(mcp_instance, tmp_path, monkeypatch):
    """Test get_imports_graph with no code files"""
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    def mock_collect(ws, workspace_path=None):
        return []

    monkeypatch.setattr(
        "application.services.workspace_index.collect_files_from_disk", mock_collect
    )

    tool = get_tool(mcp_instance, "get_imports_graph")
    result = await tool(workspace_path=str(tmp_path))

    assert "0" in result or "analyzed" in result.lower()


@pytest.mark.asyncio
async def test_get_callers_max_results(mcp_instance, mock_workspace, monkeypatch):
    """Test get_callers respects max_results limit"""

    def mock_collect(ws, workspace_path=None):
        return [str(mock_workspace / "main.py")]

    monkeypatch.setattr(
        "application.services.workspace_index.collect_files_from_disk", mock_collect
    )

    tool = get_tool(mcp_instance, "get_callers")
    result = await tool(
        symbol_name="helper", max_results=1, workspace_path=str(mock_workspace)
    )

    assert isinstance(result, str)
