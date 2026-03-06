"""
Unit tests for DependencyResolver.get_related_files_with_depth()

Tests depth tracking logic for transitive dependencies.
"""

import pytest
from unittest.mock import patch
from application.services.dependency_resolver import DependencyResolver


class TestGetRelatedFilesWithDepth:
    """Test suite for depth-aware dependency resolution."""

    @pytest.fixture
    def resolver(self, tmp_path):
        """Create resolver with temp workspace."""
        # Arrange
        resolver = DependencyResolver(tmp_path)
        return resolver

    @pytest.fixture
    def mock_files(self, tmp_path):
        """Create mock file structure for testing."""
        # Arrange: Create test files
        (tmp_path / "main.py").write_text("import utils\nimport models")
        (tmp_path / "utils.py").write_text("import helpers")
        (tmp_path / "models.py").write_text("import db")
        (tmp_path / "helpers.py").write_text("# leaf")
        (tmp_path / "db.py").write_text("# leaf")
        return tmp_path

    def test_depth_1_returns_direct_imports_only(self, resolver, mock_files):
        """Test that depth=1 returns only direct dependencies with depth=1."""
        # Arrange
        main_file = mock_files / "main.py"
        resolver.build_file_index_from_disk(mock_files)

        with (
            patch.object(resolver, "_extract_imports") as mock_extract,
            patch.object(resolver, "_resolve_imports") as mock_resolve,
        ):
            # Mock: main.py imports utils.py and models.py
            mock_extract.return_value = {"utils", "models"}
            mock_resolve.return_value = {
                mock_files / "utils.py",
                mock_files / "models.py",
            }

            # Act
            result = resolver.get_related_files_with_depth(main_file, max_depth=1)

            # Assert: Both files should have depth=1
            assert len(result) == 2
            assert result[mock_files / "utils.py"] == 1
            assert result[mock_files / "models.py"] == 1

    def test_depth_2_includes_transitive_dependencies(self, resolver, mock_files):
        """Test that depth=2 includes transitive deps with correct depth levels."""
        # Arrange
        main_file = mock_files / "main.py"
        resolver.build_file_index_from_disk(mock_files)

        with (
            patch.object(resolver, "_extract_imports") as mock_extract,
            patch.object(resolver, "_resolve_imports") as mock_resolve,
        ):

            def extract_side_effect(lang, content, lang_name, source_file):
                if source_file == main_file:
                    return {"utils"}
                elif source_file == mock_files / "utils.py":
                    return {"helpers"}
                return set()

            def resolve_side_effect(imports, source_file, lang_name):
                if source_file == main_file:
                    return {mock_files / "utils.py"}
                elif source_file == mock_files / "utils.py":
                    return {mock_files / "helpers.py"}
                return set()

            mock_extract.side_effect = extract_side_effect
            mock_resolve.side_effect = resolve_side_effect

            # Act
            result = resolver.get_related_files_with_depth(main_file, max_depth=2)

            # Assert: utils.py at depth 1, helpers.py at depth 2
            assert result[mock_files / "utils.py"] == 1
            assert result[mock_files / "helpers.py"] == 2

    def test_depth_3_tracks_three_levels(self, resolver, mock_files):
        """Test that depth=3 correctly tracks three levels of dependencies."""
        # Arrange
        main_file = mock_files / "main.py"
        resolver.build_file_index_from_disk(mock_files)

        with (
            patch.object(resolver, "_extract_imports") as mock_extract,
            patch.object(resolver, "_resolve_imports") as mock_resolve,
        ):

            def extract_side_effect(lang, content, lang_name, source_file):
                mapping = {
                    main_file: {"utils"},
                    mock_files / "utils.py": {"helpers"},
                    mock_files / "helpers.py": {"db"},
                }
                return mapping.get(source_file, set())

            def resolve_side_effect(imports, source_file, lang_name):
                mapping = {
                    main_file: {mock_files / "utils.py"},
                    mock_files / "utils.py": {mock_files / "helpers.py"},
                    mock_files / "helpers.py": {mock_files / "db.py"},
                }
                return mapping.get(source_file, set())

            mock_extract.side_effect = extract_side_effect
            mock_resolve.side_effect = resolve_side_effect

            # Act
            result = resolver.get_related_files_with_depth(main_file, max_depth=3)

            # Assert: Verify all three depth levels
            assert result[mock_files / "utils.py"] == 1
            assert result[mock_files / "helpers.py"] == 2
            assert result[mock_files / "db.py"] == 3

    def test_keeps_minimum_depth_for_shared_dependencies(self, resolver, mock_files):
        """Test that shared dependencies keep the minimum (closest) depth."""
        # Arrange: main -> utils (depth 1), main -> models (depth 1)
        #          utils -> helpers (depth 2), models -> helpers (depth 2)
        #          helpers should be depth 2, not duplicated
        main_file = mock_files / "main.py"
        resolver.build_file_index_from_disk(mock_files)

        with (
            patch.object(resolver, "_extract_imports") as mock_extract,
            patch.object(resolver, "_resolve_imports") as mock_resolve,
        ):

            def extract_side_effect(lang, content, lang_name, source_file):
                mapping = {
                    main_file: {"utils", "models"},
                    mock_files / "utils.py": {"helpers"},
                    mock_files / "models.py": {"helpers"},
                }
                return mapping.get(source_file, set())

            def resolve_side_effect(imports, source_file, lang_name):
                if source_file == main_file:
                    return {mock_files / "utils.py", mock_files / "models.py"}
                elif source_file in [mock_files / "utils.py", mock_files / "models.py"]:
                    return {mock_files / "helpers.py"}
                return set()

            mock_extract.side_effect = extract_side_effect
            mock_resolve.side_effect = resolve_side_effect

            # Act
            result = resolver.get_related_files_with_depth(main_file, max_depth=2)

            # Assert: helpers.py should appear once with depth=2
            assert result[mock_files / "helpers.py"] == 2
            assert len([k for k, v in result.items() if k.name == "helpers.py"]) == 1

    def test_empty_result_for_nonexistent_file(self, resolver, tmp_path):
        """Test that nonexistent file returns empty dict."""
        # Arrange
        nonexistent = tmp_path / "nonexistent.py"

        # Act
        result = resolver.get_related_files_with_depth(nonexistent, max_depth=2)

        # Assert
        assert result == {}

    def test_prevents_infinite_loop_with_circular_imports(self, resolver, mock_files):
        """Test that circular imports don't cause infinite recursion."""
        # Arrange: a.py -> b.py -> a.py (circular)
        a_file = mock_files / "a.py"
        b_file = mock_files / "b.py"
        a_file.write_text("import b")
        b_file.write_text("import a")
        resolver.build_file_index_from_disk(mock_files)

        with (
            patch.object(resolver, "_extract_imports") as mock_extract,
            patch.object(resolver, "_resolve_imports") as mock_resolve,
        ):

            def extract_side_effect(lang, content, lang_name, source_file):
                if source_file == a_file:
                    return {"b"}
                elif source_file == b_file:
                    return {"a"}
                return set()

            def resolve_side_effect(imports, source_file, lang_name):
                if source_file == a_file:
                    return {b_file}
                elif source_file == b_file:
                    return {a_file}
                return set()

            mock_extract.side_effect = extract_side_effect
            mock_resolve.side_effect = resolve_side_effect

            # Act - should not hang or raise
            result = resolver.get_related_files_with_depth(a_file, max_depth=3)

            # Assert: Should handle circular import gracefully
            # b.py at depth 1, a.py appears at depth 2 (a->b->a) but visited set prevents further recursion
            assert b_file in result
            assert result[b_file] == 1
            # In circular case, a.py may appear at depth 2 - this is expected behavior
            if a_file in result:
                assert result[a_file] == 2  # Circular reference detected at depth 2
