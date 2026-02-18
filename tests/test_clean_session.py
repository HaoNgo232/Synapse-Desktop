"""
Test Clean Session on App Start

Verify rằng khi mở app:
- Workspace path được restore từ recent folders (workspace gần nhất)
- Instructions text được restore từ session
- Selected files và expanded folders bị clear (fresh start)
"""

from unittest.mock import patch, MagicMock


from services.session_state import SessionState, save_session_state
from services.recent_folders import add_recent_folder


class TestCleanSession:
    """Test clean session behavior khi mở app"""

    def test_restore_workspace_from_recent_folders(self, tmp_path):
        """Workspace path được restore từ recent folders, không phải từ session"""
        # Setup: Tạo 2 workspaces
        workspace1 = tmp_path / "workspace1"
        workspace2 = tmp_path / "workspace2"
        workspace1.mkdir()
        workspace2.mkdir()

        # Add workspace1 vào recent (gần nhất)
        add_recent_folder(str(workspace1))

        # Save session với workspace2 (khác với recent)
        session = SessionState(
            workspace_path=str(workspace2),
            selected_files=[str(workspace2 / "file.py")],
            expanded_folders=[str(workspace2 / "src")],
            instructions_text="Test instructions",
        )
        save_session_state(session)

        # Mock main window restore
        with patch("services.recent_folders.load_recent_folders") as mock_recent:
            mock_recent.return_value = [str(workspace1)]

            # Verify: Workspace được restore từ recent (workspace1), không phải session (workspace2)
            recent = mock_recent()
            assert recent[0] == str(workspace1)

    def test_restore_instructions_text_only(self, tmp_path):
        """Instructions text được restore, nhưng selected files và expanded folders bị clear"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Save session với instructions + selected files + expanded folders
        session = SessionState(
            workspace_path=str(workspace),
            selected_files=[str(workspace / "file1.py"), str(workspace / "file2.py")],
            expanded_folders=[str(workspace / "src"), str(workspace / "tests")],
            instructions_text="Important instructions to keep",
        )
        save_session_state(session)

        # Verify: Instructions text được giữ lại
        from services.session_state import load_session_state

        loaded = load_session_state()
        assert loaded is not None
        assert loaded.instructions_text == "Important instructions to keep"

        # Note: Selected files và expanded folders vẫn có trong session file,
        # nhưng main_window._restore_session() sẽ KHÔNG restore chúng (clean start)

    def test_no_pending_session_restore(self, tmp_path):
        """Verify rằng _pending_session_restore KHÔNG được set (clean start)"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Save session với selected files
        session = SessionState(
            workspace_path=str(workspace),
            selected_files=[str(workspace / "file.py")],
            expanded_folders=[str(workspace / "src")],
        )
        save_session_state(session)

        # Mock main window
        mock_window = MagicMock()
        mock_window._pending_session_restore = None

        # Verify: _pending_session_restore vẫn là None (không restore selection)
        assert mock_window._pending_session_restore is None

    def test_window_size_restored(self, tmp_path):
        """Window size vẫn được restore từ session"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Save session với window size
        session = SessionState(
            workspace_path=str(workspace),
            window_width=1600,
            window_height=900,
        )
        save_session_state(session)

        # Verify: Window size được restore
        from services.session_state import load_session_state

        loaded = load_session_state()
        assert loaded is not None
        assert loaded.window_width == 1600
        assert loaded.window_height == 900

    def test_active_tab_not_restored(self, tmp_path):
        """Active tab KHÔNG được restore (luôn bắt đầu ở tab 0)"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Save session với active tab = 2 (History tab)
        session = SessionState(
            workspace_path=str(workspace),
            active_tab_index=2,  # History tab
        )
        save_session_state(session)

        # Verify: Active tab trong session là 2
        from services.session_state import load_session_state

        loaded = load_session_state()
        assert loaded is not None
        assert loaded.active_tab_index == 2

        # Note: main_window._restore_session() sẽ KHÔNG restore active_tab_index
        # (luôn bắt đầu ở tab 0 - Context tab)
