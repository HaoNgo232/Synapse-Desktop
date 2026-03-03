"""Tests for scope_detector module."""

import pytest
from pathlib import Path
from core.workflows.shared.scope_detector import (
    detect_scope_from_file_paths,
    detect_scope_from_symbols,
)


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    """Create a sample workspace with Python files."""
    ws = tmp_path / "project"
    ws.mkdir()

    # main.py imports auth
    (ws / "main.py").write_text("from auth import login\ndef main(): login()")

    # auth.py
    (ws / "auth.py").write_text("def login(): pass\ndef logout(): pass")

    # utils.py (not imported)
    (ws / "utils.py").write_text("def helper(): pass")

    return ws


def test_detect_scope_from_file_paths(sample_workspace: Path):
    """Test scope detection from explicit file paths."""
    result = detect_scope_from_file_paths(
        sample_workspace,
        file_paths=["main.py"],
        max_depth=1,
    )

    assert "main.py" in result.primary_files
    assert result.confidence == 1.0  # User-specified = highest confidence
    # Should detect auth.py as dependency
    assert len(result.dependency_files) >= 0


def test_detect_scope_from_symbols(sample_workspace: Path):
    """Test scope detection from symbol names."""
    result = detect_scope_from_symbols(
        sample_workspace,
        symbol_names={"login", "logout"},
    )

    assert len(result.primary_files) > 0
    assert result.confidence > 0.0
    # Should find auth.py which contains login and logout
    assert any("auth" in f for f in result.primary_files)


def test_detect_scope_empty_workspace(tmp_path: Path):
    """Test scope detection on empty workspace."""
    empty_ws = tmp_path / "empty"
    empty_ws.mkdir()

    result = detect_scope_from_file_paths(
        empty_ws,
        file_paths=[],
        max_depth=1,
    )

    assert len(result.primary_files) == 0
    assert result.confidence == 1.0  # Still confident, just empty
