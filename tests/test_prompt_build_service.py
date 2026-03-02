"""
Tests cho PromptBuildService va service interfaces.

Verify:
1. IPromptBuilder / IClipboardService protocol compliance
2. PromptBuildService.build_prompt cho xml va smart formats
3. PromptBuildService.build_file_map delegation
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

from services.service_interfaces import IPromptBuilder, IClipboardService
from services.prompt_build_service import PromptBuildService, QtClipboardService


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

    @patch("services.prompt_build_service.get_git_logs")
    @patch("services.prompt_build_service.get_git_diffs")
    @patch("services.prompt_build_service.generate_prompt")
    @patch("services.prompt_build_service.generate_file_contents_xml")
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

        with patch("services.settings_manager.load_app_settings") as mock_settings:
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

    @patch("services.prompt_build_service.get_git_logs")
    @patch("services.prompt_build_service.get_git_diffs")
    @patch("services.prompt_build_service.build_smart_prompt")
    @patch("services.prompt_build_service.generate_smart_context")
    def test_build_prompt_smart(self, mock_smart_ctx, mock_build, mock_diff, mock_logs):
        """build_prompt smart format goi smart pipeline."""
        mock_svc = MagicMock()
        mock_svc.count_tokens.return_value = 100
        service = PromptBuildService(tokenization_service=mock_svc)

        mock_smart_ctx.return_value = "smart context output"
        mock_build.return_value = "smart prompt"
        mock_diff.return_value = None
        mock_logs.return_value = None

        with patch("services.settings_manager.load_app_settings") as mock_settings:
            mock_settings_inst = MagicMock()
            mock_settings_inst.get_rule_filenames_set.return_value = set()
            mock_settings.return_value = mock_settings_inst

            prompt, count, breakdown = service.build_prompt(
                file_paths=[Path("/a.py")],
                workspace=Path("/project"),
                instructions="refactor",
                output_format="smart",
                include_git_changes=True,
                use_relative_paths=True,
            )

        assert prompt == "smart prompt"
        assert count == 100
        assert isinstance(breakdown, dict)
        mock_smart_ctx.assert_called_once()
        mock_build.assert_called_once()

    @patch("services.prompt_build_service.generate_file_map")
    def test_build_file_map(self, mock_map):
        """build_file_map delegate den generate_file_map."""
        service = PromptBuildService()
        mock_map.return_value = "tree output"

        from core.utils.file_utils import TreeItem

        tree = TreeItem(
            label="root", path="/project", is_dir=True, is_loaded=True, children=[]
        )

        result = service.build_file_map(
            tree_item=tree,
            selected_paths={"/project/a.py"},
            workspace=Path("/project"),
        )

        assert result == "tree output"
        mock_map.assert_called_once()

    @patch("services.prompt_build_service.get_git_logs")
    @patch("services.prompt_build_service.get_git_diffs")
    @patch("services.prompt_build_service.generate_prompt")
    @patch("services.prompt_build_service.generate_file_contents_xml")
    def test_build_prompt_extracts_rules(
        self, mock_gen_xml, mock_gen_prompt, mock_diff, mock_logs, tmp_path
    ):
        """Test build_prompt removes rule files and passes project_rules args."""
        mock_svc = MagicMock()
        mock_svc.count_tokens.return_value = 42
        service = PromptBuildService(tokenization_service=mock_svc)

        rule_file = tmp_path / ".cursorrules"
        rule_file.write_text("Rule 1")
        normal_file = tmp_path / "a.py"

        mock_gen_xml.return_value = "<file contents>"
        mock_gen_prompt.return_value = "<prompt>test</prompt>"
        mock_diff.return_value = None
        mock_logs.return_value = None

        with patch("services.settings_manager.load_app_settings") as mock_settings:
            mock_settings_inst = MagicMock()
            mock_settings_inst.get_rule_filenames_set.return_value = {".cursorrules"}
            mock_settings.return_value = mock_settings_inst

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
