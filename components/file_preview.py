"""
File Preview Dialog - Component để preview nội dung file

Reusable dialog component có thể sử dụng ở nhiều views.
Ported pattern từ PasteMax FilePreviewModal.
"""

import flet as ft
from pathlib import Path
from typing import Optional

from core.theme import ThemeColors
from core.utils.language_utils import get_language_from_path
from core.utils.file_utils import is_binary_by_extension


class FilePreviewDialog:
    """
    Reusable File Preview Dialog.

    Hiển thị nội dung file trong modal dialog với:
    - Syntax highlighting hint (dựa trên extension)
    - Line numbers
    - Scrollable content
    - Copy button
    - ESC để đóng

    Usage:
        FilePreviewDialog.show(page, file_path)
    """

    # Giới hạn kích thước file để preview (1MB)
    MAX_PREVIEW_SIZE = 1024 * 1024

    # Số dòng tối đa hiển thị
    MAX_LINES = 5000

    @staticmethod
    def show(
        page: ft.Page,
        file_path: str,
        content: Optional[str] = None,
        highlight_line: Optional[int] = None,
    ) -> None:
        """
        Hiển thị preview dialog cho một file.

        Args:
            page: Flet page instance
            file_path: Đường dẫn đến file cần preview
            content: Optional - nội dung file (nếu đã đọc sẵn)
            highlight_line: Optional - số dòng cần highlight và auto-scroll (1-indexed)
        """
        path = Path(file_path)
        file_name = path.name

        # Kiểm tra file có tồn tại không
        if not path.exists():
            FilePreviewDialog._show_error(page, file_name, "File not found")
            return

        # Kiểm tra binary file
        if is_binary_by_extension(path):
            FilePreviewDialog._show_error(
                page,
                file_name,
                "Cannot preview binary file.\nThis file type is not supported for text preview.",
            )
            return

        # Kiểm tra kích thước file
        try:
            file_size = path.stat().st_size
            if file_size > FilePreviewDialog.MAX_PREVIEW_SIZE:
                size_mb = file_size / (1024 * 1024)
                FilePreviewDialog._show_error(
                    page,
                    file_name,
                    f"File too large to preview.\nSize: {size_mb:.1f} MB (max: 1 MB)",
                )
                return
        except OSError as e:
            FilePreviewDialog._show_error(page, file_name, f"Cannot access file: {e}")
            return

        # Đọc nội dung file nếu chưa có
        if content is None:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                FilePreviewDialog._show_error(
                    page, file_name, f"Error reading file: {e}"
                )
                return

        # Giới hạn số dòng
        lines = content.split("\n")
        truncated = False
        if len(lines) > FilePreviewDialog.MAX_LINES:
            lines = lines[: FilePreviewDialog.MAX_LINES]
            truncated = True
            content = "\n".join(lines)

        # Lấy language hint
        language = get_language_from_path(file_path)

        # Tạo và hiển thị dialog
        FilePreviewDialog._show_preview_dialog(
            page=page,
            file_name=file_name,
            file_path=file_path,
            content=content,
            language=language,
            line_count=len(lines),
            truncated=truncated,
            highlight_line=highlight_line,
        )

    @staticmethod
    def _show_preview_dialog(
        page: ft.Page,
        file_name: str,
        file_path: str,
        content: str,
        language: str,
        line_count: int,
        truncated: bool,
        highlight_line: Optional[int] = None,
    ) -> None:
        """Tạo và hiển thị preview dialog với optional line highlighting."""
        from core.utils.ui_utils import safe_page_update

        # Tạo dialog trước, sau đó define close function
        dialog = None  # Will be assigned later

        def close_dialog(e=None):
            """Đóng dialog - pattern giống context_view.py."""
            nonlocal dialog
            if dialog is not None:
                dialog.open = False
                safe_page_update(page)

        def copy_content(e):
            """Copy nội dung file vào clipboard."""
            from services.clipboard_utils import copy_to_clipboard

            copy_to_clipboard(content)
            # Visual feedback
            e.control.text = "Copied!"
            e.control.icon = ft.Icons.CHECK
            safe_page_update(page)
            # Reset sau 2 giây
            import threading

            def reset():
                try:
                    e.control.text = "Copy"
                    e.control.icon = ft.Icons.CONTENT_COPY
                    safe_page_update(page)
                except Exception:
                    pass

            threading.Timer(2.0, reset).start()

        def copy_path(e):
            """Copy đường dẫn file vào clipboard."""
            from services.clipboard_utils import copy_to_clipboard

            copy_to_clipboard(file_path)
            # Visual feedback
            e.control.icon = ft.Icons.CHECK
            safe_page_update(page)
            import threading

            def reset():
                try:
                    e.control.icon = ft.Icons.CONTENT_COPY
                    safe_page_update(page)
                except Exception:
                    pass

            threading.Timer(1.5, reset).start()

        # Tạo line numbers
        lines = content.split("\n")
        line_numbers = "\n".join(str(i + 1) for i in range(len(lines)))

        # Header với file info
        header = ft.Row(
            [
                ft.Icon(ft.Icons.INSERT_DRIVE_FILE, color=ThemeColors.PRIMARY, size=20),
                ft.Text(
                    file_name,
                    weight=ft.FontWeight.BOLD,
                    size=14,
                    color=ThemeColors.TEXT_PRIMARY,
                    expand=True,
                ),
                ft.Text(
                    f"{language} • {line_count} lines",
                    size=12,
                    color=ThemeColors.TEXT_SECONDARY,
                ),
                ft.IconButton(
                    icon=ft.Icons.CONTENT_COPY,
                    icon_size=16,
                    icon_color=ThemeColors.TEXT_SECONDARY,
                    tooltip="Copy file path",
                    on_click=copy_path,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
        )

        # Content area với line numbers - cả 2 cột scroll cùng nhau
        content_row = ft.Row(
            [
                # Line numbers column
                ft.Container(
                    content=ft.Text(
                        line_numbers,
                        size=12,
                        color=ThemeColors.TEXT_MUTED,
                        font_family="monospace",
                    ),
                    padding=ft.padding.only(right=12),
                    border=ft.border.only(right=ft.BorderSide(1, ThemeColors.BORDER)),
                ),
                # Code content
                ft.Text(
                    content,
                    size=12,
                    color=ThemeColors.TEXT_PRIMARY,
                    font_family="monospace",
                    selectable=True,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        # Scrollable container - scroll cả Row (line numbers + content)
        scroll_container = ft.Container(
            content=ft.Column(
                [content_row],
                scroll=ft.ScrollMode.AUTO,  # Scroll được đặt ở đây
            ),
            bgcolor=ThemeColors.BG_SURFACE,
            padding=16,
            border_radius=4,
            border=ft.border.all(1, ThemeColors.BORDER),
            height=400,
        )

        # Warning nếu truncated
        truncation_warning = None
        if truncated:
            truncation_warning = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.WARNING_AMBER, color=ThemeColors.WARNING, size=16
                        ),
                        ft.Text(
                            f"Showing first {FilePreviewDialog.MAX_LINES} lines only",
                            size=12,
                            color=ThemeColors.WARNING,
                        ),
                    ],
                    spacing=8,
                ),
                padding=ft.padding.only(top=8),
            )

        # Highlight info nếu có
        highlight_info = None
        if highlight_line is not None and 1 <= highlight_line <= len(lines):
            highlight_info = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.WARNING_AMBER, color=ThemeColors.WARNING, size=16
                        ),
                        ft.Text(
                            f"Security issue found at line {highlight_line}",
                            size=12,
                            color=ThemeColors.WARNING,
                            weight=ft.FontWeight.W_600,
                        ),
                    ],
                    spacing=8,
                ),
                bgcolor="#422006",  # Dark amber background
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=4,
                margin=ft.margin.only(bottom=8),
            )

        # Main content column - scroll_container đã có height, không duplicate
        content_column = ft.Column(
            [
                header,
                ft.Container(height=12),
            ]
            + ([highlight_info] if highlight_info else [])
            + [scroll_container]
            + ([truncation_warning] if truncation_warning else []),
            tight=True,
        )

        # Tạo dialog - KHÔNG có on_dismiss để tránh conflict
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("File Preview", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=content_column,
                width=800,
                height=500,
            ),
            actions=[
                ft.TextButton(
                    "Close",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY),
                ),
                ft.OutlinedButton(
                    "Copy",
                    icon=ft.Icons.CONTENT_COPY,
                    on_click=copy_content,
                    style=ft.ButtonStyle(
                        color=ThemeColors.PRIMARY,
                        side=ft.BorderSide(1, ThemeColors.PRIMARY),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # Hiển thị dialog
        page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(page)

    @staticmethod
    def _show_error(page: ft.Page, file_name: str, message: str) -> None:
        """Hiển thị error dialog."""
        from core.utils.ui_utils import safe_page_update

        dialog = None

        def close_dialog(e=None):
            nonlocal dialog
            if dialog is not None:
                dialog.open = False
                safe_page_update(page)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ThemeColors.ERROR, size=24),
                    ft.Text(
                        f"Cannot Preview: {file_name}",
                        weight=ft.FontWeight.BOLD,
                        color=ThemeColors.ERROR,
                    ),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Text(
                    message,
                    size=14,
                    color=ThemeColors.TEXT_PRIMARY,
                ),
                width=400,
                padding=16,
            ),
            actions=[
                ft.TextButton(
                    "Close",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(page)
