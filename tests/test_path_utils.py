"""
Tests cho core.prompting.path_utils.path_for_display().

Kiem tra cac truong hop:
- Absolute path (use_relative_paths=False)
- Relative path (use_relative_paths=True)
- Root path display (rel == ".")
- Path ngoai workspace (ValueError fallback)
- workspace_root la None
- Symlink paths
"""

from pathlib import Path


from core.prompting.path_utils import path_for_display


class TestPathForDisplay:
    """Test suite cho path_for_display - single source of truth."""

    def test_absolute_path_khi_use_relative_false(self, tmp_path: Path):
        """Khi use_relative_paths=False, tra ve absolute path khong doi."""
        file_path = tmp_path / "src" / "main.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

        result = path_for_display(file_path, tmp_path, use_relative_paths=False)
        assert result == str(file_path)

    def test_absolute_path_khi_workspace_none(self, tmp_path: Path):
        """Khi workspace_root la None, tra ve absolute path."""
        file_path = tmp_path / "src" / "main.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

        result = path_for_display(file_path, None, use_relative_paths=True)
        assert result == str(file_path)

    def test_relative_path_tu_workspace_root(self, tmp_path: Path):
        """Khi use_relative_paths=True, tra ve path tuong doi tu workspace."""
        file_path = tmp_path / "src" / "main.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

        result = path_for_display(file_path, tmp_path, use_relative_paths=True)
        assert result == "src/main.py"

    def test_nested_relative_path(self, tmp_path: Path):
        """Relative path nhieu cap (nested directories)."""
        file_path = tmp_path / "src" / "core" / "utils" / "helper.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

        result = path_for_display(file_path, tmp_path, use_relative_paths=True)
        assert result == "src/core/utils/helper.py"

    def test_root_path_hien_thi_ten_folder(self, tmp_path: Path):
        """Khi path == workspace_root (rel=="."), hien thi ten folder lowercase."""
        result = path_for_display(tmp_path, tmp_path, use_relative_paths=True)
        assert result == tmp_path.name.lower()

    def test_path_ngoai_workspace_fallback_absolute(self, tmp_path: Path):
        """Path khong nam trong workspace -> fallback ve absolute."""
        workspace = tmp_path / "project"
        workspace.mkdir()
        outside_file = tmp_path / "outside" / "file.txt"
        outside_file.parent.mkdir(parents=True, exist_ok=True)
        outside_file.touch()

        result = path_for_display(outside_file, workspace, use_relative_paths=True)
        assert result == str(outside_file)

    def test_file_tai_root_workspace(self, tmp_path: Path):
        """File ngay tai root cua workspace (rel = filename)."""
        file_path = tmp_path / "README.md"
        file_path.touch()

        result = path_for_display(file_path, tmp_path, use_relative_paths=True)
        assert result == "README.md"

    def test_path_la_directory(self, tmp_path: Path):
        """path_for_display cung hoat dong voi directories."""
        dir_path = tmp_path / "src" / "components"
        dir_path.mkdir(parents=True)

        result = path_for_display(dir_path, tmp_path, use_relative_paths=True)
        assert result == "src/components"

    def test_workspace_root_co_trailing_slash(self, tmp_path: Path):
        """Workspace root co trailing slash van hoat dong dung."""
        file_path = tmp_path / "main.py"
        file_path.touch()

        # Dung Path(str(tmp_path) + "/") de mo phong trailing slash
        workspace_with_slash = Path(str(tmp_path) + "/")
        result = path_for_display(
            file_path, workspace_with_slash, use_relative_paths=True
        )
        assert result == "main.py"

    def test_both_flags_false(self):
        """Ca hai flags deu False/None."""
        path = Path("/some/absolute/path.py")
        result = path_for_display(path, None, use_relative_paths=False)
        assert result == str(path)
