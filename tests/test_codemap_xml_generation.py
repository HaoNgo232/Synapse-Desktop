"""
Unit tests for codemap XML generation in prompt_generator.py

Tests the _generate_codemap_xml() helper and generate_file_contents_xml() with codemap_paths.
"""

import pytest
from unittest.mock import patch, Mock
from domain.prompt.generator import generate_file_contents_xml, _generate_codemap_xml


class TestCodemapXMLGeneration:
    """Test suite for codemap XML generation."""

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create temporary workspace with test files."""
        # Arrange: Create Python file
        py_file = tmp_path / "test.py"
        py_file.write_text("def hello():\n    return 'world'\n")

        # Create JS file
        js_file = tmp_path / "test.js"
        js_file.write_text("function hello() { return 'world'; }\n")

        return tmp_path

    def test_generate_codemap_xml_with_supported_language(self, temp_workspace):
        """Test that codemap XML is generated for supported languages."""
        # Arrange
        py_file = temp_workspace / "test.py"
        paths = {str(py_file)}

        with (
            patch("domain.smart_context.smart_parse") as mock_parse,
            patch("domain.smart_context.is_supported") as mock_supported,
        ):
            mock_supported.return_value = True
            mock_parse.return_value = "def hello(): ..."

            # Act
            result = _generate_codemap_xml(
                paths,
                max_file_size=1024 * 1024,
                workspace_root=temp_workspace,
                use_relative_paths=True,
            )

            # Assert: Should contain codemap XML with context attribute
            assert '<file path="test.py" context="codemap">' in result
            assert "def hello(): ..." in result
            assert "</file>" in result

    def test_generate_codemap_xml_fallback_for_unsupported_language(
        self, temp_workspace
    ):
        """Test fallback to full content when language not supported."""
        # Arrange
        txt_file = temp_workspace / "test.txt"
        txt_file.write_text("plain text content")
        paths = {str(txt_file)}

        with patch("domain.smart_context.is_supported") as mock_supported:
            mock_supported.return_value = False

            # Act
            result = _generate_codemap_xml(
                paths,
                max_file_size=1024 * 1024,
                workspace_root=temp_workspace,
                use_relative_paths=True,
            )

            # Assert: Should use codemap-fallback context
            assert '<file path="test.txt" context="codemap-fallback">' in result
            assert "plain text content" in result

    def test_generate_codemap_xml_skips_binary_files(self, temp_workspace):
        """Test that binary files are skipped."""
        # Arrange
        bin_file = temp_workspace / "test.bin"
        bin_file.write_bytes(b"\x00\x01\x02\x03")
        paths = {str(bin_file)}

        with patch("domain.prompt.generator.is_binary_file") as mock_binary:
            mock_binary.return_value = True

            # Act
            result = _generate_codemap_xml(
                paths,
                max_file_size=1024 * 1024,
                workspace_root=temp_workspace,
                use_relative_paths=True,
            )

            # Assert: Should return empty string
            assert result == ""

    def test_generate_codemap_xml_skips_large_files(self, temp_workspace):
        """Test that files exceeding max_file_size are skipped."""
        # Arrange
        large_file = temp_workspace / "large.py"
        large_file.write_text("x" * 2000)
        paths = {str(large_file)}

        # Act: Set max_file_size to 1000 bytes
        result = _generate_codemap_xml(
            paths,
            max_file_size=1000,
            workspace_root=temp_workspace,
            use_relative_paths=True,
        )

        # Assert: Should skip the file
        assert result == ""

    def test_generate_file_contents_xml_splits_full_and_codemap(self, temp_workspace):
        """Test that files are correctly split into full content and codemap groups."""
        # Arrange
        file1 = temp_workspace / "full.py"
        file2 = temp_workspace / "codemap.py"
        file1.write_text("def full(): pass")
        file2.write_text("def codemap(): pass")

        selected_paths = {str(file1), str(file2)}
        codemap_paths = {str(file2)}

        with (
            patch("domain.prompt.generator.collect_files") as mock_collect,
            patch("domain.prompt.generator.format_files_xml") as mock_format_xml,
            patch("domain.prompt.generator._generate_codemap_xml") as mock_codemap,
        ):
            # Mock full content collection
            mock_entry = Mock()
            mock_entry.display_path = "full.py"
            mock_entry.content = "def full(): pass"
            mock_collect.return_value = [mock_entry]
            mock_format_xml.return_value = (
                '<file path="full.py">def full(): pass</file>'
            )

            # Mock codemap generation
            mock_codemap.return_value = (
                '<file path="codemap.py" context="codemap">def codemap(): ...</file>'
            )

            # Act
            result = generate_file_contents_xml(
                selected_paths,
                workspace_root=temp_workspace,
                use_relative_paths=True,
                codemap_paths=codemap_paths,
            )

            # Assert: Should contain both full and codemap sections
            assert '<file path="full.py">' in result
            assert '<file path="codemap.py" context="codemap">' in result

            # Verify collect_files called with only full paths
            mock_collect.assert_called_once()
            call_args = mock_collect.call_args[0][0]
            assert call_args == {str(file1)}

    def test_generate_file_contents_xml_without_codemap_paths(self, temp_workspace):
        """Test normal behavior when codemap_paths is None."""
        # Arrange
        file1 = temp_workspace / "test.py"
        file1.write_text("def test(): pass")
        selected_paths = {str(file1)}

        with (
            patch("domain.prompt.generator.collect_files") as mock_collect,
            patch("domain.prompt.generator.format_files_xml") as mock_format,
        ):
            mock_entry = Mock()
            mock_entry.display_path = "test.py"
            mock_entry.content = "def test(): pass"
            mock_collect.return_value = [mock_entry]
            mock_format.return_value = '<file path="test.py">def test(): pass</file>'

            # Act
            result = generate_file_contents_xml(
                selected_paths,
                workspace_root=temp_workspace,
                use_relative_paths=True,
                codemap_paths=None,
            )

            # Assert: Should use normal flow without splitting
            assert '<file path="test.py">' in result
            mock_collect.assert_called_once_with(
                selected_paths, 1024 * 1024, temp_workspace, True
            )

    def test_generate_file_contents_xml_empty_codemap_paths(self, temp_workspace):
        """Test that empty codemap_paths set is handled correctly."""
        # Arrange
        file1 = temp_workspace / "test.py"
        file1.write_text("def test(): pass")
        selected_paths = {str(file1)}
        codemap_paths = set()  # Empty set

        with (
            patch("domain.prompt.generator.collect_files") as mock_collect,
            patch("domain.prompt.generator.format_files_xml") as mock_format,
        ):
            mock_entry = Mock()
            mock_collect.return_value = [mock_entry]
            mock_format.return_value = "<file>content</file>"

            # Act
            result = generate_file_contents_xml(
                selected_paths,
                workspace_root=temp_workspace,
                codemap_paths=codemap_paths,
            )

            # Assert: Should treat all as full content
            assert result == "<file>content</file>"
