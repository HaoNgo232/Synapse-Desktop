"""Tests for file_slicer module."""

import pytest
from pathlib import Path
from unittest.mock import patch
from domain.workflow.shared.file_slicer import (
    auto_slice_file,
    slice_file_by_symbols,
    slice_file_by_line_range,
    smart_truncate,
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


def test_smart_truncate_small_file(sample_python_file: Path, tmp_path: Path):
    """Test smart_truncate on a file smaller than the token budget."""
    result = smart_truncate(
        file_path=sample_python_file,
        target_tokens=1000,
        workspace_root=tmp_path,
    )
    assert result.is_full_file
    assert result.total_lines == 21
    assert "function_one" in result.content


def test_smart_truncate_hard_fallback_no_symbols(tmp_path: Path):
    """Test smart_truncate fallback to hard truncate when no symbols are extracted."""
    file_path = tmp_path / "simple.txt"
    content = "This is a plain text file without any functions or classes.\n" * 10
    file_path.write_text(content)

    # target_tokens nhỏ hơn kích thước file để trigger truncate
    result = smart_truncate(
        file_path=file_path,
        target_tokens=5,  # Xấp xỉ 20 ký tự
        workspace_root=tmp_path,
    )
    assert not result.is_full_file
    assert "[TRUNCATED - file too large to parse" in result.content
    assert len(result.content) > 0


def test_smart_truncate_greedy_knapsack(sample_python_file: Path, tmp_path: Path):
    """Test smart_truncate select units using greedy knapsack based on score."""
    # target_tokens chỉ đủ cho 1 hoặc 2 unit nhỏ
    result = smart_truncate(
        file_path=sample_python_file,
        target_tokens=20,
        workspace_root=tmp_path,
        relevance_hints={
            "function_three"
        },  # hints giúp function_three có score cực cao
    )
    assert not result.is_full_file
    assert "function_three" in result.symbols_included
    assert "function_three" in result.content
    assert "MyClass" not in result.symbols_included


def test_smart_truncate_greedy_no_units_selected(
    sample_python_file: Path, tmp_path: Path
):
    """Test smart_truncate fallback to hard truncate when budget is too small for any unit."""
    # target_tokens = 1 (cực nhỏ, không chứa nổi unit nào)
    result = smart_truncate(
        file_path=sample_python_file,
        target_tokens=1,
        workspace_root=tmp_path,
    )
    assert not result.is_full_file
    assert "[TRUNCATED - file too large to parse" in result.content


def test_smart_truncate_skipped_lines_formatting(
    sample_python_file: Path, tmp_path: Path
):
    """Test smart_truncate inserts skipped lines comment when there is a gap between selected units."""
    # Chọn target_tokens đủ để chứa function_one và function_three, nhưng bỏ qua MyClass
    result = smart_truncate(
        file_path=sample_python_file,
        target_tokens=40,
        relevance_hints={"function_one", "function_three"},
        workspace_root=tmp_path,
    )
    assert not result.is_full_file
    assert "function_one" in result.symbols_included
    assert "function_three" in result.symbols_included
    assert "skipped] ..." in result.content


def test_smart_truncate_exception(tmp_path: Path):
    """Test smart_truncate handles exception gracefully."""
    result = smart_truncate(
        file_path=tmp_path / "nonexistent.py",
        target_tokens=100,
        workspace_root=tmp_path,
    )
    assert not result.is_full_file
    assert "[Error reading file]" in result.content


def test_slice_by_symbols_fallback_no_match(sample_python_file: Path, tmp_path: Path):
    """Test slice_file_by_symbols falls back to first SMALL_FILE_THRESHOLD lines when no symbol matches."""
    result = slice_file_by_symbols(
        sample_python_file,
        target_symbols={"nonexistent_symbol"},
        workspace_root=tmp_path,
    )
    assert not result.is_full_file
    assert "Sample Python file" in result.content


def test_slice_by_symbols_overlapping_ranges(sample_python_file: Path, tmp_path: Path):
    """Test slice_file_by_symbols merges overlapping ranges correctly."""
    result = slice_file_by_symbols(
        sample_python_file,
        target_symbols={"function_one", "function_two"},
        context_padding=5,
        workspace_root=tmp_path,
    )
    assert not result.is_full_file
    assert "function_one" in result.content
    assert "function_two" in result.content
    assert "skipped" not in result.content  # Vì được merge làm một range liên tục


def test_file_slicer_exceptions(sample_python_file: Path, tmp_path: Path):
    # slice_file_by_symbols exception
    res_sym = slice_file_by_symbols(
        tmp_path / "nonexistent.py",
        target_symbols={"func"},
        workspace_root=tmp_path,
    )
    assert "[Error reading file]" in res_sym.content

    # slice_file_by_line_range exception
    res_range = slice_file_by_line_range(
        tmp_path / "nonexistent.py", 1, 10, workspace_root=tmp_path
    )
    assert "[Error reading file]" in res_range.content

    # auto_slice_file exception
    res_auto = auto_slice_file(tmp_path / "nonexistent.py", workspace_root=tmp_path)
    assert "[Error reading file]" in res_auto.content


@patch("domain.workflow.shared.file_slicer.extract_symbols")
def test_get_file_symbols_cached_exception(mock_extract, sample_python_file: Path):
    """Test that _get_file_symbols_cached returns empty list on exception."""
    mock_extract.side_effect = Exception("Parsing error")
    # Gọi gián tiếp qua smart_truncate
    result = smart_truncate(
        file_path=sample_python_file,
        target_tokens=10,
        workspace_root=sample_python_file.parent,
    )
    assert not result.is_full_file
    assert "[TRUNCATED" in result.content


def test_slice_by_symbols_large_file_no_match(large_python_file: Path, tmp_path: Path):
    """Test slice_file_by_symbols on a large file with no matching symbols to trigger line 289."""
    result = slice_file_by_symbols(
        large_python_file,
        target_symbols={"nonexistent_symbol"},
        workspace_root=tmp_path,
    )
    assert not result.is_full_file
    assert "truncated" in result.content.lower()


def test_auto_slice_large_file_with_relevance_hints(
    large_python_file: Path, tmp_path: Path
):
    """Test auto_slice_file on a large file with relevance hints to trigger line 489."""
    from domain.codemap.types import Symbol, SymbolKind

    with patch(
        "domain.workflow.shared.file_slicer._get_file_symbols_cached"
    ) as mock_get_symbols:
        mock_get_symbols.return_value = [
            Symbol(
                name="my_target_symbol",
                kind=SymbolKind.FUNCTION,
                file_path=str(large_python_file),
                line_start=10,
                line_end=20,
            )
        ]
        result = auto_slice_file(
            large_python_file,
            relevance_hints={"my_target_symbol"},
            workspace_root=tmp_path,
        )
        assert not result.is_full_file
        assert "my_target_symbol" in result.symbols_included
