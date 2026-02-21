"""Tests cho ApplyViewQt - paste, preview, apply, error context, render, convert.

Covers: lines 340-798 cua apply_view_qt.py
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from PySide6.QtWidgets import QMessageBox

from views.apply_view_qt import ApplyViewQt, _convert_to_row_results
from core.file_actions import ActionResult
from services.error_context import ApplyRowResult


@pytest.fixture
def apply_view(qtbot):
    """Fixture tao ApplyViewQt."""
    with patch("views.apply_view_qt.toast_success"), \
         patch("views.apply_view_qt.toast_error"):
        view = ApplyViewQt(get_workspace=lambda: Path("/fake/workspace"))
        qtbot.addWidget(view)
    return view


def test_apply_view_initialization(apply_view):
    """Kiem tra ApplyViewQt khoi tao thanh cong."""
    view = apply_view
    assert view.last_preview_data is None
    assert view.last_apply_results == []
    assert view.last_opx_text == ""
    assert view._cached_file_actions == []


def test_set_opx_content(apply_view):
    """Kiem tra set_opx_content."""
    view = apply_view
    view.set_opx_content('<edit file="test.py" op="create">content</edit>')
    assert '<edit file="test.py"' in view._opx_input.toPlainText()


def test_paste_from_clipboard(apply_view):
    """Kiem tra _paste_from_clipboard (line 342-345)."""
    view = apply_view
    with patch("views.apply_view_qt.get_clipboard_text",
               return_value=(True, "clipboard text")):
        view._paste_from_clipboard()
    assert view._opx_input.toPlainText() == "clipboard text"


def test_paste_from_clipboard_fail(apply_view):
    """Kiem tra _paste_from_clipboard khi fail."""
    view = apply_view
    view._opx_input.setPlainText("existing")
    with patch("views.apply_view_qt.get_clipboard_text",
               return_value=(False, "")):
        view._paste_from_clipboard()
    assert view._opx_input.toPlainText() == "existing"


def test_clear_input(apply_view):
    """Kiem tra _clear_input xoa input va results."""
    view = apply_view
    view._opx_input.setPlainText("some text")
    view._clear_input()
    assert view._opx_input.toPlainText() == ""


def test_preview_no_content(apply_view):
    """Kiem tra _preview_changes khi khong co opx (line 356-358)."""
    view = apply_view
    view._opx_input.clear()
    with patch("views.apply_view_qt.toast_error") as mock_error:
        view._preview_changes()
        mock_error.assert_called_with("No OPX content to preview")


def test_preview_no_workspace(apply_view):
    """Kiem tra _preview_changes khi khong co workspace (line 361-363)."""
    view = apply_view
    view.get_workspace = lambda: None
    view._opx_input.setPlainText("<edit>test</edit>")
    with patch("views.apply_view_qt.toast_error") as mock_error:
        view._preview_changes()
        mock_error.assert_called_with("No workspace selected")


def test_preview_no_valid_actions(apply_view):
    """Kiem tra _preview_changes khi parse khong ra actions (line 368-370)."""
    view = apply_view
    view._opx_input.setPlainText("not valid opx")

    mock_result = MagicMock()
    mock_result.file_actions = []

    with patch("views.apply_view_qt.parse_opx_response", return_value=mock_result), \
         patch("views.apply_view_qt.toast_error") as mock_error:
        view._preview_changes()
        mock_error.assert_called_with("No valid OPX actions found")


def test_preview_success(apply_view):
    """Kiem tra _preview_changes thanh cong (lines 365-387)."""
    view = apply_view
    view._opx_input.setPlainText('<edit file="test.py" op="create">code</edit>')

    mock_action = MagicMock()
    mock_parse = MagicMock()
    mock_parse.file_actions = [mock_action]

    mock_row = MagicMock()
    mock_row.diff_lines = []
    mock_preview = MagicMock()
    mock_preview.rows = [mock_row]

    with patch("views.apply_view_qt.parse_opx_response", return_value=mock_parse), \
         patch("views.apply_view_qt.analyze_file_actions", return_value=mock_preview), \
         patch("views.apply_view_qt.generate_preview_diff_lines", return_value=[]), \
         patch("views.apply_view_qt.toast_success") as mock_toast, \
         patch.object(view, '_render_preview'):
        view._preview_changes()
        mock_toast.assert_called_with("Previewing 1 change(s)")


def test_preview_parse_error(apply_view):
    """Kiem tra _preview_changes khi parse raise exception (line 388-389)."""
    view = apply_view
    view._opx_input.setPlainText("some opx text")

    with patch("views.apply_view_qt.parse_opx_response",
               side_effect=Exception("Bad XML")), \
         patch("views.apply_view_qt.toast_error") as mock_error:
        view._preview_changes()
        assert "Parse error" in mock_error.call_args[0][0]


def test_apply_no_content(apply_view):
    """Kiem tra _apply_changes khi khong co noi dung (line 398-401)."""
    view = apply_view
    view._opx_input.clear()
    with patch("views.apply_view_qt.toast_error") as mock_error:
        view._apply_changes()
        mock_error.assert_called_with("No OPX content to apply")


def test_apply_no_workspace(apply_view):
    """Kiem tra _apply_changes khi khong co workspace (line 403-406)."""
    view = apply_view
    view.get_workspace = lambda: None
    view._opx_input.setPlainText("<edit>test</edit>")
    with patch("views.apply_view_qt.toast_error") as mock_error:
        view._apply_changes()
        mock_error.assert_called_with("No workspace selected")


def test_apply_cancelled(apply_view):
    """Kiem tra _apply_changes khi user cancel (line 416-417)."""
    view = apply_view
    view._opx_input.setPlainText("<edit>test</edit>")
    with patch("views.apply_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.No):
        view._apply_changes()


def test_apply_no_valid_actions(apply_view):
    """Kiem tra _apply_changes khi parse khong ra actions (line 425-427)."""
    view = apply_view
    view._opx_input.setPlainText("not valid opx")
    view._cached_file_actions = []

    mock_result = MagicMock()
    mock_result.file_actions = []

    with patch("views.apply_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes), \
         patch("views.apply_view_qt.parse_opx_response", return_value=mock_result), \
         patch("views.apply_view_qt.toast_error") as mock_error:
        view._apply_changes()
        mock_error.assert_called_with("No valid OPX actions found")


def test_apply_success(apply_view):
    """Kiem tra _apply_changes thanh cong (lines 418-469)."""
    view = apply_view
    view._opx_input.setPlainText('<edit file="test.py" op="create">code</edit>')

    mock_action = MagicMock()
    mock_action.path = "test.py"
    view._cached_file_actions = [mock_action]

    mock_result = ActionResult(
        success=True, action="create", path="test.py", message="Created"
    )

    mock_row = MagicMock()
    mock_row.diff_lines = []
    mock_preview = MagicMock()
    mock_preview.rows = [mock_row]

    with patch("views.apply_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes), \
         patch("views.apply_view_qt.apply_file_actions", return_value=[mock_result]), \
         patch("views.apply_view_qt.analyze_file_actions", return_value=mock_preview), \
         patch("views.apply_view_qt.generate_preview_diff_lines", return_value=[]), \
         patch("views.apply_view_qt.add_history_entry"), \
         patch("views.apply_view_qt.toast_success") as mock_toast, \
         patch.object(view, '_render_results'):
        view._apply_changes()
        mock_toast.assert_called()


def test_apply_with_fresh_parse(apply_view):
    """Kiem tra _apply_changes parse tu dau khi chua co cached actions (line 422-424)."""
    view = apply_view
    view._opx_input.setPlainText("opx text")
    view._cached_file_actions = []

    mock_action = MagicMock()
    mock_action.path = "test.py"
    mock_parse = MagicMock()
    mock_parse.file_actions = [mock_action]

    mock_result = ActionResult(
        success=True, action="create", path="test.py", message="OK"
    )

    mock_preview = MagicMock()
    mock_preview.rows = [MagicMock(diff_lines=[])]

    with patch("views.apply_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes), \
         patch("views.apply_view_qt.parse_opx_response", return_value=mock_parse), \
         patch("views.apply_view_qt.apply_file_actions", return_value=[mock_result]), \
         patch("views.apply_view_qt.analyze_file_actions", return_value=mock_preview), \
         patch("views.apply_view_qt.generate_preview_diff_lines", return_value=[]), \
         patch("views.apply_view_qt.add_history_entry"), \
         patch("views.apply_view_qt.toast_success"), \
         patch.object(view, '_render_results'):
        view._apply_changes()


def test_apply_exception(apply_view):
    """Kiem tra _apply_changes xu ly exception (line 468-469)."""
    view = apply_view
    view._opx_input.setPlainText("opx")
    view._cached_file_actions = [MagicMock()]

    with patch("views.apply_view_qt.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes), \
         patch("views.apply_view_qt.apply_file_actions",
               side_effect=Exception("Crash")), \
         patch("views.apply_view_qt.analyze_file_actions",
               return_value=MagicMock(rows=[])), \
         patch("views.apply_view_qt.toast_error") as mock_error:
        view._apply_changes()
        assert "Apply error" in mock_error.call_args[0][0]


def test_copy_error_context_with_results(apply_view):
    """Kiem tra _copy_error_context voi apply results (line 478-497)."""
    view = apply_view
    view.last_apply_results = [MagicMock()]
    view.last_preview_data = MagicMock()
    view.last_opx_text = "opx"

    with patch("views.apply_view_qt.build_error_context_for_ai",
               return_value="error context") as mock_build, \
         patch("views.apply_view_qt.copy_to_clipboard") as mock_copy, \
         patch("views.apply_view_qt.toast_success") as mock_toast:
        view._copy_error_context()
        mock_build.assert_called_once()
        mock_copy.assert_called_once_with("error context")


def test_copy_error_context_fallback(apply_view):
    """Kiem tra _copy_error_context fallback khi khong co results (line 489-495)."""
    view = apply_view
    view.last_apply_results = []
    view.last_preview_data = None

    with patch("views.apply_view_qt.build_general_error_context",
               return_value="general context") as mock_build, \
         patch("views.apply_view_qt.copy_to_clipboard"), \
         patch("views.apply_view_qt.toast_success"):
        view._copy_error_context()
        mock_build.assert_called_once()


def test_render_preview(apply_view):
    """Kiem tra _render_preview tao cards (line 501-509)."""
    view = apply_view
    mock_row = MagicMock()
    mock_row.action = "create"
    mock_row.path = "test.py"
    mock_row.changes = None
    mock_row.description = ""
    mock_row.diff_lines = None
    mock_preview = MagicMock()
    mock_preview.rows = [mock_row]

    view._render_preview(mock_preview)

    # Should have at least 1 card + stretch
    assert view._results_layout.count() >= 2


def test_render_results_with_errors(apply_view):
    """Kiem tra _render_results shows error button (line 511-525)."""
    view = apply_view
    error_result = ActionResult(
        success=False, action="modify", path="fail.py", message="Search not found"
    )

    view._render_results([error_result])

    # copy_error_btn.show() was called in _render_results
    assert view._copy_error_btn.isHidden() is False


def test_render_results_all_success(apply_view):
    """Kiem tra _render_results hides error button khi thanh cong het."""
    view = apply_view
    result = ActionResult(
        success=True, action="create", path="ok.py", message="Created"
    )
    view._render_results([result])
    assert not view._copy_error_btn.isVisible()


def test_create_preview_card_with_diff(apply_view):
    """Kiem tra _create_preview_card voi diff data (line 606-663)."""
    from PySide6.QtWidgets import QWidget
    view = apply_view
    row = MagicMock()
    row.action = "modify"
    row.path = "main.py"
    row.changes = MagicMock(added=5, removed=2)
    row.description = "Update function"
    row.diff_lines = [("add", "+new line"), ("remove", "-old line")]

    fake_diff = QWidget()
    with patch("views.apply_view_qt.DiffViewerWidget", return_value=fake_diff):
        card = view._create_preview_card(row)
    assert card is not None


def test_create_preview_card_no_diff(apply_view):
    """Kiem tra _create_preview_card without diff (line 654-661)."""
    view = apply_view
    row = MagicMock()
    row.action = "create"
    row.path = "new.py"
    row.changes = None
    row.description = ""
    row.diff_lines = None

    card = view._create_preview_card(row)
    assert card is not None


def test_create_preview_card_rename(apply_view):
    """Kiem tra _create_preview_card voi rename (no hint label)."""
    view = apply_view
    row = MagicMock()
    row.action = "rename"
    row.path = "old.py -> new.py"
    row.changes = None
    row.description = ""
    row.diff_lines = None

    card = view._create_preview_card(row)
    assert card is not None


def test_create_result_card_success(apply_view):
    """Kiem tra _create_result_card success (line 665-747)."""
    view = apply_view
    result = ActionResult(
        success=True, action="create", path="test.py", message="File created"
    )
    card = view._create_result_card(result)
    assert card is not None


def test_create_result_card_error(apply_view):
    """Kiem tra _create_result_card error."""
    view = apply_view
    result = ActionResult(
        success=False, action="modify", path="broken.py", message="Search failed"
    )
    card = view._create_result_card(result)
    assert card is not None


def test_show_status_error(apply_view):
    """Kiem tra _show_status error (line 757-765)."""
    view = apply_view
    with patch("views.apply_view_qt.toast_error") as mock_error:
        view._show_status("Error!", is_error=True)
        mock_error.assert_called_with("Error!")


def test_show_status_empty(apply_view):
    """Kiem tra _show_status empty (line 759-760)."""
    view = apply_view
    with patch("views.apply_view_qt.toast_success") as mock_success:
        view._show_status("")
        mock_success.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# _convert_to_row_results tests
# ═══════════════════════════════════════════════════════════════

def test_convert_to_row_results_success():
    """Kiem tra _convert_to_row_results voi thanh cong (line 779-798)."""
    results = [
        ActionResult(success=True, action="create", path="a.py", message="OK"),
        ActionResult(success=True, action="modify", path="b.py", message="OK"),
    ]
    row_results = _convert_to_row_results(results, [MagicMock(), MagicMock()])
    assert len(row_results) == 2
    assert all(r.success for r in row_results)
    assert not any(r.is_cascade_failure for r in row_results)


def test_convert_to_row_results_cascade():
    """Kiem tra _convert_to_row_results detect cascade failure."""
    results = [
        ActionResult(success=True, action="modify", path="a.py", message="OK"),
        ActionResult(success=False, action="modify", path="a.py", message="Search fail"),
    ]
    row_results = _convert_to_row_results(results, [MagicMock(), MagicMock()])
    assert len(row_results) == 2
    assert row_results[0].success is True
    assert row_results[1].success is False
    assert row_results[1].is_cascade_failure is True
