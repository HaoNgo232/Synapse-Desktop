import json
import pytest

from core.prompting.prompt_assembler import assemble_prompt, assemble_smart_prompt
from config.output_format import OutputStyle
from core.opx_instruction import XML_FORMATTING_INSTRUCTIONS
from core.utils.git_utils import (
    GitDiffResult,
    GitLogResult,
    DiffOnlyResult,
    build_diff_only_prompt,
)
from core.tree_map_generator import generate_tree_map_only
from core.utils.file_utils import TreeItem


@pytest.fixture
def sample_file_map():
    return "src/\n  main.py\n  utils.py"


@pytest.fixture
def sample_file_contents_xml():
    return "<files>\n<file path=\"src/main.py\">\nprint('hello')\n</file>\n</files>"


@pytest.fixture
def sample_file_contents_json():
    return json.dumps({"src/main.py": "print('hello')"})


@pytest.fixture
def sample_file_contents_plain():
    return "File: src/main.py\nprint('hello')\n----------------"


class TestAssemblePrompt:
    """Test output format consistency for different copy modes."""

    def test_assemble_xml_format(self, sample_file_map, sample_file_contents_xml):
        """Verify the exact structure of XML output mode."""
        prompt = assemble_prompt(
            file_map=sample_file_map,
            file_contents=sample_file_contents_xml,
            user_instructions="Please fix bugs.",
            output_style=OutputStyle.XML,
            include_xml_formatting=False,
        )

        assert "<file_summary>" in prompt
        assert "<directory_structure>" in prompt
        assert sample_file_map in prompt
        assert "</directory_structure>" in prompt
        assert sample_file_contents_xml in prompt
        assert "<user_instructions>" in prompt
        assert "Please fix bugs." in prompt
        assert XML_FORMATTING_INSTRUCTIONS not in prompt

    def test_assemble_json_format(self, sample_file_map, sample_file_contents_json):
        """Verify the exact structure of JSON output mode."""
        prompt = assemble_prompt(
            file_map=sample_file_map,
            file_contents=sample_file_contents_json,
            user_instructions="Refactor code.",
            output_style=OutputStyle.JSON,
            include_xml_formatting=False,
        )

        # Parse output to verify it's valid JSON
        data = json.loads(prompt)
        assert "system_instruction" in data
        assert "file_summary" in data
        assert data["directory_structure"] == sample_file_map
        assert "src/main.py" in data["files"]
        assert data["instructions"] == "Refactor code."
        assert "formatting_instructions" not in data

    def test_assemble_plain_format(self, sample_file_map, sample_file_contents_plain):
        """Verify the exact structure of Plain Text output mode."""
        prompt = assemble_prompt(
            file_map=sample_file_map,
            file_contents=sample_file_contents_plain,
            user_instructions="Explain this.",
            output_style=OutputStyle.PLAIN,
            include_xml_formatting=False,
        )

        assert "SYSTEM INSTRUCTION" in prompt
        assert "FILE SUMMARY" in prompt
        assert "Directory Structure:" in prompt
        assert sample_file_map in prompt
        assert "File Contents:" in prompt
        assert sample_file_contents_plain in prompt
        assert "Instructions:" in prompt
        assert "Explain this." in prompt
        assert "<system_instruction>" not in prompt  # No XML tags in plain text

    def test_assemble_markdown_format(
        self, sample_file_map, sample_file_contents_plain
    ):
        """Verify the exact structure of Markdown output mode."""
        # Note: In practice Markdown uses similar content payload as Plain but wrapped in XML semantic tags for the AI
        prompt = assemble_prompt(
            file_map=sample_file_map,
            file_contents=sample_file_contents_plain,
            user_instructions="Document code.",
            output_style=OutputStyle.MARKDOWN,
            include_xml_formatting=False,
        )

        assert "<system_instruction>" in prompt
        assert "<file_map>" in prompt
        assert sample_file_map in prompt
        assert "</file_map>" in prompt
        assert "<file_contents>" in prompt
        assert sample_file_contents_plain in prompt
        assert "</file_contents>" in prompt
        assert "<user_instructions>" in prompt

    def test_assemble_opx_injection(self, sample_file_map, sample_file_contents_xml):
        """Verify that XML formatting instructions (OPX) are included when include_xml_formatting is True."""
        prompt = assemble_prompt(
            file_map=sample_file_map,
            file_contents=sample_file_contents_xml,
            user_instructions="Review it.",
            output_style=OutputStyle.XML,
            include_xml_formatting=True,
        )

        assert XML_FORMATTING_INSTRUCTIONS in prompt
        assert "Review it." in prompt

    def test_assemble_with_git_changes_xml(
        self, sample_file_map, sample_file_contents_xml
    ):
        """Verify git changes are properly formatting in XML."""
        git_diffs = GitDiffResult(work_tree_diff="diff --git a/main.py", staged_diff="")
        git_logs = GitLogResult(log_content="abc1234 fix bug", commits=[])

        prompt = assemble_prompt(
            file_map=sample_file_map,
            file_contents=sample_file_contents_xml,
            output_style=OutputStyle.XML,
            git_diffs=git_diffs,
            git_logs=git_logs,
        )

        assert "<git_changes>" in prompt
        assert "<git_diff_worktree>" in prompt
        assert "diff --git a/main.py" in prompt
        assert "<git_log>" in prompt
        assert "abc1234 fix bug" in prompt
        assert "</git_changes>" in prompt


class TestAssembleSmartPrompt:
    """Test smart context output format."""

    def test_assemble_smart_prompt(self, sample_file_map):
        smart_contents = "File: src/main.py\ndef run():\n    pass"
        prompt = assemble_smart_prompt(
            smart_contents=smart_contents,
            file_map=sample_file_map,
            user_instructions="What is missing?",
        )

        assert "<file_summary>" in prompt
        assert "<directory_structure>" in prompt
        assert sample_file_map in prompt
        assert "</directory_structure>" in prompt
        assert "<smart_context>" in prompt
        assert smart_contents in prompt
        assert "</smart_context>" in prompt
        assert "<user_instructions>" in prompt
        assert "What is missing?" in prompt


class TestAssembleProjectRules:
    """Test project rules inclusion."""

    def test_assemble_with_project_rules(
        self, sample_file_map, sample_file_contents_plain
    ):
        """Verify project rules are appended correctly."""
        prompt = assemble_prompt(
            file_map=sample_file_map,
            file_contents=sample_file_contents_plain,
            project_rules="Rule 1: Always type hint.",
            output_style=OutputStyle.XML,
        )

        assert "<project_rules>" in prompt
        assert "Rule 1: Always type hint." in prompt
        assert "</project_rules>" in prompt


class TestAssembleDiffOnlyPrompt:
    """Test Diff Only format structure."""

    def test_build_diff_only_prompt_basic(self):
        """Verify the exact structure of Diff Only output mode."""
        diff_result = DiffOnlyResult(
            diff_content="diff --git a/main.py\n+new line",
            files_changed=1,
            insertions=1,
            deletions=0,
            commits_included=0,
            changed_files=["main.py"],
        )

        prompt = build_diff_only_prompt(
            diff_result=diff_result,
            instructions="Review changes.",
            include_changed_content=False,
            include_tree_structure=True,
        )

        assert "<file_summary>" in prompt
        assert "This file contains git changes (diff) from the repository." in prompt
        assert "<diff_context>" in prompt
        assert "Files changed: 1" in prompt
        assert "Lines: +1 / -0" in prompt
        assert "</diff_context>" in prompt
        assert "<directory_structure>" in prompt
        assert "main.py" in prompt  # The tree structure
        assert "<git_diff>" in prompt
        assert "+new line" in prompt
        assert "</git_diff>" in prompt
        assert "<user_instructions>" in prompt
        assert "Review changes." in prompt
        assert "<changed_files_content>" not in prompt

    def test_build_diff_only_with_content(self, tmp_path):
        """Verify Diff Only includes changed file contents when requested."""
        main_py = tmp_path / "main.py"
        main_py.write_text("print('test')")

        diff_result = DiffOnlyResult(
            diff_content="diff",
            files_changed=1,
            insertions=1,
            deletions=0,
            commits_included=0,
            changed_files=["main.py"],
        )

        prompt = build_diff_only_prompt(
            diff_result=diff_result,
            instructions="",
            include_changed_content=True,
            include_tree_structure=False,
            workspace_root=tmp_path,
        )

        assert "<changed_files_content>" in prompt
        assert "<file path=" in prompt
        assert "print('test')" in prompt
        assert "</file>" in prompt
        assert "</changed_files_content>" in prompt
        assert "<directory_structure>" not in prompt


class TestAssembleTreeMapPrompt:
    """Test Tree Map Only format structure."""

    def test_generate_tree_map_only(self):
        """Verify the exact structure of Tree Map output mode."""
        tree = TreeItem(
            label="root",
            path="/root",
            is_dir=True,
            children=[
                TreeItem(
                    label="main.py", path="/root/main.py", is_dir=False, children=[]
                )
            ],
        )

        prompt = generate_tree_map_only(
            tree=tree,
            selected_paths={"/root/main.py"},
            user_instructions="Look at this structure.",
        )

        # generate_file_map formats it as a nice structure
        assert "<file_map>" in prompt
        assert "</file_map>" in prompt
        assert "root" in prompt or "main.py" in prompt
        assert "<user_instructions>" in prompt
        assert "Look at this structure." in prompt
        assert "<file_contents>" not in prompt
        assert "<system_instruction>" not in prompt
