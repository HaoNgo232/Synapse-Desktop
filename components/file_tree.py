"""
File Tree Component - Reusable file tree voi search, collapse/expand

Tach ra tu context_view.py de tranh god content.
"""

import flet as ft
import logging
from pathlib import Path
from typing import Callable, Optional, Set

from core.file_utils import TreeItem
from services.token_display import TokenDisplayService
from core.theme import ThemeColors


class FileTreeComponent:
    """
    Reusable File Tree Component voi:
    - Checkbox selection
    - Collapse/Expand folders
    - Search/Filter files
    - Token counts per file
    """

    def __init__(
        self,
        page: ft.Page,
        on_selection_changed: Optional[Callable[[Set[str]], None]] = None,
        show_tokens: bool = True,
    ):
        self.page = page
        self.on_selection_changed = on_selection_changed
        self.show_tokens = show_tokens

        # State
        self.tree: Optional[TreeItem] = None
        self.selected_paths: Set[str] = set()
        self.expanded_paths: Set[str] = set()
        self.search_query: str = ""
        self.matched_paths: Set[str] = set()

        # Token display service
        self._token_service = TokenDisplayService(on_update=self._on_tokens_updated)

        # UI elements
        self.tree_container: Optional[ft.Column] = None
        self.search_field: Optional[ft.TextField] = None
        self.match_count_text: Optional[ft.Text] = None

    def build(self) -> ft.Container:
        """Build file tree component UI"""

        # Search field
        self.search_field = ft.TextField(
            hint_text="Search files...",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            height=36,
            text_size=13,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            on_change=self._on_search_changed,
            suffix=ft.IconButton(
                icon=ft.Icons.CLOSE,
                icon_size=14,
                icon_color=ThemeColors.TEXT_MUTED,
                tooltip="Clear search",
                on_click=self._clear_search,
                visible=False,
            ),
        )

        self.match_count_text = ft.Text("", size=11, color=ThemeColors.TEXT_SECONDARY)

        # Tree container
        self.tree_container = ft.Column(
            controls=[
                ft.Text(
                    "Open a folder to see files",
                    color=ThemeColors.TEXT_MUTED,
                    italic=True,
                    size=14,
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        return ft.Container(
            content=ft.Column(
                [
                    # Search bar
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(content=self.search_field, expand=True),
                                self.match_count_text,
                            ],
                            spacing=8,
                        ),
                        padding=ft.padding.only(bottom=8),
                    ),
                    # Tree
                    self.tree_container,
                ],
                expand=True,
            ),
            expand=True,
        )

    def set_tree(self, tree: TreeItem, preserve_selection: bool = False):
        """
        Set tree data va render.

        Args:
            tree: TreeItem root moi
            preserve_selection: Neu True, giu lai cac selected paths van ton tai trong tree moi
                               va auto-select files moi trong cac folders da duoc chon
        """
        # Luu lai selected paths neu can preserve
        old_selected = self.selected_paths.copy() if preserve_selection else set()

        # Tim cac folders da duoc chon (de auto-select files moi trong do)
        old_selected_folders: Set[str] = set()
        if preserve_selection:
            for path in old_selected:
                from pathlib import Path

                if Path(path).is_dir():
                    old_selected_folders.add(path)

        self.tree = tree
        self.expanded_paths = {tree.path}
        self.search_query = ""
        self.matched_paths.clear()

        if preserve_selection:
            # Lay tat ca paths trong tree moi
            valid_paths = self._get_all_paths_in_tree(tree)

            # Giu lai cac paths van ton tai
            self.selected_paths = old_selected & valid_paths

            # Auto-select files moi trong cac folders da duoc chon
            for folder_path in old_selected_folders:
                self._auto_select_children_in_folder(tree, folder_path)
        else:
            self.selected_paths.clear()

        # Clear token cache va request tokens cho visible files
        self._token_service.clear_cache()
        self._render_tree()

        # Request tokens sau khi render
        if self.show_tokens:
            self._request_visible_tokens()

    def get_selected_paths(self) -> Set[str]:
        """
        Lay danh sach TAT CA paths duoc chon (khong quan tam search filter).
        Day la behavior goc, giu nguyen de khong break logic cu.
        """
        return self.selected_paths.copy()

    def get_visible_selected_paths(self) -> Set[str]:
        """
        Lay danh sach paths duoc chon VA dang hien thi (sau search filter).

        - Neu KHONG co search query: tra ve tat ca selected paths (behavior goc)
        - Neu CO search query: chi tra ve selected paths nam trong matched_paths

        Dung method nay khi copy context de chi copy files dang hien thi.
        """
        if not self.search_query:
            # Khong co search -> tra ve tat ca (behavior goc)
            return self.selected_paths.copy()

        # Co search -> chi tra ve paths dang hien thi
        # Chi lay files (khong lay folders) de tranh duplicate
        visible_selected: Set[str] = set()

        for path in self.selected_paths:
            # Path phai nam trong matched_paths (dang hien thi)
            if path in self.matched_paths:
                # Neu la file, them vao
                if not Path(path).is_dir():
                    visible_selected.add(path)
                else:
                    # Neu la folder, chi them cac files con dang hien thi
                    self._collect_visible_files_in_folder(path, visible_selected)

        return visible_selected

    def _collect_visible_files_in_folder(self, folder_path: str, result: Set[str]):
        """Thu thap cac files dang hien thi trong folder"""
        if not self.tree:
            return

        # Tim folder trong tree
        folder_item = self._find_item_by_path(self.tree, folder_path)
        if not folder_item:
            return

        # Duyet qua children
        self._collect_visible_files_recursive(folder_item, result)

    def _collect_visible_files_recursive(self, item: TreeItem, result: Set[str]):
        """Recursive helper de thu thap visible files"""
        for child in item.children:
            # Chi lay neu dang hien thi (trong matched_paths)
            if child.path in self.matched_paths:
                if not child.is_dir:
                    result.add(child.path)
                else:
                    self._collect_visible_files_recursive(child, result)

    def _find_item_by_path(
        self, item: TreeItem, target_path: str
    ) -> Optional[TreeItem]:
        """Tim TreeItem theo path"""
        if item.path == target_path:
            return item
        for child in item.children:
            found = self._find_item_by_path(child, target_path)
            if found:
                return found
        return None

    def is_searching(self) -> bool:
        """Check xem co dang search khong"""
        return bool(self.search_query)

    def expand_all(self):
        """Expand tat ca folders"""
        if self.tree:
            self._collect_all_folder_paths(self.tree)
            self._render_tree()

    def collapse_all(self):
        """Collapse tat ca (giu root open)"""
        if self.tree:
            self.expanded_paths = {self.tree.path}
            self._render_tree()

    # =========================================================================
    # SEARCH
    # =========================================================================

    def _on_search_changed(self, e):
        """Xu ly khi search query thay doi"""
        assert self.search_field is not None
        assert self.match_count_text is not None

        self.search_query = (e.control.value or "").lower().strip()

        # Update clear button visibility
        if self.search_field.suffix:
            self.search_field.suffix.visible = bool(self.search_query)

        if self.search_query:
            self._perform_search()
        else:
            self.matched_paths.clear()
            self.match_count_text.value = ""

        self._render_tree()

    def _clear_search(self, e):
        """Clear search"""
        assert self.search_field is not None
        assert self.match_count_text is not None

        self.search_field.value = ""
        self.search_query = ""
        self.matched_paths.clear()
        self.match_count_text.value = ""
        if self.search_field.suffix:
            self.search_field.suffix.visible = False
        self._render_tree()

    def _perform_search(self):
        """Tim kiem files matching query"""
        self.matched_paths.clear()
        if not self.tree or not self.search_query:
            return

        self._search_in_item(self.tree)

        # Auto-expand folders chua matched files
        self._expand_matched_parents()

        # Update count
        assert self.match_count_text is not None
        file_count = sum(1 for p in self.matched_paths if not Path(p).is_dir())
        self.match_count_text.value = f"{file_count} found"

    def _search_in_item(self, item: TreeItem) -> bool:
        """
        Tim kiem trong item va children.
        Returns True neu item hoac bat ky child nao match.
        """
        # Check if this item matches
        item_matches = self.search_query in item.label.lower()

        # Check children
        any_child_matches = False
        for child in item.children:
            if self._search_in_item(child):
                any_child_matches = True

        # If item or any child matches, add to matched
        if item_matches or any_child_matches:
            self.matched_paths.add(item.path)
            return True

        return False

    def _expand_matched_parents(self):
        """Expand tat ca folders chua matched files"""
        if not self.tree:
            return

        for path in self.matched_paths:
            # Expand all parent folders
            self._expand_parents_of(self.tree, path)

    def _expand_parents_of(self, item: TreeItem, target_path: str) -> bool:
        """Expand parents cua target_path. Returns True neu target o trong item."""
        if item.path == target_path:
            return True

        for child in item.children:
            if self._expand_parents_of(child, target_path):
                self.expanded_paths.add(item.path)
                return True

        return False

    # =========================================================================
    # RENDER
    # =========================================================================

    def _render_tree(self):
        """Render tree vao UI"""
        assert self.tree_container is not None

        if not self.tree:
            return

        self.tree_container.controls.clear()
        self._render_tree_item(self.tree, 0)
        self.page.update()

    def _render_tree_item(self, item: TreeItem, depth: int):
        """Render mot item voi search highlighting"""

        # Neu dang search, chi hien thi matched items
        if self.search_query and item.path not in self.matched_paths:
            return

        indent = depth * 16
        is_expanded = item.path in self.expanded_paths
        has_children = item.is_dir and len(item.children) > 0
        is_match = self.search_query and self.search_query in item.label.lower()

        # Expand/Collapse arrow
        if has_children:
            # Count visible children when searching
            visible_children = len(item.children)
            if self.search_query:
                visible_children = sum(
                    1 for c in item.children if c.path in self.matched_paths
                )

            if visible_children > 0:
                expand_icon = ft.IconButton(
                    icon=(
                        ft.Icons.KEYBOARD_ARROW_DOWN
                        if is_expanded
                        else ft.Icons.KEYBOARD_ARROW_RIGHT
                    ),
                    icon_size=16,
                    icon_color=ThemeColors.TEXT_SECONDARY,
                    width=24,
                    height=24,
                    padding=0,
                    on_click=lambda e: self._toggle_expand(item.path),
                )
            else:
                expand_icon = ft.Container(width=24)
        else:
            expand_icon = ft.Container(width=24)

        # Checkbox
        checkbox = ft.Checkbox(
            value=item.path in self.selected_paths,
            active_color=ThemeColors.PRIMARY,
            check_color="#FFFFFF",
            on_change=lambda e: self._on_item_toggled(
                e, item.path, item.is_dir, item.children
            ),
        )

        # Icon
        if item.is_dir:
            icon = ft.Icons.FOLDER_OPEN if is_expanded else ft.Icons.FOLDER
            icon_color = ThemeColors.ICON_FOLDER
        else:
            icon = ft.Icons.INSERT_DRIVE_FILE
            icon_color = ThemeColors.ICON_FILE

        # Text voi highlight
        text_weight = ft.FontWeight.W_500 if item.is_dir else ft.FontWeight.NORMAL
        text_bgcolor = ThemeColors.SEARCH_HIGHLIGHT if is_match else None

        label_container = ft.Container(
            content=ft.Text(
                item.label, size=13, color=ThemeColors.TEXT_PRIMARY, weight=text_weight
            ),
            bgcolor=text_bgcolor,
            padding=ft.padding.symmetric(horizontal=4, vertical=1) if is_match else 0,
            border_radius=3 if is_match else 0,
        )

        row = ft.Row(
            [
                ft.Container(width=indent),
                expand_icon,
                checkbox,
                ft.Icon(icon, size=18, color=icon_color),
                label_container,
                # Token count display (cho ca files va folders)
                self._create_token_badge(item) if self.show_tokens else ft.Container(),
            ],
            spacing=2,
        )

        assert self.tree_container is not None
        self.tree_container.controls.append(row)

        # Render children if expanded
        if item.is_dir and is_expanded:
            for child in item.children:
                self._render_tree_item(child, depth + 1)

    def _toggle_expand(self, path: str):
        """Toggle expand/collapse"""
        if path in self.expanded_paths:
            self.expanded_paths.discard(path)
        else:
            self.expanded_paths.add(path)
        self._render_tree()

    def _collect_all_folder_paths(self, item: TreeItem):
        """Collect all folder paths for expand all"""
        if item.is_dir:
            self.expanded_paths.add(item.path)
            for child in item.children:
                self._collect_all_folder_paths(child)

    # =========================================================================
    # SELECTION
    # =========================================================================

    def _on_item_toggled(self, e, path: str, is_dir: bool, children: list):
        """Xu ly khi item duoc tick/untick"""
        if e.control.value:
            self.selected_paths.add(path)
            if is_dir:
                self._select_all_children(children)
        else:
            self.selected_paths.discard(path)
            if is_dir:
                self._deselect_all_children(children)

        self._render_tree()

        # Notify parent
        if self.on_selection_changed:
            self.on_selection_changed(self.selected_paths)

    def _select_all_children(self, children: list):
        """Chon tat ca children recursively"""
        for child in children:
            self.selected_paths.add(child.path)
            if child.children:
                self._select_all_children(child.children)

    def _deselect_all_children(self, children: list):
        """Bo chon tat ca children recursively"""
        for child in children:
            self.selected_paths.discard(child.path)
            if child.children:
                self._deselect_all_children(child.children)

    # =========================================================================
    # TOKEN DISPLAY
    # =========================================================================

    def _create_token_badge(self, item: TreeItem) -> ft.Container:
        """
        Tao badge hien thi token count cho file hoac folder.
        - File: hien thi token count cua file
        - Folder: hien thi tong tokens cua tat ca files ben trong
        """
        if item.is_dir:
            # Folder: tinh tong tu children
            assert self.tree is not None
            folder_tokens = self._token_service.get_folder_tokens(item.path, self.tree)
            if folder_tokens is None:
                # Chua tinh xong - return empty
                return ft.Container(width=0)
            if folder_tokens == 0:
                # Empty folder hoac chi chua folders
                return ft.Container(width=0)
            token_text = self._token_service._format_tokens(folder_tokens)
        else:
            # File: lay tu cache
            token_text = self._token_service.get_token_display(item.path)
            if not token_text:
                # Chua co - request va return empty
                self._token_service.request_token_count(item.path)
                return ft.Container(width=0)

        return ft.Container(
            content=ft.Text(
                token_text,
                size=10,
                color=ThemeColors.TEXT_MUTED,
            ),
            margin=ft.margin.only(left=8),
        )

    def _on_tokens_updated(self):
        """Callback khi TokenService update cache - re-render tree"""
        # Re-render de cap nhat token displays
        # Su dung page.update thay vi _render_tree de tranh re-render toan bo
        try:
            if self.page:
                self.page.update()
        except Exception as e:
            logging.debug(f"Error updating page from token service: {e}")
            pass  # Ignore errors khi page chua san sang

    def _request_visible_tokens(self):
        """Request tokens cho cac files dang hien thi"""
        if not self.tree:
            return

        # Collect visible paths
        visible = self.matched_paths if self.search_query else None
        self._token_service.request_tokens_for_tree(
            self.tree, visible_only=bool(self.search_query), visible_paths=visible
        )

    def _get_all_paths_in_tree(self, item: TreeItem) -> Set[str]:
        """
        Lay tat ca paths trong tree (de dang cho so sanh).

        Args:
            item: TreeItem root

        Returns:
            Set chua tat ca paths trong tree
        """
        paths: Set[str] = {item.path}
        for child in item.children:
            paths.update(self._get_all_paths_in_tree(child))
        return paths

    def _auto_select_children_in_folder(self, tree: TreeItem, folder_path: str):
        """
        Tim folder trong tree va auto-select tat ca children cua no.
        Dung de auto-select files moi trong folder da duoc chon sau khi refresh.

        Args:
            tree: TreeItem root
            folder_path: Path cua folder can tim
        """
        folder_item = self._find_item_by_path(tree, folder_path)
        if folder_item and folder_item.is_dir:
            # Select folder va tat ca children
            self._select_all_children(folder_item.children)

    def _find_item_by_path(
        self, item: TreeItem, target_path: str
    ) -> Optional[TreeItem]:
        """
        Tim TreeItem theo path trong tree.

        Args:
            item: TreeItem hien tai
            target_path: Path can tim

        Returns:
            TreeItem neu tim thay, None neu khong
        """
        if item.path == target_path:
            return item
        for child in item.children:
            found = self._find_item_by_path(child, target_path)
            if found:
                return found
        return None
