"""
Tests cho mcp_server/core/workspace_manager.py

Kiem tra WorkspaceManager xu ly dung cac truong hop:
- Workspace hop le (sync va async)
- Workspace khong ton tai, khong phai directory
- Path traversal bi chan
- Session file duoc tao dung duong dan
- Auto-detect tu MCP Context roots
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from mcp_server.core.workspace_manager import WorkspaceManager


class TestWorkspaceManagerResolveSync:
    """Kiem tra WorkspaceManager.resolve_sync() (backward compat)."""

    def test_resolve_valid_workspace(self, tmp_path):
        """Workspace hop le tra ve Path object."""
        ws = WorkspaceManager.resolve_sync(str(tmp_path))
        assert isinstance(ws, Path)
        assert ws == tmp_path.resolve()

    def test_resolve_nonexistent_path(self):
        """Path khong ton tai -> ValueError."""
        with pytest.raises(ValueError, match="Workspace does not exist"):
            WorkspaceManager.resolve_sync("/this/path/does/not/exist/xyz")

    def test_resolve_file_not_directory(self, tmp_path):
        """Path la file, khong phai directory -> ValueError."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")

        with pytest.raises(ValueError, match="Workspace is not a directory"):
            WorkspaceManager.resolve_sync(str(file_path))

    def test_resolve_returns_absolute_path(self, tmp_path, monkeypatch):
        """Ket qua luon la absolute path (resolved)."""
        monkeypatch.chdir(tmp_path)
        ws = WorkspaceManager.resolve_sync(".")
        assert ws.is_absolute()
        assert ws == tmp_path.resolve()


class TestWorkspaceManagerResolveAsync:
    """Kiem tra WorkspaceManager.resolve() async voi workspace_path explicit."""

    @pytest.mark.asyncio
    async def test_resolve_with_explicit_path(self, tmp_path):
        """Khi workspace_path duoc cung cap, dung no."""
        ws = await WorkspaceManager.resolve(str(tmp_path))
        assert isinstance(ws, Path)
        assert ws == tmp_path.resolve()

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_path(self):
        """Path khong ton tai -> ValueError."""
        with pytest.raises(ValueError, match="Workspace does not exist"):
            await WorkspaceManager.resolve("/this/path/does/not/exist/xyz")

    @pytest.mark.asyncio
    async def test_resolve_file_not_directory(self, tmp_path):
        """Path la file -> ValueError."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")
        with pytest.raises(ValueError, match="Workspace is not a directory"):
            await WorkspaceManager.resolve(str(file_path))

    @pytest.mark.asyncio
    async def test_resolve_no_path_no_context_returns_cwd(self):
        """Khong co path va khong co context -> fallback CWD."""
        ws = await WorkspaceManager.resolve(None, None)
        assert ws == Path.cwd().resolve()


class TestWorkspaceManagerAutoDetect:
    """Kiem tra auto-detect workspace tu MCP Context roots."""

    @pytest.mark.asyncio
    async def test_auto_detect_from_context_roots(self, tmp_path):
        """Auto-detect workspace tu ctx.session.list_roots()."""
        # Mock Root object
        mock_root = MagicMock()
        mock_root.uri = f"file://{tmp_path}"

        # Mock ListRootsResult
        mock_roots_result = MagicMock()
        mock_roots_result.roots = [mock_root]

        # Mock session
        mock_session = MagicMock()
        mock_session.list_roots = AsyncMock(return_value=mock_roots_result)

        # Mock context
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        ws = await WorkspaceManager.resolve(None, mock_ctx)
        assert ws == tmp_path.resolve()

    @pytest.mark.asyncio
    async def test_auto_detect_multiple_roots_uses_first(self, tmp_path):
        """Khi co nhieu roots, dung root dau tien."""
        other_dir = tmp_path / "other"
        other_dir.mkdir()

        mock_root1 = MagicMock()
        mock_root1.uri = f"file://{tmp_path}"
        mock_root2 = MagicMock()
        mock_root2.uri = f"file://{other_dir}"

        mock_roots_result = MagicMock()
        mock_roots_result.roots = [mock_root1, mock_root2]

        mock_session = MagicMock()
        mock_session.list_roots = AsyncMock(return_value=mock_roots_result)

        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        ws = await WorkspaceManager.resolve(None, mock_ctx)
        assert ws == tmp_path.resolve()

    @pytest.mark.asyncio
    async def test_auto_detect_empty_roots_returns_cwd(self):
        """Empty roots list -> fallback CWD."""
        mock_roots_result = MagicMock()
        mock_roots_result.roots = []

        mock_session = MagicMock()
        mock_session.list_roots = AsyncMock(return_value=mock_roots_result)

        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        ws = await WorkspaceManager.resolve(None, mock_ctx)
        assert ws == Path.cwd().resolve()

    @pytest.mark.asyncio
    async def test_auto_detect_session_error_returns_cwd(self):
        """Khi list_roots() raise exception -> fallback CWD."""
        mock_session = MagicMock()
        mock_session.list_roots = AsyncMock(side_effect=Exception("Connection lost"))

        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        ws = await WorkspaceManager.resolve(None, mock_ctx)
        assert ws == Path.cwd().resolve()

    @pytest.mark.asyncio
    async def test_auto_detect_no_session_attribute_returns_cwd(self):
        """Context khong co session attribute -> fallback CWD."""
        mock_ctx = MagicMock(spec=[])  # No attributes

        ws = await WorkspaceManager.resolve(None, mock_ctx)
        assert ws == Path.cwd().resolve()

    @pytest.mark.asyncio
    async def test_explicit_path_overrides_context(self, tmp_path):
        """Khi co ca workspace_path va ctx, workspace_path thang."""
        other_dir = tmp_path / "other"
        other_dir.mkdir()

        mock_root = MagicMock()
        mock_root.uri = f"file://{other_dir}"
        mock_roots_result = MagicMock()
        mock_roots_result.roots = [mock_root]
        mock_session = MagicMock()
        mock_session.list_roots = AsyncMock(return_value=mock_roots_result)
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        # Explicit path should win
        ws = await WorkspaceManager.resolve(str(tmp_path), mock_ctx)
        assert ws == tmp_path.resolve()

    @pytest.mark.asyncio
    async def test_auto_detect_with_dict_root(self, tmp_path):
        """Root la dict thay vi object (edge case)."""
        mock_roots_result = MagicMock()
        mock_roots_result.roots = [{"uri": f"file://{tmp_path}"}]

        mock_session = MagicMock()
        mock_session.list_roots = AsyncMock(return_value=mock_roots_result)

        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        ws = await WorkspaceManager.resolve(None, mock_ctx)
        assert ws == tmp_path.resolve()

    @pytest.mark.asyncio
    async def test_auto_detect_nonexistent_root_path(self):
        """Root URI tro toi path khong ton tai -> ValueError."""
        mock_root = MagicMock()
        mock_root.uri = "file:///nonexistent/path/that/does/not/exist"

        mock_roots_result = MagicMock()
        mock_roots_result.roots = [mock_root]

        mock_session = MagicMock()
        mock_session.list_roots = AsyncMock(return_value=mock_roots_result)

        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        with pytest.raises(ValueError, match="Workspace does not exist"):
            await WorkspaceManager.resolve(None, mock_ctx)


class TestUriToPath:
    """Kiem tra WorkspaceManager._uri_to_path()."""

    def test_unix_path(self):
        assert (
            WorkspaceManager._uri_to_path("file:///home/user/project")
            == "/home/user/project"
        )

    def test_windows_path(self):
        result = WorkspaceManager._uri_to_path("file:///C:/Users/user/project")
        assert result == "C:/Users/user/project"

    def test_non_file_uri(self):
        assert WorkspaceManager._uri_to_path("https://example.com") is None

    def test_empty_uri(self):
        assert WorkspaceManager._uri_to_path("") is None

    def test_none_uri(self):
        assert WorkspaceManager._uri_to_path(None) is None  # type: ignore


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
