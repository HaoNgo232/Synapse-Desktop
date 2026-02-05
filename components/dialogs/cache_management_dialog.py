"""
Cache Management Dialog - Manage cloned repositories.
"""

import flet as ft
import threading
from pathlib import Path
from typing import Callable, Optional

from components.dialogs.base_dialog import BaseDialog
from components.dialogs.dirty_repo_dialog import DirtyRepoDialog
from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update
from core.utils.repo_manager import RepoManager, CachedRepo


class CacheManagementDialog(BaseDialog):
    """Dialog for managing cached repositories."""
    
    def __init__(
        self,
        page: ft.Page,
        repo_manager: RepoManager,
        on_open_repo: Callable[[Path], None],
    ):
        super().__init__(page)
        self.repo_manager = repo_manager
        self.on_open_repo = on_open_repo
        self.repo_list: Optional[ft.Column] = None
        self.status_text: Optional[ft.Text] = None
        self._build()
    
    def _build(self):
        """Build the dialog UI."""
        cached_repos = self.repo_manager.get_cached_repos()
        total_size = self.repo_manager.get_cache_size()
        total_size_str = self.repo_manager.format_size(total_size)
        
        self.repo_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8)
        self.status_text = self.create_status_text()
        
        self._refresh_list()
        
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Text(
                    "Cached Repositories",
                    weight=ft.FontWeight.BOLD,
                    color=ThemeColors.TEXT_PRIMARY,
                ),
                ft.Container(expand=True),
                ft.Text(f"Total: {total_size_str}", size=13, color=ThemeColors.TEXT_SECONDARY),
            ]),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        f"Cached repositories: {len(cached_repos)}",
                        size=13,
                        color=ThemeColors.TEXT_SECONDARY,
                    ),
                    ft.Container(height=8),
                    ft.Container(
                        content=self.repo_list,
                        height=400,
                        border=ft.border.all(1, ThemeColors.BORDER),
                        border_radius=4,
                        padding=8,
                    ),
                    ft.Container(height=8),
                    self.status_text,
                ], tight=True),
                width=600,
            ),
            actions=[
                self.secondary_button("Close", self.close),
                self.outlined_button("Clear All", ft.Icons.DELETE_SWEEP, self._clear_all, ThemeColors.ERROR),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
    
    def _refresh_list(self):
        """Refresh the repository list."""
        self.repo_list.controls.clear()
        cached_repos = self.repo_manager.get_cached_repos()
        
        if not cached_repos:
            self.repo_list.controls.append(
                ft.Container(
                    content=ft.Text(
                        "No repositories cloned yet.",
                        size=13,
                        color=ThemeColors.TEXT_SECONDARY,
                        italic=True,
                    ),
                    padding=20,
                    alignment=ft.Alignment(0, 0),
                )
            )
        else:
            for repo in cached_repos:
                self.repo_list.controls.append(self._build_repo_card(repo))
        
        safe_page_update(self.page)
    
    def _build_repo_card(self, repo: CachedRepo) -> ft.Container:
        """Build a card for a single repository."""
        size_str = self.repo_manager.format_size(repo.size_bytes)
        time_str = repo.last_modified.strftime("%Y-%m-%d %H:%M") if repo.last_modified else ""
        
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(repo.name, size=14, weight=ft.FontWeight.W_600, color=ThemeColors.TEXT_PRIMARY),
                    ft.Row([
                        ft.Icon(ft.Icons.FOLDER, size=12, color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(size_str, size=12, color=ThemeColors.TEXT_SECONDARY),
                        ft.Container(width=8),
                        ft.Icon(ft.Icons.ACCESS_TIME, size=12, color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(time_str, size=12, color=ThemeColors.TEXT_SECONDARY),
                    ], spacing=4),
                ], spacing=4, expand=True),
                ft.Row([
                    self.outlined_button("Open", ft.Icons.FOLDER_OPEN, lambda e, p=repo.path: self._open_repo(p), ThemeColors.PRIMARY),
                    ft.IconButton(
                        icon=ft.Icons.SYNC,
                        icon_size=20,
                        icon_color=ThemeColors.SUCCESS,
                        tooltip="Update (git pull)",
                        on_click=lambda e, p=repo.path, n=repo.name: self._update_repo(p, n),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=20,
                        icon_color=ThemeColors.ERROR,
                        tooltip="Delete",
                        on_click=lambda e, n=repo.name: self._delete_repo(n),
                    ),
                ], spacing=8),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=12,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=8,
            bgcolor=ThemeColors.BG_SURFACE,
        )
    
    def _open_repo(self, path: Path):
        """Open a repository."""
        self.close()
        self.on_open_repo(path)
    
    def _delete_repo(self, name: str):
        """Delete a repository."""
        if self.repo_manager.delete_repo(name):
            self.status_text.value = f"Deleted: {name}"
            self.status_text.color = ThemeColors.SUCCESS
            self._refresh_list()
        else:
            self.status_text.value = f"Failed to delete: {name}"
            self.status_text.color = ThemeColors.ERROR
            safe_page_update(self.page)
    
    def _update_repo(self, path: Path, name: str):
        """Update a repository with git pull."""
        git_dir = path / ".git"
        if not git_dir.exists():
            self.status_text.value = f"{name}: No .git, need to delete and reclone"
            self.status_text.color = ThemeColors.WARNING
            safe_page_update(self.page)
            return
        
        if self.repo_manager.is_dirty(path):
            dirty_dialog = DirtyRepoDialog(
                self.page,
                self.repo_manager,
                path,
                name,
                self.status_text,
                self._refresh_list,
            )
            dirty_dialog.show()
        else:
            self.status_text.value = f"Updating {name}..."
            self.status_text.color = ThemeColors.PRIMARY
            safe_page_update(self.page)
            
            def do_update():
                try:
                    self.repo_manager._update_repo(path, None, None)
                    self.status_text.value = f"Updated: {name}"
                    self.status_text.color = ThemeColors.SUCCESS
                except Exception as ex:
                    self.status_text.value = f"Update failed: {ex}"
                    self.status_text.color = ThemeColors.ERROR
                self._refresh_list()
                safe_page_update(self.page)
            
            threading.Thread(target=do_update, daemon=True).start()
    
    def _clear_all(self, e):
        """Clear all cached repositories."""
        count = self.repo_manager.clear_cache()
        self.status_text.value = f"Cleared {count} repositories"
        self.status_text.color = ThemeColors.SUCCESS
        self._refresh_list()