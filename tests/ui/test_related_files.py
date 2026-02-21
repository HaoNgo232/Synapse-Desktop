"""Tests cho RelatedFilesMixin - set mode, activate, deactivate, resolve, apply.

Su dung context_view fixture tu conftest.py.
Covers: lines 29-162 cua _related_files.py
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_set_related_mode_activate(context_view):
    """Kiem tra _set_related_mode(True, depth) bat related mode."""
    view = context_view
    with patch.object(view, '_resolve_related_files'):
        view._set_related_mode(True, 2)
        assert view._related_mode_active is True
        assert view._related_depth == 2


def test_set_related_mode_deactivate(context_view):
    """Kiem tra _set_related_mode(False, 0) tat related mode."""
    view = context_view
    view._related_mode_active = True
    view._last_added_related_files = set()
    view._set_related_mode(False, 0)
    assert view._related_mode_active is False


def test_update_related_button_text_off(context_view):
    """Kiem tra button text khi mode off."""
    view = context_view
    view._related_mode_active = False
    view._update_related_button_text()
    assert "Off" in view._related_menu_btn.text()


def test_update_related_button_text_with_depth(context_view):
    """Kiem tra button text khi mode on voi depth cu the."""
    view = context_view
    view._related_mode_active = True
    view._related_depth = 1
    view._last_added_related_files = set()
    view._update_related_button_text()
    assert "Direct" in view._related_menu_btn.text()


def test_update_related_button_text_with_count(context_view):
    """Kiem tra button text hien thi so luong related files."""
    view = context_view
    view._related_mode_active = True
    view._related_depth = 3
    view._last_added_related_files = {"a.py", "b.py", "c.py"}
    view._update_related_button_text()
    text = view._related_menu_btn.text()
    assert "Deep" in text
    assert "(3)" in text


def test_deactivate_clears_added_files(context_view):
    """Kiem tra deactivate xoa cac related files da them."""
    view = context_view
    view._related_mode_active = True
    view._last_added_related_files = {"file1.py", "file2.py"}
    view.file_tree_widget.remove_paths_from_selection = MagicMock(return_value=2)

    view._deactivate_related_mode()

    assert view._related_mode_active is False
    assert len(view._last_added_related_files) == 0
    view.file_tree_widget.remove_paths_from_selection.assert_called_once()


def test_deactivate_no_added_files(context_view):
    """Kiem tra deactivate khi khong co added files."""
    view = context_view
    view._related_mode_active = True
    view._last_added_related_files = set()

    view._deactivate_related_mode()

    assert view._related_mode_active is False


def test_apply_related_results_when_deactivated(context_view):
    """Kiem tra _apply_related_results khong lam gi khi mode da tat."""
    view = context_view
    view._related_mode_active = False
    view._apply_related_results({"new.py"}, {"existing.py"})


def test_apply_related_results_adds_and_removes(context_view):
    """Kiem tra _apply_related_results them files moi va xoa files cu."""
    view = context_view
    view._related_mode_active = True
    view._last_added_related_files = {"old.py"}
    view.file_tree_widget.remove_paths_from_selection = MagicMock(return_value=1)
    view.file_tree_widget.add_paths_to_selection = MagicMock()

    view._apply_related_results({"new.py"}, {"user.py"})

    view.file_tree_widget.remove_paths_from_selection.assert_called_once_with({"old.py"})
    view.file_tree_widget.add_paths_to_selection.assert_called_once_with({"new.py"})
    assert view._last_added_related_files == {"new.py"}


def test_apply_related_results_empty(context_view):
    """Kiem tra _apply_related_results voi empty set -> shows No related (line 159-160)."""
    view = context_view
    view._related_mode_active = True
    view._last_added_related_files = set()
    view.file_tree_widget.remove_paths_from_selection = MagicMock()
    view.file_tree_widget.add_paths_to_selection = MagicMock()

    view._apply_related_results(set(), {"user.py"})

    assert view._last_added_related_files == set()


def test_depth_name_mapping(context_view):
    """Kiem tra cac ten depth khac nhau hien thi dung."""
    view = context_view
    view._related_mode_active = True
    view._last_added_related_files = set()

    depth_names = {1: "Direct", 2: "Nearby", 3: "Deep", 4: "Deeper", 5: "Deepest"}
    for depth, name in depth_names.items():
        view._related_depth = depth
        view._update_related_button_text()
        assert name in view._related_menu_btn.text()


def test_depth_name_unknown(context_view):
    """Kiem tra depth > 5 hien thi Depth N."""
    view = context_view
    view._related_mode_active = True
    view._last_added_related_files = set()
    view._related_depth = 10
    view._update_related_button_text()
    assert "Depth 10" in view._related_menu_btn.text()


@patch("views.context._related_files.schedule_background")
def test_resolve_related_files_no_workspace(mock_schedule, context_view):
    """Kiem tra _resolve_related_files khong lam gi khi khong co workspace (line 74-76)."""
    view = context_view
    view.get_workspace = lambda: None
    view._resolve_related_files()
    mock_schedule.assert_not_called()


@patch("views.context._related_files.schedule_background")
def test_resolve_related_files_no_source_files(mock_schedule, context_view):
    """Kiem tra _resolve_related_files khi khong co supported files (line 92-99)."""
    view = context_view
    view.file_tree_widget.get_all_selected_paths = MagicMock(
        return_value={"readme.md", "image.png"}
    )
    view._last_added_related_files = {"old_related.py"}
    view.file_tree_widget.remove_paths_from_selection = MagicMock()

    view._resolve_related_files()

    # Should clear old related files
    view.file_tree_widget.remove_paths_from_selection.assert_called_once()
    assert len(view._last_added_related_files) == 0
    mock_schedule.assert_not_called()


@patch("views.context._related_files.schedule_background")
def test_resolve_related_files_dispatches_background(mock_schedule, context_view, tmp_path):
    """Kiem tra _resolve_related_files dispatch resolve() to background (line 100-130)."""
    view = context_view
    # Create a real .py file for filtering
    py_file = tmp_path / "main.py"
    py_file.write_text("print('hello')")

    view.file_tree_widget.get_all_selected_paths = MagicMock(
        return_value={str(py_file)}
    )
    view._last_added_related_files = set()

    view._resolve_related_files()

    mock_schedule.assert_called_once()


@patch("views.context._related_files.schedule_background")
def test_resolve_related_files_no_source_no_old_related(mock_schedule, context_view):
    """Kiem tra resolve voi no source files va no old related files."""
    view = context_view
    view.file_tree_widget.get_all_selected_paths = MagicMock(return_value=set())
    view._last_added_related_files = set()

    view._resolve_related_files()
    mock_schedule.assert_not_called()
