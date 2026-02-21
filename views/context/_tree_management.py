"""
Tree Management Mixin cho ContextViewQt.

Chua logic quan ly file tree, file watcher callbacks, va ignore patterns.
"""

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from PySide6.QtCore import Slot

from core.utils.qt_utils import run_on_main_thread

if TYPE_CHECKING:
    from views.context_view_qt import ContextViewQt
    from core.utils.repo_manager import RepoManager


class TreeManagementMixin:
    """Mixin chua tree management methods cho ContextViewQt.

    Note: All instance attributes are initialized in ContextViewQt.__init__,
    not here. Class-level annotations are for documentation/type-checking only.
    """

    _repo_manager: Optional["RepoManager"]
    _last_ignored_patterns: List[str]

    @Slot()
    def _refresh_tree(self: "ContextViewQt") -> None:
        """Refresh file tree."""
        workspace = self.get_workspace()
        if workspace:
            self.file_tree_widget.load_tree(workspace)

    def _add_to_ignore(self: "ContextViewQt") -> None:
        """Add selected to ignore list."""
        selected = self.file_tree_widget.get_all_selected_paths()
        if not selected:
            self._show_status("No files selected", is_error=True)
            return

        workspace = self.get_workspace()
        if not workspace:
            return

        from services.workspace_config import add_excluded_patterns

        patterns = []
        for p in selected:
            try:
                rel = Path(p).relative_to(workspace)
                # Use full relative path for gitignore-style matching
                patterns.append(str(rel))
            except ValueError:
                continue

        unique = list(set(patterns))
        if unique and add_excluded_patterns(unique):
            self._last_ignored_patterns = unique
            self._show_status(f"Added {len(unique)} pattern(s). Click Undo to revert.")
            self._refresh_tree()

    def _undo_ignore(self: "ContextViewQt") -> None:
        """Undo last ignore."""
        if not self._last_ignored_patterns:
            self._show_status("Nothing to undo", is_error=True)
            return

        from services.workspace_config import remove_excluded_patterns

        if remove_excluded_patterns(self._last_ignored_patterns):
            self._show_status(f"Removed {len(self._last_ignored_patterns)} pattern(s)")
            self._last_ignored_patterns = []
            self._refresh_tree()

    @Slot(str)
    def _preview_file(self: "ContextViewQt", file_path: str) -> None:
        """Preview file in dialog."""
        from components.dialogs_qt import FilePreviewDialogQt

        FilePreviewDialogQt.show_preview(self, file_path)

    def _open_remote_repo_dialog(self: "ContextViewQt") -> None:
        """Open remote repo clone dialog."""
        from core.utils.repo_manager import RepoManager
        from components.dialogs_qt import RemoteRepoDialogQt

        if self._repo_manager is None:
            self._repo_manager = RepoManager()

        def on_clone_success(repo_path):
            """Handle successful clone — open the cloned repo as workspace."""
            self._show_status(f"Cloned to {repo_path}")
            self.on_workspace_changed(repo_path)

        dialog = RemoteRepoDialogQt(self, self._repo_manager, on_clone_success)
        dialog.exec()

    def _open_cache_management_dialog(self: "ContextViewQt") -> None:
        """Open cache management dialog for cloned repos."""
        from core.utils.repo_manager import RepoManager
        from components.dialogs_qt import CacheManagementDialogQt

        if self._repo_manager is None:
            self._repo_manager = RepoManager()

        def on_open_repo(repo_path):
            """Handle opening a cached repo."""
            self.on_workspace_changed(repo_path)

        dialog = CacheManagementDialogQt(self, self._repo_manager, on_open_repo)
        dialog.exec()

    def _on_file_modified(self: "ContextViewQt", path: str) -> None:
        """Handle file modified — invalidate tat ca caches qua CacheRegistry."""
        from services.cache_registry import cache_registry

        cache_registry.invalidate_for_path(path)
        # Prompt cache la instance-level (khong nam trong registry)
        # nen phai invalidate rieng
        self._prompt_cache.invalidate_all()

    def _on_file_created(self: "ContextViewQt", path: str) -> None:
        """Handle file created — no cache invalidation needed for new files."""

    def _on_file_deleted(self: "ContextViewQt", path: str) -> None:
        """Handle file deleted — delegates to _on_file_modified for cache cleanup."""
        self._on_file_modified(path)

    def _on_file_system_changed(self: "ContextViewQt") -> None:
        """Handle batch file system changes."""
        workspace = self.get_workspace()
        if workspace:
            run_on_main_thread(lambda: self._refresh_tree())
