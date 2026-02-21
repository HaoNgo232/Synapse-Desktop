"""Tests cho SettingsViewQt - load, toggle, save, reset, export, import, presets.

Covers: lines 434-862 cua settings_view_qt.py
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QMessageBox

from views.settings_view_qt import SettingsViewQt


@pytest.fixture
def mock_settings():
    """Mock settings data cho fixture."""
    return {
        "excluded_folders": "node_modules\n.git",
        "rule_file_names": [".cursorrules"],
        "use_gitignore": True,
        "enable_security_check": False,
        "include_git_changes": True,
        "use_relative_paths": False,
    }


@pytest.fixture
def settings_view(qtbot, mock_settings):
    """Tao SettingsViewQt voi mock settings."""
    with patch("views.settings_view_qt.load_settings", return_value=mock_settings), \
         patch("views.settings_view_qt.get_excluded_patterns", return_value=["node_modules", ".git"]):
        view = SettingsViewQt()
        qtbot.addWidget(view)
    return view


def test_settings_view_initial_load(settings_view):
    """Kiem tra Settings load dung gia tri tu mock settings."""
    view = settings_view
    assert view._gitignore_toggle.isChecked() is True
    assert view._security_toggle.isChecked() is False
    assert view._git_toggle.isChecked() is True
    assert view._relative_toggle.isChecked() is False
    assert view._tag_chips.get_patterns() == ["node_modules", ".git"]
    assert view._rule_chips.get_patterns() == [".cursorrules"]


def test_settings_view_initial_load_invalid_rules(qtbot):
    """Kiem tra Settings voi rule_file_names khong phai list (line 433-434)."""
    settings = {
        "excluded_folders": "",
        "rule_file_names": "not_a_list",
        "use_gitignore": True,
        "enable_security_check": True,
        "include_git_changes": True,
        "use_relative_paths": True,
    }
    with patch("views.settings_view_qt.load_settings", return_value=settings), \
         patch("views.settings_view_qt.get_excluded_patterns", return_value=[]):
        view = SettingsViewQt()
        qtbot.addWidget(view)
    assert view._rule_chips.get_patterns() == []


def test_settings_view_toggle_change(settings_view):
    """Kiem tra toggle thay doi trigger save logic."""
    view = settings_view
    view._gitignore_toggle.setChecked(False)

    with patch("views.settings_view_qt.save_settings", return_value=True) as mock_save:
        view._save_settings()
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert saved_data["use_gitignore"] is False


def test_settings_view_reset_defaults(settings_view):
    """Kiem tra Reset All to Defaults ap dung dung gia tri mac dinh."""
    view = settings_view
    with patch("views.settings_view_qt.save_settings", return_value=True), \
         patch("views.settings_view_qt.QMessageBox.warning",
               return_value=QMessageBox.StandardButton.Yes), \
         patch("views.settings_view_qt.toast_success"):
        view._reset_settings()
        assert view._gitignore_toggle.isChecked() is True
        assert view._security_toggle.isChecked() is True


def test_settings_view_reset_cancelled(settings_view):
    """Kiem tra Reset bi cancel (line 706-707)."""
    view = settings_view
    with patch("views.settings_view_qt.QMessageBox.warning",
               return_value=QMessageBox.StandardButton.Cancel):
        view._security_toggle.setChecked(False)
        view._reset_settings()
        # Toggle should remain unchanged
        assert view._security_toggle.isChecked() is False


def test_save_settings_success(settings_view):
    """Kiem tra _save_settings thanh cong (line 661-678)."""
    view = settings_view
    view.on_settings_changed = MagicMock()

    with patch("views.settings_view_qt.save_settings", return_value=True) as mock_save:
        view._save_settings()
        mock_save.assert_called_once()
        view.on_settings_changed.assert_called_once()
        assert view._has_unsaved is False


def test_save_settings_failure(settings_view):
    """Kiem tra _save_settings that bai (line 682-687)."""
    view = settings_view
    with patch("views.settings_view_qt.save_settings", return_value=False), \
         patch("views.settings_view_qt.toast_error") as mock_error:
        view._save_settings()
        mock_error.assert_called_once_with("Error saving settings")


def test_mark_changed(settings_view):
    """Kiem tra _mark_changed trigger debounce timer (line 632-640)."""
    view = settings_view
    view._mark_changed()
    assert view._has_unsaved is True
    assert "Auto-saving" in view._auto_save_indicator.text()


def test_trigger_auto_save(settings_view):
    """Kiem tra _trigger_auto_save goi _mark_changed (line 689-691)."""
    view = settings_view
    view._trigger_auto_save()
    assert view._has_unsaved is True


def test_reload_excluded_from_settings(settings_view):
    """Kiem tra _reload_excluded_from_settings (line 622-625)."""
    view = settings_view
    with patch("views.settings_view_qt.get_excluded_patterns",
               return_value=["new_pattern"]):
        view._reload_excluded_from_settings()
    assert view._tag_chips.get_patterns() == ["new_pattern"]


def test_on_patterns_changed(settings_view):
    """Kiem tra _on_patterns_changed triggers mark_changed (line 628-630)."""
    view = settings_view
    view._on_patterns_changed(["a", "b"])
    assert view._has_unsaved is True


def test_load_preset(settings_view):
    """Kiem tra _load_preset merge patterns (line 735-758)."""
    view = settings_view
    # Get first available preset name
    with patch("views.settings_view_qt.save_settings", return_value=True), \
         patch("views.settings_view_qt.toast_success"):
        from views.settings_view_qt import PRESET_PROFILES
        if PRESET_PROFILES:
            first_preset = next(iter(PRESET_PROFILES))
            view._load_preset(first_preset)


def test_load_preset_select_placeholder(settings_view):
    """Kiem tra _load_preset voi placeholder (line 736-737)."""
    view = settings_view
    view._load_preset("Select profile...")
    # Should do nothing


def test_load_preset_unknown(settings_view):
    """Kiem tra _load_preset voi unknown name."""
    view = settings_view
    view._load_preset("NonexistentPreset")
    # Should do nothing


def test_clear_session_confirmed(settings_view):
    """Kiem tra _clear_session khi confirmed (line 760-775)."""
    view = settings_view
    with patch("views.settings_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes), \
         patch("views.settings_view_qt.clear_session_state", return_value=True), \
         patch("views.settings_view_qt.toast_success") as mock_toast:
        view._clear_session()
        mock_toast.assert_called_with("Session cleared. Restart to see effect.")


def test_clear_session_failed(settings_view):
    """Kiem tra _clear_session khi clear fail (line 774-775)."""
    view = settings_view
    with patch("views.settings_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes), \
         patch("views.settings_view_qt.clear_session_state", return_value=False), \
         patch("views.settings_view_qt.toast_error") as mock_error:
        view._clear_session()
        mock_error.assert_called_with("Failed to clear session")


def test_clear_session_cancelled(settings_view):
    """Kiem tra _clear_session khi cancelled (line 769-770)."""
    view = settings_view
    with patch("views.settings_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Cancel), \
         patch("views.settings_view_qt.clear_session_state") as mock_clear:
        view._clear_session()
        mock_clear.assert_not_called()


def test_export_settings(settings_view):
    """Kiem tra _export_settings copy JSON to clipboard (line 778-793)."""
    view = settings_view
    with patch("views.settings_view_qt.copy_to_clipboard",
               return_value=(True, None)) as mock_copy, \
         patch("views.settings_view_qt.toast_success") as mock_toast:
        view._export_settings()
        mock_copy.assert_called_once()
        exported = json.loads(mock_copy.call_args[0][0])
        assert "excluded_folders" in exported
        assert "export_version" in exported
        assert "rule_file_names" in exported
        mock_toast.assert_called_with("Settings exported to clipboard")


def test_export_settings_failed(settings_view):
    """Kiem tra _export_settings khi clipboard fail."""
    view = settings_view
    with patch("views.settings_view_qt.copy_to_clipboard",
               return_value=(False, None)), \
         patch("views.settings_view_qt.toast_error") as mock_error:
        view._export_settings()
        mock_error.assert_called_with("Export failed")


def test_import_settings(settings_view):
    """Kiem tra _import_settings tu clipboard (line 796-844)."""
    view = settings_view
    import_data = json.dumps({
        "excluded_folders": "dist\nbuild",
        "rule_file_names": [".agentrules"],
        "use_gitignore": False,
        "include_git_changes": False,
        "use_relative_paths": True,
        "enable_security_check": False,
    })
    with patch("views.settings_view_qt.get_clipboard_text",
               return_value=(True, import_data)), \
         patch("views.settings_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes), \
         patch("views.settings_view_qt.save_settings", return_value=True), \
         patch("views.settings_view_qt.toast_success") as mock_toast:
        view._import_settings()
        assert view._gitignore_toggle.isChecked() is False
        assert view._git_toggle.isChecked() is False
        mock_toast.assert_called_with("Settings imported from clipboard.")


def test_import_settings_empty_clipboard(settings_view):
    """Kiem tra _import_settings khi clipboard empty (line 798-800)."""
    view = settings_view
    with patch("views.settings_view_qt.get_clipboard_text",
               return_value=(False, "")), \
         patch("views.settings_view_qt.toast_error") as mock_error:
        view._import_settings()
        mock_error.assert_called_with("Clipboard is empty")


def test_import_settings_invalid_json(settings_view):
    """Kiem tra _import_settings voi JSON khong hop le (line 807-809)."""
    view = settings_view
    with patch("views.settings_view_qt.get_clipboard_text",
               return_value=(True, "not json")), \
         patch("views.settings_view_qt.toast_error") as mock_error:
        view._import_settings()
        mock_error.assert_called_with("Invalid JSON in clipboard")


def test_import_settings_missing_key(settings_view):
    """Kiem tra _import_settings voi missing excluded_folders (line 804-806)."""
    view = settings_view
    with patch("views.settings_view_qt.get_clipboard_text",
               return_value=(True, '{"some_key": "value"}')), \
         patch("views.settings_view_qt.toast_error") as mock_error:
        view._import_settings()
        mock_error.assert_called_with("Invalid settings format")


def test_import_settings_cancelled(settings_view):
    """Kiem tra _import_settings bi cancel (line 818-819)."""
    view = settings_view
    import_data = json.dumps({"excluded_folders": "dist"})
    with patch("views.settings_view_qt.get_clipboard_text",
               return_value=(True, import_data)), \
         patch("views.settings_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Cancel), \
         patch("views.settings_view_qt.save_settings") as mock_save:
        view._import_settings()
        mock_save.assert_not_called()


def test_import_settings_non_list_rules(settings_view):
    """Kiem tra _import_settings voi rule_file_names khong phai list (line 833-834)."""
    view = settings_view
    import_data = json.dumps({
        "excluded_folders": "dist",
        "rule_file_names": "not_a_list",
    })
    with patch("views.settings_view_qt.get_clipboard_text",
               return_value=(True, import_data)), \
         patch("views.settings_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes), \
         patch("views.settings_view_qt.save_settings", return_value=True), \
         patch("views.settings_view_qt.toast_success"):
        view._import_settings()
        assert view._rule_chips.get_patterns() == []


def test_has_unsaved_changes(settings_view):
    """Kiem tra has_unsaved_changes (line 848-849)."""
    view = settings_view
    assert view.has_unsaved_changes() is False
    view._has_unsaved = True
    assert view.has_unsaved_changes() is True


def test_show_status_error(settings_view):
    """Kiem tra _show_status voi is_error (line 853-861)."""
    view = settings_view
    with patch("views.settings_view_qt.toast_error") as mock_error:
        view._show_status("Error!", is_error=True)
        mock_error.assert_called_with("Error!")


def test_show_status_empty(settings_view):
    """Kiem tra _show_status voi empty (line 855-856)."""
    view = settings_view
    with patch("views.settings_view_qt.toast_success") as mock_success:
        view._show_status("")
        mock_success.assert_not_called()


def test_reset_save_btn(settings_view):
    """Kiem tra _reset_save_btn (deprecated, line 693-695)."""
    view = settings_view
    view._reset_save_btn()  # Should do nothing
