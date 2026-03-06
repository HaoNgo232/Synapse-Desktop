"""Tests for file_slicer module."""

import pytest
from pathlib import Path
from domain.workflow.shared.file_slicer import (
    auto_slice_file,
    slice_file_by_symbols,
    slice_file_by_line_range,
    SMALL_FILE_THRESHOLD,
)


@pytest.fixture
def sample_python_file(tmp_path: Path) -> Path:
    """Create a sample Python file for testing."""
    file_path = tmp_path / "sample.py"
    content = """# Sample Python file
import os

def function_one():
    '''First function'''
    return 1

def function_two():
    '''Second function'''
    return 2

class MyClass:
    def method_one(self):
        return "method1"
    
    def method_two(self):
        return "method2"

def function_three():
    '''Third function'''
    return 3
"""
    file_path.write_text(content)
    return file_path


@pytest.fixture
def large_python_file(tmp_path: Path) -> Path:
    """Create a large Python file (> SMALL_FILE_THRESHOLD lines)."""
    file_path = tmp_path / "large.py"
    lines = ["# Large file\n"]
    for i in range(SMALL_FILE_THRESHOLD + 50):
        lines.append(f"# Line {i}\n")
    file_path.write_text("".join(lines))
    return file_path


def test_auto_slice_small_file(sample_python_file: Path, tmp_path: Path):
    """Test that small files are returned in full."""
    result = auto_slice_file(sample_python_file, workspace_root=tmp_path)

    assert result.is_full_file
    assert result.total_lines < SMALL_FILE_THRESHOLD
    assert "function_one" in result.content
    assert "function_two" in result.content


def test_auto_slice_large_file_no_hints(large_python_file: Path, tmp_path: Path):
    """Test that large files without hints are truncated."""
    result = auto_slice_file(large_python_file, workspace_root=tmp_path, max_lines=100)

    assert not result.is_full_file
    assert result.end_line <= 100
    assert "truncated" in result.content.lower()


def test_slice_by_symbols(sample_python_file: Path, tmp_path: Path):
    """Test slicing by symbol names."""
    result = slice_file_by_symbols(
        sample_python_file,
        target_symbols={"function_one", "MyClass"},
        context_padding=2,
        workspace_root=tmp_path,
    )

    assert not result.is_full_file
    assert (
        "function_one" in result.symbols_included
        or "MyClass" in result.symbols_included
    )
    assert "function_one" in result.content


def test_slice_by_line_range(sample_python_file: Path, tmp_path: Path):
    """Test slicing by line range."""
    result = slice_file_by_line_range(
        sample_python_file,
        start_line=5,
        end_line=10,
        context_padding=2,
        workspace_root=tmp_path,
    )

    assert not result.is_full_file
    assert result.start_line >= 3  # 5 - 2 padding
    assert result.end_line <= 12  # 10 + 2 padding


def test_auto_slice_with_relevance_hints(sample_python_file: Path, tmp_path: Path):
    """Test auto slice with relevance hints uses symbol slicing."""
    result = auto_slice_file(
        sample_python_file,
        relevance_hints={"function_two"},
        workspace_root=tmp_path,
    )

    assert "function_two" in result.content
