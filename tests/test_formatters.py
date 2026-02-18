"""
Unit tests cho formatters va prompt_assembler.

Test cac module:
- formatters/markdown.py: format_files_markdown()
- formatters/xml.py: format_files_xml(), generate_file_summary_xml(), generate_smart_summary_xml()
- formatters/json_fmt.py: format_files_json()
- formatters/plain.py: format_files_plain()
- prompt_assembler.py: assemble_prompt(), assemble_smart_prompt()
"""

import json
from pathlib import Path

from core.prompting.types import FileEntry
from core.prompting.formatters.markdown import (
    format_files_markdown,
    _calculate_max_backticks,
)
from core.prompting.formatters.xml import (
    format_files_xml,
    generate_file_summary_xml,
    generate_smart_summary_xml,
)
from core.prompting.formatters.json_fmt import format_files_json
from core.prompting.formatters.plain import format_files_plain
from core.prompting.prompt_assembler import assemble_prompt, assemble_smart_prompt
from core.utils.git_utils import GitDiffResult
from config.output_format import OutputStyle


# === Helpers ===


def _make_entry(
    path="test.py",
    content="print('hello')",
    error=None,
    language="python",
    display_path=None,
):
    """Tao FileEntry nhanh cho tests."""
    return FileEntry(
        path=Path(path),
        display_path=display_path or path,
        content=content,
        error=error,
        language=language,
    )


# ===========================================================================
# Markdown Formatter Tests
# ===========================================================================


class TestCalculateMaxBackticks:
    """Test _calculate_max_backticks() helper."""

    def test_no_backticks(self):
        """Content khong co backticks -> 3."""
        entries = [_make_entry(content="no backticks here")]
        assert _calculate_max_backticks(entries) == 3

    def test_triple_backticks(self):
        """Content co ``` -> can 4."""
        entries = [_make_entry(content="some ```code``` here")]
        assert _calculate_max_backticks(entries) == 4

    def test_quad_backticks(self):
        """Content co ```` -> can 5."""
        entries = [_make_entry(content="text ````nested```` end")]
        assert _calculate_max_backticks(entries) == 5

    def test_empty_entries(self):
        """Empty list -> 3."""
        assert _calculate_max_backticks([]) == 3

    def test_skipped_entries_ignored(self):
        """Entries voi content=None bi bo qua."""
        entries = [_make_entry(content=None, error="Binary file")]
        assert _calculate_max_backticks(entries) == 3

    def test_multiple_entries_max(self):
        """Nhieu entries lay max backticks."""
        entries = [
            _make_entry(content="no ticks"),
            _make_entry(content="has ``` triple"),
            _make_entry(content="has ````` quintuple"),
        ]
        assert _calculate_max_backticks(entries) == 6


class TestFormatFilesMarkdown:
    """Test format_files_markdown()."""

    def test_empty_entries(self):
        """Empty list tra ve empty string."""
        assert format_files_markdown([]) == ""

    def test_single_file(self):
        """Single file co code block voi language."""
        entries = [_make_entry()]
        result = format_files_markdown(entries)
        assert "File: test.py" in result
        assert "```python" in result
        assert "print('hello')" in result

    def test_skipped_file(self):
        """Skipped file hien thi error."""
        entries = [_make_entry(content=None, error="Binary file")]
        result = format_files_markdown(entries)
        assert "File: test.py" in result
        assert "*** Skipped: Binary file ***" in result

    def test_backtick_delimiter(self):
        """File co backticks su dung dynamic delimiter."""
        entries = [_make_entry(content="```python\ncode\n```")]
        result = format_files_markdown(entries)
        # Delimiter phai la 4 backticks (3 + 1)
        assert "````python" in result

    def test_multiple_files_separated(self):
        """Nhieu files duoc ngan cach bang newline."""
        entries = [
            _make_entry(path="a.py", display_path="a.py", content="a_content"),
            _make_entry(path="b.py", display_path="b.py", content="b_content"),
        ]
        result = format_files_markdown(entries)
        assert "File: a.py" in result
        assert "File: b.py" in result
        assert "a_content" in result
        assert "b_content" in result


# ===========================================================================
# XML Formatter Tests
# ===========================================================================


class TestFormatFilesXml:
    """Test format_files_xml()."""

    def test_empty_entries(self):
        """Empty list tra ve <files></files>."""
        assert format_files_xml([]) == "<files></files>"

    def test_single_file(self):
        """Single file co XML structure."""
        entries = [_make_entry()]
        result = format_files_xml(entries)
        assert "<files>" in result
        assert "</files>" in result
        assert '<file path="test.py">' in result
        assert "print(&#x27;hello&#x27;)" in result  # HTML escaped

    def test_skipped_file(self):
        """Skipped file co attribute skipped='true'."""
        entries = [_make_entry(content=None, error="Binary file")]
        result = format_files_xml(entries)
        assert 'skipped="true"' in result
        assert "Binary file" in result

    def test_special_chars_escaped(self):
        """XML special chars duoc escape."""
        entries = [_make_entry(content="a < b && c > d")]
        result = format_files_xml(entries)
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result

    def test_path_with_special_chars(self):
        """Path co special chars cung duoc escape."""
        entries = [_make_entry(display_path='path/with"quotes.py')]
        result = format_files_xml(entries)
        assert "&quot;" in result


class TestGenerateFileSummaryXml:
    """Test generate_file_summary_xml()."""

    def test_contains_required_sections(self):
        """Summary XML chua tat ca sections can thiet."""
        result = generate_file_summary_xml()
        assert "<file_summary>" in result
        assert "</file_summary>" in result
        assert "<purpose>" in result
        assert "<file_format>" in result
        assert "<usage_guidelines>" in result
        assert "<notes>" in result

    def test_contains_synapse_branding(self):
        """Summary XML co ten Synapse Desktop."""
        result = generate_file_summary_xml()
        assert "Synapse Desktop" in result


class TestGenerateSmartSummaryXml:
    """Test generate_smart_summary_xml()."""

    def test_contains_smart_context_info(self):
        """Smart summary co thong tin ve signatures/docstrings."""
        result = generate_smart_summary_xml()
        assert "Smart context" in result or "SMART" in result
        assert "signatures" in result or "declarations" in result

    def test_contains_required_sections(self):
        """Smart summary chua tat ca sections."""
        result = generate_smart_summary_xml()
        assert "<file_summary>" in result
        assert "<purpose>" in result
        assert "<file_format>" in result
        assert "<usage_guidelines>" in result
        assert "<notes>" in result


# ===========================================================================
# JSON Formatter Tests
# ===========================================================================


class TestFormatFilesJson:
    """Test format_files_json()."""

    def test_empty_entries(self):
        """Empty list tra ve valid empty JSON object."""
        result = format_files_json([])
        assert json.loads(result) == {}

    def test_single_file(self):
        """Single file tra ve valid JSON voi path:content."""
        entries = [_make_entry()]
        result = format_files_json(entries)
        data = json.loads(result)
        assert "test.py" in data
        assert data["test.py"] == "print('hello')"

    def test_binary_skip_message(self):
        """Binary file co message 'Binary file (skipped)'."""
        entries = [_make_entry(content=None, error="Binary file")]
        result = format_files_json(entries)
        data = json.loads(result)
        assert data["test.py"] == "Binary file (skipped)"

    def test_large_file_skip_message(self):
        """File qua lon co message voi '(skipped)'."""
        entries = [_make_entry(content=None, error="File too large (2048KB)")]
        result = format_files_json(entries)
        data = json.loads(result)
        assert "(skipped)" in data["test.py"]

    def test_multiple_files_valid_json(self):
        """Nhieu files tao valid JSON."""
        entries = [
            _make_entry(path="a.py", display_path="a.py", content="a_code"),
            _make_entry(path="b.py", display_path="b.py", content="b_code"),
        ]
        result = format_files_json(entries)
        data = json.loads(result)
        assert len(data) == 2
        assert data["a.py"] == "a_code"
        assert data["b.py"] == "b_code"

    def test_unicode_content(self):
        """Content Unicode duoc giu nguyen."""
        entries = [_make_entry(content="tieng Viet co dau")]
        result = format_files_json(entries)
        data = json.loads(result)
        assert data["test.py"] == "tieng Viet co dau"


# ===========================================================================
# Plain Formatter Tests
# ===========================================================================


class TestFormatFilesPlain:
    """Test format_files_plain()."""

    def test_empty_entries(self):
        """Empty list tra ve 'No files selected.'."""
        assert format_files_plain([]) == "No files selected."

    def test_single_file(self):
        """Single file co header, separator, va content."""
        entries = [_make_entry()]
        result = format_files_plain(entries)
        assert "File: test.py" in result
        assert "----------------" in result
        assert "print('hello')" in result

    def test_binary_skip_message(self):
        """Binary file co message 'Binary file (skipped)'."""
        entries = [_make_entry(content=None, error="Binary file")]
        result = format_files_plain(entries)
        assert "Binary file (skipped)" in result

    def test_multiple_files_separated(self):
        """Nhieu files duoc ngan cach bang 2 newlines."""
        entries = [
            _make_entry(path="a.py", display_path="a.py", content="a_code"),
            _make_entry(path="b.py", display_path="b.py", content="b_code"),
        ]
        result = format_files_plain(entries)
        assert "File: a.py" in result
        assert "File: b.py" in result
        # Ngan cach bang double newline
        assert "\n\n" in result

    def test_content_stripped(self):
        """Content duoc strip whitespace."""
        entries = [_make_entry(content="  hello  \n  ")]
        result = format_files_plain(entries)
        assert "hello" in result


# ===========================================================================
# Prompt Assembler Tests
# ===========================================================================


class TestAssemblePromptXml:
    """Test assemble_prompt() voi XML output style."""

    def test_xml_contains_file_summary(self):
        """XML prompt co file_summary section."""
        result = assemble_prompt(
            file_map="src/\n  main.py",
            file_contents="<files></files>",
            output_style=OutputStyle.XML,
        )
        assert "<file_summary>" in result
        assert "<directory_structure>" in result

    def test_xml_with_user_instructions(self):
        """XML prompt co user_instructions o cuoi."""
        result = assemble_prompt(
            file_map="map",
            file_contents="contents",
            user_instructions="Fix bug",
            output_style=OutputStyle.XML,
        )
        assert "<user_instructions>" in result
        assert "Fix bug" in result

    def test_xml_with_git_diffs(self):
        """XML prompt co git_changes section."""
        diffs = GitDiffResult(
            work_tree_diff="diff --git a/file.py",
            staged_diff="staged changes",
        )
        result = assemble_prompt(
            file_map="map",
            file_contents="contents",
            git_diffs=diffs,
            output_style=OutputStyle.XML,
        )
        assert "<git_changes>" in result
        assert "<git_diff_worktree>" in result
        assert "<git_diff_staged>" in result


class TestAssemblePromptJson:
    """Test assemble_prompt() voi JSON output style."""

    def test_json_valid(self):
        """JSON prompt la valid JSON."""
        result = assemble_prompt(
            file_map="map",
            file_contents='{"file.py": "content"}',
            output_style=OutputStyle.JSON,
        )
        data = json.loads(result)
        assert "directory_structure" in data
        assert "files" in data

    def test_json_with_git(self):
        """JSON prompt co git_diffs key."""
        diffs = GitDiffResult(work_tree_diff="diff", staged_diff="staged")
        result = assemble_prompt(
            file_map="map",
            file_contents="{}",
            git_diffs=diffs,
            output_style=OutputStyle.JSON,
        )
        data = json.loads(result)
        assert "git_diffs" in data


class TestAssemblePromptPlain:
    """Test assemble_prompt() voi Plain output style."""

    def test_plain_no_xml_tags(self):
        """Plain prompt khong co XML tags."""
        result = assemble_prompt(
            file_map="map",
            file_contents="contents",
            output_style=OutputStyle.PLAIN,
        )
        assert "<file_summary>" not in result
        assert "Directory Structure:" in result
        assert "File Contents:" in result

    def test_plain_with_instructions_first(self):
        """Plain prompt co instructions o dau."""
        result = assemble_prompt(
            file_map="map",
            file_contents="contents",
            user_instructions="Do this",
            output_style=OutputStyle.PLAIN,
        )
        # Instructions xuat hien truoc Directory Structure
        inst_pos = result.index("Instructions:")
        dir_pos = result.index("Directory Structure:")
        assert inst_pos < dir_pos


class TestAssembleSmartPrompt:
    """Test assemble_smart_prompt()."""

    def test_contains_smart_context_section(self):
        """Smart prompt co smart_context section."""
        result = assemble_smart_prompt(
            smart_contents="def foo(): pass",
            file_map="src/\n  main.py",
        )
        assert "<smart_context>" in result
        assert "</smart_context>" in result
        assert "def foo(): pass" in result

    def test_contains_file_summary(self):
        """Smart prompt co file_summary voi Smart branding."""
        result = assemble_smart_prompt(
            smart_contents="content",
            file_map="map",
        )
        assert "<file_summary>" in result
        assert "SMART" in result

    def test_with_git_changes(self):
        """Smart prompt co git_changes."""
        diffs = GitDiffResult(work_tree_diff="diff", staged_diff="")
        result = assemble_smart_prompt(
            smart_contents="content",
            file_map="map",
            git_diffs=diffs,
        )
        assert "<git_changes>" in result
        assert "<git_diff_worktree>" in result

    def test_with_user_instructions(self):
        """Smart prompt co user_instructions."""
        result = assemble_smart_prompt(
            smart_contents="content",
            file_map="map",
            user_instructions="Review this",
        )
        assert "<user_instructions>" in result
        assert "Review this" in result
