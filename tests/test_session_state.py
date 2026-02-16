"""
Unit tests cho Session State Service
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch
import tempfile
import shutil

from services.session_state import (
    SessionState,
    save_session_state,
    load_session_state,
    clear_session_state,
    get_session_age_hours,
)


class TestSessionState:
    """Test SessionState dataclass"""

    def test_default_values(self):
        """Test default values"""
        state = SessionState()
        assert state.workspace_path is None
        assert state.selected_files == []
        assert state.expanded_folders == []
        assert state.instructions_text == ""
        assert state.active_tab_index == 0

    def test_with_values(self):
        """Test with custom values"""
        state = SessionState(
            workspace_path="/home/user/project",
            selected_files=["/home/user/project/main.py"],
            instructions_text="Fix the bug",
        )
        assert state.workspace_path == "/home/user/project"
        assert len(state.selected_files) == 1
        assert state.instructions_text == "Fix the bug"


class TestSaveLoadSession:
    """Test save and load session"""

    @pytest.fixture
    def temp_session_file(self):
        """Create temp directory for session file"""
        temp_dir = tempfile.mkdtemp()
        session_file = Path(temp_dir) / "session.json"
        yield session_file
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_save_and_load(self, temp_session_file):
        """Test save then load session"""
        with patch("services.session_state.SESSION_FILE", temp_session_file):
            # Create temp workspace
            workspace = temp_session_file.parent / "workspace"
            workspace.mkdir()
            test_file = workspace / "test.py"
            test_file.write_text("# test")

            state = SessionState(
                workspace_path=str(workspace),
                selected_files=[str(test_file)],
                instructions_text="Test instructions",
            )

            # Save
            assert save_session_state(state) is True

            # Load
            loaded = load_session_state()
            assert loaded is not None
            assert loaded.workspace_path == str(workspace)
            assert str(test_file) in loaded.selected_files
            assert loaded.instructions_text == "Test instructions"

    def test_load_nonexistent(self, temp_session_file):
        """Test load when file doesn't exist"""
        with patch("services.session_state.SESSION_FILE", temp_session_file):
            result = load_session_state()
            assert result is None

    def test_clear_session(self, temp_session_file):
        """Test clear session"""
        with patch("services.session_state.SESSION_FILE", temp_session_file):
            # Save first
            state = SessionState(instructions_text="test")
            save_session_state(state)
            assert temp_session_file.exists()

            # Clear
            assert clear_session_state() is True
            assert not temp_session_file.exists()

    def test_invalid_workspace_filtered(self, temp_session_file):
        """Test that invalid workspace is filtered out"""
        with patch("services.session_state.SESSION_FILE", temp_session_file):
            # Save with non-existent workspace
            data = {
                "workspace_path": "/nonexistent/path",
                "selected_files": ["/nonexistent/file.py"],
                "instructions_text": "test",
            }
            temp_session_file.parent.mkdir(parents=True, exist_ok=True)
            temp_session_file.write_text(json.dumps(data))

            # Load should filter out invalid paths
            loaded = load_session_state()
            assert loaded is not None
            assert loaded.workspace_path is None
            assert loaded.selected_files == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
