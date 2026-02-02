"""
Logs View - Tab hiển thị logs để debug app

Cho phép:
- Xem logs real-time
- Copy logs để báo cáo lỗi
- Lọc logs theo level (DEBUG, INFO, WARNING, ERROR)
- Clear logs display
"""

import flet as ft
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update
from core.logging_config import LOG_DIR
from services.clipboard_utils import copy_to_clipboard


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class LogEntry:
    """Một entry log"""

    timestamp: str
    level: str
    message: str


class LogsView:
    """View cho Logs tab"""

    def __init__(self, page: ft.Page):
        self.page = page

        self.logs_column: Optional[ft.Column] = None
        self.status_text: Optional[ft.Text] = None
        self.filter_dropdown: Optional[ft.Dropdown] = None
        self.auto_scroll_checkbox: Optional[ft.Checkbox] = None
        self.log_count_text: Optional[ft.Text] = None

        # State
        self.all_logs: List[LogEntry] = []
        self.current_filter: Optional[str] = None
        self.auto_scroll: bool = True
        self.max_display_logs: int = 500  # Giới hạn số logs hiển thị

    def build(self) -> ft.Container:
        """Build UI cho Logs view"""

        self.status_text = ft.Text("", size=12)
        self.log_count_text = ft.Text(
            "0 logs",
            size=12,
            color=ThemeColors.TEXT_SECONDARY,
        )

        self.filter_dropdown = ft.Dropdown(
            width=120,
            text_size=12,
            value="ALL",
            options=[
                ft.dropdown.Option(key="ALL", text="All Levels"),
                ft.dropdown.Option(key="DEBUG", text="Debug"),
                ft.dropdown.Option(key="INFO", text="Info"),
                ft.dropdown.Option(key="WARNING", text="Warning"),
                ft.dropdown.Option(key="ERROR", text="Error"),
            ],
            on_select=lambda e: self._on_filter_changed(e.control.value),
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
        )

        self.auto_scroll_checkbox = ft.Checkbox(
            label="Auto-scroll",
            value=True,
            active_color=ThemeColors.PRIMARY,
            check_color="#FFFFFF",
            label_style=ft.TextStyle(color=ThemeColors.TEXT_SECONDARY, size=12),
            on_change=lambda e: self._on_auto_scroll_changed(e.control.value),
        )

        self.logs_column = ft.Column(
            controls=[
                ft.Text(
                    "Click 'Load Logs' to view application logs",
                    color=ThemeColors.TEXT_MUTED,
                    italic=True,
                    size=12,
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=2,
        )

        return ft.Container(
            content=ft.Column(
                [
                    # Header
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.TERMINAL,
                                color=ThemeColors.TEXT_PRIMARY,
                                size=24,
                            ),
                            ft.Text(
                                "Logs",
                                size=20,
                                weight=ft.FontWeight.W_600,
                                color=ThemeColors.TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            self.log_count_text,
                        ],
                        spacing=12,
                    ),
                    ft.Divider(height=1, color=ThemeColors.BORDER),
                    ft.Container(height=8),
                    # Toolbar
                    ft.Container(
                        content=ft.Row(
                            [
                                self.filter_dropdown,
                                self.auto_scroll_checkbox,
                                ft.Checkbox(
                                    label="Debug Mode",
                                    value=False,
                                    active_color=ThemeColors.WARNING,
                                    check_color="#FFFFFF",
                                    label_style=ft.TextStyle(
                                        color=ThemeColors.TEXT_SECONDARY, size=12
                                    ),
                                    on_change=lambda e: self._toggle_debug_mode(
                                        e.control.value
                                    ),
                                    tooltip="Enable verbose DEBUG logging (restart may be needed)",
                                ),
                                ft.Container(expand=True),
                                ft.OutlinedButton(
                                    "Load Logs",
                                    icon=ft.Icons.REFRESH,
                                    on_click=lambda _: self._load_logs(),
                                    style=ft.ButtonStyle(
                                        color=ThemeColors.TEXT_PRIMARY,
                                        side=ft.BorderSide(1, ThemeColors.BORDER),
                                    ),
                                ),
                                ft.OutlinedButton(
                                    "Copy All",
                                    icon=ft.Icons.CONTENT_COPY,
                                    on_click=lambda _: self._copy_all_logs(),
                                    style=ft.ButtonStyle(
                                        color=ThemeColors.TEXT_PRIMARY,
                                        side=ft.BorderSide(1, ThemeColors.BORDER),
                                    ),
                                ),
                                ft.OutlinedButton(
                                    "Copy Errors",
                                    icon=ft.Icons.ERROR_OUTLINE,
                                    on_click=lambda _: self._copy_error_logs(),
                                    tooltip="Copy only ERROR and WARNING logs",
                                    style=ft.ButtonStyle(
                                        color=ThemeColors.WARNING,
                                        side=ft.BorderSide(1, ThemeColors.WARNING),
                                    ),
                                ),
                                ft.OutlinedButton(
                                    "Clear Display",
                                    icon=ft.Icons.CLEAR_ALL,
                                    on_click=lambda _: self._clear_display(),
                                    style=ft.ButtonStyle(
                                        color=ThemeColors.TEXT_SECONDARY,
                                        side=ft.BorderSide(1, ThemeColors.BORDER),
                                    ),
                                ),
                            ],
                            spacing=12,
                        ),
                        padding=ft.padding.only(bottom=12),
                    ),
                    # Logs display
                    ft.Container(
                        content=self.logs_column,
                        padding=12,
                        expand=True,
                        bgcolor=ThemeColors.BG_SURFACE,
                        border=ft.border.all(1, ThemeColors.BORDER),
                        border_radius=8,
                    ),
                    ft.Container(height=8),
                    # Status bar
                    ft.Row(
                        [
                            ft.Text(
                                f"Log directory: {LOG_DIR}",
                                size=11,
                                color=ThemeColors.TEXT_MUTED,
                            ),
                            ft.Container(expand=True),
                            self.status_text,
                        ]
                    ),
                ],
                expand=True,
            ),
            padding=20,
            expand=True,
            bgcolor=ThemeColors.BG_PAGE,
        )

    def on_view_activated(self):
        """Called when view becomes active (tab selected)"""
        # Tự động load logs khi tab được chọn lần đầu
        if not self.all_logs:
            self._load_logs()

    def _load_logs(self):
        """Load logs từ file"""
        assert self.logs_column is not None
        assert self.log_count_text is not None

        self.all_logs.clear()
        self.logs_column.controls.clear()

        try:
            # Tìm log file mới nhất
            log_files = sorted(LOG_DIR.glob("app.log*"), reverse=True)

            if not log_files:
                self.logs_column.controls.append(
                    ft.Text(
                        "No log files found",
                        color=ThemeColors.TEXT_MUTED,
                        italic=True,
                        size=12,
                    )
                )
                self._show_status("No log files found")
                safe_page_update(self.page)
                return

            # Đọc log file mới nhất
            log_file = log_files[0]
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()

            # Parse logs
            for line in lines[-1000:]:  # Chỉ lấy 1000 dòng cuối
                entry = self._parse_log_line(line)
                if entry:
                    self.all_logs.append(entry)

            # Display logs với filter
            self._render_logs()

            self.log_count_text.value = f"{len(self.all_logs)} logs"
            self._show_status(f"Loaded from {log_file.name}")

        except Exception as e:
            self.logs_column.controls.append(
                ft.Text(
                    f"Error loading logs: {e}",
                    color=ThemeColors.ERROR,
                    size=12,
                )
            )
            self._show_status(f"Error: {e}", is_error=True)

        safe_page_update(self.page)

    def _parse_log_line(self, line: str) -> Optional[LogEntry]:
        """Parse một dòng log thành LogEntry"""
        if not line.strip():
            return None

        # Format: 2025-01-01 12:00:00 [LEVEL] module: message
        try:
            # Tìm level trong brackets
            level = "INFO"
            for lv in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                if f"[{lv}]" in line:
                    level = lv
                    break

            # Extract timestamp (first 19 chars nếu có)
            timestamp = ""
            if len(line) >= 19 and line[4] == "-" and line[7] == "-":
                timestamp = line[:19]
                message = line[20:].strip()
            else:
                message = line

            return LogEntry(
                timestamp=timestamp,
                level=level,
                message=message,
            )
        except Exception:
            return LogEntry(
                timestamp="",
                level="INFO",
                message=line,
            )

    def _render_logs(self):
        """Render logs với filter hiện tại"""
        assert self.logs_column is not None

        self.logs_column.controls.clear()

        # Lọc theo level
        filtered_logs = self.all_logs
        if self.current_filter and self.current_filter != "ALL":
            filtered_logs = [
                log for log in self.all_logs if log.level == self.current_filter
            ]

        # Giới hạn số lượng hiển thị
        display_logs = filtered_logs[-self.max_display_logs :]

        if not display_logs:
            self.logs_column.controls.append(
                ft.Text(
                    "No logs match the current filter",
                    color=ThemeColors.TEXT_MUTED,
                    italic=True,
                    size=12,
                )
            )
        else:
            for log in display_logs:
                self.logs_column.controls.append(self._create_log_row(log))

        safe_page_update(self.page)

        # Auto-scroll to bottom
        if self.auto_scroll and self.logs_column.controls:
            # Flet tự động scroll khi có scroll mode
            pass

    def _create_log_row(self, log: LogEntry) -> ft.Container:
        """Tạo row hiển thị một log entry"""

        # Màu theo level
        level_colors = {
            "DEBUG": ThemeColors.TEXT_MUTED,
            "INFO": ThemeColors.PRIMARY,
            "WARNING": ThemeColors.WARNING,
            "ERROR": ThemeColors.ERROR,
        }
        level_color = level_colors.get(log.level, ThemeColors.TEXT_SECONDARY)

        # Background cho errors
        bg_color = None
        if log.level == "ERROR":
            bg_color = "#2D1F1F"  # Dark red tint
        elif log.level == "WARNING":
            bg_color = "#2D2A1F"  # Dark yellow tint

        return ft.Container(
            content=ft.Row(
                [
                    # Timestamp
                    ft.Text(
                        log.timestamp,
                        size=10,
                        color=ThemeColors.TEXT_MUTED,
                        font_family="monospace",
                        width=140,
                    ),
                    # Level badge
                    ft.Container(
                        content=ft.Text(
                            log.level,
                            size=9,
                            weight=ft.FontWeight.W_600,
                            color=level_color,
                        ),
                        width=60,
                    ),
                    # Message
                    ft.Text(
                        log.message,
                        size=11,
                        color=ThemeColors.TEXT_PRIMARY,
                        font_family="monospace",
                        expand=True,
                        no_wrap=False,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=4, horizontal=8),
            bgcolor=bg_color,
            border_radius=4,
        )

    def _on_filter_changed(self, value: str):
        """Handle filter dropdown change"""
        self.current_filter = value if value != "ALL" else None
        self._render_logs()

    def _on_auto_scroll_changed(self, value: bool):
        """Handle auto-scroll checkbox change"""
        self.auto_scroll = value

    def _copy_all_logs(self):
        """Copy tất cả logs ra clipboard"""
        if not self.all_logs:
            self._show_status("No logs to copy", is_error=True)
            return

        lines: List[str] = []
        for log in self.all_logs:
            lines.append(f"{log.timestamp} [{log.level}] {log.message}")

        text = "\n".join(lines)
        success, message = copy_to_clipboard(text)

        if success:
            self._show_status(f"Copied {len(self.all_logs)} logs to clipboard")
        else:
            self._show_status(f"Copy failed: {message}", is_error=True)

    def _copy_error_logs(self):
        """Copy chỉ ERROR và WARNING logs"""
        error_logs = [log for log in self.all_logs if log.level in ("ERROR", "WARNING")]

        if not error_logs:
            self._show_status("No error/warning logs to copy", is_error=True)
            return

        lines: List[str] = []
        for log in error_logs:
            lines.append(f"{log.timestamp} [{log.level}] {log.message}")

        text = "\n".join(lines)
        success, message = copy_to_clipboard(text)

        if success:
            self._show_status(f"Copied {len(error_logs)} error/warning logs")
        else:
            self._show_status(f"Copy failed: {message}", is_error=True)

    def _clear_display(self):
        """Clear logs display (không xóa file)"""
        assert self.logs_column is not None
        assert self.log_count_text is not None

        self.all_logs.clear()
        self.logs_column.controls.clear()
        self.logs_column.controls.append(
            ft.Text(
                "Display cleared. Click 'Load Logs' to reload.",
                color=ThemeColors.TEXT_MUTED,
                italic=True,
                size=12,
            )
        )
        self.log_count_text.value = "0 logs"
        self._show_status("Display cleared")
        safe_page_update(self.page)

    def _toggle_debug_mode(self, enabled: bool):
        """Toggle debug logging mode"""
        from core.logging_config import set_debug_mode

        set_debug_mode(enabled)

        if enabled:
            self._show_status("Debug mode enabled - verbose logging active")
        else:
            self._show_status("Debug mode disabled - normal logging")

    def _show_status(self, message: str, is_error: bool = False):
        """Hiển thị status message"""
        assert self.status_text is not None
        self.status_text.value = message
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        safe_page_update(self.page)
