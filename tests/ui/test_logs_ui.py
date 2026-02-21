"""Tests cho LogsViewQt - load, filter, parse, copy, toggle, status.

Covers: lines 212-374 cua logs_view_qt.py
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from PySide6.QtCore import Qt

from views.logs_view_qt import LogsViewQt


@pytest.fixture
def mock_log_file(tmp_path):
    """Tao log dir va file gia."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_text(
        "2026-02-21 10:00:00 [INFO] App started\n"
        "2026-02-21 10:00:01 [DEBUG] Connecting...\n"
        "2026-02-21 10:00:02 [ERROR] Failed to connect\n"
        "2026-02-21 10:00:03 [WARNING] Retry in 5s\n",
        encoding="utf-8"
    )
    return log_dir, log_file


def _create_view(qtbot, log_dir):
    """Helper tao LogsViewQt voi mock LOG_DIR."""
    with patch("views.logs_view_qt.LOG_DIR", log_dir), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
    return view


def test_logs_view_load_and_filter(qtbot, mock_log_file):
    """Kiem tra load logs va filter theo level."""
    log_dir, _ = mock_log_file

    with patch("views.logs_view_qt.LOG_DIR", log_dir), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._load_logs()

        assert len(view.all_logs) == 4
        assert view._count_label.text() == "4 logs"

        text = view._log_view.toPlainText()
        assert "App started" in text
        assert "Failed to connect" in text

        view._filter_combo.setCurrentText("ERROR")
        filtered_text = view._log_view.toPlainText()
        assert "Failed to connect" in filtered_text
        assert "App started" not in filtered_text


def test_logs_view_clear(qtbot, mock_log_file):
    """Kiem tra clear logs display."""
    log_dir, _ = mock_log_file

    with patch("views.logs_view_qt.LOG_DIR", log_dir), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._load_logs()
        assert len(view.all_logs) == 4

        view._clear_display()
        assert len(view.all_logs) == 0
        assert "Display cleared" in view._log_view.toPlainText()
        assert view._count_label.text() == "0 logs"


def test_on_view_activated_loads_once(qtbot, mock_log_file):
    """Kiem tra on_view_activated chi load khi chua co logs (line 212-214)."""
    log_dir, _ = mock_log_file

    with patch("views.logs_view_qt.LOG_DIR", log_dir), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)

        # First activation loads
        view.on_view_activated()
        assert len(view.all_logs) == 4

        # Second activation does NOT reload
        old_count = len(view.all_logs)
        view.on_view_activated()
        assert len(view.all_logs) == old_count


def test_load_logs_no_files(qtbot, tmp_path):
    """Kiem tra _load_logs khi khong co log files (line 224-226)."""
    empty_dir = tmp_path / "empty_logs"
    empty_dir.mkdir()

    with patch("views.logs_view_qt.LOG_DIR", empty_dir), \
         patch("views.logs_view_qt.toast_success") as mock_success, \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._load_logs()

        assert len(view.all_logs) == 0
        mock_success.assert_called_with("No log files found")


def test_load_logs_exception(qtbot, tmp_path):
    """Kiem tra _load_logs xu ly exception (line 240-241)."""
    with patch("views.logs_view_qt.LOG_DIR", tmp_path), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error") as mock_error:
        view = LogsViewQt()
        qtbot.addWidget(view)

        # Patch sorted to raise when called during _load_logs
        with patch("views.logs_view_qt.sorted", side_effect=PermissionError("denied")):
            view._load_logs()
            mock_error.assert_called_once()


def test_parse_log_line_empty(qtbot, tmp_path):
    """Kiem tra _parse_log_line voi empty line (line 244-245)."""
    with patch("views.logs_view_qt.LOG_DIR", tmp_path), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        assert view._parse_log_line("") is None
        assert view._parse_log_line("   ") is None


def test_parse_log_line_no_timestamp(qtbot, tmp_path):
    """Kiem tra _parse_log_line voi line khong co timestamp (line 256-257)."""
    with patch("views.logs_view_qt.LOG_DIR", tmp_path), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        entry = view._parse_log_line("Just a plain message")
        assert entry is not None
        assert entry.timestamp == ""
        assert entry.message == "Just a plain message"


def test_parse_log_line_with_timestamp(qtbot, tmp_path):
    """Kiem tra _parse_log_line voi timestamp (line 253-255)."""
    with patch("views.logs_view_qt.LOG_DIR", tmp_path), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        entry = view._parse_log_line("2026-02-21 10:00:00 [ERROR] Something failed")
        assert entry is not None
        assert entry.timestamp == "2026-02-21 10:00:00"
        assert entry.level == "ERROR"


def test_render_logs_empty_filter(qtbot, mock_log_file):
    """Kiem tra _render_logs khi filter khong khop (line 274-276)."""
    log_dir, _ = mock_log_file

    with patch("views.logs_view_qt.LOG_DIR", log_dir), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._load_logs()

        # Set filter to something that doesn't match
        view.current_filter = "CRITICAL"
        view._render_logs()
        assert "No logs match" in view._log_view.toPlainText()


def test_render_logs_warning_background(qtbot, mock_log_file):
    """Kiem tra _render_logs WARNING co background tint (line 301-302)."""
    log_dir, _ = mock_log_file

    with patch("views.logs_view_qt.LOG_DIR", log_dir), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._load_logs()

        # Filter to WARNING only
        view.current_filter = "WARNING"
        view._render_logs()
        text = view._log_view.toPlainText()
        assert "Retry" in text


def test_toggle_debug(qtbot, tmp_path):
    """Kiem tra _toggle_debug goi set_debug_mode (line 313-319)."""
    with patch("views.logs_view_qt.LOG_DIR", tmp_path), \
         patch("views.logs_view_qt.toast_success") as mock_success, \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)

        with patch("core.logging_config.set_debug_mode") as mock_debug:
            view._toggle_debug(Qt.CheckState.Checked.value)
            mock_debug.assert_called_once_with(True)
            mock_success.assert_called_with("Debug mode enabled")

        with patch("core.logging_config.set_debug_mode") as mock_debug:
            view._toggle_debug(Qt.CheckState.Unchecked.value)
            mock_debug.assert_called_once_with(False)


def test_copy_all(qtbot, mock_log_file):
    """Kiem tra _copy_all copy tat ca logs (line 321-334)."""
    log_dir, _ = mock_log_file

    with patch("views.logs_view_qt.LOG_DIR", log_dir), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"), \
         patch("views.logs_view_qt.copy_to_clipboard", return_value=(True, None)) as mock_copy:
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._load_logs()
        view._copy_all()
        mock_copy.assert_called_once()
        assert "App started" in mock_copy.call_args[0][0]


def test_copy_all_no_logs(qtbot, tmp_path):
    """Kiem tra _copy_all khi khong co logs (line 323-324)."""
    with patch("views.logs_view_qt.LOG_DIR", tmp_path), \
         patch("views.logs_view_qt.toast_success") as mock_success, \
         patch("views.logs_view_qt.toast_error") as mock_error:
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._copy_all()
        mock_error.assert_called_with("No logs to copy")


def test_copy_errors(qtbot, mock_log_file):
    """Kiem tra _copy_errors chi copy ERROR/WARNING (line 336-355)."""
    log_dir, _ = mock_log_file

    with patch("views.logs_view_qt.LOG_DIR", log_dir), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error"), \
         patch("views.logs_view_qt.copy_to_clipboard", return_value=(True, None)) as mock_copy:
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._load_logs()
        view._copy_errors()
        mock_copy.assert_called_once()
        text = mock_copy.call_args[0][0]
        assert "Failed to connect" in text
        assert "Retry" in text
        assert "App started" not in text


def test_copy_errors_no_errors(qtbot, mock_log_file):
    """Kiem tra _copy_errors khi khong co error logs (line 341-343)."""
    log_dir, _ = mock_log_file

    with patch("views.logs_view_qt.LOG_DIR", log_dir), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error") as mock_error:
        view = LogsViewQt()
        qtbot.addWidget(view)
        # Only add INFO logs
        view.all_logs = [MagicMock(level="INFO", timestamp="", message="ok")]
        view._copy_errors()
        mock_error.assert_called_with("No error/warning logs")


def test_show_status_error(qtbot, tmp_path):
    """Kiem tra _show_status voi is_error (line 365-373)."""
    with patch("views.logs_view_qt.LOG_DIR", tmp_path), \
         patch("views.logs_view_qt.toast_success"), \
         patch("views.logs_view_qt.toast_error") as mock_error:
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._show_status("Broken", is_error=True)
        mock_error.assert_called_with("Broken")


def test_show_status_empty(qtbot, tmp_path):
    """Kiem tra _show_status voi empty message (line 367-368)."""
    with patch("views.logs_view_qt.LOG_DIR", tmp_path), \
         patch("views.logs_view_qt.toast_success") as mock_success, \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._show_status("")
        mock_success.assert_not_called()


def test_show_status_success(qtbot, tmp_path):
    """Kiem tra _show_status thanh cong (line 371-373)."""
    with patch("views.logs_view_qt.LOG_DIR", tmp_path), \
         patch("views.logs_view_qt.toast_success") as mock_success, \
         patch("views.logs_view_qt.toast_error"):
        view = LogsViewQt()
        qtbot.addWidget(view)
        view._show_status("All good")
        mock_success.assert_called_with("All good")
