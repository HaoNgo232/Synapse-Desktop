"""
History View - Tab hiển thị lịch sử các thao tác đã thực hiện

Cho phép:
- Xem lại các OPX đã apply
- Copy lại OPX để sử dụng
- Xóa entries không cần thiết
"""

import flet as ft
from datetime import datetime
from typing import Optional, Callable, List

from core.theme import ThemeColors
from services.history_service import (
    get_history_entries,
    get_entry_by_id,
    delete_entry,
    clear_history,
    get_history_stats,
    HistoryEntry,
)
from services.clipboard_utils import copy_to_clipboard


class HistoryView:
    """View cho History tab"""

    def __init__(
        self,
        page: ft.Page,
        on_reapply: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            page: Flet page
            on_reapply: Callback khi user muốn re-apply OPX (chuyển sang Apply tab)
        """
        self.page = page
        self.on_reapply = on_reapply

        self.entries_column: Optional[ft.Column] = None
        self.stats_text: Optional[ft.Text] = None
        self.status_text: Optional[ft.Text] = None
        self.detail_container: Optional[ft.Container] = None

        # Currently selected entry
        self.selected_entry_id: Optional[str] = None

    def build(self) -> ft.Container:
        """Build UI cho History view"""

        self.stats_text = ft.Text(
            "",
            size=12,
            color=ThemeColors.TEXT_SECONDARY,
        )

        self.status_text = ft.Text("", size=12)

        self.entries_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.detail_container = ft.Container(
            content=ft.Text(
                "Select an entry to view details",
                color=ThemeColors.TEXT_MUTED,
                italic=True,
            ),
            padding=16,
            expand=True,
        )

        # Build layout
        return ft.Container(
            content=ft.Column(
                [
                    # Header
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.HISTORY,
                                color=ThemeColors.TEXT_PRIMARY,
                                size=24,
                            ),
                            ft.Text(
                                "History",
                                size=20,
                                weight=ft.FontWeight.W_600,
                                color=ThemeColors.TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            self.stats_text,
                            ft.OutlinedButton(
                                "Refresh",
                                icon=ft.Icons.REFRESH,
                                on_click=lambda _: self._refresh(),
                                style=ft.ButtonStyle(
                                    color=ThemeColors.TEXT_SECONDARY,
                                    side=ft.BorderSide(1, ThemeColors.BORDER),
                                ),
                            ),
                            ft.OutlinedButton(
                                "Clear All",
                                icon=ft.Icons.DELETE_SWEEP,
                                on_click=lambda _: self._confirm_clear_all(),
                                style=ft.ButtonStyle(
                                    color=ThemeColors.ERROR,
                                    side=ft.BorderSide(1, ThemeColors.ERROR),
                                ),
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Divider(height=1, color=ThemeColors.BORDER),
                    ft.Container(height=8),
                    # Main content - split view
                    ft.Row(
                        [
                            # Left: Entry list
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "Recent Operations",
                                            weight=ft.FontWeight.W_600,
                                            size=13,
                                            color=ThemeColors.TEXT_PRIMARY,
                                        ),
                                        ft.Divider(height=1, color=ThemeColors.BORDER),
                                        self.entries_column,
                                    ],
                                    expand=True,
                                ),
                                padding=12,
                                bgcolor=ThemeColors.BG_SURFACE,
                                border=ft.border.all(1, ThemeColors.BORDER),
                                border_radius=8,
                                expand=1,
                            ),
                            # Right: Detail view
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "Details",
                                            weight=ft.FontWeight.W_600,
                                            size=13,
                                            color=ThemeColors.TEXT_PRIMARY,
                                        ),
                                        ft.Divider(height=1, color=ThemeColors.BORDER),
                                        self.detail_container,
                                    ],
                                    expand=True,
                                ),
                                padding=12,
                                bgcolor=ThemeColors.BG_SURFACE,
                                border=ft.border.all(1, ThemeColors.BORDER),
                                border_radius=8,
                                expand=2,
                            ),
                        ],
                        expand=True,
                        spacing=16,
                    ),
                    ft.Container(height=8),
                    self.status_text,
                ],
                expand=True,
            ),
            padding=20,
            expand=True,
            bgcolor=ThemeColors.BG_PAGE,
        )

    def on_view_activated(self):
        """Called when view becomes active (tab selected)"""
        self._refresh()

    def _refresh(self):
        """Refresh danh sách entries"""
        assert self.entries_column is not None
        assert self.stats_text is not None

        # Clear current
        self.entries_column.controls.clear()

        # Load entries
        entries = get_history_entries(limit=50)

        if not entries:
            self.entries_column.controls.append(
                ft.Text(
                    "No history yet. Apply some OPX to see history here.",
                    color=ThemeColors.TEXT_MUTED,
                    italic=True,
                    size=12,
                )
            )
        else:
            for entry in entries:
                self.entries_column.controls.append(self._create_entry_row(entry))

        # Update stats
        stats = get_history_stats()
        self.stats_text.value = (
            f"{stats['total_entries']} entries | "
            f"{stats['total_operations']} ops | "
            f"{stats['success_rate']:.0f}% success"
        )

        self.page.update()

    def _create_entry_row(self, entry: HistoryEntry) -> ft.Container:
        """Tạo row cho một entry"""

        # Parse timestamp
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            time_str = dt.strftime("%m/%d %H:%M")
        except ValueError:
            time_str = entry.timestamp[:16]

        # Status color
        if entry.fail_count == 0:
            status_color = ThemeColors.SUCCESS
            status_icon = ft.Icons.CHECK_CIRCLE
        elif entry.success_count == 0:
            status_color = ThemeColors.ERROR
            status_icon = ft.Icons.ERROR
        else:
            status_color = ThemeColors.WARNING
            status_icon = ft.Icons.WARNING

        # Background for selected
        is_selected = entry.id == self.selected_entry_id
        bg_color = ThemeColors.BG_ELEVATED if is_selected else ThemeColors.BG_SURFACE

        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(status_icon, size=16, color=status_color),
                    ft.Column(
                        [
                            ft.Text(
                                f"{entry.file_count} files",
                                size=12,
                                weight=ft.FontWeight.W_500,
                                color=ThemeColors.TEXT_PRIMARY,
                            ),
                            ft.Text(
                                time_str,
                                size=10,
                                color=ThemeColors.TEXT_MUTED,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Text(
                        f"+{entry.success_count}/-{entry.fail_count}",
                        size=11,
                        color=status_color,
                    ),
                ],
                spacing=8,
            ),
            padding=10,
            bgcolor=bg_color,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=6,
            margin=ft.margin.only(bottom=6),
            on_click=(lambda eid: lambda e: self._select_entry(eid))(entry.id),
            ink=True,
        )

    def _select_entry(self, entry_id: str):
        """Chọn một entry để xem chi tiết"""
        self.selected_entry_id = entry_id
        entry = get_entry_by_id(entry_id)

        if not entry:
            return

        self._show_entry_detail(entry)
        self._refresh()  # Re-render để highlight selected

    def _show_entry_detail(self, entry: HistoryEntry):
        """Hiển thị chi tiết entry"""
        assert self.detail_container is not None

        # Parse timestamp
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            time_str = entry.timestamp

        # Action summary
        action_chips: List[ft.Control] = []
        for action in entry.action_summary[:10]:  # Max 10
            parts = action.split(" ", 1)
            action_type = parts[0] if parts else "?"
            file_name = parts[1] if len(parts) > 1 else ""

            color = {
                "CREATE": ThemeColors.SUCCESS,
                "MODIFY": ThemeColors.PRIMARY,
                "REWRITE": ThemeColors.WARNING,
                "DELETE": ThemeColors.ERROR,
                "RENAME": "#8B5CF6",
            }.get(action_type, ThemeColors.TEXT_SECONDARY)

            action_chips.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(
                                    action_type,
                                    size=9,
                                    weight=ft.FontWeight.W_600,
                                    color="#FFFFFF",
                                ),
                                bgcolor=color,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                border_radius=3,
                            ),
                            ft.Text(
                                file_name,
                                size=11,
                                color=ThemeColors.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=6,
                    ),
                    margin=ft.margin.only(bottom=4),
                )
            )

        if len(entry.action_summary) > 10:
            action_chips.append(
                ft.Text(
                    f"... and {len(entry.action_summary) - 10} more",
                    size=10,
                    color=ThemeColors.TEXT_MUTED,
                    italic=True,
                )
            )

        # Error messages (if any)
        error_section = []
        if entry.error_messages:
            error_section = [
                ft.Container(height=12),
                ft.Text(
                    "Errors:",
                    weight=ft.FontWeight.W_600,
                    size=12,
                    color=ThemeColors.ERROR,
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                msg[:100] + "..." if len(msg) > 100 else msg,
                                size=11,
                                color=ThemeColors.TEXT_SECONDARY,
                            )
                            for msg in entry.error_messages[:5]
                        ],
                        spacing=4,
                    ),
                    bgcolor=ThemeColors.BG_ELEVATED,
                    padding=8,
                    border_radius=4,
                ),
            ]

        self.detail_container.content = ft.Column(
            [
                # Header
                ft.Row(
                    [
                        ft.Text(
                            f"Entry #{entry.id}",
                            weight=ft.FontWeight.W_600,
                            size=14,
                            color=ThemeColors.TEXT_PRIMARY,
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            time_str,
                            size=11,
                            color=ThemeColors.TEXT_MUTED,
                        ),
                    ]
                ),
                ft.Container(height=8),
                # Stats
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(
                                f"{entry.success_count} success",
                                size=11,
                                color=ThemeColors.SUCCESS,
                            ),
                            bgcolor=ThemeColors.BG_ELEVATED,
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=4,
                        ),
                        ft.Container(
                            content=ft.Text(
                                f"{entry.fail_count} failed",
                                size=11,
                                color=(
                                    ThemeColors.ERROR
                                    if entry.fail_count > 0
                                    else ThemeColors.TEXT_MUTED
                                ),
                            ),
                            bgcolor=ThemeColors.BG_ELEVATED,
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=4,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Container(height=12),
                # Actions
                ft.Text(
                    "Actions:",
                    weight=ft.FontWeight.W_600,
                    size=12,
                    color=ThemeColors.TEXT_PRIMARY,
                ),
                ft.Container(
                    content=ft.Column(action_chips, spacing=0),
                    padding=8,
                ),
                # Errors
                *error_section,
                ft.Container(expand=True),
                # Action buttons
                ft.Row(
                    [
                        ft.OutlinedButton(
                            "Copy OPX",
                            icon=ft.Icons.CONTENT_COPY,
                            on_click=lambda _: self._copy_opx(entry),
                            style=ft.ButtonStyle(
                                color=ThemeColors.TEXT_PRIMARY,
                                side=ft.BorderSide(1, ThemeColors.BORDER),
                            ),
                        ),
                        ft.ElevatedButton(
                            "Re-apply",
                            icon=ft.Icons.REPLAY,
                            on_click=lambda _: self._reapply_opx(entry),
                            style=ft.ButtonStyle(
                                color="#FFFFFF",
                                bgcolor=ThemeColors.PRIMARY,
                            ),
                        ),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=ThemeColors.ERROR,
                            tooltip="Delete entry",
                            on_click=lambda _: self._delete_entry(entry.id),
                        ),
                    ],
                    spacing=8,
                ),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        self.page.update()

    def _copy_opx(self, entry: HistoryEntry):
        """Copy OPX content to clipboard"""
        success, message = copy_to_clipboard(entry.opx_content)

        if success:
            self._show_status("OPX copied to clipboard!")
        else:
            self._show_status(f"Copy failed: {message}", is_error=True)

    def _reapply_opx(self, entry: HistoryEntry):
        """Re-apply OPX (chuyển sang Apply tab với OPX đã fill)"""
        if self.on_reapply:
            self.on_reapply(entry.opx_content)
            self._show_status("OPX loaded to Apply tab")

    def _delete_entry(self, entry_id: str):
        """Xóa một entry"""
        assert self.detail_container is not None
        if delete_entry(entry_id):
            self.selected_entry_id = None
            self.detail_container.content = ft.Text(
                "Entry deleted",
                color=ThemeColors.TEXT_MUTED,
                italic=True,
            )
            self._refresh()
            self._show_status("Entry deleted")
        else:
            self._show_status("Failed to delete entry", is_error=True)

    def _confirm_clear_all(self):
        """Show confirmation dialog before clearing all"""

        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def confirm_clear(e):
            dialog.open = False
            self.page.update()
            self._clear_all()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Clear All History?", weight=ft.FontWeight.W_600),
            content=ft.Text(
                "This will permanently delete all history entries. This action cannot be undone.",
                color=ThemeColors.TEXT_SECONDARY,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton(
                    "Clear All",
                    on_click=confirm_clear,
                    style=ft.ButtonStyle(
                        color="#FFFFFF",
                        bgcolor=ThemeColors.ERROR,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _clear_all(self):
        """Xóa toàn bộ lịch sử"""
        assert self.detail_container is not None
        if clear_history():
            self.selected_entry_id = None
            self.detail_container.content = ft.Text(
                "Select an entry to view details",
                color=ThemeColors.TEXT_MUTED,
                italic=True,
            )
            self._refresh()
            self._show_status("History cleared")
        else:
            self._show_status("Failed to clear history", is_error=True)

    def _show_status(self, message: str, is_error: bool = False):
        """Hiển thị status message"""
        assert self.status_text is not None
        self.status_text.value = message
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self.page.update()
