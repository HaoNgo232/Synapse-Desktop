"""
Remote Repo Dialog - Clone GitHub repositories.
"""

import flet as ft
import threading
from pathlib import Path
from typing import Callable, Optional

from components.dialogs.base_dialog import BaseDialog
from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update
from core.utils.repo_manager import RepoManager, CloneProgress


class RemoteRepoDialog(BaseDialog):
    """Dialog for cloning remote GitHub repositories."""
    
    def __init__(
        self,
        page: ft.Page,
        repo_manager: RepoManager,
        on_clone_success: Callable[[Path], None],
    ):
        super().__init__(page)
        self.repo_manager = repo_manager
        self.on_clone_success = on_clone_success
        self._build()
    
    def _build(self):
        """Build the dialog UI."""
        self.url_field = ft.TextField(
            label="GitHub URL",
            hint_text="owner/repo or https://github.com/owner/repo",
            autofocus=True,
            expand=True,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            label_style=ft.TextStyle(color=ThemeColors.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY),
        )
        
        self.progress_ring = self.create_progress_ring()
        self.status_text = self.create_status_text()
        
        self.clone_button = ft.ElevatedButton(
            "Clone",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_clone_click,
            style=ft.ButtonStyle(color="#FFFFFF", bgcolor=ThemeColors.PRIMARY),
        )
        
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Open Remote Repository",
                weight=ft.FontWeight.BOLD,
                color=ThemeColors.TEXT_PRIMARY,
            ),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Enter GitHub URL or shorthand (owner/repo) to clone repository.",
                        size=13,
                        color=ThemeColors.TEXT_SECONDARY,
                    ),
                    ft.Container(height=12),
                    self.url_field,
                    ft.Container(height=8),
                    ft.Row([self.progress_ring, self.status_text], spacing=8),
                ], tight=True),
                width=450,
                height=180,
            ),
            actions=[
                self.secondary_button("Cancel", self.close),
                self.clone_button,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    
    def _on_clone_click(self, e):
        """Handle clone button click."""
        url = self.url_field.value
        if not url or not url.strip():
            self.status_text.value = "Please enter a GitHub URL"
            self.status_text.color = ThemeColors.ERROR
            safe_page_update(self.page)
            return
        
        self.progress_ring.visible = True
        self.clone_button.disabled = True
        self.status_text.value = "Cloning..."
        self.status_text.color = ThemeColors.TEXT_SECONDARY
        safe_page_update(self.page)
        
        def do_clone():
            try:
                def on_progress(progress: CloneProgress):
                    self.status_text.value = progress.status
                    if progress.percentage is not None:
                        self.status_text.value += f" ({progress.percentage}%)"
                    safe_page_update(self.page)
                
                repo_path = self.repo_manager.clone_repo(url.strip(), on_progress=on_progress)
                
                def switch_workspace():
                    self.close()
                    self.on_clone_success(repo_path)
                
                self.page.run_thread(switch_workspace)
                
            except Exception as ex:
                error_msg = str(ex)
                
                def show_error():
                    self.progress_ring.visible = False
                    self.clone_button.disabled = False
                    self.status_text.value = error_msg
                    self.status_text.color = ThemeColors.ERROR
                    safe_page_update(self.page)
                
                self.page.run_thread(show_error)
        
        threading.Thread(target=do_clone, daemon=True).start()