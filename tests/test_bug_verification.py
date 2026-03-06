"""
Test để verify các bug được report trong analysis.
"""

from pathlib import Path
from application.services.dependency_resolver import DependencyResolver


class TestBug1ShortestPathReexploration:
    """
    Bug #1: Thuật toán depth-tracking không re-explore khi tìm được đường ngắn hơn.

    Scenario:
    - max_depth = 3
    - A imports B (depth 1), B imports C (depth 2), C imports D (depth 3)
    - A imports C (depth 1) <- shorter path discovered

    Expected: D should be updated to depth 2 (via A->C->D)
    Actual (buggy): D stays at depth 3, children of D are missed
    """

    def test_shorter_path_updates_transitive_deps(self, tmp_path: Path):
        """Test that finding a shorter path re-explores transitive dependencies."""

        # Setup file structure
        a_py = tmp_path / "a.py"
        b_py = tmp_path / "b.py"
        c_py = tmp_path / "c.py"
        d_py = tmp_path / "d.py"
        e_py = tmp_path / "e.py"

        # A imports B and C (C is imported twice: via B and directly)
        a_py.write_text("import b\nimport c\n")

        # B imports C
        b_py.write_text("import c\n")

        # C imports D
        c_py.write_text("import d\n")

        # D imports E
        d_py.write_text("import e\n")

        # E is a leaf
        e_py.write_text("# leaf\n")

        resolver = DependencyResolver(tmp_path)
        resolver.build_file_index_from_disk(tmp_path)

        # Collect with max_depth=3
        # Expected paths:
        # A -> B (depth 1)
        # A -> C (depth 1, shorter than via B)
        # A -> C -> D (depth 2, should be updated from depth 3)
        # A -> C -> D -> E (depth 3, should be included)
        depths = resolver.get_related_files_with_depth(a_py, max_depth=3)

        # Verify all files are included
        result_paths = {p.name for p in depths.keys()}
        assert "b.py" in result_paths, "B should be at depth 1"
        assert "c.py" in result_paths, "C should be at depth 1"
        assert "d.py" in result_paths, "D should be at depth 2 (via A->C->D)"
        assert "e.py" in result_paths, "E should be at depth 3 (via A->C->D->E)"

        # Verify depths
        assert depths[b_py] == 1
        assert depths[c_py] == 1, "C should have depth 1 (direct import from A)"
        assert depths[d_py] == 2, "D should have depth 2 (via A->C->D, not A->B->C->D)"
        assert depths[e_py] == 3, "E should have depth 3 (via A->C->D->E)"


class TestBug2OSErrorBypassSizeCheck:
    """
    Bug #2: OSError trong stat() bypass file size check.
    """

    def test_oserror_skips_file(self, tmp_path: Path, monkeypatch):
        """Test that OSError during stat() causes file to be skipped."""
        from domain.prompt.generator import _generate_codemap_xml

        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\n")

        # Mock stat() to raise OSError
        original_stat = Path.stat

        def mock_stat(self):
            if self.name == "test.py":
                raise OSError("Permission denied")
            return original_stat(self)

        monkeypatch.setattr(Path, "stat", mock_stat)

        # Should skip the file instead of processing it
        result = _generate_codemap_xml(
            {str(test_file)},
            workspace_root=tmp_path,
            use_relative_paths=False,
            max_file_size=1024,
        )

        # File should NOT be in result (currently buggy: file IS in result)
        assert "test.py" not in result, "File with OSError should be skipped"


class TestBug3DoubleFileRead:
    """
    Bug #3: File được đọc 2 lần khi smart_parse thất bại.
    """

    def test_file_read_once_only(self, tmp_path: Path, monkeypatch):
        """Test that file is read only once even when smart_parse fails."""
        from domain.prompt.generator import _generate_codemap_xml

        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\n")

        read_count = {"count": 0}
        original_read_text = Path.read_text

        def mock_read_text(self, *args, **kwargs):
            if self.name == "test.py":
                read_count["count"] += 1
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", mock_read_text)

        # Mock smart_parse to return None (failure)
        def mock_smart_parse(*args, **kwargs):
            return None

        import core.smart_context

        monkeypatch.setattr(core.smart_context, "smart_parse", mock_smart_parse)

        _generate_codemap_xml(
            {str(test_file)},
            workspace_root=tmp_path,
            use_relative_paths=False,
            max_file_size=1024 * 1024,
        )

        # File should be read only ONCE (currently buggy: read TWICE)
        assert read_count["count"] == 1, (
            f"File should be read once, but was read {read_count['count']} times"
        )


class TestBug4PathFormatMismatch:
    """
    Bug #4: Silent failure khi path format không nhất quán.
    """

    def test_mixed_path_formats_handled(self, tmp_path: Path):
        """Test that mixed absolute/relative paths are normalized correctly."""
        from domain.prompt.generator import generate_file_contents_xml

        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\n")

        # Mix absolute and relative paths
        selected_paths = {str(test_file.absolute())}  # absolute
        codemap_paths = {"test.py"}  # relative

        result = generate_file_contents_xml(
            selected_paths=selected_paths,
            workspace_root=tmp_path,
            use_relative_paths=False,
            codemap_paths=codemap_paths,
        )

        # Should recognize test.py as codemap (currently buggy: treated as full content)
        assert (
            'context="codemap"' in result or 'context="codemap-fallback"' in result
        ), "File should be recognized as codemap despite path format mismatch"
