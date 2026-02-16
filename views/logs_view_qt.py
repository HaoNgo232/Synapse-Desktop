"""
Logs View (PySide6) - Tab hiển thị logs để debug.

Port từ views/logs_view.py (Flet) sang QWidget.
"""

from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QComboBox,
    QCheckBox,
)
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
from PySide6.QtCore import Qt, Slot, QTimer

from core.theme import ThemeColors
from core.logging_config import LOG_DIR
from services.clipboard_utils import copy_to_clipboard


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str


# Level → color
_LEVEL_COLORS = {
    "DEBUG": ThemeColors.TEXT_MUTED,
    "INFO": ThemeColors.PRIMARY,
    "WARNING": ThemeColors.WARNING,
    "ERROR": ThemeColors.ERROR,
}


class LogsViewQt(QWidget):
    """View cho Logs tab — PySide6."""

    MAX_DISPLAY_LOGS = 500

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.all_logs: List[LogEntry] = []
        self.current_filter: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("🖥️ Logs")
        title.setStyleSheet(
            f"font-weight: 600; font-size: 20px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(title)
        header.addStretch()
        self._count_label = QLabel("0 logs")
        self._count_label.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(self._count_label)
        layout.addLayout(header)

        # Toolbar
        toolbar = QHBoxLayout()

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["All Levels", "DEBUG", "INFO", "WARNING", "ERROR"])
        self._filter_combo.setFixedWidth(130)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._filter_combo)

        self._auto_scroll = QCheckBox("Auto-scroll")
        self._auto_scroll.setChecked(True)
        toolbar.addWidget(self._auto_scroll)

        self._debug_mode = QCheckBox("Debug Mode")
        self._debug_mode.stateChanged.connect(self._toggle_debug)
        toolbar.addWidget(self._debug_mode)

        toolbar.addStretch()

        load_btn = QPushButton("Load Logs")
        load_btn.setProperty("class", "outlined")
        load_btn.clicked.connect(self._load_logs)
        toolbar.addWidget(load_btn)

        copy_all_btn = QPushButton("Copy All")
        copy_all_btn.setProperty("class", "outlined")
        copy_all_btn.clicked.connect(self._copy_all)
        toolbar.addWidget(copy_all_btn)

        copy_err_btn = QPushButton("Copy Errors")
        copy_err_btn.setProperty("class", "outlined")
        copy_err_btn.setStyleSheet(
            f"color: {ThemeColors.WARNING}; border: 1px solid {ThemeColors.WARNING}; "
            f"border-radius: 6px; padding: 6px 12px;"
        )
        copy_err_btn.clicked.connect(self._copy_errors)
        toolbar.addWidget(copy_err_btn)

        clear_btn = QPushButton("Clear Display")
        clear_btn.setProperty("class", "outlined")
        clear_btn.clicked.connect(self._clear_display)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # Log display
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("JetBrains Mono, Fira Code, Consolas", 11))
        self._log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._log_view.setStyleSheet(
            f"QPlainTextEdit {{ "
            f"background-color: {ThemeColors.BG_SURFACE}; "
            f"border: 1px solid {ThemeColors.BORDER}; "
            f"border-radius: 8px; padding: 12px; }}"
        )
        layout.addWidget(self._log_view, stretch=1)

        # Status bar
        status_row = QHBoxLayout()
        dir_label = QLabel(f"Log directory: {LOG_DIR}")
        dir_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        status_row.addWidget(dir_label)
        status_row.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size: 12px;")
        status_row.addWidget(self._status)
        layout.addLayout(status_row)

    # ===== Public =====

    def on_view_activated(self) -> None:
        if not self.all_logs:
            self._load_logs()

    # ===== Internal =====

    @Slot()
    def _load_logs(self) -> None:
        self.all_logs.clear()

        try:
            log_files = sorted(LOG_DIR.glob("app.log*"), reverse=True)
            if not log_files:
                self._show_status("No log files found")
                return

            log_file = log_files[0]
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()

            for line in lines[-1000:]:
                entry = self._parse_log_line(line)
                if entry:
                    self.all_logs.append(entry)

            self._render_logs()
            self._count_label.setText(f"{len(self.all_logs)} logs")
            self._show_status(f"Loaded from {log_file.name}")

        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    def _parse_log_line(self, line: str) -> Optional[LogEntry]:
        if not line.strip():
            return None
        try:
            level = "INFO"
            for lv in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                if f"[{lv}]" in line:
                    level = lv
                    break
            timestamp = ""
            if len(line) >= 19 and line[4] == "-" and line[7] == "-":
                timestamp = line[:19]
                message = line[20:].strip()
            else:
                message = line
            return LogEntry(timestamp=timestamp, level=level, message=message)
        except Exception:
            return LogEntry(timestamp="", level="INFO", message=line)

    def _render_logs(self) -> None:
        """Render logs vào QPlainTextEdit với màu theo level."""
        self._log_view.clear()

        filtered = self.all_logs
        if self.current_filter and self.current_filter != "All Levels":
            filtered = [l for l in self.all_logs if l.level == self.current_filter]

        display = filtered[-self.MAX_DISPLAY_LOGS :]

        if not display:
            self._log_view.setPlainText("No logs match the current filter")
            return

        cursor = self._log_view.textCursor()
        for i, log in enumerate(display):
            if i > 0:
                cursor.insertText("\n")

            # Timestamp (dim)
            ts_fmt = QTextCharFormat()
            ts_fmt.setForeground(QColor(ThemeColors.TEXT_MUTED))
            cursor.insertText(f"{log.timestamp:<20}", ts_fmt)

            # Level badge
            level_fmt = QTextCharFormat()
            color = _LEVEL_COLORS.get(log.level, ThemeColors.TEXT_SECONDARY)
            level_fmt.setForeground(QColor(color))
            level_fmt.setFontWeight(600)
            cursor.insertText(f" [{log.level:<7}] ", level_fmt)

            # Message
            msg_fmt = QTextCharFormat()
            msg_fmt.setForeground(QColor(ThemeColors.TEXT_PRIMARY))
            # Background for errors
            if log.level == "ERROR":
                msg_fmt.setBackground(QColor("#2D1F1F"))
            elif log.level == "WARNING":
                msg_fmt.setBackground(QColor("#2D2A1F"))
            cursor.insertText(log.message, msg_fmt)

        if self._auto_scroll.isChecked():
            self._log_view.moveCursor(QTextCursor.MoveOperation.End)

    @Slot(str)
    def _on_filter_changed(self, value: str) -> None:
        self.current_filter = value if value != "All Levels" else None
        self._render_logs()

    @Slot(int)
    def _toggle_debug(self, state: int) -> None:
        from core.logging_config import set_debug_mode

        enabled = state == Qt.CheckState.Checked.value
        set_debug_mode(enabled)
        self._show_status("Debug mode enabled" if enabled else "Debug mode disabled")

    @Slot()
    def _copy_all(self) -> None:
        if not self.all_logs:
            self._show_status("No logs to copy", is_error=True)
            return
        lines = [f"{l.timestamp} [{l.level}] {l.message}" for l in self.all_logs]
        success, _ = copy_to_clipboard("\n".join(lines))
        self._show_status(
            f"Copied {len(self.all_logs)} logs" if success else "Copy failed",
            not success,
        )

    @Slot()
    def _copy_errors(self) -> None:
        error_logs = [l for l in self.all_logs if l.level in ("ERROR", "WARNING")]
        if not error_logs:
            self._show_status("No error/warning logs", is_error=True)
            return
        lines = [f"{l.timestamp} [{l.level}] {l.message}" for l in error_logs]
        success, _ = copy_to_clipboard("\n".join(lines))
        self._show_status(
            f"Copied {len(error_logs)} error/warning logs"
            if success
            else "Copy failed",
            not success,
        )

    @Slot()
    def _clear_display(self) -> None:
        self.all_logs.clear()
        self._log_view.clear()
        self._log_view.setPlainText("Display cleared. Click 'Load Logs' to reload.")
        self._count_label.setText("0 logs")
        self._show_status("Display cleared")

    def _show_status(self, message: str, is_error: bool = False) -> None:
        color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self._status.setStyleSheet(f"font-size: 12px; color: {color};")
        self._status.setText(message)
        if not is_error:
            QTimer.singleShot(4000, lambda: self._status.setText(""))
