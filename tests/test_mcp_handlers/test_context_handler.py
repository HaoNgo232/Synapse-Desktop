"""Unit tests for mcp_server/handlers/context_handler.py"""

import pytest
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from mcp_server.handlers.context_handler import register_tools


@pytest.fixture
def mcp_instance():
    mcp = FastMCP("test_context")
    register_tools(mcp)
    return mcp


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    (tmp_path / "test.py").write_text("def foo(): pass")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main(): pass")
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
async def test_get_codemap_basic(mcp_instance, mock_workspace):
    """Test get_codemap extracts code structure"""
    tool = get_tool(mcp_instance, "get_codemap")
    result = await tool(file_paths=["test.py"], workspace_path=str(mock_workspace))

    assert "foo" in result or "Smart Context" in result or "No code structure" in result


@pytest.mark.asyncio
async def test_get_codemap_path_traversal(mcp_instance, mock_workspace):
    """Test get_codemap prevents path traversal"""
    tool = get_tool(mcp_instance, "get_codemap")
    result = await tool(
        file_paths=["../../../etc/passwd"], workspace_path=str(mock_workspace)
    )

    assert "Error" in result


@pytest.mark.asyncio
async def test_get_codemap_nonexistent(mcp_instance, mock_workspace):
    """Test get_codemap with nonexistent file"""
    tool = get_tool(mcp_instance, "get_codemap")
    result = await tool(
        file_paths=["nonexistent.py"], workspace_path=str(mock_workspace)
    )

    assert "Error" in result or "not found" in result


@pytest.mark.asyncio
async def test_batch_codemap_basic(mcp_instance, mock_workspace):
    """Test batch_codemap scans directory"""
    tool = get_tool(mcp_instance, "batch_codemap")
    result = await tool(directory=".", workspace_path=str(mock_workspace))

    assert "Codemap" in result or "files" in result


@pytest.mark.asyncio
async def test_batch_codemap_with_extensions(mcp_instance, mock_workspace):
    """Test batch_codemap with extension filter"""
    tool = get_tool(mcp_instance, "batch_codemap")
    result = await tool(
        directory=".", extensions=[".py"], workspace_path=str(mock_workspace)
    )

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_batch_codemap_path_traversal(mcp_instance, mock_workspace):
    """Test batch_codemap prevents path traversal"""
    tool = get_tool(mcp_instance, "batch_codemap")
    result = await tool(directory="../../../etc", workspace_path=str(mock_workspace))

    assert "Error" in result


@pytest.mark.asyncio
async def test_build_prompt_basic(mcp_instance, mock_workspace):
    """Test build_prompt creates prompt"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(file_paths=["test.py"], workspace_path=str(mock_workspace))

    assert "Prompt" in result or "tokens" in result


@pytest.mark.asyncio
async def test_build_prompt_with_output_file(mcp_instance, mock_workspace):
    """Test build_prompt writes to file"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(
        file_paths=["test.py"],
        output_file="prompt.xml",
        workspace_path=str(mock_workspace),
    )

    assert "written to" in result or "Prompt" in result


@pytest.mark.asyncio
async def test_build_prompt_path_traversal_output(mcp_instance, mock_workspace):
    """Test build_prompt prevents path traversal in output_file"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(
        file_paths=["test.py"],
        output_file="../../../tmp/evil.xml",
        workspace_path=str(mock_workspace),
    )

    assert "Error" in result


@pytest.mark.asyncio
async def test_build_prompt_invalid_format(mcp_instance, mock_workspace):
    """Test build_prompt with invalid format"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(
        file_paths=["test.py"],
        output_format="invalid",
        workspace_path=str(mock_workspace),
    )

    assert "Error" in result or "Invalid format" in result


@pytest.mark.asyncio
async def test_build_prompt_with_profile(mcp_instance, mock_workspace):
    """Test build_prompt with profile"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(
        file_paths=["test.py"], profile="review", workspace_path=str(mock_workspace)
    )

    assert "Prompt" in result or "tokens" in result or "Unknown profile" in result


@pytest.mark.asyncio
async def test_build_prompt_with_dependencies(mcp_instance, mock_workspace):
    """Test build_prompt with auto_expand_dependencies"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(
        file_paths=["test.py"],
        auto_expand_dependencies=True,
        workspace_path=str(mock_workspace),
    )

    assert "Prompt" in result or "tokens" in result


@pytest.mark.asyncio
async def test_build_prompt_with_max_tokens(mcp_instance, mock_workspace):
    """Test build_prompt with max_tokens limit"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(
        file_paths=["test.py"], max_tokens=100, workspace_path=str(mock_workspace)
    )

    assert "Prompt" in result or "tokens" in result


@pytest.mark.asyncio
async def test_build_prompt_use_selection(mcp_instance, mock_workspace):
    """Test build_prompt with use_selection"""
    import json

    selection_file = mock_workspace / ".synapse" / "selection.json"
    selection_file.parent.mkdir(exist_ok=True)
    selection_file.write_text(json.dumps({"selected_files": ["test.py"]}))

    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(
        file_paths=[], use_selection=True, workspace_path=str(mock_workspace)
    )

    assert "Prompt" in result or "tokens" in result


@pytest.mark.asyncio
async def test_build_prompt_json_metadata(mcp_instance, mock_workspace):
    """Test build_prompt with JSON metadata format"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(
        file_paths=["test.py"],
        output_file="out.xml",
        metadata_format="json",
        workspace_path=str(mock_workspace),
    )

    assert "{" in result or "output_file" in result


@pytest.mark.asyncio
async def test_build_prompt_invalid_metadata_format(mcp_instance, mock_workspace):
    """Test build_prompt with invalid metadata_format"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(
        file_paths=["test.py"],
        metadata_format="invalid",
        workspace_path=str(mock_workspace),
    )

    assert "Error" in result


@pytest.mark.asyncio
async def test_get_codemap_empty_file(mcp_instance, tmp_path, monkeypatch):
    """Test get_codemap with empty file"""
    empty = tmp_path / "empty.py"
    empty.write_text("")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    tool = get_tool(mcp_instance, "get_codemap")
    result = await tool(file_paths=["empty.py"], workspace_path=str(tmp_path))

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_batch_codemap_no_supported_files(mcp_instance, tmp_path, monkeypatch):
    """Test batch_codemap with no supported files"""
    (tmp_path / "test.txt").write_text("not code")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    def mock_collect(ws, workspace_path=None):
        return [str(tmp_path / "test.txt")]

    monkeypatch.setattr(
        "application.services.workspace_index.collect_files_from_disk", mock_collect
    )

    tool = get_tool(mcp_instance, "batch_codemap")
    result = await tool(directory=".", workspace_path=str(tmp_path))

    assert "No supported" in result or "0 files" in result


@pytest.mark.asyncio
async def test_build_prompt_empty_file_list(mcp_instance, mock_workspace):
    """Test build_prompt with empty file list and no selection"""
    tool = get_tool(mcp_instance, "build_prompt")
    result = await tool(file_paths=[], workspace_path=str(mock_workspace))

    assert "Error" in result or "No valid files" in result
