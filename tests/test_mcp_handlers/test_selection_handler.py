# """Unit tests for mcp_server/handlers/selection_handler.py"""
#
# import pytest
# from pathlib import Path
# from mcp.server.fastmcp import FastMCP
#
# from infrastructure.mcp.handlers.selection_handler import register_tools
#
#
# @pytest.fixture
# def mcp_instance():
#     mcp = FastMCP("test_selection")
#     register_tools(mcp)
#     return mcp
#
#
# @pytest.fixture
# def mock_workspace(tmp_path, monkeypatch):
#     test_file = tmp_path / "test.py"
#     test_file.write_text("pass")
#     monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
#     return tmp_path
#
#
# def get_tool(mcp, name):
#     return mcp._tool_manager._tools[name].fn
#
#
# @pytest.mark.asyncio
# async def test_manage_selection_get_empty(mcp_instance, mock_workspace):
#     """Test get action with no selection"""
#     tool = get_tool(mcp_instance, "manage_selection")
#     result = await tool(action="get", workspace_path=str(mock_workspace))
#
#     assert "No files" in result
#
#
# @pytest.mark.asyncio
# async def test_manage_selection_set(mcp_instance, mock_workspace):
#     """Test set action"""
#     tool = get_tool(mcp_instance, "manage_selection")
#     result = await tool(
#         action="set", paths=["test.py"], workspace_path=str(mock_workspace)
#     )
#
#     assert "updated" in result or "selected" in result
#
#
# @pytest.mark.asyncio
# async def test_manage_selection_add(mcp_instance, mock_workspace):
#     """Test add action"""
#     tool = get_tool(mcp_instance, "manage_selection")
#     await tool(action="set", paths=["test.py"], workspace_path=str(mock_workspace))
#     result = await tool(
#         action="add", paths=["test.py"], workspace_path=str(mock_workspace)
#     )
#
#     assert "updated" in result or "selected" in result
#
#
# @pytest.mark.asyncio
# async def test_manage_selection_clear(mcp_instance, mock_workspace):
#     """Test clear action"""
#     tool = get_tool(mcp_instance, "manage_selection")
#     await tool(action="set", paths=["test.py"], workspace_path=str(mock_workspace))
#     result = await tool(action="clear", workspace_path=str(mock_workspace))
#
#     assert "cleared" in result.lower()
#
#
# @pytest.mark.asyncio
# async def test_manage_selection_path_traversal(mcp_instance, mock_workspace):
#     """Test set action prevents path traversal"""
#     tool = get_tool(mcp_instance, "manage_selection")
#     result = await tool(
#         action="set", paths=["../../../etc/passwd"], workspace_path=str(mock_workspace)
#     )
#
#     assert "Error" in result
#
#
# @pytest.mark.asyncio
# async def test_manage_selection_nonexistent_file(mcp_instance, mock_workspace):
#     """Test set action with nonexistent file"""
#     tool = get_tool(mcp_instance, "manage_selection")
#     result = await tool(
#         action="set", paths=["nonexistent.py"], workspace_path=str(mock_workspace)
#     )
#
#     assert "Error" in result or "not found" in result
#
#
# @pytest.mark.asyncio
# async def test_manage_selection_invalid_action(mcp_instance, mock_workspace):
#     """Test invalid action"""
#     tool = get_tool(mcp_instance, "manage_selection")
#     result = await tool(action="invalid", workspace_path=str(mock_workspace))
#
#     assert "Error" in result and "Invalid action" in result
#
#
# @pytest.mark.asyncio
# async def test_manage_selection_missing_paths(mcp_instance, mock_workspace):
#     """Test set/add without paths parameter"""
#     tool = get_tool(mcp_instance, "manage_selection")
#     result = await tool(action="set", workspace_path=str(mock_workspace))
#
#     assert "Error" in result and "required" in result
