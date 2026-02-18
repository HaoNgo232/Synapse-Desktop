"""
Test Workspace Index - Unit tests cho services/workspace_index.py.

Verify:
1. build_search_index() - correct filtering, binary skip, pathspec respect
2. search_in_index() - case-insensitive, empty query, empty index
3. collect_files_from_disk() - binary skip, gitignore respect

NOTE: workspace_index.py dung lazy imports ben trong function body,
nen ta patch o module goc (core.ignore_engine, core.utils.file_utils, etc.)
thay vi patch o services.workspace_index.
"""

from unittest.mock import patch, MagicMock

from services.workspace_index import (
    build_search_index,
    search_in_index,
    collect_files_from_disk,
)


# =============================================================================
# Test search_in_index (pure function, khong can mock)
# =============================================================================
class TestSearchInIndex:
    """Test search execution tren flat index."""

    def test_empty_index_returns_empty(self):
        """Tim kiem tren index rong tra ve list rong."""
        result = search_in_index({}, "test")
        assert result == []

    def test_empty_query_returns_empty(self):
        """Query rong tra ve list rong."""
        index = {"main.py": ["/project/main.py"]}
        assert search_in_index(index, "") == []
        assert search_in_index(index, "   ") == []
        assert search_in_index(index, None) == []

    def test_exact_filename_match(self):
        """Tim kiem chinh xac filename."""
        index = {
            "main.py": ["/project/main.py"],
            "utils.py": ["/project/utils.py"],
        }
        result = search_in_index(index, "main.py")
        assert result == ["/project/main.py"]

    def test_substring_match(self):
        """Tim kiem substring trong filename."""
        index = {
            "main.py": ["/project/main.py"],
            "main_test.py": ["/project/main_test.py"],
            "utils.py": ["/project/utils.py"],
        }
        result = search_in_index(index, "main")
        assert "/project/main.py" in result
        assert "/project/main_test.py" in result
        assert "/project/utils.py" not in result

    def test_case_insensitive(self):
        """Tim kiem KHONG phan biet hoa thuong."""
        index = {
            "readme.md": ["/project/README.md"],
        }
        result = search_in_index(index, "README")
        assert result == ["/project/README.md"]

    def test_multiple_files_same_name(self):
        """Nhieu files cung ten o cac folder khac nhau."""
        index = {
            "config.json": [
                "/project/a/config.json",
                "/project/b/config.json",
            ],
        }
        result = search_in_index(index, "config")
        assert len(result) == 2
        # Ket qua phai sorted
        assert result == sorted(result)

    def test_results_sorted(self):
        """Ket qua tra ve da duoc sort."""
        index = {
            "z_file.py": ["/z/z_file.py"],
            "a_file.py": ["/a/a_file.py"],
            "m_file.py": ["/m/m_file.py"],
        }
        result = search_in_index(index, "file")
        assert result == sorted(result)

    def test_no_match_returns_empty(self):
        """Khong co ket qua matching tra ve list rong."""
        index = {
            "main.py": ["/project/main.py"],
        }
        result = search_in_index(index, "nonexistent")
        assert result == []


# =============================================================================
# Test build_search_index (can mock filesystem)
# =============================================================================
class TestBuildSearchIndex:
    """Test search index building tu workspace."""

    def test_basic_index_building(self, tmp_path):
        """Build index tu folder co files."""
        # Tao files
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("# utils")
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "app.py").write_text("# app")

        mock_spec = MagicMock()
        mock_spec.match_file.return_value = False

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.utils.file_utils.is_binary_file", return_value=False),
            patch("core.utils.file_utils.is_system_path", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
        ):
            index = build_search_index(tmp_path)

        assert "main.py" in index
        assert "utils.py" in index
        assert "app.py" in index
        assert len(index["main.py"]) == 1
        assert str(tmp_path / "main.py") in index["main.py"]

    def test_binary_files_skipped(self, tmp_path):
        """Binary files KHONG duoc index."""
        (tmp_path / "code.py").write_text("# code")
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")

        def mock_is_binary(path):
            return path.suffix == ".png"

        mock_spec = MagicMock()
        mock_spec.match_file.return_value = False

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.utils.file_utils.is_binary_file", side_effect=mock_is_binary),
            patch("core.utils.file_utils.is_system_path", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
        ):
            index = build_search_index(tmp_path)

        assert "code.py" in index
        assert "image.png" not in index

    def test_ignored_files_skipped(self, tmp_path):
        """Files matching pathspec bi bo qua."""
        (tmp_path / "code.py").write_text("# code")
        (tmp_path / "secret.env").write_text("KEY=val")

        def mock_match(rel_path):
            return rel_path.endswith(".env")

        mock_spec = MagicMock()
        mock_spec.match_file.side_effect = mock_match

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.utils.file_utils.is_binary_file", return_value=False),
            patch("core.utils.file_utils.is_system_path", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
        ):
            index = build_search_index(tmp_path)

        assert "code.py" in index
        assert "secret.env" not in index

    def test_generation_check_cancels(self, tmp_path):
        """Generation check stale tra ve index rong."""
        (tmp_path / "file.py").write_text("# code")

        mock_spec = MagicMock()
        mock_spec.match_file.return_value = False

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.utils.file_utils.is_binary_file", return_value=False),
            patch("core.utils.file_utils.is_system_path", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
        ):
            # generation_check tra ve False -> cancel ngay
            index = build_search_index(tmp_path, generation_check=lambda: False)

        assert index == {}

    def test_empty_workspace(self, tmp_path):
        """Workspace rong tra ve index rong."""
        mock_spec = MagicMock()
        mock_spec.match_file.return_value = False

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
        ):
            index = build_search_index(tmp_path)

        assert index == {}


# =============================================================================
# Test collect_files_from_disk (can mock filesystem)
# =============================================================================
class TestCollectFilesFromDisk:
    """Test filesystem scanning cho unloaded folders."""

    def test_basic_file_collection(self, tmp_path):
        """Collect tat ca files tu folder."""
        (tmp_path / "a.py").write_text("# a")
        (tmp_path / "b.py").write_text("# b")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.py").write_text("# c")

        mock_spec = MagicMock()
        mock_spec.match_file.return_value = False

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.utils.file_utils.is_binary_file", return_value=False),
            patch("core.utils.file_utils.is_system_path", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
        ):
            result = collect_files_from_disk(tmp_path)

        assert len(result) == 3
        paths = set(result)
        assert str(tmp_path / "a.py") in paths
        assert str(tmp_path / "b.py") in paths
        assert str(sub / "c.py") in paths

    def test_binary_files_excluded(self, tmp_path):
        """Binary files bi loai bo."""
        (tmp_path / "code.py").write_text("# code")
        (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0")

        def mock_is_binary(path):
            return path.suffix in (".jpg", ".png")

        mock_spec = MagicMock()
        mock_spec.match_file.return_value = False

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.utils.file_utils.is_binary_file", side_effect=mock_is_binary),
            patch("core.utils.file_utils.is_system_path", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
        ):
            result = collect_files_from_disk(tmp_path)

        assert len(result) == 1
        assert str(tmp_path / "code.py") in result

    def test_no_duplicates(self, tmp_path):
        """Ket qua khong co duplicates."""
        (tmp_path / "file.py").write_text("# code")

        mock_spec = MagicMock()
        mock_spec.match_file.return_value = False

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.utils.file_utils.is_binary_file", return_value=False),
            patch("core.utils.file_utils.is_system_path", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
        ):
            result = collect_files_from_disk(tmp_path)

        # Khong co file trung lap
        assert len(result) == len(set(result))

    def test_permission_error_handled(self, tmp_path):
        """PermissionError khong crash, tra ve ket qua rong."""
        mock_spec = MagicMock()
        mock_spec.match_file.return_value = False

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
            patch("os.walk", side_effect=PermissionError("denied")),
        ):
            result = collect_files_from_disk(tmp_path)

        assert result == []

    def test_empty_folder(self, tmp_path):
        """Folder rong tra ve list rong."""
        mock_spec = MagicMock()
        mock_spec.match_file.return_value = False

        with (
            patch("core.ignore_engine.find_git_root", return_value=tmp_path),
            patch("services.workspace_config.get_excluded_patterns", return_value=[]),
            patch("services.workspace_config.get_use_gitignore", return_value=False),
            patch("core.ignore_engine.build_pathspec", return_value=mock_spec),
        ):
            result = collect_files_from_disk(tmp_path)

        assert result == []
