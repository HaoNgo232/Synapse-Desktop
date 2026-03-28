# """Unit tests for mcp_server/handlers/analysis_handler.py"""
#
# import pytest
# from pathlib import Path
# from mcp.server.fastmcp import FastMCP
#
# from infrastructure.mcp.handlers.analysis_handler import register_tools
#
#
# @pytest.fixture
# def mcp_instance():
#     mcp = FastMCP("test_analysis")
#     register_tools(mcp)
#     return mcp
#
#
# @pytest.fixture
# def mock_workspace(tmp_path, monkeypatch):
#     """Mock workspace with CWD fallback"""
#     test_file = tmp_path / "test.py"
#     test_file.write_text("def foo():\n    pass\n# TODO: fix")
#     monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
#     return tmp_path
#
#
# def get_tool(mcp, name):
#     return mcp._tool_manager._tools[name].fn
#
#
# @pytest.mark.asyncio
# async def test_find_references_basic(mcp_instance, mock_workspace, monkeypatch):
#     """Test find_references with valid symbol"""
#
#     def mock_collect(ws, workspace_path=None):
#         return [str(mock_workspace / "test.py")]
#
#     monkeypatch.setattr(
#         "application.services.workspace_index.collect_files_from_disk", mock_collect
#     )
#
#     tool = get_tool(mcp_instance, "find_references")
#     result = await tool(symbol_name="foo", workspace_path=str(mock_workspace))
#
#     assert "foo" in result or "No references found" in result
#
#
# @pytest.mark.asyncio
# async def test_find_references_invalid_workspace(mcp_instance):
#     """Test find_references with invalid workspace"""
#     tool = get_tool(mcp_instance, "find_references")
#     result = await tool(symbol_name="foo", workspace_path="/nonexistent")
#
#     assert "Error" in result
#
#
# @pytest.mark.asyncio
# async def test_find_references_path_traversal(mcp_instance, mock_workspace):
#     """Test find_references doesn't allow path traversal"""
#     tool = get_tool(mcp_instance, "find_references")
#     result = await tool(
#         symbol_name="foo", workspace_path=str(mock_workspace / "../../../etc")
#     )
#
#     assert "Error" in result or "not a valid directory" in result
#
#
# @pytest.mark.asyncio
# async def test_get_symbols_basic(mcp_instance, mock_workspace):
#     """Test get_symbols extracts symbols"""
#     tool = get_tool(mcp_instance, "get_symbols")
#     result = await tool(file_path="test.py", workspace_path=str(mock_workspace))
#
#     assert "symbols" in result.lower() or "foo" in result
#
#
# @pytest.mark.asyncio
# async def test_get_symbols_path_traversal(mcp_instance, mock_workspace):
#     """Test get_symbols prevents path traversal"""
#     tool = get_tool(mcp_instance, "get_symbols")
#     result = await tool(
#         file_path="../../../etc/passwd", workspace_path=str(mock_workspace)
#     )
#
#     assert "Error" in result or "traversal" in result
#
#
# @pytest.mark.asyncio
# async def test_get_symbols_nonexistent_file(mcp_instance, mock_workspace):
#     """Test get_symbols with nonexistent file"""
#     tool = get_tool(mcp_instance, "get_symbols")
#     result = await tool(file_path="nonexistent.py", workspace_path=str(mock_workspace))
#
#     assert "Error" in result or "not found" in result
#
#
# @pytest.mark.asyncio
# async def test_find_references_with_extensions(
#     mcp_instance, mock_workspace, monkeypatch
# ):
#     """Test find_references with file extension filter"""
#
#     def mock_collect(ws, workspace_path=None):
#         return [str(mock_workspace / "test.py")]
#
#     monkeypatch.setattr(
#         "application.services.workspace_index.collect_files_from_disk", mock_collect
#     )
#
#     tool = get_tool(mcp_instance, "find_references")
#     result = await tool(
#         symbol_name="foo", file_extensions=[".py"], workspace_path=str(mock_workspace)
#     )
#
#     assert isinstance(result, str)
#
#
# @pytest.mark.asyncio
# async def test_get_symbols_no_symbols(mcp_instance, tmp_path, monkeypatch):
#     """Test get_symbols with file containing no symbols"""
#     empty_file = tmp_path / "empty.py"
#     empty_file.write_text("# Just a comment")
#     monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
#
#     tool = get_tool(mcp_instance, "get_symbols")
#     result = await tool(file_path="empty.py", workspace_path=str(tmp_path))
#
#     assert "No symbols" in result or "symbols" in result.lower()
#
#
# @pytest.mark.asyncio
# async def test_find_references_exception_handling(
#     mcp_instance, mock_workspace, monkeypatch
# ):
#     """Test find_references handles file read errors"""
#
#     def mock_collect(ws, workspace_path=None):
#         return [str(mock_workspace / "test.py")]
#
#     monkeypatch.setattr(
#         "application.services.workspace_index.collect_files_from_disk", mock_collect
#     )
#
#     # Mock Path.read_text to raise exception
#     original_read = Path.read_text
#
#     def mock_read(self, *args, **kwargs):
#         if "test.py" in str(self):
#             raise UnicodeDecodeError("utf-8", b"", 0, 1, "test")
#         return original_read(self, *args, **kwargs)
#
#     monkeypatch.setattr(Path, "read_text", mock_read)
#
#     tool = get_tool(mcp_instance, "find_references")
#     result = await tool(symbol_name="foo", workspace_path=str(mock_workspace))
#
#     assert isinstance(result, str)
