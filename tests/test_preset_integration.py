"""Integration test for Context Presets UI."""

import pytest
from PySide6.QtWidgets import QApplication

from presentation.views.context.context_view_qt import ContextViewQt


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace with files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file1.py").write_text("print('1')")
    (workspace / "file2.py").write_text("print('2')")
    return workspace


@pytest.fixture
def context_view(qapp, temp_workspace):
    """Create ContextViewQt instance."""
    view = ContextViewQt(
        get_workspace=lambda: temp_workspace,
    )
    view.on_workspace_changed(temp_workspace)
    yield view
    view.cleanup()


class TestPresetIntegration:
    """Integration tests for preset feature."""

    def test_preset_widget_exists(self, context_view):
        """Test that preset widget is created."""
        assert hasattr(context_view, "_preset_widget")
        assert context_view._preset_widget is not None

    def test_preset_controller_exists(self, context_view):
        """Test that preset controller is created."""
        assert hasattr(context_view, "_preset_controller")
        assert context_view._preset_controller is not None

    def test_create_and_load_preset_ui(self, context_view, temp_workspace):
        """Test creating and loading preset through UI."""
        # Select files
        paths = {
            str(temp_workspace / "file1.py"),
            str(temp_workspace / "file2.py"),
        }
        context_view.file_tree_widget.set_selected_paths(paths)

        # Set instructions
        context_view.set_instructions_text("Test instructions")

        # Create preset
        entry = context_view._preset_controller.create_preset("Test Preset")
        assert entry is not None
        assert entry.name == "Test Preset"

        # Clear selection
        context_view.file_tree_widget.set_selected_paths(set())
        context_view.set_instructions_text("")

        # Load preset
        success = context_view._preset_controller.load_preset(entry.preset_id)
        assert success is True

        # Verify selection restored
        selected = context_view.get_selected_paths()
        assert len(selected) == 2

        # Verify instructions restored
        assert context_view.get_instructions_text() == "Test instructions"

    def test_preset_widget_combo_updates(self, context_view, temp_workspace):
        """Test that combo box updates when presets change."""
        # Initial: placeholder + empty state message = 2 items
        context_view._preset_widget._combo.count()

        # Create preset
        paths = {str(temp_workspace / "file1.py")}
        context_view.file_tree_widget.set_selected_paths(paths)
        context_view._preset_controller.create_preset("New Preset")

        # After creating preset: placeholder + 1 preset = 2 items (empty state removed)
        # So count stays same but content changes
        assert context_view._preset_widget._combo.count() >= 2

        # Verify preset appears in combo
        preset_names = [
            context_view._preset_widget._combo.itemText(i)
            for i in range(context_view._preset_widget._combo.count())
        ]
        assert any("New Preset" in name for name in preset_names)

    def test_keyboard_shortcuts_registered(self, context_view):
        """Test that keyboard shortcuts are registered."""
        # Check that shortcut methods exist
        assert hasattr(context_view, "_quick_save_preset")
        assert hasattr(context_view, "_focus_preset_combo")

    def test_workspace_change_resets_presets(
        self, context_view, temp_workspace, tmp_path
    ):
        """Test that changing workspace resets preset state."""
        # Create preset in first workspace
        paths = {str(temp_workspace / "file1.py")}
        context_view.file_tree_widget.set_selected_paths(paths)
        context_view._preset_controller.create_preset("Test")

        assert len(context_view._preset_controller.list_presets()) == 1

        # Change workspace
        new_workspace = tmp_path / "new_workspace"
        new_workspace.mkdir()
        context_view.on_workspace_changed(new_workspace)

        # Presets should be empty for new workspace
        assert len(context_view._preset_controller.list_presets()) == 0
