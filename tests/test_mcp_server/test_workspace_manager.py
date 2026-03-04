"""
Tests cho mcp_server/core/workspace_manager.py

Kiem tra WorkspaceManager xu ly dung cac truong hop:
- Workspace hop le
- Workspace khong ton tai, khong phai directory
- Path traversal bi chan
- Session file duoc tao dung duong dan
"""

import pytest
from pathlib import Path

from mcp_server.core.workspace_manager import WorkspaceManager


class TestWorkspaceManagerResolve:
    """Kiem tra WorkspaceManager.resolve() chuyen doi va validate workspace path."""

    def test_resolve_valid_workspace(self, tmp_path):
        """Workspace hop le tra ve Path object."""
        ws = WorkspaceManager.resolve(str(tmp_path))
        assert isinstance(ws, Path)
        assert ws == tmp_path.resolve()

    def test_resolve_nonexistent_path(self):
        """Path khong ton tai -> ValueError."""
        with pytest.raises(ValueError, match="Workspace does not exist"):
            WorkspaceManager.resolve("/this/path/does/not/exist/xyz")

    def test_resolve_file_not_directory(self, tmp_path):
        """Path la file, khong phai directory -> ValueError."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")

        with pytest.raises(ValueError, match="Workspace is not a directory"):
            WorkspaceManager.resolve(str(file_path))

    def test_resolve_returns_absolute_path(self, tmp_path, monkeypatch):
        """Ket qua luon la absolute path (resolved)."""
        monkeypatch.chdir(tmp_path)
        ws = WorkspaceManager.resolve(".")
        assert ws.is_absolute()
        assert ws == tmp_path.resolve()


class TestWorkspaceManagerValidateRelativePath:
    """Kiem tra validate_relative_path chan path traversal."""

    def test_valid_relative_path(self, tmp_path):
        """File nam trong workspace -> tra ve resolved path."""
        (tmp_path / "src").mkdir()
        test_file = tmp_path / "src" / "main.py"
        test_file.write_text("print('hello')")

        result = WorkspaceManager.validate_relative_path(tmp_path, "src/main.py")
        assert result == test_file.resolve()

    def test_path_traversal_blocked(self, tmp_path):
        """Path traversal (../../..) -> ValueError."""
        with pytest.raises(ValueError, match="outside workspace"):
            WorkspaceManager.validate_relative_path(tmp_path, "../../../etc/passwd")

    def test_nested_traversal_blocked(self, tmp_path):
        """Path traversal an trong subdir cung bi chan."""
        (tmp_path / "src").mkdir()
        with pytest.raises(ValueError, match="outside workspace"):
            WorkspaceManager.validate_relative_path(
                tmp_path, "src/../../../../../../etc/shadow"
            )


class TestWorkspaceManagerGetSessionFile:
    """Kiem tra get_session_file tao dung duong dan .synapse/selection.json."""

    def test_returns_correct_path(self, tmp_path):
        """Session file nam trong .synapse/ subfolder."""
        result = WorkspaceManager.get_session_file(tmp_path)
        assert result == tmp_path / ".synapse" / "selection.json"

    def test_creates_parent_directory(self, tmp_path):
        """Tu dong tao thu muc .synapse/ neu chua co."""
        synapse_dir = tmp_path / ".synapse"
        assert not synapse_dir.exists()

        WorkspaceManager.get_session_file(tmp_path)
        assert synapse_dir.exists()
        assert synapse_dir.is_dir()
