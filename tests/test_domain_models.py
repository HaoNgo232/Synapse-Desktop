"""Tests for domain models: execution_contract, assumption_verifier, plan_dag."""

from domain.contracts.execution_contract import (
    ExecutionContract,
    load_execution_contract,
    save_execution_contract,
)
from domain.workflow.assumption_verifier import (
    verify_assumptions,
    VerificationReport,
    AssumptionResult,
)
from domain.workflow.plan_dag import (
    PlanDAG,
    PlanNode,
    PlanEdge,
    load_plan_dag,
    save_plan_dag,
)


# ================================================================
# Execution Contract tests
# ================================================================


class TestExecutionContract:
    """Test ExecutionContract domain model."""

    def test_to_dict(self):
        """Contract serializes to dict."""
        c = ExecutionContract(
            task="Add auth",
            scope_files=["auth.py"],
            assumptions=["No existing auth"],
        )
        d = c.to_dict()
        assert d["task"] == "Add auth"
        assert d["scope_files"] == ["auth.py"]

    def test_from_dict(self):
        """Contract deserializes from dict."""
        d = {
            "task": "Test task",
            "scope_files": ["a.py", "b.py"],
            "status": "active",
        }
        c = ExecutionContract.from_dict(d)
        assert c.task == "Test task"
        assert c.status == "active"
        assert len(c.scope_files) == 2

    def test_format_for_prompt(self):
        """Format produces XML structure."""
        c = ExecutionContract(
            task="Test",
            scope_files=["a.py"],
            risks=["breaking change"],
        )
        prompt = c.format_for_prompt()
        assert "<execution_contract>" in prompt
        assert "Test" in prompt
        assert "breaking change" in prompt

    def test_format_empty_contract(self):
        """Empty contract returns empty string."""
        c = ExecutionContract()
        assert c.format_for_prompt() == ""

    def test_save_and_load(self, tmp_path):
        """Save and load roundtrip."""
        c = ExecutionContract(
            task="Test save",
            scope_files=["x.py"],
            guarded_paths=["api/"],
        )
        save_execution_contract(tmp_path, c)
        loaded = load_execution_contract(tmp_path)
        assert loaded is not None
        assert loaded.task == "Test save"
        assert loaded.scope_files == ["x.py"]

    def test_load_nonexistent(self, tmp_path):
        """Load from nonexistent file returns None."""
        result = load_execution_contract(tmp_path)
        assert result is None


# ================================================================
# Assumption Verifier tests
# ================================================================


class TestAssumptionVerifier:
    """Test assumption verifier."""

    def test_verify_test_coverage_pass(self, tmp_path):
        """Verify test coverage when tests exist."""
        (tmp_path / "auth.py").write_text("def login(): pass")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_auth.py").write_text(
            "from auth import login\ndef test_login(): login()"
        )
        report = verify_assumptions(
            tmp_path,
            ["'login' has test coverage"],
            all_files=[
                str(tmp_path / "auth.py"),
                str(tmp_path / "tests" / "test_auth.py"),
            ],
        )
        assert report.total == 1
        assert report.results[0].verdict == "pass"

    def test_verify_test_coverage_fail(self, tmp_path):
        """Verify test coverage when no tests."""
        (tmp_path / "auth.py").write_text("def secret_func(): pass")
        report = verify_assumptions(
            tmp_path,
            ["'secret_func' has test coverage"],
            all_files=[str(tmp_path / "auth.py")],
        )
        assert report.total == 1
        assert report.results[0].verdict == "fail"

    def test_verify_impact_count(self, tmp_path):
        """Verify impact count assumption."""
        (tmp_path / "a.py").write_text("import helper")
        (tmp_path / "b.py").write_text("import helper")
        (tmp_path / "c.py").write_text("x = 1")
        report = verify_assumptions(
            tmp_path,
            ["'helper' impacts 3 files"],
            all_files=[
                str(tmp_path / "a.py"),
                str(tmp_path / "b.py"),
                str(tmp_path / "c.py"),
            ],
        )
        assert report.total == 1
        # helper found in 2 files, expected <= 3, so pass
        assert report.results[0].verdict == "pass"

    def test_verify_unknown_pattern(self, tmp_path):
        """Unknown pattern returns uncertain."""
        report = verify_assumptions(
            tmp_path,
            ["something completely different"],
            all_files=[],
        )
        assert report.total == 1
        assert report.results[0].verdict == "uncertain"

    def test_report_format(self, tmp_path):
        """Report formats correctly."""
        report = VerificationReport(
            results=[
                AssumptionResult(
                    assumption="test",
                    verdict="pass",
                    confidence=0.8,
                )
            ],
            total=1,
            passed=1,
        )
        summary = report.format_summary()
        assert "Assumption Verification Report" in summary
        assert "Pass: 1" in summary


# ================================================================
# Plan DAG tests
# ================================================================


class TestPlanDAG:
    """Test Plan DAG domain model."""

    def test_create_empty(self):
        """Create empty DAG."""
        dag = PlanDAG(task="Test")
        assert dag.task == "Test"
        assert len(dag.nodes) == 0

    def test_add_node(self):
        """Add node to DAG."""
        dag = PlanDAG(task="Test")
        dag.add_node(PlanNode(id="N1", type="change", title="Step 1"))
        assert len(dag.nodes) == 1

    def test_add_edge(self):
        """Add edge to DAG."""
        dag = PlanDAG(task="Test")
        dag.add_edge(PlanEdge(source="N1", target="N2", kind="implements"))
        assert len(dag.edges) == 1

    def test_to_dict_roundtrip(self):
        """Serialize and deserialize."""
        dag = PlanDAG(task="Test")
        dag.add_node(PlanNode(id="N1", type="decision", title="Choose approach"))
        dag.add_node(PlanNode(id="N2", type="change", title="Implement", file="x.py"))
        dag.add_edge(PlanEdge(source="N1", target="N2", kind="implements"))

        d = dag.to_dict()
        loaded = PlanDAG.from_dict(d)
        assert loaded.task == "Test"
        assert len(loaded.nodes) == 2
        assert len(loaded.edges) == 1
        assert loaded.edges[0].kind == "implements"

    def test_get_ready_nodes(self):
        """Get nodes with all dependencies completed."""
        dag = PlanDAG(task="Test")
        dag.add_node(PlanNode(id="N1", type="decision", title="A", status="completed"))
        dag.add_node(PlanNode(id="N2", type="change", title="B"))
        dag.add_node(PlanNode(id="N3", type="test", title="C"))
        dag.add_edge(PlanEdge(source="N1", target="N2", kind="implements"))
        dag.add_edge(PlanEdge(source="N2", target="N3", kind="must_verify"))

        ready = dag.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == "N2"

    def test_update_status(self):
        """Update node status."""
        dag = PlanDAG(task="Test")
        dag.add_node(PlanNode(id="N1", type="change", title="A"))
        assert dag.update_node_status("N1", "completed")
        assert dag.nodes[0].status == "completed"
        assert not dag.update_node_status("nonexistent", "completed")

    def test_save_and_load(self, tmp_path):
        """Save and load roundtrip."""
        dag = PlanDAG(task="Test save")
        dag.add_node(PlanNode(id="N1", type="change", title="Step 1"))
        save_plan_dag(tmp_path, dag)

        loaded = load_plan_dag(tmp_path)
        assert loaded is not None
        assert loaded.task == "Test save"
        assert len(loaded.nodes) == 1

    def test_load_nonexistent(self, tmp_path):
        """Load from nonexistent returns None."""
        assert load_plan_dag(tmp_path) is None

    def test_format_summary(self):
        """Format as human-readable summary."""
        dag = PlanDAG(task="Build auth")
        dag.add_node(PlanNode(id="N1", type="decision", title="Design auth"))
        dag.add_node(PlanNode(id="N2", type="change", title="Impl", file="auth.py"))
        dag.add_edge(PlanEdge(source="N1", target="N2", kind="implements"))

        summary = dag.format_summary()
        assert "Plan DAG Summary" in summary
        assert "Build auth" in summary
        assert "N1" in summary
        assert "auth.py" in summary
