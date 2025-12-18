"""
Overwrite Desktop - Main Application Entry Point

Flet-based desktop app ke thua tinh nang Copy Context va OPX Apply
tu Overwrite VS Code extension.
"""

import flet as ft
from pathlib import Path
from typing import Optional

from views.context_view import ContextView
from views.apply_view import ApplyView
from views.settings_view import SettingsView


class OverwriteApp:
    """Main application class"""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.workspace_path: Optional[Path] = None
        
        # Configure page
        self.page.title = "Overwrite Desktop"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        
        # Minimum window size
        self.page.window.min_width = 800
        self.page.window.min_height = 600
        self.page.window.width = 1100
        self.page.window.height = 750
        
        # Build UI
        self._build_ui()
    
    def _build_ui(self):
        """Xay dung giao dien chinh"""
        
        # Header voi folder picker
        self.folder_path_text = ft.Text(
            "No folder selected",
            size=14,
            color=ft.Colors.GREY_400,
            expand=True,
            overflow=ft.TextOverflow.ELLIPSIS
        )
        
        folder_picker = ft.FilePicker(on_result=self._on_folder_picked)
        self.page.overlay.append(folder_picker)
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.FOLDER_OPEN, color=ft.Colors.BLUE_400),
                self.folder_path_text,
                ft.ElevatedButton(
                    "Open Folder",
                    icon=ft.Icons.FOLDER,
                    on_click=lambda _: folder_picker.get_directory_path(
                        dialog_title="Select Workspace Folder"
                    )
                )
            ], spacing=10),
            padding=15,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
        )
        
        # Views
        self.context_view = ContextView(self.page, self._get_workspace_path)
        self.apply_view = ApplyView(self.page, self._get_workspace_path)
        self.settings_view = SettingsView(self.page, self._on_settings_changed)
        
        # Tabs
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
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
                ft.Divider(height=1, color=ft.Colors.GREY_800),
                tabs
            ], spacing=0, expand=True)
        )
    
    def _on_folder_picked(self, e: ft.FilePickerResultEvent):
        """Xu ly khi user chon folder"""
        if e.path:
            self.workspace_path = Path(e.path)
            self.folder_path_text.value = str(self.workspace_path)
            self.folder_path_text.color = ft.Colors.WHITE
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

