"""
Unit tests cho formatters và prompt_assembler.

Kiểm tra các module:
- formatters/xml.py: format_files_xml(), generate_file_summary_xml(), generate_smart_summary_xml()
- formatters/plain.py: format_files_plain()
- prompt_assembler.py: assemble_prompt(), assemble_smart_prompt()
"""

import pytest
from pathlib import Path
from typing import Optional

from shared.types.prompt_types import FileEntry
from domain.prompt.formatters.xml import (
    format_files_xml,
    generate_file_summary_xml,
    generate_smart_summary_xml,
)
from domain.prompt.formatters.plain import format_files_plain
from domain.prompt.assembler import assemble_prompt, assemble_smart_prompt
from infrastructure.git.git_utils import GitDiffResult
from presentation.config.output_format import OutputStyle


# === Helpers ===

def _make_entry(
    path: str = "test.py",
    content: Optional[str] = "print('hello')",
    error: Optional[str] = None,
    language: str = "python",
    display_path: Optional[str] = None,
    dependencies: Optional[list[str]] = None,
) -> FileEntry:
    """Tạo FileEntry nhanh để phục vụ unit test."""
    return FileEntry(
        path=Path(path),
        display_path=display_path or path,
        content=content,
        error=error,
        language=language,
        dependencies=dependencies or [],
    )


# ===========================================================================
# XML Formatter Tests
# ===========================================================================

class TestFormatFilesXml:
    """Kiểm tra format_files_xml()."""

    def test_empty_entries(self) -> None:
        """Danh sách rỗng trả về tag files rỗng."""
        assert format_files_xml([]) == "<files></files>"

    def test_single_file(self) -> None:
        """Kiểm tra một file đơn lẻ có cấu trúc XML chính xác."""
        entries = [_make_entry()]
        result = format_files_xml(entries)
        assert "<files>" in result
        assert "</files>" in result
        assert '<file path="test.py">' in result
        assert "print('hello')" in result

    def test_skipped_file(self) -> None:
        """Kiểm tra file bị bỏ qua có attribute skipped='true'."""
        entries = [_make_entry(content=None, error="Binary file")]
        result = format_files_xml(entries)
        assert 'skipped="true"' in result
        assert "Binary file" in result


class TestGenerateFileSummaryXml:
    """Kiểm tra generate_file_summary_xml()."""

    def test_contains_required_sections(self) -> None:
        """Summary XML chứa các sections cần thiết."""
        result = generate_file_summary_xml()
        assert "<file_summary>" in result
        assert "</file_summary>" in result
        assert "<purpose>" in result
        assert "<file_format>" in result
        assert "<usage_guidelines>" in result
        assert "<notes>" in result


class TestGenerateSmartSummaryXml:
    """Kiểm tra generate_smart_summary_xml()."""

    def test_contains_required_sections(self) -> None:
        """Smart summary chứa tất cả các sections."""
        result = generate_smart_summary_xml()
        assert "<file_summary>" in result
        assert "<purpose>" in result
        assert "<file_format>" in result
        assert "<usage_guidelines>" in result
        assert "<notes>" in result


# ===========================================================================
# Plain Formatter Tests
# ===========================================================================

class TestFormatFilesPlain:
    """Kiểm tra format_files_plain()."""

    def test_empty_entries(self) -> None:
        """Danh sách rỗng trả về thông báo No files selected."""
        assert format_files_plain([]) == "No files selected."

    def test_single_file(self) -> None:
        """Kiểm tra cấu trúc plain text của một file đơn lẻ."""
        entries = [_make_entry()]
        result = format_files_plain(entries)
        assert "FILE: test.py" in result
        assert "print('hello')" in result

    def test_binary_skip_message(self) -> None:
        """Kiểm tra hiển thị bỏ qua file nhị phân."""
        entries = [_make_entry(content=None, error="Binary file")]
        result = format_files_plain(entries)
        assert "Binary file (skipped)" in result

    def test_multiple_files_separated(self) -> None:
        """Kiểm tra nhiều file được phân tách bằng double newlines."""
        entries = [
            _make_entry(path="a.py", display_path="a.py", content="a_code"),
            _make_entry(path="b.py", display_path="b.py", content="b_code"),
        ]
        result = format_files_plain(entries)
        assert "FILE: a.py" in result
        assert "FILE: b.py" in result
        assert "\n\n" in result


# ===========================================================================
# Prompt Assembler Tests
# ===========================================================================

class TestAssemblePromptXml:
    """Kiểm tra assemble_prompt() với XML output style."""

    def test_xml_contains_file_summary(self) -> None:
        """XML prompt có file_summary section."""
        result = assemble_prompt(
            file_map="src/\n  main.py",
            file_contents="<files></files>",
            output_style=OutputStyle.XML,
        )
        assert "<file_summary>" in result
        assert "<structure>" in result

    def test_xml_with_user_instructions(self) -> None:
        """XML prompt có user_instructions ở cuối."""
        result = assemble_prompt(
            file_map="map",
            file_contents="contents",
            user_instructions="Fix bug",
            output_style=OutputStyle.XML,
        )
        assert "<user_instructions>" in result
        assert "Fix bug" in result


class TestAssemblePromptPlain:
    """Kiểm tra assemble_prompt() với Plain output style."""

    def test_plain_no_xml_tags(self) -> None:
        """Plain prompt không có XML tags."""
        result = assemble_prompt(
            file_map="map",
            file_contents="contents",
            output_style=OutputStyle.PLAIN,
        )
        assert "<file_summary>" not in result
        assert "DIRECTORY STRUCTURE" in result
        assert "FILE CONTEXT" in result

    def test_plain_with_instructions_first(self) -> None:
        """Plain prompt có instructions ở cuối (recency bias)."""
        result = assemble_prompt(
            file_map="map",
            file_contents="contents",
            user_instructions="Do this",
            output_style=OutputStyle.PLAIN,
        )
        # Instructions xuất hiện sau Directory Structure và File Context (recency bias)
        inst_pos = result.index("USER INSTRUCTIONS")
        dir_pos = result.index("DIRECTORY STRUCTURE")
        contents_pos = result.index("FILE CONTEXT")
        assert dir_pos < contents_pos < inst_pos, (
            "Instructions should be at the end for recency bias"
        )


class TestAssembleSmartPrompt:
    """Kiểm tra assemble_smart_prompt()."""

    def test_contains_smart_context_section(self) -> None:
        """Smart prompt có smart_context section."""
        result = assemble_smart_prompt(
            smart_contents="def foo(): pass",
            file_map="src/\n  main.py",
        )
        assert "<smart_context>" in result
        assert "</smart_context>" in result
        assert "def foo(): pass" in result
