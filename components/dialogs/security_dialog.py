"""
Security Dialog - Shows warning when secrets are detected.
"""

import flet as ft
from pathlib import Path
from typing import Callable, List

from components.dialogs.base_dialog import BaseDialog
from components.file_preview import FilePreviewDialog
from core.theme import ThemeColors
from core.security_check import SecretMatch, format_security_warning
from core.utils.ui_utils import safe_page_update
from services.clipboard_utils import copy_to_clipboard


class SecurityDialog(BaseDialog):
    """Dialog shown when potential secrets are detected in content."""
    
    def __init__(
        self,
        page: ft.Page,
        prompt: str,
        matches: List[SecretMatch],
        on_copy_anyway: Callable[[str], None],
    ):
        super().__init__(page)
        self.prompt = prompt
        self.matches = matches
        self.on_copy_anyway = on_copy_anyway
        self._build()
    
    def _build(self):
        """Build the dialog UI."""
        warning_message = format_security_warning(self.matches)
        
        # Build details list
        details_col = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            height=200,
            spacing=4,
            width=500,
        )
        
        for match in self.matches:
            display_name = Path(match.file_path).name if match.file_path else ""
            file_info = f" in {display_name}" if display_name else ""
            
            item_container = self._build_match_item(match, file_info)
            
            if match.file_path:
                clickable = ft.GestureDetector(
                    content=ft.Container(content=item_container, ink=True),
                    on_tap=self._make_preview_handler(match.file_path, match.line_number),
                    mouse_cursor=ft.MouseCursor.CLICK,
                )
                details_col.controls.append(clickable)
            else:
                details_col.controls.append(item_container)
        
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ThemeColors.WARNING),
                ft.Text("Security Warning", weight=ft.FontWeight.BOLD, color=ThemeColors.WARNING),
            ]),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(warning_message, size=14, color=ThemeColors.TEXT_PRIMARY),
                    ft.Container(height=8),
                    ft.Text("Details:", size=12, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=details_col,
                        border=ft.border.all(1, ThemeColors.BORDER),
                        border_radius=4,
                        padding=4,
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        "Please review your content before sharing with AI tools.",
                        size=12,
                        color=ThemeColors.TEXT_SECONDARY,
                        italic=True,
                    ),
                ], tight=True),
                width=550,
            ),
            actions=[
                self.secondary_button("Cancel", self.close),
                self.outlined_button("Copy Results", ft.Icons.BUG_REPORT, self._copy_results),
                ft.ElevatedButton(
                    "Copy Anyway",
                    on_click=self._copy_anyway_click,
                    style=ft.ButtonStyle(color="#FFFFFF", bgcolor=ThemeColors.WARNING),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    
    def _build_match_item(self, match: SecretMatch, file_info: str) -> ft.Container:
        """Build a single match item container."""
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.SECURITY, size=14, color=ThemeColors.WARNING),
                    ft.Text(f"{match.secret_type}", size=12, weight=ft.FontWeight.W_600),
                    ft.Text(
                        f"{file_info} (Line {match.line_number})",
                        size=12,
                        color=ThemeColors.TEXT_SECONDARY,
                    ),
                ], spacing=6),
                ft.Text(
                    f"Value: {match.redacted_preview}",
                    size=11,
                    color=ThemeColors.TEXT_SECONDARY,
                    font_family="monospace",
                    italic=True,
                ),
            ], spacing=2),
            bgcolor=ThemeColors.BG_SURFACE,
            padding=6,
            border_radius=4,
        )
    
    def _make_preview_handler(self, file_path: str, line_num: int):
        """Create handler to open file preview."""
        def handler(e):
            self.close()
            FilePreviewDialog.show(
                page=self.page,
                file_path=file_path,
                highlight_line=line_num,
            )
        return handler
    
    def _copy_results(self, e):
        """Copy scan results to clipboard."""
        import json
        results_data = [
            {
                "type": m.secret_type,
                "file": m.file_path or "N/A",
                "line": m.line_number,
                "preview": m.redacted_preview,
            }
            for m in self.matches
        ]
        copy_to_clipboard(json.dumps(results_data, indent=2, ensure_ascii=False))
    
    def _copy_anyway_click(self, e):
        """Handle copy anyway button."""
        self.close()
        self.on_copy_anyway(self.prompt)