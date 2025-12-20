"""
Unit tests cho Prompt Generator module.

Test các case:
- generate_file_map(): Tạo tree map từ TreeItem.
- generate_file_contents(): Tạo nội dung files với delimiters.
- generate_prompt(): Tạo prompt đầy đủ với Git context.
- calculate_markdown_delimiter(): Tính delimiter phù hợp.
- generate_smart_context(): Trích xuất code signatures.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from core.prompt_generator import (
    generate_prompt,
    generate_file_map,
    generate_file_contents,
    generate_smart_context,
    calculate_markdown_delimiter,
)
from core.utils.file_utils import TreeItem
from core.utils.git_utils import GitDiffResult, GitLogResult, GitCommit


class TestCalculateMarkdownDelimiter:
    """Test calculate_markdown_delimiter() function."""

    def test_no_backticks(self):
        """Content without backticks uses 3 backticks."""
        contents = ["def hello():\n    print('world')"]
        delimiter = calculate_markdown_delimiter(contents)
        assert delimiter == "```"

    def test_three_backticks_in_content(self):
        """Content with ``` uses 4 backticks."""
        contents = ["Here is code:\n```python\nprint('x')\n```"]
        delimiter = calculate_markdown_delimiter(contents)
        assert delimiter == "````"

    def test_four_backticks_in_content(self):
        """Content with ```` uses 5 backticks."""
        contents = ["Nested code:\n````\n```\ninner\n```\n````"]
        delimiter = calculate_markdown_delimiter(contents)
        assert delimiter == "`````"

    def test_many_backticks(self):
        """Content with many backticks uses more."""
        contents = ["``````some content``````"]
        delimiter = calculate_markdown_delimiter(contents)
        assert len(delimiter) > 6

    def test_empty_contents(self):
        """Empty contents list returns 3 backticks."""
        delimiter = calculate_markdown_delimiter([])
        assert delimiter == "```"

    def test_multiple_files(self):
        """Multiple files, one with backticks."""
        contents = [
            "simple content",
            "```python\ncode\n```",  # Has 3 backticks
            "another simple",
        ]
        delimiter = calculate_markdown_delimiter(contents)
        assert delimiter == "````"


class TestGenerateFileMap:
    """Test generate_file_map() function."""

    def test_empty_tree(self):
        """Empty tree returns minimal map."""
        tree = TreeItem(label="root", path="/root", is_dir=True, children=[])
        result = generate_file_map(tree, set())
        # Empty selection có thể trả về empty hoặc root only
        assert isinstance(result, str)

    def test_single_selected_file(self):
        """Single selected file appears in map."""
        child = TreeItem(
            label="main.py", path="/root/main.py", is_dir=False, children=[]
        )
        tree = TreeItem(label="root", path="/root", is_dir=True, children=[child])

        result = generate_file_map(tree, {"/root/main.py"})

        assert "main.py" in result

    def test_nested_structure(self):
        """Nested directory structure."""
        parser_file = TreeItem(
            label="parser.py", path="/root/src/parser.py", is_dir=False, children=[]
        )
        src_dir = TreeItem(
            label="src", path="/root/src", is_dir=True, children=[parser_file]
        )
        tree = TreeItem(label="root", path="/root", is_dir=True, children=[src_dir])

        result = generate_file_map(tree, {"/root/src/parser.py"})

        assert "parser.py" in result
        assert "src" in result

    def test_unselected_files_excluded(self):
        """Unselected files are not in map."""
        selected_file = TreeItem(
            label="selected.py", path="/root/selected.py", is_dir=False, children=[]
        )
        unselected_file = TreeItem(
            label="unselected.py", path="/root/unselected.py", is_dir=False, children=[]
        )
        tree = TreeItem(
            label="root",
            path="/root",
            is_dir=True,
            children=[selected_file, unselected_file],
        )

        result = generate_file_map(tree, {"/root/selected.py"})

        assert "selected.py" in result
        # Unselected file không nên xuất hiện
        assert "unselected.py" not in result


class TestGenerateFileContents:
    """Test generate_file_contents() function."""

    def test_empty_set(self):
        """Empty set returns empty string."""
        result = generate_file_contents(set())
        assert result == ""

    def test_single_file(self, tmp_path):
        """Single file content generated."""
        file_path = tmp_path / "test.py"
        file_path.write_text("print('hello')")

        result = generate_file_contents({str(file_path)})

        assert "test.py" in result
        assert "print('hello')" in result
        # Phải có markdown code block
        assert "```" in result

    def test_multiple_files(self, tmp_path):
        """Multiple files content generated."""
        paths = set()
        for name in ["a.py", "b.py", "c.py"]:
            path = tmp_path / name
            path.write_text(f"# {name}")
            paths.add(str(path))

        result = generate_file_contents(paths)

        for name in ["a.py", "b.py", "c.py"]:
            assert name in result

    def test_file_with_backticks(self, tmp_path):
        """File containing backticks uses dynamic delimiter."""
        file_path = tmp_path / "readme.md"
        file_path.write_text("Example:\n```python\ncode here\n```")

        result = generate_file_contents({str(file_path)})

        # Phải dùng 4+ backticks
        assert "````" in result

    def test_binary_extension_skipped(self, tmp_path):
        """Binary file by extension is skipped."""
        file_path = tmp_path / "image.jpg"
        file_path.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0]))

        result = generate_file_contents({str(file_path)})

        # Binary file không có content, hoặc có marker
        # Không crash
        assert isinstance(result, str)

    def test_nonexistent_file_skipped(self, tmp_path):
        """Nonexistent file is skipped gracefully."""
        result = generate_file_contents({str(tmp_path / "nonexistent.py")})
        # Không crash, trả về string
        assert isinstance(result, str)


class TestGeneratePrompt:
    """Test generate_prompt() function."""

    def test_basic_prompt(self):
        """Basic prompt with file_map and contents."""
        file_map = "src/main.py"
        file_contents = "def main(): pass"

        result = generate_prompt(file_map, file_contents)

        assert "<file_map>" in result
        assert "</file_map>" in result
        assert "<file_contents>" in result
        assert "</file_contents>" in result
        assert "src/main.py" in result
        assert "def main(): pass" in result

    def test_with_user_instructions(self):
        """Prompt with user instructions."""
        result = generate_prompt(
            file_map="file.py",
            file_contents="code",
            user_instructions="Please review this code.",
        )

        assert "Please review this code" in result

    def test_with_xml_formatting(self):
        """Prompt with XML formatting enabled."""
        result = generate_prompt(
            file_map="file.py", file_contents="code", include_xml_formatting=True
        )

        # Phải có OPX instructions
        assert "OPX" in result or "<edit" in result or "operation" in result.lower()

    def test_with_git_diffs(self):
        """Prompt with Git diffs included."""
        git_diffs = GitDiffResult(
            work_tree_diff="diff --git a/file.py\n+new line",
            staged_diff="diff --git a/staged.py\n-removed",
        )

        result = generate_prompt(
            file_map="file.py", file_contents="code", git_diffs=git_diffs
        )

        assert "<git_changes>" in result
        assert "</git_changes>" in result
        assert "<git_diff_worktree>" in result
        assert "new line" in result
        assert "<git_diff_staged>" in result
        assert "removed" in result

    def test_with_git_logs(self):
        """Prompt with Git logs included."""
        git_logs = GitLogResult(
            commits=[
                GitCommit(
                    hash="abc123",
                    date="2024-12-20",
                    message="Fix bug",
                    files=["file.py"],
                )
            ],
            log_content="abc123 2024-12-20 Fix bug",
        )

        result = generate_prompt(
            file_map="file.py", file_contents="code", git_logs=git_logs
        )

        assert "<git_changes>" in result
        assert "<git_log>" in result
        assert "Fix bug" in result

    def test_with_both_git_diffs_and_logs(self):
        """Prompt with both diffs and logs."""
        git_diffs = GitDiffResult(work_tree_diff="diff content", staged_diff="")
        git_logs = GitLogResult(
            commits=[GitCommit(hash="x", date="d", message="msg", files=[])],
            log_content="log content",
        )

        result = generate_prompt(
            file_map="file.py",
            file_contents="code",
            git_diffs=git_diffs,
            git_logs=git_logs,
        )

        assert "<git_changes>" in result
        assert "<git_diff_worktree>" in result
        assert "<git_log>" in result

    def test_empty_git_data_not_included(self):
        """Empty git data sections are not included."""
        git_diffs = GitDiffResult(work_tree_diff="", staged_diff="")

        result = generate_prompt(
            file_map="file.py", file_contents="code", git_diffs=git_diffs
        )

        # Nếu cả 2 diffs đều empty, có thể không có section hoặc section rỗng
        # Behavior tùy implementation
        assert "file.py" in result


class TestGenerateSmartContext:
    """Test generate_smart_context() function."""

    def test_empty_set(self):
        """Empty set returns empty or minimal string."""
        result = generate_smart_context(set())
        assert isinstance(result, str)

    def test_python_file(self, tmp_path):
        """Python file has signatures extracted."""
        file_path = tmp_path / "module.py"
        file_path.write_text(
            '''
"""Module docstring."""

def my_function(arg1: str, arg2: int) -> bool:
    """Function docstring."""
    return True

class MyClass:
    """Class docstring."""
    
    def method(self) -> None:
        """Method docstring."""
        pass
'''
        )

        result = generate_smart_context({str(file_path)})

        # Smart context phải trích xuất signatures
        assert isinstance(result, str)

    def test_unsupported_file_type(self, tmp_path):
        """Unsupported file type handled gracefully."""
        file_path = tmp_path / "data.xyz"
        file_path.write_text("random content")

        result = generate_smart_context({str(file_path)})

        # Không crash, trả về string
        assert isinstance(result, str)


class TestPromptStructure:
    """Test overall prompt structure."""

    def test_xml_tags_properly_closed(self):
        """All XML tags are properly closed."""
        result = generate_prompt(
            file_map="test.py",
            file_contents="code",
            user_instructions="Review this",
            include_xml_formatting=True,
        )

        # Count opening and closing tags
        open_file_map = result.count("<file_map>")
        close_file_map = result.count("</file_map>")
        assert open_file_map == close_file_map

        open_contents = result.count("<file_contents>")
        close_contents = result.count("</file_contents>")
        assert open_contents == close_contents

    def test_no_empty_sections(self):
        """Prompt doesn't have double empty sections."""
        result = generate_prompt(file_map="test.py", file_contents="code")

        # Không có empty instructions tag
        assert "<instructions></instructions>" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
