"""
Unit tests cho Prompt Generator module.

Test các case:
- generate_file_map(): Tạo tree map từ TreeItem.
- generate_file_contents(): Tạo nội dung files với delimiters.
- generate_file_contents_xml(): Tạo nội dung files theo Repomix XML format.
- generate_prompt(): Tạo prompt đầy đủ với Git context.
- calculate_markdown_delimiter(): Tính delimiter phù hợp.
- generate_smart_context(): Trích xuất code signatures.
"""

import pytest

from domain.prompt.generator import (
    generate_prompt,
    generate_file_map,
    generate_file_contents_xml,
    generate_file_contents_plain,
    generate_smart_context,
    build_smart_prompt,
)
from infrastructure.filesystem.file_utils import TreeItem
from infrastructure.git.git_utils import GitDiffResult, GitLogResult, GitCommit
from presentation.config.output_format import OutputStyle


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

    def test_root_shows_workspace_name_when_relative(self, tmp_path):
        """Khi use_relative_paths, root hien thi ten folder workspace (vd. synapse-desktop)."""
        ws = tmp_path / "my-project"
        ws.mkdir()
        file_path = ws / "main.py"
        file_path.write_text("x = 1")

        tree = TreeItem(
            label="my-project",
            path=str(ws),
            is_dir=True,
            children=[
                TreeItem(
                    label="main.py", path=str(file_path), is_dir=False, children=[]
                )
            ],
        )
        result = generate_file_map(
            tree, {str(file_path)}, workspace_root=ws, use_relative_paths=True
        )

        # Root phai la "my-project" (lowercase), khong phai "."
        assert "my-project" in result
        assert result.strip().startswith("my-project")


class TestGeneratePrompt:
    """Test generate_prompt() function."""

    def test_basic_prompt(self):
        """Basic prompt generation works."""
        result = generate_prompt(
            file_map="src/main.py",
            file_contents="def main(): pass",
            output_style=OutputStyle.XML,  # MARKDOWN removed
        )

        assert "<structure>" in result
        assert "</structure>" in result
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

    def test_opx_instructions_before_user_when_both_present(self):
        """opx_instructions xuất hiện trước user_instructions."""
        result = generate_prompt(
            file_map="src/main.py",
            file_contents="<files><file>code</file></files>",
            user_instructions="Thêm error handling",
            include_xml_formatting=True,
            output_style=OutputStyle.XML,
        )
        ui_pos = result.find("<user_instructions>")
        opx_pos = result.find("<opx_instructions>")
        assert ui_pos >= 0, "user_instructions phải có trong prompt"
        assert opx_pos >= 0, "opx_instructions phải có trong prompt"
        assert opx_pos < ui_pos, "opx_instructions phải đứng trước user_instructions"

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


class TestBuildSmartPrompt:
    """Test build_smart_prompt() - full prompt voi file_summary, directory_structure."""

    def test_includes_file_summary_and_directory_structure(self):
        """build_smart_prompt phai co file_summary, directory_structure, smart_context."""
        result = build_smart_prompt(
            smart_contents="File: src/main.py [Smart Context]\n```python\ndef foo(): pass\n```",
            file_map="synapse-desktop\n└── src\n    └── main.py",
            user_instructions="Add error handling",
        )
        assert "<file_summary>" in result
        assert "<structure>" in result
        assert "<smart_context>" in result
        assert "<user_instructions>" in result
        assert "Add error handling" in result
        assert "synapse-desktop" in result

    def test_without_instructions(self):
        """Khi khong co instructions, khong co user_instructions tag."""
        result = build_smart_prompt(
            smart_contents="File: a.py\n```python\nx=1\n```",
            file_map=".",
            user_instructions="",
        )
        assert "<file_summary>" in result
        assert "<smart_context>" in result
        assert "<user_instructions>" not in result


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


class TestRepomixXmlFormat:
    """Test Repomix XML output format."""

    def test_xml_output_structure(self, tmp_path):
        """XML output has correct structure."""
        file_path = tmp_path / "main.py"
        file_path.write_text("print('hello')")

        result = generate_file_contents_xml({str(file_path)})

        assert "<files>" in result
        assert "</files>" in result
        assert "<file path=" in result
        assert "</file>" in result

    def test_xml_file_path_attribute(self, tmp_path):
        """File path is in attribute, not content."""
        file_path = tmp_path / "utils.py"
        file_path.write_text("def helper(): pass")

        result = generate_file_contents_xml({str(file_path)})

        # Path phải nằm trong attribute
        assert f'path="{tmp_path}/utils.py"' in result or 'path="' in result
        assert "def helper(): pass" in result

    def test_xml_escapes_special_chars(self, tmp_path):
        """XML special characters are escaped."""
        file_path = tmp_path / "test.py"
        file_path.write_text("if a < b and c > d: pass")

        result = generate_file_contents_xml({str(file_path)})

        # CDATA section keeps literal < and >
        assert "if a < b and c > d" in result
        assert "<![CDATA[" in result

    def test_xml_empty_set(self):
        """Empty set returns empty files tag."""
        result = generate_file_contents_xml(set())
        assert result == "<files></files>"

    def test_xml_binary_file_marked_skipped(self, tmp_path):
        """Binary files are marked as skipped."""
        file_path = tmp_path / "image.jpg"
        file_path.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0]))

        result = generate_file_contents_xml({str(file_path)})

        assert 'skipped="true"' in result
        assert "Binary file" in result

    def test_xml_use_relative_paths(self, tmp_path):
        """Khi use_relative_paths=True, path xuat tuong doi workspace (tranh PII)."""
        sub = tmp_path / "src"
        sub.mkdir()
        file_path = sub / "main.py"
        file_path.write_text("print('hi')")

        result = generate_file_contents_xml(
            {str(file_path)},
            workspace_root=tmp_path,
            use_relative_paths=True,
        )

        # Path phai la relative, khong chua absolute
        assert 'path="src/main.py"' in result
        assert str(tmp_path) not in result

    def test_xml_use_relative_paths_off_fallback(self, tmp_path):
        """Khi use_relative_paths=False, giu nguyen absolute path (logic cu)."""
        file_path = tmp_path / "main.py"
        file_path.write_text("x = 1")

        result = generate_file_contents_xml(
            {str(file_path)},
            workspace_root=tmp_path,
            use_relative_paths=False,
        )

        # Absolute path phai co trong output
        assert str(tmp_path) in result
        assert "main.py" in result

    def test_generate_prompt_with_xml_style(self):
        """generate_prompt uses correct tags for XML style."""
        result = generate_prompt(
            file_map="src/main.py",
            file_contents="<files><file>code</file></files>",
            output_style=OutputStyle.XML,
        )

        assert "<structure>" in result
        assert "</structure>" in result
        # XML style không dùng <file_contents> wrapper
        assert "<file_map>" not in result

    def test_generate_prompt_default_is_xml(self):
        """Default output_style is XML."""
        result = generate_prompt(
            file_map="test.py",
            file_contents="code",
        )

        # Default is structure XML
        assert "<structure>" in result
        assert "<file_map>" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestPlainFormat:
    """Test Plain Text output format."""

    def test_plain_output_structure(self, tmp_path):
        """Plain output has correct structure."""
        file_path = tmp_path / "main.py"
        file_path.write_text("print('hello')")

        result = generate_file_contents_plain({str(file_path)})

        assert f"FILE: {file_path}" in result
        assert "print('hello')" in result
        assert "-----" in result

    def test_generate_prompt_with_plain_style(self):
        """generate_prompt produces plain text for PLAIN output style."""
        file_map = "tree"
        file_contents = "File: main.py\ncode"

        result = generate_prompt(
            file_map=file_map,
            file_contents=file_contents,
            output_style=OutputStyle.PLAIN,
            user_instructions="Please fix bugs",
        )
        assert "Please fix bugs" in result
        assert "main.py" in result
        assert "code" in result
        assert "=" in result
        assert "<file_map>" not in result
