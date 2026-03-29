"""
Integration tests for PromptBuildService with codemap_paths parameter.

Tests end-to-end flow of building prompts with codemap-only files.
"""

import pytest
from unittest.mock import Mock, patch
from application.services.prompt_build_service import PromptBuildService


class TestPromptBuildServiceCodemapIntegration:
    """Integration tests for codemap_paths feature in PromptBuildService."""

    @pytest.fixture
    def service(self):
        """Create PromptBuildService with mocked tokenization."""
        # Arrange
        mock_tokenization = Mock()
        mock_tokenization.count_tokens = Mock(
            side_effect=lambda text: len(text.split())
        )
        return PromptBuildService(tokenization_service=mock_tokenization)

    @pytest.fixture
    def workspace(self, tmp_path):
        """Create temporary workspace with test files."""
        # Arrange
        (tmp_path / "main.py").write_text("def main(): pass")
        (tmp_path / "utils.py").write_text("def helper(): pass")
        (tmp_path / "config.py").write_text("CONFIG = {}")
        return tmp_path

    def test_build_prompt_full_with_codemap_paths(self, service, workspace):
        """Test that codemap_paths are correctly passed through the pipeline."""
        # Arrange
        file_paths = [
            workspace / "main.py",
            workspace / "utils.py",
            workspace / "config.py",
        ]
        codemap_paths = {str(workspace / "utils.py"), str(workspace / "config.py")}

        mock_gen = Mock(return_value="<files>mocked</files>")

        with patch.dict(
            "application.services.prompt_build_service._FORMAT_TO_GENERATOR",
            {"xml": mock_gen},
        ):
            # Act
            service.build_prompt_full(
                file_paths=file_paths,
                workspace=workspace,
                instructions="Test instructions",
                output_format="xml",
                include_git_changes=False,
                use_relative_paths=True,
                codemap_paths=codemap_paths,
            )

            # Assert: Verify codemap_paths passed to generator
            mock_gen.assert_called_once()
            call_kwargs = mock_gen.call_args[1]
            assert "codemap_paths" in call_kwargs
            # Should be normalized to absolute paths
            assert str(workspace / "utils.py") in call_kwargs["codemap_paths"]
            assert str(workspace / "config.py") in call_kwargs["codemap_paths"]

    def test_build_prompt_full_normalizes_relative_codemap_paths(
        self, service, workspace
    ):
        """Test that relative codemap_paths are normalized to absolute."""
        # Arrange
        file_paths = [workspace / "main.py"]
        codemap_paths = {"utils.py"}  # Relative path

        mock_gen = Mock(return_value="<files>mocked</files>")

        with patch.dict(
            "application.services.prompt_build_service._FORMAT_TO_GENERATOR",
            {"xml": mock_gen},
        ):
            # Act
            service.build_prompt_full(
                file_paths=file_paths,
                workspace=workspace,
                instructions="",
                output_format="xml",
                include_git_changes=False,
                use_relative_paths=True,
                codemap_paths=codemap_paths,
            )

            # Assert: Should normalize to absolute path
            call_kwargs = mock_gen.call_args[1]
            normalized = call_kwargs["codemap_paths"]
            assert any(str(workspace / "utils.py") == p for p in normalized)

    def test_count_per_file_tokens_sets_is_codemap_flag(self, service, workspace):
        """Test that count_per_file_tokens correctly sets is_codemap flag."""
        # Arrange
        file_paths = [workspace / "main.py", workspace / "utils.py"]
        codemap_paths = {str(workspace / "utils.py")}

        with patch("application.services.prompt_helpers.collect_files") as mock_collect:
            # Mock file entries
            entry1 = Mock()
            entry1.path = workspace / "main.py"
            entry1.display_path = "main.py"
            entry1.content = "def main(): pass"

            entry2 = Mock()
            entry2.path = workspace / "utils.py"
            entry2.display_path = "utils.py"
            entry2.content = "def helper(): ..."

            mock_collect.return_value = [entry1, entry2]

            # Act - dung count_per_file_tokens tu prompt_helpers
            from application.services.prompt_helpers import count_per_file_tokens

            mock_tokenizer = Mock()
            mock_tokenizer.count_tokens = Mock(
                side_effect=lambda text: len(text.split())
            )
            result = count_per_file_tokens(
                file_paths=file_paths,
                workspace=workspace,
                use_relative_paths=True,
                dep_path_set=set(),
                tokenization_service=mock_tokenizer,
                codemap_paths=codemap_paths,
            )

            # Assert: main.py should have is_codemap=False, utils.py should have is_codemap=True
            assert len(result) == 2
            main_info = next(f for f in result if f.path == "main.py")
            utils_info = next(f for f in result if f.path == "utils.py")

            assert main_info.is_codemap is False
            assert utils_info.is_codemap is True

    def test_build_prompt_full_without_codemap_paths(self, service, workspace):
        """Test backward compatibility when codemap_paths is None."""
        # Arrange
        file_paths = [workspace / "main.py"]

        mock_gen = Mock(return_value="<files>mocked</files>")

        with patch.dict(
            "application.services.prompt_build_service._FORMAT_TO_GENERATOR",
            {"xml": mock_gen},
        ):
            # Act
            service.build_prompt_full(
                file_paths=file_paths,
                workspace=workspace,
                instructions="",
                output_format="xml",
                include_git_changes=False,
                use_relative_paths=True,
                codemap_paths=None,
            )

            # Assert: Should pass None to generator
            call_kwargs = mock_gen.call_args[1]
            assert call_kwargs["codemap_paths"] is None

    def test_build_prompt_legacy_api_passes_codemap_paths(self, service, workspace):
        """Test that legacy build_prompt() API passes codemap_paths through."""
        # Arrange
        file_paths = [workspace / "main.py"]
        codemap_paths = {str(workspace / "main.py")}

        with patch.object(service, "build_prompt_full") as mock_full:
            mock_result = Mock()
            mock_result.to_legacy_tuple.return_value = ("prompt", 100, {})
            mock_full.return_value = mock_result

            # Act
            service.build_prompt(
                file_paths=file_paths,
                workspace=workspace,
                instructions="",
                output_format="xml",
                include_git_changes=False,
                use_relative_paths=True,
                codemap_paths=codemap_paths,
            )

            # Assert: Should pass codemap_paths to build_prompt_full
            mock_full.assert_called_once()
            assert mock_full.call_args[1]["codemap_paths"] == codemap_paths

    def test_build_prompt_full_with_mixed_full_and_codemap_files(
        self, service, workspace
    ):
        """Test building prompt with mix of full content and codemap files."""
        # Arrange
        file_paths = [
            workspace / "main.py",
            workspace / "utils.py",
            workspace / "config.py",
        ]
        # Only utils.py and config.py are codemap
        codemap_paths = {str(workspace / "utils.py"), str(workspace / "config.py")}

        with (
            patch(
                "application.services.prompt_build_service.generate_file_contents_xml"
            ) as mock_gen,
            patch(
                "application.services.prompt_build_service.collect_files"
            ) as mock_collect,
        ):
            mock_gen.return_value = "<files>mixed content</files>"

            # Mock file entries for token counting
            entries = []
            for fp in file_paths:
                entry = Mock()
                entry.path = fp
                entry.display_path = fp.name
                entry.content = f"content of {fp.name}"
                entries.append(entry)
            mock_collect.return_value = entries

            # Act
            result = service.build_prompt_full(
                file_paths=file_paths,
                workspace=workspace,
                instructions="Test",
                output_format="xml",
                include_git_changes=False,
                use_relative_paths=True,
                codemap_paths=codemap_paths,
            )

            # Assert: Check FileTokenInfo has correct is_codemap flags
            assert len(result.files) == 3
            main_info = next(f for f in result.files if f.path == "main.py")
            utils_info = next(f for f in result.files if f.path == "utils.py")
            config_info = next(f for f in result.files if f.path == "config.py")

            assert main_info.is_codemap is False
            assert utils_info.is_codemap is True
            assert config_info.is_codemap is True
