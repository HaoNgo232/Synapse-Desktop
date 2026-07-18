"""
Test Ignore Selected functionality.

Tests:
1. Pattern format: relative path vs filename
2. Excluded patterns applied to scan
3. Ignored files don't appear in tree
"""

import tempfile
from pathlib import Path

from infrastructure.filesystem.file_utils import scan_directory_shallow
from infrastructure.filesystem.ignore_engine import IgnoreEngine
from application.services.workspace_config import (
    add_excluded_patterns,
    remove_excluded_patterns,
    get_excluded_patterns,
)
from infrastructure.persistence.settings_manager import save_settings, load_settings


class TestIgnoreSelectedPatternFormat:
    """Test pattern format for ignore selected."""

    def test_relative_path_pattern(self):
        """Pattern should be relative path, not just filename."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir).resolve()

            # Create structure
            (workspace / "src").mkdir()
            (workspace / "src" / "utils").mkdir()
            (workspace / "src" / "utils" / "helper.py").write_text("# helper")
            (workspace / "tests").mkdir()
            (workspace / "tests" / "helper.py").write_text("# test helper")

            # Simulate selecting src/utils/helper.py
            selected_path = workspace / "src" / "utils" / "helper.py"
            rel_path = selected_path.relative_to(workspace)

            # Pattern should be full relative path
            pattern = rel_path.as_posix()
            assert pattern == "src/utils/helper.py"
            assert pattern != "helper.py"  # ❌ Wrong format

    def test_pattern_matches_gitignore_style(self):
        """Pattern should work with gitignore-style matching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir).resolve()

            # Create files
            (workspace / "src").mkdir()
            (workspace / "src" / "app.py").write_text("# app")
            (workspace / "src" / "config.py").write_text("# config")
            (workspace / "tests").mkdir()
            (workspace / "tests" / "test_app.py").write_text("# test")

            # Add pattern
            patterns = ["src/config.py"]

            # Scan with pattern
            tree = scan_directory_shallow(
                workspace,
                depth=2,
                excluded_patterns=patterns,
                use_gitignore=False,
                use_default_ignores=False,
                ignore_engine=IgnoreEngine(),
            )

            # Collect all file paths
            def collect_files(item, files):
                if not item.is_dir:
                    files.append(item.path)
                for child in item.children:
                    collect_files(child, files)

            files = []
            collect_files(tree, files)

            # config.py should be excluded
            assert str(workspace / "src" / "app.py") in files
            assert str(workspace / "tests" / "test_app.py") in files
            assert str(workspace / "src" / "config.py") not in files


from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from typing import Any


class FakeSettingsService:
    def __init__(self):
        self._settings = AppSettings()
        raw = load_settings()
        self._settings.excluded_folders = raw.get("excluded_folders", "")

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: Any) -> None:
        if key == "excluded_folders":
            self._settings.excluded_folders = value
            raw = load_settings()
            raw[key] = value
            save_settings(raw)

    def add_instruction_history(self, instruction: str) -> None:
        pass


class TestIgnoreSelectedIntegration:
    """Test full ignore selected workflow."""

    def setup_method(self):
        """Clear settings before each test."""
        self._old_settings_service = DomainRegistry._settings_service
        self._fake_service = FakeSettingsService()
        DomainRegistry.register_settings_service(self._fake_service)

        settings = load_settings()
        settings["excluded_folders"] = ""
        save_settings(settings)
        self._fake_service._settings.excluded_folders = ""

    def teardown_method(self):
        """Clear settings after each test."""
        settings = load_settings()
        settings["excluded_folders"] = ""
        save_settings(settings)
        DomainRegistry._settings_service = self._old_settings_service

    def test_add_and_scan_with_exclusion(self):
        """Test adding pattern and scanning with exclusion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir).resolve()

            # Create structure
            (workspace / "src").mkdir()
            (workspace / "src" / "main.py").write_text("# main")
            (workspace / "src" / "secret.py").write_text("# secret")
            (workspace / "docs").mkdir()
            (workspace / "docs" / "README.md").write_text("# readme")

            # Add pattern to settings
            patterns = ["src/secret.py"]
            assert add_excluded_patterns(patterns)

            # Verify pattern saved
            saved = get_excluded_patterns()
            assert "src/secret.py" in saved

            # Scan with exclusion
            tree = scan_directory_shallow(
                workspace,
                depth=2,
                excluded_patterns=saved,
                use_gitignore=False,
                use_default_ignores=False,
                ignore_engine=IgnoreEngine(),
            )

            # Collect files
            def collect_files(item, files):
                if not item.is_dir:
                    files.append(Path(item.path).name)
                for child in item.children:
                    collect_files(child, files)

            files = []
            collect_files(tree, files)

            # Verify exclusion
            assert "main.py" in files
            assert "README.md" in files
            assert "secret.py" not in files

    def test_undo_ignore_removes_pattern(self):
        """Test undo removes pattern from settings."""
        # Add patterns
        patterns = ["src/temp.py", "build/output.js"]
        assert add_excluded_patterns(patterns)

        saved = get_excluded_patterns()
        assert "src/temp.py" in saved
        assert "build/output.js" in saved

        # Remove patterns
        assert remove_excluded_patterns(patterns)

        saved = get_excluded_patterns()
        assert "src/temp.py" not in saved
        assert "build/output.js" not in saved

    def test_multiple_files_same_name_different_paths(self):
        """Test ignoring one file doesn't affect same-named file in different path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir).resolve()

            # Create same filename in different paths
            (workspace / "frontend").mkdir()
            (workspace / "frontend" / "config.js").write_text("// frontend config")
            (workspace / "backend").mkdir()
            (workspace / "backend" / "config.js").write_text("// backend config")

            # Ignore only frontend/config.js
            patterns = ["frontend/config.js"]

            tree = scan_directory_shallow(
                workspace,
                depth=2,
                excluded_patterns=patterns,
                use_gitignore=False,
                use_default_ignores=False,
                ignore_engine=IgnoreEngine(),
            )

            def collect_paths(item, paths):
                if not item.is_dir:
                    paths.append(item.path)
                for child in item.children:
                    collect_paths(child, paths)

            paths = []
            collect_paths(tree, paths)

            # Only frontend/config.js should be excluded
            assert str(workspace / "backend" / "config.js") in paths
            assert str(workspace / "frontend" / "config.js") not in paths


class TestIgnoreSelectedEdgeCases:
    """Test edge cases."""

    def test_ignore_folder(self):
        """Test ignoring entire folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir).resolve()

            (workspace / "src").mkdir()
            (workspace / "src" / "app.py").write_text("# app")
            (workspace / "build").mkdir()
            (workspace / "build" / "output.js").write_text("// output")
            (workspace / "build" / "bundle.js").write_text("// bundle")

            # Ignore entire build folder
            patterns = ["build"]

            tree = scan_directory_shallow(
                workspace,
                depth=2,
                excluded_patterns=patterns,
                use_gitignore=False,
                use_default_ignores=False,
                ignore_engine=IgnoreEngine(),
            )

            def collect_names(item, names):
                names.append(item.label)
                for child in item.children:
                    collect_names(child, names)

            names = []
            collect_names(tree, names)

            # build folder and its contents should be excluded
            assert "src" in names
            assert "app.py" in names
            assert "build" not in names
            assert "output.js" not in names
            assert "bundle.js" not in names

    def test_ignore_nested_file(self):
        """Test ignoring deeply nested file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir).resolve()

            (workspace / "a").mkdir()
            (workspace / "a" / "b").mkdir()
            (workspace / "a" / "b" / "c").mkdir()
            (workspace / "a" / "b" / "c" / "deep.py").write_text("# deep")
            (workspace / "a" / "shallow.py").write_text("# shallow")

            patterns = ["a/b/c/deep.py"]

            tree = scan_directory_shallow(
                workspace,
                depth=4,
                excluded_patterns=patterns,
                use_gitignore=False,
                use_default_ignores=False,
                ignore_engine=IgnoreEngine(),
            )

            def collect_files(item, files):
                if not item.is_dir:
                    files.append(Path(item.path).name)
                for child in item.children:
                    collect_files(child, files)

            files = []
            collect_files(tree, files)

            assert "shallow.py" in files
            assert "deep.py" not in files
