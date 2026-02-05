"""
Base Dialog - Common dialog utilities and patterns.
"""

import flet as ft
from typing import Optional, Callable
from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update


class BaseDialog:
    """Base class for dialog components with common utilities."""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.dialog: Optional[ft.AlertDialog] = None
    
    def show(self):
        """Show the dialog."""
        if self.dialog:
            self.page.overlay.append(self.dialog)
            self.dialog.open = True
            safe_page_update(self.page)
    
    def close(self, e=None):
        """Close the dialog."""
        if self.dialog:
            self.dialog.open = False
            safe_page_update(self.page)
    
    @staticmethod
    def create_status_text() -> ft.Text:
        """Create a status text control."""
        return ft.Text("", size=12, color=ThemeColors.TEXT_SECONDARY)
    
    @staticmethod
    def create_progress_ring() -> ft.ProgressRing:
        """Create a progress ring control."""
        return ft.ProgressRing(
            width=20,
            height=20,
            stroke_width=2,
            color=ThemeColors.PRIMARY,
            visible=False,
        )
    
    @staticmethod
    def primary_button(text: str, icon: str, on_click: Callable) -> ft.ElevatedButton:
        """Create a primary elevated button."""
        return ft.ElevatedButton(
            text,
            icon=icon,
            on_click=on_click,
            style=ft.ButtonStyle(
                color="#FFFFFF",
                bgcolor=ThemeColors.PRIMARY,
            ),
        )
    
    @staticmethod
    def secondary_button(text: str, on_click: Callable) -> ft.TextButton:
        """Create a secondary text button."""
        return ft.TextButton(
            text,
            on_click=on_click,
            style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY),
        )
    
    @staticmethod
    def outlined_button(
        text: str, 
        icon: Optional[str] = None,
        on_click: Optional[Callable] = None,
        color: str = ThemeColors.TEXT_SECONDARY,
    ) -> ft.OutlinedButton:
        """Create an outlined button."""
        return ft.OutlinedButton(
            text,
            icon=icon,
            on_click=on_click,
            style=ft.ButtonStyle(
                color=color,
                side=ft.BorderSide(1, color),
            ),
        )