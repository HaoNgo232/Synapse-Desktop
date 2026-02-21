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

    def setup_method(self):
        self.service = PromptBuildService()

    @patch("services.prompt_build_service.generate_prompt")
    @patch("services.prompt_build_service.generate_file_contents_xml")
    @patch("services.prompt_build_service.get_tokenization_service")
    def test_build_prompt_xml(self, mock_tokenizer, mock_gen_xml, mock_gen_prompt):
        """build_prompt xml format goi generate_prompt dung."""
        mock_gen_xml.return_value = "<file contents>"
        mock_gen_prompt.return_value = "<prompt>test</prompt>"
        mock_svc = MagicMock()
        mock_svc.count_tokens.return_value = 42
        mock_tokenizer.return_value = mock_svc

        with patch("services.settings_manager.load_app_settings") as mock_settings:
            mock_settings_inst = MagicMock()
            mock_settings_inst.get_rule_filenames_set.return_value = set()
            mock_settings.return_value = mock_settings_inst

            prompt, count = self.service.build_prompt(
                file_paths=[Path("/a.py")],
                workspace=Path("/project"),
                instructions="fix bugs",
                output_format="xml",
                include_git_changes=False,
                use_relative_paths=True,
            )

        assert prompt == "<prompt>test</prompt>"
        assert count == 42
        mock_gen_prompt.assert_called_once()

    @patch("services.prompt_build_service.build_smart_prompt")
    @patch("services.prompt_build_service.generate_smart_context")
    @patch("services.prompt_build_service.get_tokenization_service")
    def test_build_prompt_smart(self, mock_tokenizer, mock_smart_ctx, mock_build):
        """build_prompt smart format goi smart pipeline."""
        mock_smart_ctx.return_value = "smart context output"
        mock_build.return_value = "smart prompt"
        mock_svc = MagicMock()
        mock_svc.count_tokens.return_value = 100
        mock_tokenizer.return_value = mock_svc

        with patch("services.settings_manager.load_app_settings") as mock_settings:
            mock_settings_inst = MagicMock()
            mock_settings_inst.get_rule_filenames_set.return_value = set()
            mock_settings.return_value = mock_settings_inst

            prompt, count = self.service.build_prompt(
                file_paths=[Path("/a.py")],
                workspace=Path("/project"),
                instructions="refactor",
                output_format="smart",
                include_git_changes=True,
                use_relative_paths=True,
            )

        assert prompt == "smart prompt"
        assert count == 100
        mock_smart_ctx.assert_called_once()
        mock_build.assert_called_once()

    @patch("services.prompt_build_service.generate_file_map")
    def test_build_file_map(self, mock_map):
        """build_file_map delegate den generate_file_map."""
        mock_map.return_value = "tree output"

        from core.utils.file_utils import TreeItem

        tree = TreeItem(
            label="root", path="/project", is_dir=True, is_loaded=True, children=[]
        )

        result = self.service.build_file_map(
            tree_item=tree,
            selected_paths={"/project/a.py"},
            workspace=Path("/project"),
        )

        assert result == "tree output"
        mock_map.assert_called_once()

    @patch("services.prompt_build_service.generate_prompt")
    @patch("services.prompt_build_service.generate_file_contents_xml")
    @patch("services.prompt_build_service.get_tokenization_service")
    def test_build_prompt_extracts_rules(
        self, mock_tokenizer, mock_gen_xml, mock_gen_prompt, tmp_path
    ):
        """Test build_prompt removes rule files and passes project_rules args."""
        rule_file = tmp_path / ".cursorrules"
        rule_file.write_text("Rule 1")
        normal_file = tmp_path / "a.py"

        mock_gen_xml.return_value = "<file contents>"
        mock_gen_prompt.return_value = "<prompt>test</prompt>"
        mock_svc = MagicMock()
        mock_svc.count_tokens.return_value = 42
        mock_tokenizer.return_value = mock_svc

        with patch("services.settings_manager.load_app_settings") as mock_settings:
            mock_settings_inst = MagicMock()
            mock_settings_inst.get_rule_filenames_set.return_value = {".cursorrules"}
            mock_settings.return_value = mock_settings_inst

            prompt, count = self.service.build_prompt(
                file_paths=[rule_file, normal_file],
                workspace=tmp_path,
                instructions="fix",
                output_format="xml",
                include_git_changes=False,
                use_relative_paths=True,
            )

            # Test generator call arguments explicitly if possible.
            # But since it's resolved via _FORMAT_TO_GENERATOR, mock_gen_xml is NOT the one called.
            # We simply check the generate_prompt arguments instead.

            # Kiem tra generate_prompt duoc goi dung params project_rules
            called_kwargs = mock_gen_prompt.call_args[1]
            assert "--- Rule File: .cursorrules ---" in called_kwargs["project_rules"]
            assert "Rule 1" in called_kwargs["project_rules"]

            # Kiem tra generate_prompt duoc goi dung params project_rules
            called_kwargs = mock_gen_prompt.call_args[1]
            assert "--- Rule File: .cursorrules ---" in called_kwargs["project_rules"]
            assert "Rule 1" in called_kwargs["project_rules"]
