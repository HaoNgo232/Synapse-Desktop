"""
Related Files Mixin cho ContextViewQt.

Chua logic auto-select related files dua tren dependency analysis.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Set

from core.dependency_resolver import DependencyResolver
from core.utils.qt_utils import run_on_main_thread, schedule_background

if TYPE_CHECKING:
    from views.context_view_qt import ContextViewQt


class RelatedFilesMixin:
    """Mixin chua logic related files cho ContextViewQt.

    Note: All instance attributes are initialized in ContextViewQt.__init__,
    not here. Class-level annotations are for documentation/type-checking only.
    """

    _related_mode_active: bool
    _related_depth: int
    _last_added_related_files: Set[str]
    _resolving_related: bool

    def _set_related_mode(self: "ContextViewQt", active: bool, depth: int) -> None:
        """Set related mode with specific depth preset."""
        if active:
            self._related_depth = depth
            self._activate_related_mode()
        else:
            self._deactivate_related_mode()

    def _activate_related_mode(self: "ContextViewQt") -> None:
        """Activate related mode and resolve for current selection."""
        self._related_mode_active = True
        self._update_related_button_text()
        self._resolve_related_files()

    def _deactivate_related_mode(self: "ContextViewQt") -> None:
        """Deactivate related mode and remove auto-added files."""
        if self._last_added_related_files:
            removed = self.file_tree_widget.remove_paths_from_selection(
                self._last_added_related_files
            )
            self._show_status(f"Removed {removed} related files")

        self._last_added_related_files.clear()
        self._related_mode_active = False
        self._related_menu_btn.setText("Related: Off")

    def _update_related_button_text(self: "ContextViewQt") -> None:
        """Update button text based on current depth and count."""
        if not self._related_mode_active:
            self._related_menu_btn.setText("Related: Off")
            return

        depth_names = {1: "Direct", 2: "Nearby", 3: "Deep", 4: "Deeper", 5: "Deepest"}
        depth_name = depth_names.get(
            self._related_depth, f"Depth {self._related_depth}"
        )
        count = len(self._last_added_related_files)

        if count > 0:
            self._related_menu_btn.setText(f"Related: {depth_name} ({count})")
        else:
            self._related_menu_btn.setText(f"Related: {depth_name}")

    def _resolve_related_files(self: "ContextViewQt") -> None:
        """Resolve related files for all currently selected files."""
        workspace = self.get_workspace()
        if not workspace:
            return

        assert workspace is not None  # Type narrowing for pyrefly

        # Get user-selected files only (exclude auto-added related files)
        all_selected = self.file_tree_widget.get_all_selected_paths()
        user_selected = all_selected - self._last_added_related_files

        # Filter to supported file types
        supported_exts = {".py", ".js", ".jsx", ".ts", ".tsx"}
        source_files = [
            Path(p)
            for p in user_selected
            if Path(p).is_file() and Path(p).suffix in supported_exts
        ]

        if not source_files:
            if self._last_added_related_files:
                self.file_tree_widget.remove_paths_from_selection(
                    self._last_added_related_files
                )
                self._last_added_related_files.clear()
            self._update_related_button_text()
            return

        depth = self._related_depth

        # Resolve in background to avoid UI freeze
        def resolve():
            assert workspace is not None  # Type narrowing for nested function
            try:
                # Dùng full scan thay vì lazy UI tree — đảm bảo file index đầy đủ
                full_tree = self._scan_full_tree(workspace)
                resolver = DependencyResolver(workspace)
                resolver.build_file_index(full_tree)

                all_related: Set[Path] = set()
                for file_path in source_files:
                    related = resolver.get_related_files(file_path, max_depth=depth)
                    all_related.update(related)

                # Convert to string paths
                related_strs = {str(p) for p in all_related if p.exists()}
                # Exclude files already selected by user
                new_related = related_strs - user_selected

                # Apply on main thread
                run_on_main_thread(
                    lambda: self._apply_related_results(new_related, user_selected)
                )
            except Exception as err:
                error_msg = f"Related files error: {err}"
                run_on_main_thread(lambda: self._show_status(error_msg, is_error=True))

        schedule_background(resolve)

    def _apply_related_results(
        self: "ContextViewQt", new_related: Set[str], user_selected: Set[str]
    ) -> None:
        """Apply resolved related files to selection (main thread)."""
        if not self._related_mode_active:
            return  # Mode was deactivated while resolving

        self._resolving_related = True
        try:
            # Remove previously auto-added files that are no longer related
            old_to_remove = self._last_added_related_files - new_related
            if old_to_remove:
                self.file_tree_widget.remove_paths_from_selection(old_to_remove)

            # Add new related files
            to_add = new_related - self._last_added_related_files
            if to_add:
                self.file_tree_widget.add_paths_to_selection(to_add)

            self._last_added_related_files = new_related

            count = len(new_related)
            self._update_related_button_text()
            if count > 0:
                self._show_status(
                    f"Found {count} related files (depth={self._related_depth})"
                )
            else:
                self._show_status("No related files found")
        finally:
            self._resolving_related = False
