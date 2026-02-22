"""Tests cho HistoryViewQt - load, search, clear, actions, helpers.

Covers: lines 44-1547 cua history_view_qt.py
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QMessageBox

from views.history_view_qt import (
    HistoryViewQt,
    create_status_dot_icon,
    create_search_icon,
    format_date_group,
    group_entries_by_date,
    FileChangeRow,
    ErrorCard,
)


# ═══════════════════════════════════════════════════════════════
# Helper function tests
# ═══════════════════════════════════════════════════════════════


def test_create_status_dot_icon():
    """Kiem tra create_status_dot_icon tao icon (line 44-57)."""
    icon = create_status_dot_icon("#FF0000")
    assert icon is not None


def test_create_search_icon():
    """Kiem tra create_search_icon tao icon (line 60-79)."""
    icon = create_search_icon()
    assert icon is not None


def test_format_date_group_today():
    """Kiem tra format_date_group voi hom nay (line 95-96)."""
    result = format_date_group(datetime.now())
    assert "Today" in result


def test_format_date_group_yesterday():
    """Kiem tra format_date_group voi hom qua (line 97-98)."""
    yesterday = datetime.now() - timedelta(days=1)
    result = format_date_group(yesterday)
    assert "Yesterday" in result


def test_format_date_group_older():
    """Kiem tra format_date_group voi ngay cu (line 99-100)."""
    old_date = datetime.now() - timedelta(days=30)
    result = format_date_group(old_date)
    assert "/" in result
    assert "Today" not in result
    assert "Yesterday" not in result


def test_group_entries_by_date():
    """Kiem tra group_entries_by_date (line 103-119)."""
    entry_today = MagicMock()
    entry_today.timestamp = datetime.now().isoformat()

    entry_old = MagicMock()
    entry_old.timestamp = (datetime.now() - timedelta(days=5)).isoformat()

    groups = group_entries_by_date([entry_today, entry_old])
    assert len(groups) >= 1


def test_group_entries_invalid_timestamp():
    """Kiem tra group_entries_by_date voi invalid timestamp (line 115-119)."""
    entry = MagicMock()
    entry.timestamp = "not-a-date"

    groups = group_entries_by_date([entry])
    assert "Unknown" in groups
    assert len(groups["Unknown"]) == 1


# ═══════════════════════════════════════════════════════════════
# Widget tests
# ═══════════════════════════════════════════════════════════════


def test_file_change_row_success(qtbot):
    """Kiem tra FileChangeRow voi success (line 220-267)."""
    row = FileChangeRow("CREATE", "new_file.py", success=True)
    qtbot.addWidget(row)
    assert row is not None


def test_file_change_row_failure(qtbot):
    """Kiem tra FileChangeRow voi failure (line 245-253)."""
    row = FileChangeRow("MODIFY", "broken.py", success=False)
    qtbot.addWidget(row)
    assert row is not None


def test_error_card(qtbot):
    """Kiem tra ErrorCard (line 270-320)."""
    card = ErrorCard("test.py", "Search pattern not found")
    qtbot.addWidget(card)
    assert card is not None


# ═══════════════════════════════════════════════════════════════
# Main view tests
# ═══════════════════════════════════════════════════════════════


def _make_entry():
    """Tao fake HistoryEntry."""
    entry = MagicMock()
    entry.id = "entry-1"
    entry.timestamp = datetime.now().isoformat()
    entry.workspace = "/fake/workspace"
    entry.file_count = 3
    entry.success_count = 2
    entry.fail_count = 1
    entry.opx_content = '<edit file="test.py" op="create">code</edit>'
    entry.action_summary = ["CREATE test.py", "MODIFY main.py", "DELETE old.py"]
    entry.error_messages = ["main.py: Search pattern not found"]
    return entry


@pytest.fixture
def history_view(qtbot):
    """Fixture tao HistoryViewQt, mock get_history_entries."""
    entry = _make_entry()
    with (
        patch("views.history_view_qt.get_history_entries", return_value=[entry]),
        patch(
            "views.history_view_qt.get_history_stats",
            return_value=MagicMock(total_entries=1, total_files=3, success_rate=66.7),
        ),
    ):
        view = HistoryViewQt()
        qtbot.addWidget(view)
    return view


def test_history_view_initialization(history_view):
    """Kiem tra HistoryViewQt khoi tao thanh cong."""
    view = history_view
    assert view is not None
    assert hasattr(view, "_search_input")
    assert hasattr(view, "_footer_label")


def test_history_view_refresh(history_view):
    """Kiem tra _refresh loads entries."""
    view = history_view
    entry = _make_entry()
    with patch("views.history_view_qt.get_history_entries", return_value=[entry]):
        view._refresh()
    assert view._entry_list.count() > 0


def test_history_view_clear_all(history_view):
    """Kiem tra clear all history (line 1513-1530)."""
    view = history_view
    with (
        patch(
            "views.history_view_qt.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ),
        patch("views.history_view_qt.clear_history", return_value=True),
        patch("views.history_view_qt.get_history_entries", return_value=[]),
    ):
        view._confirm_clear_all()
        assert "cleared" in view._footer_label.text().lower()


def test_history_view_clear_all_cancelled(history_view):
    """Kiem tra clear all cancelled."""
    view = history_view
    with (
        patch(
            "views.history_view_qt.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ),
        patch("views.history_view_qt.clear_history") as mock_clear,
    ):
        view._confirm_clear_all()
        mock_clear.assert_not_called()


def test_history_view_clear_all_failed(history_view):
    """Kiem tra clear all failed (line 1529-1530)."""
    view = history_view
    with (
        patch(
            "views.history_view_qt.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ),
        patch("views.history_view_qt.clear_history", return_value=False),
    ):
        view._confirm_clear_all()
        assert "fail" in view._footer_label.text().lower()


def test_history_view_delete_entry(history_view):
    """Kiem tra delete entry (line 1492-1510)."""
    view = history_view
    with (
        patch(
            "views.history_view_qt.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ),
        patch("views.history_view_qt.delete_entry", return_value=True),
        patch("views.history_view_qt.get_history_entries", return_value=[]),
    ):
        view._confirm_delete_entry("entry-1")
        assert "deleted" in view._footer_label.text().lower()


def test_history_view_delete_entry_cancelled(history_view):
    """Kiem tra delete entry cancelled."""
    view = history_view
    with patch(
        "views.history_view_qt.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ):
        view._confirm_delete_entry("entry-1")


def test_history_view_delete_entry_failed(history_view):
    """Kiem tra delete entry failed (line 1509-1510)."""
    view = history_view
    with (
        patch(
            "views.history_view_qt.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ),
        patch("views.history_view_qt.delete_entry", return_value=False),
    ):
        view._confirm_delete_entry("entry-1")
        assert "fail" in view._footer_label.text().lower()


def test_copy_opx(history_view):
    """Kiem tra _copy_opx (line 1478-1484)."""
    view = history_view
    entry = _make_entry()
    with patch("views.history_view_qt.copy_to_clipboard", return_value=(True, None)):
        view._copy_opx(entry)
        assert "copied" in view._footer_label.text().lower()


def test_copy_opx_failed(history_view):
    """Kiem tra _copy_opx failed (line 1483-1484)."""
    view = history_view
    entry = _make_entry()
    with patch("views.history_view_qt.copy_to_clipboard", return_value=(False, "err")):
        view._copy_opx(entry)
        assert "fail" in view._footer_label.text().lower()


def test_reapply_opx(history_view):
    """Kiem tra _reapply_opx (line 1486-1490)."""
    view = history_view
    entry = _make_entry()
    mock_callback = MagicMock()
    view.on_reapply = mock_callback
    view._reapply_opx(entry)
    mock_callback.assert_called_once_with(entry.opx_content)
    assert "loaded" in view._footer_label.text().lower()


def test_show_footer_message(history_view):
    """Kiem tra _show_footer_message (line 1532-1546)."""
    view = history_view
    view._show_footer_message("Test msg", is_error=False)
    assert view._footer_label.text() == "Test msg"

    view._show_footer_message("Error msg", is_error=True)
    assert view._footer_label.text() == "Error msg"


def test_on_view_activated(history_view):
    """Kiem tra on_view_activated refresh entries."""
    view = history_view
    entry = _make_entry()
    with patch("views.history_view_qt.get_history_entries", return_value=[entry]):
        view.on_view_activated()
