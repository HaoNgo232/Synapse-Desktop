"""Tests cho ContextViewQt - initialization, instructions, format, buttons, slots.

Su dung context_view fixture tu conftest.py.
Covers: lines 43-382 cua context_view_qt.py
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from PySide6.QtCore import QObject


def test_context_view_initialization(context_view):
    """Kiem tra ContextViewQt khoi tao thanh cong."""
    view = context_view
    assert view.tree is None
    assert view._related_mode_active is False
    assert view._related_depth == 1
    assert view._is_loading is False


def test_context_view_default_services_injected(qtbot):
    """Kiem tra default services khi khong truyen (lines 87-96)."""
    from tests.ui.conftest import FakeFileTreeWidget, FakeTokenStatsPanel

    mock_app_settings = MagicMock()
    mock_app_settings.output_format = None

    with patch("views.context._ui_builder.FileTreeWidget", FakeFileTreeWidget), \
         patch("views.context._ui_builder.TokenStatsPanelQt", FakeTokenStatsPanel), \
         patch("views.context._ui_builder.load_app_settings", return_value=mock_app_settings), \
         patch("core.prompting.template_manager.list_templates", return_value=[]), \
         patch("views.context_view_qt.FileWatcher", return_value=MagicMock()), \
         patch("services.prompt_build_service.PromptBuildService") as mock_pb, \
         patch("services.prompt_build_service.QtClipboardService") as mock_cs:

        from views.context_view_qt import ContextViewQt
        view = ContextViewQt(
            get_workspace=lambda: Path("/fake/workspace"),
        )
        qtbot.addWidget(view)
        mock_pb.assert_called_once()
        mock_cs.assert_called_once()


def test_context_view_set_get_instructions(context_view):
    """Kiem tra set va get instructions text."""
    view = context_view
    view.set_instructions_text("Generate unit tests for this module")
    assert view.get_instructions_text() == "Generate unit tests for this module"

    view.set_instructions_text("")
    assert view.get_instructions_text() == ""


def test_context_view_format_change(context_view):
    """Kiem tra thay doi output format dropdown."""
    view = context_view
    assert hasattr(view, '_format_combo')
    if view._format_combo.count() > 1:
        view._format_combo.setCurrentIndex(1)
        assert view._format_combo.currentIndex() == 1


def test_context_view_selected_paths_empty(context_view):
    """Kiem tra get_selected_paths tra ve empty khi chua chon file."""
    view = context_view
    paths = view.get_selected_paths()
    assert len(paths) == 0 or paths == set()


def test_context_view_instructions_change_updates_word_count(context_view):
    """Kiem tra word count cap nhat khi instructions thay doi."""
    view = context_view
    view.set_instructions_text("Write comprehensive tests for the module")
    assert "words" in view._word_count_label.text()


def test_context_view_token_label_exists(context_view):
    """Kiem tra token count label ton tai va hien thi gia tri mac dinh."""
    view = context_view
    assert view._token_count_label is not None
    assert "0 tokens" in view._token_count_label.text()


def test_context_view_copy_buttons_exist(context_view):
    """Kiem tra tat ca copy buttons da duoc tao."""
    view = context_view
    assert hasattr(view, '_opx_btn')
    assert hasattr(view, '_copy_btn')
    assert hasattr(view, '_smart_btn')
    assert hasattr(view, '_diff_btn')
    assert hasattr(view, '_tree_map_btn')


def test_on_workspace_changed(context_view):
    """Kiem tra on_workspace_changed xu ly day du (lines 104-152)."""
    view = context_view
    view.file_tree_widget.load_tree = MagicMock()
    view._related_mode_active = True
    view._last_added_related_files = {"old.py"}

    mock_watcher = MagicMock()
    view._file_watcher = mock_watcher

    new_path = Path("/new/workspace")
    with patch("services.cache_registry.cache_registry") as mock_registry, \
         patch("core.logging_config.log_info"):
        # workspace path doesn't exist in test
        view.on_workspace_changed(new_path)

    mock_watcher.stop.assert_called_once()
    assert view._related_mode_active is False
    assert len(view._last_added_related_files) == 0
    mock_registry.invalidate_for_workspace.assert_called_once()
    view.file_tree_widget.load_tree.assert_called_once_with(new_path)


def test_on_workspace_changed_starts_watcher(context_view, tmp_path):
    """Kiem tra on_workspace_changed starts file watcher khi path exists (line 142-152)."""
    view = context_view
    view.file_tree_widget.load_tree = MagicMock()
    mock_watcher = MagicMock()
    view._file_watcher = mock_watcher

    with patch("services.cache_registry.cache_registry"), \
         patch("core.logging_config.log_info"):
        view.on_workspace_changed(tmp_path)

    mock_watcher.start.assert_called_once()


def test_restore_tree_state(context_view, tmp_path):
    """Kiem tra restore_tree_state voi files va folders (lines 154-164)."""
    view = context_view
    view.file_tree_widget.set_selected_paths = MagicMock()
    view.file_tree_widget.set_expanded_paths = MagicMock()

    # Create real files
    f1 = tmp_path / "a.py"
    f1.write_text("x")

    view.restore_tree_state(
        selected_files=[str(f1)],
        expanded_folders=[str(tmp_path)],
    )

    view.file_tree_widget.set_selected_paths.assert_called_once()
    view.file_tree_widget.set_expanded_paths.assert_called_once()


def test_restore_tree_state_empty(context_view):
    """Kiem tra restore_tree_state voi empty lists."""
    view = context_view
    view.file_tree_widget.set_selected_paths = MagicMock()
    view.file_tree_widget.set_expanded_paths = MagicMock()
    view.restore_tree_state([], [])
    view.file_tree_widget.set_selected_paths.assert_not_called()
    view.file_tree_widget.set_expanded_paths.assert_not_called()


def test_cleanup(context_view):
    """Kiem tra cleanup tai nguyen (lines 179-211)."""
    view = context_view
    view.file_tree_widget.cleanup = MagicMock()
    mock_watcher = MagicMock()
    view._file_watcher = mock_watcher

    # Add some stale workers
    mock_qobj = MagicMock(spec=QObject)
    view._stale_workers = [mock_qobj, "not_a_qobject"]

    with patch("components.toast_qt.ToastManager") as mock_toast_mgr:
        mock_instance = MagicMock()
        mock_toast_mgr.instance.return_value = mock_instance
        view.cleanup()

    mock_qobj.deleteLater.assert_called_once()
    assert view._stale_workers == []
    assert view._current_copy_worker is None
    assert view._file_watcher is None
    mock_watcher.stop.assert_called_once()
    view.file_tree_widget.cleanup.assert_called_once()


def test_cleanup_toast_exception(context_view):
    """Kiem tra cleanup xu ly exception khi ToastManager fail (line 203-205)."""
    view = context_view
    view.file_tree_widget.cleanup = MagicMock()
    view._file_watcher = None

    with patch("components.toast_qt.ToastManager") as mock_toast_mgr:
        mock_toast_mgr.instance.side_effect = RuntimeError("no app")
        view.cleanup()  # Should not raise


def test_on_selection_changed(context_view):
    """Kiem tra _on_selection_changed tang generation va update display (lines 215-224)."""
    view = context_view
    old_gen = view._token_generation
    view._related_mode_active = False
    view._on_selection_changed({"file1.py"})
    assert view._token_generation == old_gen + 1


def test_on_selection_changed_triggers_related(context_view):
    """Kiem tra _on_selection_changed triggers related resolution khi active (line 223-224)."""
    view = context_view
    view._related_mode_active = True
    view._resolving_related = False
    with patch.object(view, '_resolve_related_files') as mock_resolve:
        view._on_selection_changed({"file.py"})
        mock_resolve.assert_called_once()


def test_on_format_changed(context_view):
    """Kiem tra _on_format_changed cap nhat style va settings (lines 234-244)."""
    view = context_view
    with patch("views.context_view_qt.update_app_setting") as mock_update, \
         patch("views.context_view_qt.get_style_by_id") as mock_get_style:
        mock_get_style.return_value = MagicMock()
        view._format_combo.setCurrentIndex(0)
        # Trigger manually
        view._on_format_changed(0)


def test_on_format_changed_value_error(context_view):
    """Kiem tra _on_format_changed xu ly ValueError (line 243-244)."""
    view = context_view
    with patch("views.context_view_qt.get_style_by_id", side_effect=ValueError("bad")):
        view._on_format_changed(0)  # Should not raise


def test_on_template_selected(context_view):
    """Kiem tra _on_template_selected insert template (lines 246-267)."""
    view = context_view
    mock_action = MagicMock()
    mock_action.data.return_value = "test_template_id"

    with patch("core.prompting.template_manager.load_template", return_value="Template content"):
        view._on_template_selected(mock_action)

    assert "Template content" in view._instructions_field.toPlainText()


def test_on_template_selected_append_to_existing(context_view):
    """Kiem tra _on_template_selected append khi da co text (line 258-261)."""
    view = context_view
    view._instructions_field.setPlainText("Existing instructions")
    mock_action = MagicMock()
    mock_action.data.return_value = "test_template_id"

    with patch("core.prompting.template_manager.load_template", return_value="New template"):
        view._on_template_selected(mock_action)

    text = view._instructions_field.toPlainText()
    assert "Existing instructions" in text
    assert "New template" in text


def test_on_template_selected_error(context_view):
    """Kiem tra _on_template_selected xu ly error (line 266-267)."""
    view = context_view
    mock_action = MagicMock()
    mock_action.data.return_value = "bad_id"

    with patch("core.prompting.template_manager.load_template", side_effect=Exception("fail")):
        view._on_template_selected(mock_action)  # Should not raise


def test_populate_history_menu_empty(context_view):
    """Kiem tra _populate_history_menu khi history empty (lines 269-283)."""
    view = context_view
    mock_settings = MagicMock()
    mock_settings.instruction_history = []
    with patch("services.settings_manager.load_app_settings", return_value=mock_settings):
        view._populate_history_menu()

    # Menu should have "No history yet"
    actions = view._history_menu.actions()
    assert len(actions) == 1
    assert actions[0].isEnabled() is False


def test_populate_history_menu_with_entries(context_view):
    """Kiem tra _populate_history_menu voi entries (lines 285-291)."""
    view = context_view
    mock_settings = MagicMock()
    mock_settings.instruction_history = [
        "Short instruction",
        "A" * 100,  # Long instruction -> truncated label
    ]
    with patch("services.settings_manager.load_app_settings", return_value=mock_settings):
        view._populate_history_menu()

    actions = view._history_menu.actions()
    assert len(actions) == 2


def test_on_history_selected(context_view):
    """Kiem tra _on_history_selected sets text (lines 293-299)."""
    view = context_view
    mock_action = MagicMock()
    mock_action.data.return_value = "Previous instructions text"
    view._on_history_selected(mock_action)
    assert view._instructions_field.toPlainText() == "Previous instructions text"


def test_on_history_selected_no_data(context_view):
    """Kiem tra _on_history_selected khi action.data() la None."""
    view = context_view
    mock_action = MagicMock()
    mock_action.data.return_value = None
    view._on_history_selected(mock_action)


def test_on_model_changed(context_view):
    """Kiem tra _on_model_changed reinitialize encoder (lines 344-366)."""
    view = context_view
    mock_model = view.file_tree_widget.get_model()
    mock_model._token_cache = {}
    view.file_tree_widget._start_token_counting = MagicMock()

    with patch("services.encoder_registry.initialize_encoder") as mock_init:
        view._on_model_changed("claude-3")

    mock_init.assert_called_once()
    view.file_tree_widget._start_token_counting.assert_called_once()


def test_show_status_error(context_view):
    """Kiem tra _show_status voi is_error=True (lines 370-382)."""
    view = context_view
    with patch("components.toast_qt.toast_error") as mock_toast:
        view._show_status("Something failed", is_error=True)
        mock_toast.assert_called_once_with("Something failed")


def test_show_status_success(context_view):
    """Kiem tra _show_status voi is_error=False."""
    view = context_view
    with patch("components.toast_qt.toast_success") as mock_toast:
        view._show_status("Done!", is_error=False)
        mock_toast.assert_called_once_with("Done!")


def test_show_status_empty_message(context_view):
    """Kiem tra _show_status voi empty message (line 372-373)."""
    view = context_view
    with patch("components.toast_qt.toast_success") as mock_toast:
        view._show_status("")
        mock_toast.assert_not_called()
