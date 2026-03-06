"""Tests for bug_investigator workflow."""

import pytest
from pathlib import Path
from domain.workflow.bug_investigator import (
    run_bug_investigation,
    _parse_error_trace,
)


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    """Create a sample workspace."""
    ws = tmp_path / "project"
    ws.mkdir()

    (ws / "main.py").write_text("""
def main():
    result = calculate(10, 0)
    print(result)

def calculate(a, b):
    return a / b
""")

    return ws


def test_parse_python_traceback(sample_workspace: Path):
    """Test parsing Python traceback."""
    trace = """
Traceback (most recent call last):
  File "main.py", line 3, in main
    result = calculate(10, 0)
  File "main.py", line 7, in calculate
    return a / b
ZeroDivisionError: division by zero
"""

    entry_points = _parse_error_trace(trace, sample_workspace)

    assert len(entry_points) > 0
    assert any(ep["file"] == "main.py" for ep in entry_points)
    assert any(ep["function"] == "calculate" for ep in entry_points)


def test_parse_js_stack_trace(sample_workspace: Path):
    """Test parsing JavaScript stack trace."""
    (sample_workspace / "app.js").write_text("function test() {}")

    trace = """
Error: Something went wrong
    at test (app.js:10:5)
    at main (app.js:20:3)
"""

    entry_points = _parse_error_trace(trace, sample_workspace)

    assert len(entry_points) > 0
    assert any(ep["file"] == "app.js" for ep in entry_points)


def test_bug_investigation_basic(sample_workspace: Path):
    """Test basic bug investigation."""
    result = run_bug_investigation(
        workspace_path=str(sample_workspace),
        bug_description="Division by zero error",
        entry_files=["main.py"],
        max_depth=2,
        max_tokens=50_000,
    )

    assert result.files_investigated > 0
    assert result.total_tokens > 0
    assert len(result.entry_points) > 0


def test_bug_investigation_with_trace(sample_workspace: Path):
    """Test investigation with error trace."""
    trace = 'File "main.py", line 7, in calculate'

    result = run_bug_investigation(
        workspace_path=str(sample_workspace),
        bug_description="Error in calculate",
        error_trace=trace,
        max_depth=2,
        max_tokens=50_000,
    )

    assert result.files_investigated > 0
    assert "main.py" in result.entry_points


def test_bug_investigation_no_entry_points(sample_workspace: Path):
    """Test error when no entry points found."""
    result = run_bug_investigation(
        workspace_path=str(sample_workspace),
        bug_description="Test bug",
        max_tokens=50_000,
    )

    assert "Error" in result.prompt or "No entry points" in result.prompt
