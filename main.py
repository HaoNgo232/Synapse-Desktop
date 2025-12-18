"""
Overwrite Desktop - Main Application Entry Point

Flet-based desktop app ke thua tinh nang Copy Context va OPX Apply
tu Overwrite VS Code extension.

Theme: Swiss Professional (Light)
"""

import flet as ft
from pathlib import Path
from typing import Optional

from views.context_view import ContextView
from views.apply_view import ApplyView
from views.settings_view import SettingsView


# ============================================================================
# SWISS PROFESSIONAL THEME - Color Constants
# ============================================================================

class ThemeColors:
    """Swiss Professional Light Theme Colors"""
    # Primary
    PRIMARY = "#2563EB"       # Blue 600
    PRIMARY_HOVER = "#1D4ED8" # Blue 700
    
    # Backgrounds
    BG_PAGE = "#F8FAFC"       # Slate 50
    BG_SURFACE = "#FFFFFF"    # White
    BG_ELEVATED = "#F1F5F9"   # Slate 100
    
    # Text
    TEXT_PRIMARY = "#0F172A"   # Slate 900
    TEXT_SECONDARY = "#475569" # Slate 600
    TEXT_MUTED = "#94A3B8"     # Slate 400
    
    # Borders
    BORDER = "#E2E8F0"         # Slate 200
    BORDER_FOCUS = "#2563EB"   # Blue 600
    
    # Status
    SUCCESS = "#10B981"        # Emerald 500
    WARNING = "#F59E0B"        # Amber 500
    ERROR = "#EF4444"          # Red 500
    
    # Icons
    ICON_FOLDER = "#F59E0B"    # Amber 500
    ICON_FILE = "#64748B"      # Slate 500


class OverwriteApp:
    """Main application class"""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.workspace_path: Optional[Path] = None
        
        # Apply Swiss Professional Light Theme
        self._apply_theme()
        
        # Configure page
        self.page.title = "Overwrite Desktop"
        self.page.padding = 0
        
        # Window config
        self.page.window.min_width = 800
        self.page.window.min_height = 600
        self.page.window.width = 1100
        self.page.window.height = 750
        
        # Build UI
        self._build_ui()
    
    def _apply_theme(self):
        """Apply Swiss Professional Light Theme"""
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.bgcolor = ThemeColors.BG_PAGE
        
        self.page.theme = ft.Theme(
            color_scheme_seed=ThemeColors.PRIMARY,
            color_scheme=ft.ColorScheme(
                primary=ThemeColors.PRIMARY,
                on_primary="#FFFFFF",
                secondary=ThemeColors.TEXT_SECONDARY,
                on_secondary="#FFFFFF",
                surface=ThemeColors.BG_SURFACE,
                on_surface=ThemeColors.TEXT_PRIMARY,
                background=ThemeColors.BG_PAGE,
                on_background=ThemeColors.TEXT_PRIMARY,
                error=ThemeColors.ERROR,
                on_error="#FFFFFF",
                outline=ThemeColors.BORDER,
            ),
        )
    
    def _build_ui(self):
        """Xay dung giao dien chinh voi Swiss Professional styling"""
        
        # Header voi folder picker
        self.folder_path_text = ft.Text(
            "No folder selected",
            size=14,
            color=ThemeColors.TEXT_MUTED,
            expand=True,
            overflow=ft.TextOverflow.ELLIPSIS
        )
        
        folder_picker = ft.FilePicker(on_result=self._on_folder_picked)
        self.page.overlay.append(folder_picker)
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.FOLDER_OPEN, color=ThemeColors.PRIMARY, size=20),
                self.folder_path_text,
                ft.ElevatedButton(
                    "Open Folder",
                    icon=ft.Icons.FOLDER,
                    style=ft.ButtonStyle(
                        color="#FFFFFF",
                        bgcolor=ThemeColors.PRIMARY,
                    ),
                    on_click=lambda _: folder_picker.get_directory_path(
                        dialog_title="Select Workspace Folder"
                    )
                )
            ], spacing=12),
            padding=ft.padding.symmetric(horizontal=20, vertical=12),
            bgcolor=ThemeColors.BG_SURFACE,
            border=ft.border.only(bottom=ft.BorderSide(1, ThemeColors.BORDER))
        )
        
        # Views
        self.context_view = ContextView(self.page, self._get_workspace_path)
        self.apply_view = ApplyView(self.page, self._get_workspace_path)
        self.settings_view = SettingsView(self.page, self._on_settings_changed)
        
        # Tabs voi Swiss styling
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            indicator_color=ThemeColors.PRIMARY,
            indicator_tab_size=True,
            label_color=ThemeColors.TEXT_PRIMARY,
            unselected_label_color=ThemeColors.TEXT_SECONDARY,
            divider_color=ThemeColors.BORDER,
            tabs=[
                ft.Tab(
                    text="Context",
                    icon=ft.Icons.CONTENT_COPY,
                    content=self.context_view.build()
                ),
                ft.Tab(
                    text="Apply",
                    icon=ft.Icons.PLAY_ARROW,
                    content=self.apply_view.build()
                ),
                ft.Tab(
                    text="Settings",
                    icon=ft.Icons.SETTINGS,
                    content=self.settings_view.build()
                ),
            ],
            expand=True
        )
        
        # Layout
        self.page.add(
            ft.Column([
                header,
                tabs
            ], spacing=0, expand=True)
        )
    
    def _on_folder_picked(self, e: ft.FilePickerResultEvent):
        """Xu ly khi user chon folder"""
        if e.path:
            self.workspace_path = Path(e.path)
            self.folder_path_text.value = str(self.workspace_path)
            self.folder_path_text.color = ThemeColors.TEXT_PRIMARY
            self.page.update()
            
            # Notify views
            self.context_view.on_workspace_changed(self.workspace_path)
    
    def _on_settings_changed(self):
        """Xu ly khi settings thay doi - refresh file tree"""
        if self.workspace_path:
            self.context_view.on_workspace_changed(self.workspace_path)
    
    def _get_workspace_path(self) -> Optional[Path]:
        """Getter cho workspace path"""
        return self.workspace_path


def main(page: ft.Page):
    """Entry point"""
    OverwriteApp(page)


if __name__ == "__main__":
    ft.app(target=main)
