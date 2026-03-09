"""Tests for new agent-native MCP tools: simulate_patch, execution_contract, etc."""

import json
import pytest
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from infrastructure.mcp.handlers.workflow_handler import register_tools


@pytest.fixture
def mcp_instance():
    mcp = FastMCP("test_new_tools")
    register_tools(mcp)
    return mcp


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    """Create a mock workspace with sample files."""
    (tmp_path / "main.py").write_text("from utils import helper\ndef main(): helper()")
    (tmp_path / "utils.py").write_text("def helper(): pass\ndef unused(): pass")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text(
        "from main import main\ndef test_main(): main()"
    )
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
    return tmp_path


def get_tool(mcp, name):
    return mcp._tool_manager._tools[name].fn


# ================================================================
# simulate_patch tests
# ================================================================


class TestSimulatePatch:
    """Test simulate_patch tool."""

    @pytest.mark.asyncio
    async def test_no_actions(self, mcp_instance, mock_workspace):
        """Empty OPX content returns no actions message."""
        tool = get_tool(mcp_instance, "simulate_patch")
        result = await tool(
            opx_content="no valid opx", workspace_path=str(mock_workspace)
        )
        assert "No file actions" in result

    @pytest.mark.asyncio
    async def test_invalid_workspace(self, mcp_instance):
        """Invalid workspace returns error."""
        tool = get_tool(mcp_instance, "simulate_patch")
        result = await tool(opx_content="test", workspace_path="/nonexistent")
        assert "Error" in result


# ================================================================
# manage_execution_contract tests
# ================================================================


class TestExecutionContract:
    """Test manage_execution_contract tool."""

    @pytest.mark.asyncio
    async def test_create_contract(self, mcp_instance, mock_workspace):
        """Creating a contract returns valid JSON."""
        tool = get_tool(mcp_instance, "manage_execution_contract")
        result = await tool(
            action="create",
            task="Add auth service",
            scope_files=["auth/service.py"],
            assumptions=["No existing auth module"],
            workspace_path=str(mock_workspace),
        )
        data = json.loads(result)
        assert data["task"] == "Add auth service"
        assert data["status"] == "draft"
        assert "auth/service.py" in data["scope_files"]

    @pytest.mark.asyncio
    async def test_get_contract(self, mcp_instance, mock_workspace):
        """Get contract after create."""
        tool = get_tool(mcp_instance, "manage_execution_contract")
        await tool(
            action="create",
            task="test task",
            workspace_path=str(mock_workspace),
        )
        result = await tool(action="get", workspace_path=str(mock_workspace))
        data = json.loads(result)
        assert data["task"] == "test task"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, mcp_instance, mock_workspace):
        """Get without create returns not found."""
        tool = get_tool(mcp_instance, "manage_execution_contract")
        result = await tool(action="get", workspace_path=str(mock_workspace))
        assert "No execution contract" in result

    @pytest.mark.asyncio
    async def test_activate_contract(self, mcp_instance, mock_workspace):
        """Activate sets status."""
        tool = get_tool(mcp_instance, "manage_execution_contract")
        await tool(action="create", task="test", workspace_path=str(mock_workspace))
        result = await tool(action="activate", workspace_path=str(mock_workspace))
        assert "active" in result

    @pytest.mark.asyncio
    async def test_format_for_prompt(self, mcp_instance, mock_workspace):
        """Format returns XML-like structure."""
        tool = get_tool(mcp_instance, "manage_execution_contract")
        await tool(
            action="create",
            task="test task",
            risks=["breaking change"],
            workspace_path=str(mock_workspace),
        )
        result = await tool(
            action="format_for_prompt", workspace_path=str(mock_workspace)
        )
        assert "<execution_contract>" in result
        assert "test task" in result

    @pytest.mark.asyncio
    async def test_invalid_action(self, mcp_instance, mock_workspace):
        """Invalid action returns error."""
        tool = get_tool(mcp_instance, "manage_execution_contract")
        result = await tool(action="invalid", workspace_path=str(mock_workspace))
        assert "Error" in result


# ================================================================
# verify_assumptions tests
# ================================================================


class TestVerifyAssumptions:
    """Test verify_assumptions tool."""

    @pytest.mark.asyncio
    async def test_verify_usage(self, mcp_instance, mock_workspace):
        """Verify a usage assumption."""
        tool = get_tool(mcp_instance, "verify_assumptions")
        result = await tool(
            assumptions=["'helper' has test coverage"],
            workspace_path=str(mock_workspace),
        )
        assert "Assumption Verification Report" in result
        assert "PASS" in result or "FAIL" in result or "UNCERTAIN" in result

    @pytest.mark.asyncio
    async def test_invalid_workspace(self, mcp_instance):
        """Invalid workspace returns error."""
        tool = get_tool(mcp_instance, "verify_assumptions")
        result = await tool(assumptions=["test"], workspace_path="/nonexistent")
        assert "Error" in result


# ================================================================
# manage_watchpoints tests
# ================================================================


class TestManageWatchpoints:
    """Test manage_watchpoints tool."""

    @pytest.mark.asyncio
    async def test_list_empty(self, mcp_instance, mock_workspace):
        """List when empty returns no watchpoints."""
        tool = get_tool(mcp_instance, "manage_watchpoints")
        result = await tool(action="list", workspace_path=str(mock_workspace))
        assert "No watchpoints" in result

    @pytest.mark.asyncio
    async def test_add_and_list(self, mcp_instance, mock_workspace):
        """Add watchpoints then list them."""
        tool = get_tool(mcp_instance, "manage_watchpoints")
        await tool(
            action="add",
            paths=["api/", "config/"],
            reason="Critical paths",
            workspace_path=str(mock_workspace),
        )
        result = await tool(action="list", workspace_path=str(mock_workspace))
        assert "api/" in result
        assert "config/" in result

    @pytest.mark.asyncio
    async def test_check_violations(self, mcp_instance, mock_workspace):
        """Check files against watchpoints."""
        tool = get_tool(mcp_instance, "manage_watchpoints")
        await tool(
            action="add",
            paths=["api/"],
            workspace_path=str(mock_workspace),
        )
        result = await tool(
            action="check",
            paths=["api/routes.py"],
            workspace_path=str(mock_workspace),
        )
        assert "Watchpoint Violations" in result or "⚠" in result

    @pytest.mark.asyncio
    async def test_check_no_violations(self, mcp_instance, mock_workspace):
        """Check files that don't match watchpoints."""
        tool = get_tool(mcp_instance, "manage_watchpoints")
        await tool(
            action="add",
            paths=["api/"],
            workspace_path=str(mock_workspace),
        )
        result = await tool(
            action="check",
            paths=["utils.py"],
            workspace_path=str(mock_workspace),
        )
        assert "clear" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_action(self, mcp_instance, mock_workspace):
        """Invalid action returns error."""
        tool = get_tool(mcp_instance, "manage_watchpoints")
        result = await tool(action="invalid", workspace_path=str(mock_workspace))
        assert "Error" in result


# ================================================================
# manage_plan_dag tests
# ================================================================


class TestManagePlanDAG:
    """Test manage_plan_dag tool."""

    @pytest.mark.asyncio
    async def test_create_dag(self, mcp_instance, mock_workspace):
        """Create a new plan DAG."""
        tool = get_tool(mcp_instance, "manage_plan_dag")
        result = await tool(
            action="create",
            task="Implement auth",
            workspace_path=str(mock_workspace),
        )
        data = json.loads(result)
        assert data["task"] == "Implement auth"
        assert data["nodes"] == []

    @pytest.mark.asyncio
    async def test_add_node(self, mcp_instance, mock_workspace):
        """Add a node to the DAG."""
        tool = get_tool(mcp_instance, "manage_plan_dag")
        await tool(action="create", task="test", workspace_path=str(mock_workspace))
        result = await tool(
            action="add_node",
            node_id="N1",
            node_type="change",
            node_title="Add AuthService",
            node_file="auth/service.py",
            workspace_path=str(mock_workspace),
        )
        data = json.loads(result)
        assert data["id"] == "N1"
        assert data["type"] == "change"

    @pytest.mark.asyncio
    async def test_add_edge(self, mcp_instance, mock_workspace):
        """Add an edge between nodes."""
        tool = get_tool(mcp_instance, "manage_plan_dag")
        await tool(action="create", task="test", workspace_path=str(mock_workspace))
        await tool(
            action="add_node",
            node_id="N1",
            node_title="Decision",
            node_type="decision",
            workspace_path=str(mock_workspace),
        )
        await tool(
            action="add_node",
            node_id="N2",
            node_title="Change",
            node_type="change",
            workspace_path=str(mock_workspace),
        )
        result = await tool(
            action="add_edge",
            edge_from="N1",
            edge_to="N2",
            edge_kind="implements",
            workspace_path=str(mock_workspace),
        )
        data = json.loads(result)
        assert data["from"] == "N1"
        assert data["to"] == "N2"
        assert data["kind"] == "implements"

    @pytest.mark.asyncio
    async def test_get_ready_nodes(self, mcp_instance, mock_workspace):
        """Get nodes ready to execute."""
        tool = get_tool(mcp_instance, "manage_plan_dag")
        await tool(action="create", task="test", workspace_path=str(mock_workspace))
        await tool(
            action="add_node",
            node_id="N1",
            node_title="Step 1",
            node_type="change",
            workspace_path=str(mock_workspace),
        )
        result = await tool(action="get_ready", workspace_path=str(mock_workspace))
        assert "N1" in result

    @pytest.mark.asyncio
    async def test_format_summary(self, mcp_instance, mock_workspace):
        """Format DAG as summary."""
        tool = get_tool(mcp_instance, "manage_plan_dag")
        await tool(
            action="create", task="Test task", workspace_path=str(mock_workspace)
        )
        await tool(
            action="add_node",
            node_id="N1",
            node_title="First step",
            node_type="change",
            workspace_path=str(mock_workspace),
        )
        result = await tool(action="format_summary", workspace_path=str(mock_workspace))
        assert "Plan DAG Summary" in result
        assert "N1" in result

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, mcp_instance, mock_workspace):
        """Get when no DAG exists."""
        tool = get_tool(mcp_instance, "manage_plan_dag")
        result = await tool(action="get", workspace_path=str(mock_workspace))
        assert "No plan DAG" in result

    @pytest.mark.asyncio
    async def test_invalid_action(self, mcp_instance, mock_workspace):
        """Invalid action returns error."""
        tool = get_tool(mcp_instance, "manage_plan_dag")
        result = await tool(action="invalid", workspace_path=str(mock_workspace))
        assert "Error" in result


# ================================================================
# build_handoff_bundle tests
# ================================================================


class TestBuildHandoffBundle:
    """Test build_handoff_bundle tool."""

    @pytest.mark.asyncio
    async def test_invalid_role(self, mcp_instance, mock_workspace):
        """Invalid role returns error."""
        tool = get_tool(mcp_instance, "build_handoff_bundle")
        result = await tool(
            task_description="test",
            target_role="invalid",
            workspace_path=str(mock_workspace),
        )
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_invalid_workspace(self, mcp_instance):
        """Invalid workspace returns error."""
        tool = get_tool(mcp_instance, "build_handoff_bundle")
        result = await tool(
            task_description="test",
            target_role="implementer",
            workspace_path="/nonexistent",
        )
        assert "Error" in result
