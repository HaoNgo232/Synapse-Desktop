"""
Tests cho PromptBuildService va service interfaces.

Verify:
1. IPromptBuilder / IClipboardService protocol compliance
2. PromptBuildService.build_prompt cho xml và các định dạng chuẩn
3. PromptBuildService.build_file_map delegation
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

from application.services.service_interfaces import IPromptBuilder, IClipboardService
from application.services.prompt_build_service import PromptBuildService
from infrastructure.adapters.clipboard_service import QtClipboardService


class TestProtocolCompliance:
    """Verify implementations satisfy protocols."""

    def test_prompt_build_service_is_prompt_builder(self):
        """PromptBuildService implement IPromptBuilder."""
        assert isinstance(PromptBuildService(), IPromptBuilder)

    def test_qt_clipboard_service_is_clipboard_service(self):
        """QtClipboardService implement IClipboardService."""
        assert isinstance(QtClipboardService(), IClipboardService)


class TestPromptBuildService:
    """Test PromptBuildService build operations."""

    @patch("infrastructure.git.git_utils.get_git_logs")
    @patch("infrastructure.git.git_utils.get_git_diffs")
    @patch("domain.prompt.generator.generate_prompt")
    @patch("domain.prompt.generator.generate_file_contents_xml")
    def test_build_prompt_xml(
        self, mock_gen_xml, mock_gen_prompt, mock_diff, mock_logs
    ):
        """build_prompt xml format goi generate_prompt dung."""
        mock_svc = MagicMock()
        mock_svc.count_tokens.return_value = 42
        service = PromptBuildService(tokenization_service=mock_svc)

        mock_gen_xml.return_value = "<file contents>"
        mock_gen_prompt.return_value = "<prompt>test</prompt>"
        mock_diff.return_value = None
        mock_logs.return_value = None

        with patch(
            "infrastructure.persistence.settings_manager.load_app_settings"
        ) as mock_settings:
            mock_settings_inst = MagicMock()
            mock_settings_inst.get_rule_filenames_set.return_value = set()
            mock_settings.return_value = mock_settings_inst

            prompt, count, breakdown = service.build_prompt(
                file_paths=[Path("/a.py")],
                workspace=Path("/project"),
                instructions="fix bugs",
                output_format="xml",
                include_git_changes=False,
                use_relative_paths=True,
            )

        assert prompt == "<prompt>test</prompt>"
        assert count == 42
        assert isinstance(breakdown, dict)
        assert breakdown["content_tokens"] == 42
        mock_gen_prompt.assert_called_once()

    @patch("application.services.prompt_build_service.generate_file_map")
    def test_build_file_map(self, mock_map):
        """build_file_map delegate den generate_file_map."""
        service = PromptBuildService()
        mock_map.return_value = "tree output"

        from infrastructure.filesystem.file_utils import TreeItem

        tree = TreeItem(
            label="root", path="/project", is_dir=True, is_loaded=True, children=[]
        )

        result = service.build_file_map(
            tree_item=tree,
            selected_paths={"/project/a.py"},
            workspace=Path("/project"),
        )

        assert result == "tree output"
        # Mocking check for generate_file_map in generator module
        # Because PromptBuildService.build_file_map calls it directly
        mock_map.assert_called_once()

    @patch("infrastructure.git.git_utils.get_git_logs")
    @patch("infrastructure.git.git_utils.get_git_diffs")
    @patch("domain.prompt.generator.generate_prompt")
    @patch("domain.prompt.generator.generate_file_contents_xml")
    def test_build_prompt_extracts_rules(
        self, mock_gen_xml, mock_gen_prompt, mock_diff, mock_logs, tmp_path
    ):
        """Test build_prompt loads rule files from workspace rules."""
        mock_svc = MagicMock()
        mock_svc.count_tokens.return_value = 42
        service = PromptBuildService(tokenization_service=mock_svc)

        rule_file = tmp_path / ".cursorrules"
        rule_file.write_text("Rule 1")
        normal_file = tmp_path / "a.py"
        normal_file.write_text("print('hello')")

        # Mark .cursorrules as a project rule
        from application.services.workspace_rules import add_rule_file

        add_rule_file(tmp_path, str(rule_file))

        mock_gen_xml.return_value = "<file contents>"
        mock_gen_prompt.return_value = "<prompt>test</prompt>"
        mock_diff.return_value = None
        mock_logs.return_value = None

        prompt, count, breakdown = service.build_prompt(
            file_paths=[rule_file, normal_file],
            workspace=tmp_path,
            instructions="fix",
            output_format="xml",
            include_git_changes=False,
            use_relative_paths=True,
        )

        # Kiem tra generate_prompt duoc goi dung params project_rules
        called_kwargs = mock_gen_prompt.call_args[1]
        assert "--- Rule File: .cursorrules ---" in called_kwargs["project_rules"]
        assert "Rule 1" in called_kwargs["project_rules"]
