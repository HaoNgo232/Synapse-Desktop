"""Tests for PresetController."""

import pytest
from pathlib import Path
from unittest.mock import Mock

from presentation.views.context.preset_controller import PresetController


class MockView:
    """Mock view implementing PresetViewProtocol."""

    def __init__(self, workspace: Path):
        self._workspace = workspace
        self._selected_paths = set()
        self._instructions = ""
        self._output_style = Mock(value="xml")
        self._status_messages = []

    def get_workspace(self) -> Path:
        return self._workspace

    def get_selected_paths(self) -> set:
        return self._selected_paths

    def get_instructions_text(self) -> str:
        return self._instructions

    def get_output_style(self) -> object:
        return self._output_style

    def set_selected_paths_from_preset(self, paths: set) -> None:
        self._selected_paths = paths

    def set_instructions_text(self, text: str) -> None:
        self._instructions = text

    def show_status(self, message: str, is_error: bool = False) -> None:
        self._status_messages.append((message, is_error))


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace with files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file1.py").write_text("print('1')")
    (workspace / "file2.py").write_text("print('2')")
    return workspace


@pytest.fixture
def mock_view(temp_workspace):
    """Create mock view."""
    return MockView(temp_workspace)


@pytest.fixture
def controller(mock_view, temp_workspace):
    """Create controller with mock view."""
    ctrl = PresetController(mock_view)
    ctrl.on_workspace_changed(temp_workspace)
    return ctrl


class TestPresetController:
    def test_create_preset(self, controller, mock_view, temp_workspace):
        """Test creating preset from current selection."""
        mock_view._selected_paths = {
            str(temp_workspace / "file1.py"),
            str(temp_workspace / "file2.py"),
        }
        mock_view._instructions = "Test task"

        entry = controller.create_preset("My Preset")

        assert entry is not None
        assert entry.name == "My Preset"
        assert len(entry.selected_paths) == 2
        assert entry.instructions == "Test task"
        assert controller.get_active_preset_id() == entry.preset_id

    def test_create_preset_no_selection(self, controller, mock_view):
        """Test creating preset with no files selected."""
        mock_view._selected_paths = set()

        entry = controller.create_preset("Empty")

        assert entry is None
        assert any("No files selected" in msg for msg, _ in mock_view._status_messages)

    def test_create_preset_empty_name(self, controller, mock_view, temp_workspace):
        """Test creating preset with empty name."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}

        entry = controller.create_preset("  ")

        assert entry is None
        assert any("cannot be empty" in msg for msg, _ in mock_view._status_messages)

    def test_load_preset(self, controller, mock_view, temp_workspace):
        """Test loading preset."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}
        entry = controller.create_preset("Test")

        # Clear selection
        mock_view._selected_paths = set()
        mock_view._instructions = ""

        # Load preset
        success = controller.load_preset(entry.preset_id)

        assert success is True
        assert len(mock_view._selected_paths) == 1
        assert str(temp_workspace / "file1.py") in mock_view._selected_paths

    def test_load_preset_with_instructions(self, controller, mock_view, temp_workspace):
        """Test loading preset restores instructions."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}
        mock_view._instructions = "Original instructions"
        entry = controller.create_preset("Test")

        mock_view._instructions = ""
        controller.load_preset(entry.preset_id)

        assert mock_view._instructions == "Original instructions"

    def test_load_preset_missing_files(self, controller, mock_view, temp_workspace):
        """Test loading preset with deleted files."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}
        entry = controller.create_preset("Test")

        # Delete file
        (temp_workspace / "file1.py").unlink()

        success = controller.load_preset(entry.preset_id)

        assert success is False
        assert any("no longer exist" in msg for msg, _ in mock_view._status_messages)

    def test_update_preset(self, controller, mock_view, temp_workspace):
        """Test updating preset."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}
        entry = controller.create_preset("Test")

        # Change selection
        mock_view._selected_paths = {
            str(temp_workspace / "file1.py"),
            str(temp_workspace / "file2.py"),
        }

        success = controller.update_preset(entry.preset_id)

        assert success is True

        # Reload and verify
        mock_view._selected_paths = set()
        controller.load_preset(entry.preset_id)
        assert len(mock_view._selected_paths) == 2

    def test_delete_preset(self, controller, mock_view, temp_workspace):
        """Test deleting preset."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}
        entry = controller.create_preset("Test")

        success = controller.delete_preset(entry.preset_id)

        assert success is True
        assert controller.get_active_preset_id() is None
        assert len(controller.list_presets()) == 0

    def test_rename_preset(self, controller, mock_view, temp_workspace):
        """Test renaming preset."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}
        entry = controller.create_preset("Old Name")

        success = controller.rename_preset(entry.preset_id, "New Name")

        assert success is True
        presets = controller.list_presets()
        assert presets[0].name == "New Name"

    def test_duplicate_preset(self, controller, mock_view, temp_workspace):
        """Test duplicating preset."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}
        mock_view._instructions = "Original task"
        entry = controller.create_preset("Original")

        duplicate = controller.duplicate_preset(entry.preset_id)

        assert duplicate is not None
        assert duplicate.name == "Original (Copy)"
        assert duplicate.instructions == "Original task"
        assert len(controller.list_presets()) == 2

    def test_is_selection_dirty(self, controller, mock_view, temp_workspace):
        """Test dirty state detection."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}
        controller.create_preset("Test")

        # No change
        assert controller.is_selection_dirty() is False

        # Change selection
        mock_view._selected_paths.add(str(temp_workspace / "file2.py"))
        assert controller.is_selection_dirty() is True

    def test_list_presets(self, controller, mock_view, temp_workspace):
        """Test listing presets."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}

        controller.create_preset("First")
        controller.create_preset("Second")

        presets = controller.list_presets()
        assert len(presets) == 2
        # Most recent first
        assert presets[0].name == "Second"

    def test_workspace_change_resets_state(
        self, controller, mock_view, temp_workspace, tmp_path
    ):
        """Test workspace change clears active preset."""
        mock_view._selected_paths = {str(temp_workspace / "file1.py")}
        controller.create_preset("Test")

        assert controller.get_active_preset_id() is not None

        # Change workspace
        new_workspace = tmp_path / "new"
        new_workspace.mkdir()
        controller.on_workspace_changed(new_workspace)

        assert controller.get_active_preset_id() is None
        assert len(controller.list_presets()) == 0
