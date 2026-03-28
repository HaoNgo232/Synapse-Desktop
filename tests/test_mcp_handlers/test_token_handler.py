# """Unit tests for mcp_server/handlers/token_handler.py"""
#
# import pytest
# from pathlib import Path
# from unittest.mock import patch
# from mcp.server.fastmcp import FastMCP
#
# from infrastructure.mcp.handlers.token_handler import register_tools
#
#
# @pytest.fixture
# def mcp_instance():
#     mcp = FastMCP("test_token")
#     register_tools(mcp)
#     return mcp
#
#
# @pytest.fixture
# def mock_workspace(tmp_path, monkeypatch):
#     test_file = tmp_path / "test.py"
#     test_file.write_text("def foo(): pass")
#     monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
#     return tmp_path
#
#
# def get_tool(mcp, name):
#     return mcp._tool_manager._tools[name].fn
#
#
# @pytest.mark.asyncio
# async def test_estimate_tokens_basic(mcp_instance, mock_workspace):
#     """Test estimate_tokens returns token count"""
#     with patch(
#         "application.services.tokenization_service.TokenizationService.count_tokens",
#         return_value=10,
#     ):
#         tool = get_tool(mcp_instance, "estimate_tokens")
#         result = await tool(file_paths=["test.py"], workspace_path=str(mock_workspace))
#
#         assert "Total" in result
#         assert "tokens" in result
#
#
# @pytest.mark.asyncio
# async def test_estimate_tokens_path_traversal(mcp_instance, mock_workspace):
#     """Test estimate_tokens prevents path traversal"""
#     tool = get_tool(mcp_instance, "estimate_tokens")
#     result = await tool(
#         file_paths=["../../../etc/passwd"], workspace_path=str(mock_workspace)
#     )
#
#     assert "Error" in result
#
#
# @pytest.mark.asyncio
# async def test_estimate_tokens_nonexistent(mcp_instance, mock_workspace):
#     """Test estimate_tokens with nonexistent file"""
#     tool = get_tool(mcp_instance, "estimate_tokens")
#     result = await tool(
#         file_paths=["nonexistent.py"], workspace_path=str(mock_workspace)
#     )
#
#     assert "Error" in result or "not found" in result
#
#
# @pytest.mark.asyncio
# async def test_estimate_tokens_empty_list(mcp_instance, mock_workspace):
#     """Test estimate_tokens with empty file list"""
#     tool = get_tool(mcp_instance, "estimate_tokens")
#     result = await tool(file_paths=[], workspace_path=str(mock_workspace))
#
#     assert "Error" in result or "No valid files" in result
#
#
# @pytest.mark.asyncio
# async def test_estimate_tokens_multiple_files(mcp_instance, mock_workspace):
#     """Test estimate_tokens with multiple files"""
#     (mock_workspace / "test2.py").write_text("def bar(): pass")
#
#     with patch(
#         "application.services.tokenization_service.TokenizationService.count_tokens",
#         return_value=10,
#     ):
#         tool = get_tool(mcp_instance, "estimate_tokens")
#         result = await tool(
#             file_paths=["test.py", "test2.py"], workspace_path=str(mock_workspace)
#         )
#
#         assert "Total" in result
#         assert "2" in result or "Files" in result
