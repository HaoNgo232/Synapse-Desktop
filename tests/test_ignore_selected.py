"""
Test Ignore Selected functionality.

Tests:
1. Pattern format: relative path vs filename
2. Excluded patterns applied to scan
3. Ignored files don't appear in tree
"""

import tempfile
import shutil
from pathlib import Path

from core.utils.file_utils import scan_directory_shallow
from views.settings_view_qt import (
    add_excluded_patterns, 
    remove_excluded_patterns,
    get_excluded_patterns,
    save_settings,
    load_settings,
)


class TestIgnoreSelectedPatternFormat:
    """Test pattern format for ignore selected."""
    
    def test_relative_path_pattern(self):
        """Pattern should be relative path, not just filename."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
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
            pattern = str(rel_path)
            assert pattern == "src/utils/helper.py"
            assert pattern != "helper.py"  # ❌ Wrong format
    
    def test_pattern_matches_gitignore_style(self):
        """Pattern should work with gitignore-style matching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
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


class TestIgnoreSelectedIntegration:
    """Test full ignore selected workflow."""
    
    def setup_method(self):
        """Clear settings before each test."""
        settings = load_settings()
        settings["excluded_folders"] = ""
        save_settings(settings)
    
    def teardown_method(self):
        """Clear settings after each test."""
        settings = load_settings()
        settings["excluded_folders"] = ""
        save_settings(settings)
    
    def test_add_and_scan_with_exclusion(self):
        """Test adding pattern and scanning with exclusion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
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
            workspace = Path(tmpdir)
            
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
            workspace = Path(tmpdir)
            
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
            workspace = Path(tmpdir)
            
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
