"""
RelatedFilesController - Controller quan ly logic auto-select related files.

Thay the RelatedFilesMixin bang composition pattern.
Controller nhan ViewProtocol thay vi ke thua truc tiep, giup tach biet logic
khoi UI va de dang test hon.

Pattern: Controller (logic) <-> View (UI) noi chuyen qua Protocol interface.
"""

from pathlib import Path
from typing import Any, Protocol, Set, runtime_checkable, Optional
from PySide6.QtCore import QObject

from application.services.dependency_resolver import DependencyResolver
from infrastructure.adapters.qt_utils import run_on_main_thread, schedule_background


@runtime_checkable
class RelatedFilesViewProtocol(Protocol):
    """
    Protocol dinh nghia nhung gi RelatedFilesController can tu View.

    View phai implement tat ca cac methods nay de controller hoat dong.
    """

    def get_workspace(self) -> "Path | None":
        """Tra ve workspace path hien tai."""
        ...

    def get_all_selected_paths(self) -> Set[str]:
        """Tra ve tat ca selected paths (tao cung ca related files)."""
        ...

    def add_paths_to_selection(self, paths: Set[str]) -> int:
        """Them paths vao selection. Tra ve so luong them thanh cong."""
        ...

    def remove_paths_from_selection(self, paths: Set[str]) -> int:
        """Xoa paths khoi selection. Tra ve so luong xoa thanh cong."""
        ...

    def scan_full_tree(self, workspace: Path) -> Any:
        """Scan full workspace tree de build file index."""
        ...

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Hien thi status message."""
        ...

    def update_related_button_text(self, active: bool, depth: int, count: int) -> None:
        """Cap nhat text cua related mode button."""
        ...


class RelatedFilesController(QObject):
    """
    Controller quan ly logic auto-select related files.

    Thay the RelatedFilesMixin:
    - Khong ke thua tu View - nhan ViewProtocol qua constructor injection
    - Encapsulate toan bo state cua related files feature
    - Co the test doc lap ma khong can khoi tao View

    FLOW:
    1. View goi set_mode(active, depth) khi user click button
    2. Controller goi _resolve_related_files() trong background
    3. Sau khi resolve xong, _apply_results() duoc goi tren main thread
    4. Controller goi view.add_paths_to_selection() / remove_paths_from_selection()
    """

    def __init__(
        self,
        view: RelatedFilesViewProtocol,
        parent: Optional[QObject] = None,
    ) -> None:
        """
        Khoi tao controller voi view reference.

        Args:
            view: Object implement RelatedFilesViewProtocol. Typically ContextViewQt.
        """
        super().__init__(parent)
        self._view = view

        # State
        self._mode_active: bool = False
        self._depth: int = 1
        self._last_added_related_files: Set[str] = set()
        self._resolving: bool = False

    # ===== Public API =====

    @property
    def is_active(self) -> bool:
        """Check xem related mode co dang active khong."""
        return self._mode_active

    @property
    def depth(self) -> int:
        """Lay current resolution depth."""
        return self._depth

    @property
    def related_files_count(self) -> int:
        """Lay so luong related files dang duoc auto-select."""
        return len(self._last_added_related_files)

    @property
    def added_related_files(self) -> Set[str]:
        """Tra ve copy cua tap hop related files hien tai."""
        return set(self._last_added_related_files)

    def set_mode(self, active: bool, depth: int, silent: bool = False) -> None:
        """
        Set related mode voi depth cu cu the.

        Args:
            active: True de bat mode, False de tat
            depth: Resolution depth (1=Direct, 5=Deepest)
            silent: True de an thong bao toast
        """
        if active:
            self._depth = depth
            self._activate()
        else:
            self._deactivate(silent=silent)

    def resolve_for_current_selection(self) -> None:
        """
        Re-resolve related files dua tren selection hien tai.

        Goi khi selection thay doi (neu related mode dang active).
        """
        if self._mode_active and not self._resolving:
            self._resolve_related_files()

    def cleanup(self) -> None:
        """Cleanup controller state khi view bi dong."""
        self._last_added_related_files.clear()
        self._mode_active = False
        self._resolving = False

    # ===== Private Logic =====

    def _activate(self) -> None:
        """Bat related mode va resolve cho selection hien tai."""
        self._mode_active = True
        self._update_button_text()
        self._resolve_related_files()

    def _deactivate(self, silent: bool = False) -> None:
        """Tat related mode va xoa auto-added files khoi selection."""
        if self._last_added_related_files:
            removed = self._view.remove_paths_from_selection(
                self._last_added_related_files
            )
            if not silent:
                self._view.show_status(f"Removed {removed} related files")

        self._last_added_related_files.clear()
        self._mode_active = False
        self._update_button_text()

    def _update_button_text(self) -> None:
        """Goi view de cap nhat text cua related mode button."""
        self._view.update_related_button_text(
            active=self._mode_active,
            depth=self._depth,
            count=len(self._last_added_related_files),
        )

    def _resolve_related_files(self) -> None:
        """Resolve related files cho tat ca selected files trong background."""
        workspace = self._view.get_workspace()
        if not workspace:
            return

        # Get user-selected files only (exclude auto-added related files)
        all_selected = self._view.get_all_selected_paths()
        user_selected = all_selected - self._last_added_related_files

        # Expand folders thành files (nếu user select folder)
        expanded_files: Set[str] = set()
        for path_str in user_selected:
            p = Path(path_str)
            if p.is_dir():
                # Scan tất cả files trong folder (recursive)
                for file_path in p.rglob("*"):
                    if file_path.is_file():
                        expanded_files.add(str(file_path))
            elif p.is_file():
                expanded_files.add(path_str)

        user_selected = expanded_files

        # Filter to supported file types
        supported_exts = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".go",
            ".rs",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
        }
        user_selected = {
            p
            for p in user_selected
            if Path(p).is_file() and Path(p).suffix in supported_exts
        }

        if not user_selected:
            if self._last_added_related_files:
                self._view.remove_paths_from_selection(self._last_added_related_files)
                self._last_added_related_files.clear()
            self._update_button_text()
            return

        depth = self._depth
        workspace_path: Path = workspace  # type: ignore[assignment]

        def resolve() -> None:
            try:
                related_strs: Set[str] = set()

                # Sử dụng DependencyResolver (IMPORTS)
                full_tree = self._view.scan_full_tree(workspace_path)
                resolver = DependencyResolver(workspace_path)
                resolver.build_file_index(full_tree)

                for file_path_str in user_selected:
                    p = Path(file_path_str)
                    if not p.is_file():
                        continue
                    related = resolver.get_related_files(p, max_depth=depth)
                    for target in related:
                        if target.exists():
                            related_strs.add(str(target.resolve()))

                # Loại bỏ những file user đã chọn trực tiếp
                new_related = {s for s in related_strs if s not in user_selected}

                run_on_main_thread(lambda: self._apply_results(new_related))
            except Exception as err:  # pragma: no cover - defensive path
                error_msg = f"Related files error: {err}"
                run_on_main_thread(
                    lambda: self._view.show_status(error_msg, is_error=True)
                )

        schedule_background(resolve)

    def _apply_results(self, new_related: Set[str]) -> None:
        """
        Apply resolved related files vao selection (main thread).

        Method nay PHAI duoc goi tren main thread.
        """
        if not self._mode_active:
            return  # Mode da bi tat trong khi dang resolve

        self._resolving = True
        try:
            # Xoa previously auto-added files khong con la related
            old_to_remove = self._last_added_related_files - new_related
            if old_to_remove:
                self._view.remove_paths_from_selection(old_to_remove)

            # Them new related files
            to_add = new_related - self._last_added_related_files
            if to_add:
                self._view.add_paths_to_selection(to_add)

            self._last_added_related_files = new_related

            self._update_button_text()

            count = len(new_related)
            if count > 0:
                self._view.show_status(
                    f"Found {count} related files (depth={self._depth})"
                )
            else:
                self._view.show_status("No related files found")
        finally:
            self._resolving = False
