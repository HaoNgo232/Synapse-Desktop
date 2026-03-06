"""Unit tests for mcp_server/handlers/workflow_handler.py"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from mcp.server.fastmcp import FastMCP

from infrastructure.mcp.handlers.workflow_handler import register_tools


@pytest.fixture
def mcp_instance():
    mcp = FastMCP("test_workflow")
    register_tools(mcp)
    return mcp


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    (tmp_path / "main.py").write_text("def main(): pass")
    (tmp_path / "utils.py").write_text("def helper(): pass")
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
    return tmp_path


def get_tool(mcp, name):
    return mcp._tool_manager._tools[name].fn


@pytest.mark.asyncio
async def test_rp_build_basic(mcp_instance, mock_workspace):
    """Test rp_build creates context"""
    mock_result = Mock()
    mock_result.prompt = "test prompt"
    mock_result.total_tokens = 100
    mock_result.files_included = 1
    mock_result.files_sliced = 0
    mock_result.files_smart_only = 0
    mock_result.scope_summary = "1 primary"
    mock_result.optimizations = []

    with patch(
        "domain.workflow.context_builder.run_context_builder", return_value=mock_result
    ):
        tool = get_tool(mcp_instance, "rp_build")
        result = await tool(
            task_description="Test task", workspace_path=str(mock_workspace)
        )

        assert "Context Builder" in result or "Files included" in result


@pytest.mark.asyncio
async def test_rp_build_with_output_file(mcp_instance, mock_workspace):
    """Test rp_build writes to output file"""
    mock_result = Mock()
    mock_result.prompt = "test"
    mock_result.total_tokens = 100
    mock_result.files_included = 1
    mock_result.files_sliced = 0
    mock_result.files_smart_only = 0
    mock_result.scope_summary = "1 primary"
    mock_result.optimizations = []

    with patch(
        "domain.workflow.context_builder.run_context_builder", return_value=mock_result
    ):
        tool = get_tool(mcp_instance, "rp_build")
        result = await tool(
            task_description="Test",
            output_file="output.xml",
            workspace_path=str(mock_workspace),
        )

        assert "written to" in result or "output.xml" in result


@pytest.mark.asyncio
async def test_rp_build_path_traversal(mcp_instance, mock_workspace):
    """Test rp_build prevents path traversal in output_file"""
    tool = get_tool(mcp_instance, "rp_build")
    result = await tool(
        task_description="Test",
        output_file="../../../tmp/evil.xml",
        workspace_path=str(mock_workspace),
    )

    assert "Error" in result


@pytest.mark.asyncio
async def test_rp_review_basic(mcp_instance, mock_workspace):
    """Test rp_review creates review context"""
    mock_result = Mock()
    mock_result.prompt = "review prompt"
    mock_result.total_tokens = 100
    mock_result.files_changed = 1
    mock_result.files_context = 0

    with patch(
        "domain.workflow.code_reviewer.run_code_review", return_value=mock_result
    ):
        tool = get_tool(mcp_instance, "rp_review")
        result = await tool(workspace_path=str(mock_workspace))

        assert "Code Review" in result or "Changed files" in result


@pytest.mark.asyncio
async def test_rp_review_invalid_ref(mcp_instance, mock_workspace):
    """Test rp_review with invalid git ref"""
    tool = get_tool(mcp_instance, "rp_review")
    result = await tool(
        base_ref="--output=/tmp/pwned", workspace_path=str(mock_workspace)
    )

    assert "Error" in result and "Invalid" in result


@pytest.mark.asyncio
async def test_rp_refactor_discover(mcp_instance, mock_workspace):
    """Test rp_refactor discover phase"""
    mock_result = Mock()
    mock_result.prompt = "discovery"
    mock_result.total_tokens = 100
    mock_result.scope_files = ["main.py"]

    with patch(
        "domain.workflow.refactor_workflow.run_refactor_discovery",
        return_value=mock_result,
    ):
        tool = get_tool(mcp_instance, "rp_refactor")
        result = await tool(
            refactor_scope="Refactor main",
            phase="discover",
            workspace_path=str(mock_workspace),
        )

        assert "Discovery" in result or "Scope files" in result


@pytest.mark.asyncio
async def test_rp_refactor_plan_without_discovery(mcp_instance, mock_workspace):
    """Test rp_refactor plan phase without discovery report"""
    tool = get_tool(mcp_instance, "rp_refactor")
    result = await tool(
        refactor_scope="Refactor", phase="plan", workspace_path=str(mock_workspace)
    )

    assert "Error" in result and "discovery_report required" in result


@pytest.mark.asyncio
async def test_rp_refactor_invalid_phase(mcp_instance, mock_workspace):
    """Test rp_refactor with invalid phase"""
    tool = get_tool(mcp_instance, "rp_refactor")
    result = await tool(
        refactor_scope="Refactor", phase="invalid", workspace_path=str(mock_workspace)
    )

    assert "Error" in result


@pytest.mark.asyncio
async def test_rp_investigate_basic(mcp_instance, mock_workspace):
    """Test rp_investigate creates investigation context"""
    mock_result = Mock()
    mock_result.prompt = "investigation"
    mock_result.total_tokens = 100
    mock_result.files_investigated = 1
    mock_result.max_depth_reached = 2

    with patch(
        "domain.workflow.bug_investigator.run_bug_investigation",
        return_value=mock_result,
    ):
        tool = get_tool(mcp_instance, "rp_investigate")
        result = await tool(
            bug_description="Bug description", workspace_path=str(mock_workspace)
        )

        assert "Investigation" in result or "Files investigated" in result


@pytest.mark.asyncio
async def test_rp_test_basic(mcp_instance, mock_workspace):
    """Test rp_test creates test context"""
    mock_result = Mock()
    mock_result.prompt = "test prompt"
    mock_result.total_tokens = 100
    mock_result.files_included = 1
    mock_result.files_sliced = 0
    mock_result.files_smart_only = 0
    mock_result.scope_summary = "1 primary"
    mock_result.coverage_summary = "50%"
    mock_result.untested_symbols = 5
    mock_result.suggested_test_files = []
    mock_result.optimizations = []

    with patch(
        "domain.workflow.test_builder.run_test_builder", return_value=mock_result
    ):
        tool = get_tool(mcp_instance, "rp_test")
        result = await tool(workspace_path=str(mock_workspace))

        assert "Test Builder" in result or "Coverage" in result


@pytest.mark.asyncio
async def test_rp_build_invalid_workspace(mcp_instance):
    """Test rp_build with invalid workspace"""
    tool = get_tool(mcp_instance, "rp_build")
    result = await tool(task_description="Test", workspace_path="/nonexistent")

    assert "Error" in result


@pytest.mark.asyncio
async def test_rp_review_with_focus(mcp_instance, mock_workspace):
    """Test rp_review with review_focus"""
    mock_result = Mock()
    mock_result.prompt = "review"
    mock_result.total_tokens = 100
    mock_result.files_changed = 1
    mock_result.files_context = 0

    with patch(
        "domain.workflow.code_reviewer.run_code_review", return_value=mock_result
    ):
        tool = get_tool(mcp_instance, "rp_review")
        result = await tool(review_focus="security", workspace_path=str(mock_workspace))

        assert "Code Review" in result or "Changed files" in result


@pytest.mark.asyncio
async def test_rp_refactor_plan_with_discovery(mcp_instance, mock_workspace):
    """Test rp_refactor plan phase with discovery report"""
    mock_result = Mock()
    mock_result.prompt = "plan"
    mock_result.total_tokens = 100
    mock_result.files_to_modify = ["main.py"]
    mock_result.migration_needed = False

    with patch(
        "domain.workflow.refactor_workflow.run_refactor_planning",
        return_value=mock_result,
    ):
        tool = get_tool(mcp_instance, "rp_refactor")
        result = await tool(
            refactor_scope="Refactor",
            phase="plan",
            discovery_report="Discovery report content",
            workspace_path=str(mock_workspace),
        )

        assert "Plan" in result or "Files to modify" in result


@pytest.mark.asyncio
async def test_rp_investigate_with_error_trace(mcp_instance, mock_workspace):
    """Test rp_investigate with error trace"""
    mock_result = Mock()
    mock_result.prompt = "investigation"
    mock_result.total_tokens = 100
    mock_result.files_investigated = 2
    mock_result.max_depth_reached = 3

    with patch(
        "domain.workflow.bug_investigator.run_bug_investigation",
        return_value=mock_result,
    ):
        tool = get_tool(mcp_instance, "rp_investigate")
        result = await tool(
            bug_description="Bug",
            error_trace='File "main.py", line 10, in main',
            workspace_path=str(mock_workspace),
        )

        assert "Investigation" in result or "Files investigated" in result


@pytest.mark.asyncio
async def test_rp_test_with_framework(mcp_instance, mock_workspace):
    """Test rp_test with specific test framework"""
    mock_result = Mock()
    mock_result.prompt = "test"
    mock_result.total_tokens = 100
    mock_result.files_included = 1
    mock_result.files_sliced = 0
    mock_result.files_smart_only = 0
    mock_result.scope_summary = "1 primary"
    mock_result.coverage_summary = "50%"
    mock_result.untested_symbols = 5
    mock_result.suggested_test_files = ["test_main.py"]
    mock_result.optimizations = []

    with patch(
        "domain.workflow.test_builder.run_test_builder", return_value=mock_result
    ):
        tool = get_tool(mcp_instance, "rp_test")
        result = await tool(test_framework="pytest", workspace_path=str(mock_workspace))

        assert "Test Builder" in result or "Coverage" in result
