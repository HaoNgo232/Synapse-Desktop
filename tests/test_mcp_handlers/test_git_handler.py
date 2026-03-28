# # """Unit tests for mcp_server/handlers/git_handler.py"""
# #
# # import pytest
# # from pathlib import Path
# # from unittest.mock import Mock, patch
# # from mcp.server.fastmcp import FastMCP
# #
# # from infrastructure.mcp.handlers.git_handler import register_tools
# #
# #
# # @pytest.fixture
# # def mcp_instance():
# #     mcp = FastMCP("test_git")
# #     register_tools(mcp)
# #     return mcp
# #
# #
# # @pytest.fixture
# # def mock_workspace(tmp_path, monkeypatch):
# #     monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
# #     return tmp_path
# #
# #
# # def get_tool(mcp, name):
# #     return mcp._tool_manager._tools[name].fn
# #
# #
# # @pytest.mark.asyncio
# # # async def test_diff_summary_basic(mcp_instance, mock_workspace):
# #     """Test diff_summary with valid git repo"""
# #     mock_result = Mock()
# #     mock_result.returncode = 0
# #     mock_result.stdout = "M\ttest.py\nA\tnew.py"
# #     mock_result.stderr = ""
# #
# #     with patch("subprocess.run", return_value=mock_result):
# #         tool = get_tool(mcp_instance, "diff_summary")
# #         result = await tool(workspace_path=str(mock_workspace))
# #
# #         assert "Modified" in result or "Added" in result or "No changes" in result
# #
# #
# # @pytest.mark.asyncio
# # # async def test_diff_summary_not_git_repo(mcp_instance, mock_workspace):
# #     """Test diff_summary with non-git directory"""
# #     mock_result = Mock()
# #     mock_result.returncode = 128
# #     mock_result.stderr = "not a git repository"
# #
# #     with patch("subprocess.run", return_value=mock_result):
# #         tool = get_tool(mcp_instance, "diff_summary")
# #         result = await tool(workspace_path=str(mock_workspace))
# #
# #         assert "Error" in result and "git repository" in result
# #
# #
# # @pytest.mark.asyncio
# # # async def test_diff_summary_invalid_ref(mcp_instance, mock_workspace):
# #     """Test diff_summary with invalid git ref (injection attempt)"""
# #     tool = get_tool(mcp_instance, "diff_summary")
# #     result = await tool(
# #         target="--output=/tmp/pwned", workspace_path=str(mock_workspace)
# #     )
# #
# #     assert "Error" in result and "Invalid" in result
# #
# #
# # @pytest.mark.asyncio
# # # async def test_diff_summary_timeout(mcp_instance, mock_workspace):
# #     """Test diff_summary handles timeout"""
# #     import subprocess
# #
# #     with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 15)):
# #         tool = get_tool(mcp_instance, "diff_summary")
# #         result = await tool(workspace_path=str(mock_workspace))
# #
# #         assert "Error" in result and "timed out" in result
# #
# #
# # @pytest.mark.asyncio
# # # async def test_diff_summary_no_changes(mcp_instance, mock_workspace):
# #     """Test diff_summary with no changes"""
# #     mock_result = Mock()
# #     mock_result.returncode = 0
# #     mock_result.stdout = ""
# #     mock_result.stderr = ""
# #
# #     with patch("subprocess.run", return_value=mock_result):
# #         tool = get_tool(mcp_instance, "diff_summary")
# #         result = await tool(workspace_path=str(mock_workspace))
# #
# #         assert "No changes" in result
# #
# #
# # @pytest.mark.asyncio
# # # async def test_diff_summary_with_renames(mcp_instance, mock_workspace):
# #     """Test diff_summary with renamed files"""
# #     mock_result = Mock()
# #     mock_result.returncode = 0
# #     mock_result.stdout = "R100\told.py\tnew.py"
# #     mock_result.stderr = ""
# #
# #     with patch("subprocess.run", return_value=mock_result):
# #         tool = get_tool(mcp_instance, "diff_summary")
# #         result = await tool(workspace_path=str(mock_workspace))
# #
# #         assert "Renamed" in result or "old.py" in result
# #
# #
# # @pytest.mark.asyncio
# # # async def test_diff_summary_with_deletions(mcp_instance, mock_workspace):
# #     """Test diff_summary with deleted files"""
# #     mock_result = Mock()
# #     mock_result.returncode = 0
# #     mock_result.stdout = "D\tdeleted.py"
# #     mock_result.stderr = ""
# #
# #     with patch("subprocess.run", return_value=mock_result):
# #         tool = get_tool(mcp_instance, "diff_summary")
# #         result = await tool(workspace_path=str(mock_workspace))
# #
# #         assert "Deleted" in result or "deleted.py" in result
# #
# #
# # @pytest.mark.asyncio
# # # async def test_diff_summary_with_copies(mcp_instance, mock_workspace):
# #     """Test diff_summary with copied files"""
# #     mock_result = Mock()
# #     mock_result.returncode = 0
# #     mock_result.stdout = "C100\tsrc.py\tdest.py"
# #     mock_result.stderr = ""
# #
# #     with patch("subprocess.run", return_value=mock_result):
# #         tool = get_tool(mcp_instance, "diff_summary")
# #         result = await tool(workspace_path=str(mock_workspace))
# #
# #         assert "Added" in result or "copied" in result.lower()
