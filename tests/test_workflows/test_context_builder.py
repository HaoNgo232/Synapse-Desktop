"""Tests for context_builder workflow."""

import pytest
from pathlib import Path
from application.workflows.context_builder import run_context_builder


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    """Create a sample workspace."""
    ws = tmp_path / "project"
    ws.mkdir()

    (ws / "main.py").write_text("from auth import login\ndef main(): login()")
    (ws / "auth.py").write_text("def login(): pass")

    return ws


def test_context_builder_basic(sample_workspace: Path):
    """Test basic context builder workflow."""
    result = run_context_builder(
        workspace_path=str(sample_workspace),
        task_description="Add rate limiting to login",
        file_paths=["main.py", "auth.py"],
        max_tokens=50_000,
    )

    assert result.files_included >= 2
    assert result.total_tokens > 0
    assert "auth" in result.prompt.lower() or "login" in result.prompt.lower()
    assert result.scope_summary


def test_context_builder_with_output_file(sample_workspace: Path):
    """Test writing output to file."""
    output_file = "context_output.xml"

    run_context_builder(
        workspace_path=str(sample_workspace),
        task_description="Test task",
        file_paths=["main.py"],
        max_tokens=50_000,
        output_file=output_file,
    )

    output_path = sample_workspace / output_file
    assert output_path.exists()
    assert output_path.read_text()


def test_context_builder_invalid_workspace():
    """Test error handling for invalid workspace."""
    with pytest.raises(ValueError, match="not a valid directory"):
        run_context_builder(
            workspace_path="/nonexistent/path",
            task_description="Test",
            max_tokens=50_000,
        )


def test_context_builder_path_traversal(sample_workspace: Path):
    """Test path traversal protection."""
    with pytest.raises(ValueError, match="path traversal"):
        run_context_builder(
            workspace_path=str(sample_workspace),
            task_description="Test",
            output_file="../../../etc/passwd",
            max_tokens=50_000,
        )
