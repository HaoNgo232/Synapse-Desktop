"""
Dirty Repo Dialog - Handle uncommitted changes before update.
"""

import flet as ft
import threading
from pathlib import Path
from typing import Callable

from components.dialogs.base_dialog import BaseDialog
from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update
from core.utils.repo_manager import RepoManager


class DirtyRepoDialog(BaseDialog):
    """Dialog shown when repo has uncommitted changes."""
    
    def __init__(
        self,
        page: ft.Page,
        repo_manager: RepoManager,
        repo_path: Path,
        repo_name: str,
        status_text: ft.Text,
        refresh_callback: Callable[[], None],
    ):
        super().__init__(page)
        self.repo_manager = repo_manager
        self.repo_path = repo_path
        self.repo_name = repo_name
        self.status_text = status_text
        self.refresh_callback = refresh_callback
        self._build()
    
    def _build(self):
        """Build the dialog UI."""
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Uncommitted Changes", weight=ft.FontWeight.BOLD, color=ThemeColors.WARNING),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        f"Repository '{self.repo_name}' has uncommitted local changes.",
                        color=ThemeColors.TEXT_PRIMARY,
                    ),
                    ft.Container(height=8),
                    ft.Text("What would you like to do?", size=13, color=ThemeColors.TEXT_SECONDARY),
                ], tight=True),
                width=400,
            ),
            actions=[
                self.secondary_button("Cancel", self.close),
                self.outlined_button("Discard & Pull", ft.Icons.DELETE_FOREVER, self._discard_and_pull, ThemeColors.ERROR),
                self.outlined_button("Stash & Pull", ft.Icons.SAVE, self._stash_and_pull, ThemeColors.SUCCESS),
            ],
        )
    
    def _stash_and_pull(self, e):
        """Stash changes and pull."""
        self.close()
        self.status_text.value = f"Stashing changes in {self.repo_name}..."
        self.status_text.color = ThemeColors.PRIMARY
        safe_page_update(self.page)
        
        def do_stash_pull():
            try:
                if not self.repo_manager.stash_changes(self.repo_path):
                    self.status_text.value = f"Failed to stash changes in {self.repo_name}"
                    self.status_text.color = ThemeColors.ERROR
                    safe_page_update(self.page)
                    return
                
                self.repo_manager._update_repo(self.repo_path, None, None)
                self.status_text.value = f"Updated {self.repo_name} (changes stashed)"
                self.status_text.color = ThemeColors.SUCCESS
            except Exception as ex:
                self.status_text.value = f"Update failed: {ex}"
                self.status_text.color = ThemeColors.ERROR
            self.refresh_callback()
            safe_page_update(self.page)
        
        threading.Thread(target=do_stash_pull, daemon=True).start()
    
    def _discard_and_pull(self, e):
        """Show confirmation then discard changes and pull."""
        def confirm_discard(e):
            confirm_dialog.open = False
            self.dialog.open = False
            safe_page_update(self.page)
            
            self.status_text.value = f"Discarding changes in {self.repo_name}..."
            self.status_text.color = ThemeColors.WARNING
            safe_page_update(self.page)
            
            def do_discard_pull():
                try:
                    if not self.repo_manager.discard_changes(self.repo_path):
                        self.status_text.value = f"Failed to discard changes in {self.repo_name}"
                        self.status_text.color = ThemeColors.ERROR
                        safe_page_update(self.page)
                        return
                    
                    self.repo_manager._update_repo(self.repo_path, None, None)
                    self.status_text.value = f"Updated {self.repo_name} (changes discarded)"
                    self.status_text.color = ThemeColors.SUCCESS
                except Exception as ex:
                    self.status_text.value = f"Update failed: {ex}"
                    self.status_text.color = ThemeColors.ERROR
                self.refresh_callback()
                safe_page_update(self.page)
            
            threading.Thread(target=do_discard_pull, daemon=True).start()
        
        def cancel_confirm(e):
            confirm_dialog.open = False
            safe_page_update(self.page)
        
        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm Discard", weight=ft.FontWeight.BOLD, color=ThemeColors.ERROR),
            content=ft.Text(
                f"Are you sure you want to PERMANENTLY DELETE all local changes in '{self.repo_name}'?\n\n"
                "This action CANNOT BE UNDONE!",
                color=ThemeColors.TEXT_PRIMARY,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_confirm),
                ft.TextButton(
                    "Discard & Pull",
                    on_click=confirm_discard,
                    style=ft.ButtonStyle(color=ThemeColors.ERROR),
                ),
            ],
        )
        self.page.overlay.append(confirm_dialog)
        confirm_dialog.open = True
        safe_page_update(self.page)