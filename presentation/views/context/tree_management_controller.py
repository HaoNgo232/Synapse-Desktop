"""
TreeManagementController - Controller quan ly file tree operations.

Thay the TreeManagementMixin bang composition pattern.
Controller nhan ViewProtocol thay vi ke thua truc tiep, giup tach biet logic
khoi UI va de dang test hon.

Xu ly:
- Refresh file tree
- Them/xoa ignore patterns
- File watcher callbacks (invalidate cache khi file thay doi)
- Remote repo clone dialog
- Cache management dialog
"""

from pathlib import Path
from typing import Protocol, List, Optional, Set, runtime_checkable

from PySide6.QtCore import QObject

from infrastructure.adapters.qt_utils import run_on_main_thread


@runtime_checkable
class TreeManagementViewProtocol(Protocol):
    """
    Protocol dinh nghia nhung gi TreeManagementController can tu View.

    View phai implement tat ca cac methods nay.
    """

    def get_workspace(self) -> "Path | None":
        """Tra ve workspace path hien tai."""
        ...

    def get_all_selected_paths(self) -> Set[str]:
        """Tra ve tat ca selected paths."""
        ...

    def get_expanded_paths(self) -> List[str]:
        """Tra ve danh sach cac folder dang expanded."""
        ...

    def load_tree(self, workspace: Path) -> None:
        """Reload file tree cho workspace."""
        ...

    def restore_tree_state(
        self, selected_files: List[str], expanded_folders: List[str]
    ) -> None:
        """Restore selection va expanded state sau khi reload tree."""
        ...

    def on_workspace_changed(self, workspace_path: Path) -> None:
        """Xu ly khi workspace thay doi (vi du: sau khi clone)."""
        ...

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Hien thi status message."""
        ...

    def invalidate_prompt_cache(self) -> None:
        """Invalidate prompt-level cache do view so huu."""
        ...


class TreeManagementController(QObject):
    """
    Controller quan ly file tree, file watcher callbacks, va ignore patterns.

    Thay the TreeManagementMixin:
    - Encapsulate toan bo state (repo_manager, last_ignored_patterns)
    - Nhan ViewProtocol qua constructor (khong ke thua)
    - QObject de co the su dung Slot decorator cho signal connections

    Thread Safety:
    - _on_file_modified, _on_file_created, _on_file_deleted co the duoc goi
      tu background threads. Cac method nay su dung run_on_main_thread()
      khi can update UI.
    """

    def __init__(
        self, view: TreeManagementViewProtocol, parent: Optional[QObject] = None
    ) -> None:
        """
        Khoi tao controller.

        Args:
            view: View implement TreeManagementViewProtocol (typically ContextViewQt)
            parent: QObject parent de quan ly lifecycle
        """
        super().__init__(parent)
        self._view = view

        # State
        self._repo_manager = None  # Lazy initialized
        self._last_ignored_patterns: List[str] = []

    # ===== Public API =====

    def refresh_tree(self) -> None:
        """Refresh file tree tu workspace hien tai.

        Save/Restore pattern: Luu selection + expanded state truoc khi
        rebuild tree, restore lai sau do. Dam bao user khong mat
        trang thai khi FileWatcher trigger refresh.
        """
        workspace = self._view.get_workspace()
        if not workspace:
            return

        # Luu state truoc khi rebuild
        saved_selection = list(self._view.get_all_selected_paths())
        saved_expanded = self._view.get_expanded_paths()

        # Rebuild tree tu filesystem
        self._view.load_tree(workspace)

        # Restore state da luu (chi restore paths con ton tai tren disk)
        if saved_selection or saved_expanded:
            self._view.restore_tree_state(saved_selection, saved_expanded)

    def add_to_ignore(self) -> None:
        """Them cac selected files/folders vao ignore list."""
        selected = self._view.get_all_selected_paths()
        if not selected:
            self._view.show_status("No files selected", is_error=True)
            return

        workspace = self._view.get_workspace()
        if not workspace:
            return

        from application.services.workspace_config import add_excluded_patterns

        patterns = []
        for p in selected:
            try:
                rel = Path(p).relative_to(workspace)
                # Dung full relative path cho gitignore-style matching
                patterns.append(str(rel))
            except ValueError:
                continue

        unique = list(set(patterns))
        if unique and add_excluded_patterns(unique):
            self._last_ignored_patterns = unique
            self._view.show_status(
                f"Added {len(unique)} pattern(s). Click Undo to revert."
            )
            self.refresh_tree()

    def undo_ignore(self) -> None:
        """Hoan tac thao tac ignore cuoi cung."""
        if not self._last_ignored_patterns:
            self._view.show_status("Nothing to undo", is_error=True)
            return

        from application.services.workspace_config import remove_excluded_patterns

        if remove_excluded_patterns(self._last_ignored_patterns):
            self._view.show_status(
                f"Removed {len(self._last_ignored_patterns)} pattern(s)"
            )
            self._last_ignored_patterns = []
            self.refresh_tree()

    def open_remote_repo_dialog(self, parent_widget) -> None:
        """Mo dialog clone remote repository."""
        from infrastructure.git.repo_manager import RepoManager
        from presentation.components.dialogs.dialogs_qt import RemoteRepoDialogQt

        if self._repo_manager is None:
            self._repo_manager = RepoManager()

        def on_clone_success(repo_path):
            """Handle clone thanh cong — mo cloned repo lam workspace."""
            self._view.show_status(f"Cloned to {repo_path}")
            self._view.on_workspace_changed(repo_path)

        dialog = RemoteRepoDialogQt(parent_widget, self._repo_manager, on_clone_success)
        dialog.exec()

    def open_cache_management_dialog(self, parent_widget) -> None:
        """Mo dialog quan ly cached repos."""
        from infrastructure.git.repo_manager import RepoManager
        from presentation.components.dialogs.dialogs_qt import CacheManagementDialogQt

        if self._repo_manager is None:
            self._repo_manager = RepoManager()

        def on_open_repo(repo_path):
            """Handle mo cached repo."""
            self._view.on_workspace_changed(repo_path)

        dialog = CacheManagementDialogQt(
            parent_widget, self._repo_manager, on_open_repo
        )
        dialog.exec()

    def cleanup(self) -> None:
        """Cleanup resources khi view bi dong."""
        self._last_ignored_patterns.clear()
        self._repo_manager = None

    # ===== File Watcher Callbacks =====
    # Cac method nay co the bi goi tu background thread, them run_on_main_thread()
    # khi can update UI.

    def on_file_modified(self, path: str) -> None:
        """
        Xu ly khi file bi thay doi.

        Invalidate cac cache lien quan den file nay.
        Thread-safe: co the goi tu bat ky thread nao.
        """
        from infrastructure.adapters.cache_registry import cache_registry

        cache_registry.invalidate_for_path(path)
        # Prompt cache la instance-level (khong nam trong registry)
        self._view.invalidate_prompt_cache()

        # Notify graph service cho incremental update
        if hasattr(self._view, "_graph_provider") and self._view._graph_provider:
            self._view._graph_provider.on_files_changed([path])

    def on_file_created(self, path: str) -> None:
        """
        Xu ly khi file moi duoc tao.

        Khong can invalidate cache cho files moi.
        """
        # Notify graph service de them file moi vao graph
        if hasattr(self._view, "_graph_provider") and self._view._graph_provider:
            self._view._graph_provider.on_files_changed([path])

    def on_file_deleted(self, path: str) -> None:
        """
        Xu ly khi file bi xoa.

        Delegate sang on_file_modified vi can invalidate cache tuong tu.
        """
        self.on_file_modified(path)

        # Notify graph service de xoa stale edges
        if hasattr(self._view, "_graph_provider") and self._view._graph_provider:
            self._view._graph_provider.on_files_deleted([path])

    def on_file_system_changed(self) -> None:
        """
        Xu ly khi co batch file system changes.

        Refresh tree tren main thread.
        """
        workspace = self._view.get_workspace()
        if workspace:
            run_on_main_thread(self.refresh_tree)
