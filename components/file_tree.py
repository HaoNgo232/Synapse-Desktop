"""
File Tree Component - Reusable file tree voi search, collapse/expand

Tach ra tu context_view.py de tranh god content.
"""

import flet as ft
import logging
import threading
from threading import Timer
from pathlib import Path
from core.utils.safe_timer import SafeTimer
from typing import Callable, Optional, Set

from core.utils.file_utils import TreeItem
from services.token_display import TokenDisplayService
from services.line_count_display import LineCountService
from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update


class FileTreeComponent:
    """
    Reusable File Tree Component voi:
    - Checkbox selection
    - Collapse/Expand folders
    - Search/Filter files
    - Token counts per file
    - Line counts per file
    """

    def __init__(
        self,
        page: ft.Page,
        on_selection_changed: Optional[Callable[[Set[str]], None]] = None,
        show_tokens: bool = True,
        show_lines: bool = True,
    ):
        self.page = page
        self.on_selection_changed = on_selection_changed
        self.show_tokens = show_tokens
        self.show_lines = show_lines

        # State
        self.tree: Optional[TreeItem] = None
        self.selected_paths: Set[str] = set()
        self.expanded_paths: Set[str] = set()
        self.search_query: str = ""
        self.matched_paths: Set[str] = set()

        # Token display service
        self._token_service = TokenDisplayService(on_update=self._on_metrics_updated)

        # Line count display service
        self._line_service = LineCountService(on_update=self._on_metrics_updated)

        # UI elements
        self.tree_container: Optional[ft.Column] = None
        self.search_field: Optional[ft.TextField] = None
        self.match_count_text: Optional[ft.Text] = None
        
        # RACE CONDITION FIX: Selection operations lock
        import threading
        self._selection_lock = threading.Lock()

        # Debounce timer for search
        self._search_timer: Optional[Timer] = None
        self._search_debounce_ms: float = 150  # 150ms debounce
        
        # Race condition prevention
        self._ui_lock = threading.Lock()
        self._is_rendering = False
        self._render_timer: Optional[SafeTimer] = None
        self._is_disposed = False  # Disposal flag để prevent callbacks sau cleanup

    def cleanup(self):
        """Cleanup resources when component is destroyed"""
        # Set disposal flag FIRST để prevent race với Timer callbacks
        self._is_disposed = True
        
        # Cancel search timer safely
        timer = self._search_timer
        self._search_timer = None
        if timer is not None:
            try:
                timer.dispose()  # Use dispose for SafeTimer
            except Exception:
                pass

        # Cancel render timer safely
        render_timer = self._render_timer
        self._render_timer = None
        if render_timer is not None:
            try:
                render_timer.dispose()  # Use dispose instead of cancel
            except Exception:
                pass

        # Stop token service
        self._token_service.stop()
        self._token_service.clear_cache()

        # Clear line count service
        self._line_service.clear_cache()

    def reset_for_new_tree(self):
        """
        Reset component để load tree mới mà không dispose.
        
        Khác với cleanup(), method này không set _is_disposed = True,
        cho phép component tiếp tục sử dụng cho tree mới.
        """
        # Cancel search timer safely
        timer = self._search_timer
        self._search_timer = None
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass

        # Cancel render timer safely
        render_timer = self._render_timer
        self._render_timer = None
        if render_timer is not None:
            try:
                render_timer.dispose()
            except Exception:
                pass

        # Stop token service and clear caches
        self._token_service.stop()
        self._token_service.clear_cache()

        # Clear line count service
        self._line_service.clear_cache()

        # Reset rendering state
        with self._ui_lock:
            self._is_rendering = False
        
        # Đảm bảo component chưa bị disposed
        self._is_disposed = False

    def set_loading(self, is_loading: bool):
        """Set loading state của file tree"""
        if self.loading_indicator:
            self.loading_indicator.visible = is_loading
            if self.page:
                safe_page_update(self.page)

    def build(self) -> ft.Container:
        """Build file tree component UI"""

        # Search field with keyboard support
        self.search_field = ft.TextField(
            hint_text="Search files... (Ctrl+F)",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            height=36,
            text_size=13,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            on_change=self._on_search_changed,
            on_submit=self._on_search_submit,
            on_blur=self._on_search_blur,
            autofocus=False,
            suffix=ft.IconButton(
                icon=ft.Icons.CLOSE,
                icon_size=14,
                icon_color=ThemeColors.TEXT_MUTED,
                tooltip="Clear search (Esc)",
                on_click=self._clear_search,
                visible=False,
            ),
        )

        self.match_count_text = ft.Text("", size=11, color=ThemeColors.TEXT_SECONDARY)

        # Loading indicator
        self.loading_indicator = ft.ProgressRing(
            width=20,
            height=20,
            stroke_width=2,
            color=ThemeColors.PRIMARY,
            visible=False,
        )

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
                                self.loading_indicator,
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
        self._line_service.clear_cache()
        self._render_tree()

        # Request tokens va lines sau khi render
        if self.show_tokens:
            self._request_visible_tokens()
        if self.show_lines:
            self._request_visible_lines()

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

    def is_searching(self) -> bool:
        """Check xem co dang search khong"""
        return bool(self.search_query)

    def expand_all(self):
        """Expand tat ca folders"""
        if self.tree:
            self._collect_all_folder_paths(self.tree)
            self._render_tree()

    def set_expanded_paths(self, paths: Set[str]):
        """
        Set expanded paths từ bên ngoài (e.g., restore session).

        Args:
            paths: Set các folder paths cần expand
        """
        if self.tree:
            # Chỉ giữ lại các paths tồn tại trong tree hiện tại
            valid_paths = self._get_all_paths_in_tree(self.tree)
            self.expanded_paths = paths & valid_paths
            # Đảm bảo root luôn expanded
            self.expanded_paths.add(self.tree.path)

    def collapse_all(self):
        """Collapse tat ca (giu root open)"""
        if self.tree:
            self.expanded_paths = {self.tree.path}
            self._render_tree()

    # =========================================================================
    # SEARCH
    # =========================================================================

    def _on_search_changed(self, e):
        """Xu ly khi search query thay doi voi debounce"""
        assert self.search_field is not None
        assert self.match_count_text is not None

        self.search_query = (e.control.value or "").lower().strip()

        # Update clear button visibility immediately
        if self.search_field.suffix:
            self.search_field.suffix.visible = bool(self.search_query)
            safe_page_update(self.page)

        # Cancel previous timer if exists
        if self._search_timer is not None:
            self._search_timer.cancel()

        # Debounce search execution
        self._search_timer = Timer(
            self._search_debounce_ms / 1000.0, self._execute_search
        )
        self._search_timer.start()

    def _execute_search(self):
        """
        Execute search after debounce delay.

        RACE CONDITION FIX: Method này được gọi từ Timer thread.
        Phải defer việc render đến main thread thông qua page.run_task().
        """
        # ========================================
        # RACE CONDITION FIX: Defer execution đến main thread
        # Timer callback chạy trên background thread, không an toàn để
        # thao tác trực tiếp với UI controls
        # Flet 0.80.5+ yêu cầu async function cho run_task
        # ========================================
        async def _do_search():
            try:
                if self.match_count_text is None:
                    return

                if self.search_query:
                    self._perform_search()
                else:
                    self.matched_paths.clear()
                    self.match_count_text.value = ""

                self._render_tree()
            except Exception as e:
                import logging
                logging.debug(f"Error in deferred search: {e}")

        # Nếu có page, defer đến main thread
        if self.page:
            try:
                self.page.run_task(_do_search)
            except Exception:
                # Fallback nếu page không hỗ trợ run_task
                pass
        else:
            # Không có page, skip search
            pass

    def _on_search_submit(self, e):
        """Handle Enter key trong search field - select first match"""
        if self.search_query and self.matched_paths:
            # Select first matched file (not folder)
            for path in sorted(self.matched_paths):
                if not Path(path).is_dir():
                    self.selected_paths.add(path)
                    if self.on_selection_changed:
                        self.on_selection_changed(self.selected_paths)
                    self._render_tree()
                    break

    def _clear_search(self, e=None):
        """Clear search"""
        # Cancel any pending search timer
        if self._search_timer is not None:
            self._search_timer.cancel()
            self._search_timer = None

        assert self.search_field is not None
        assert self.match_count_text is not None

        self.search_field.value = ""
        self.search_query = ""
        self.matched_paths.clear()
        self.match_count_text.value = ""
        if self.search_field.suffix:
            self.search_field.suffix.visible = False
        self._render_tree()

    def _on_search_blur(self, e):
        """Handle search field blur - used for keyboard events"""
        pass  # Placeholder for future keyboard handling

    def handle_keyboard_event(self, e: ft.KeyboardEvent) -> bool:
        """
        Handle keyboard events for the file tree.
        Returns True if event was handled.
        """
        if e.key == "Escape" and self.search_query:
            self._clear_search()
            return True
        return False

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
        """
        Render tree vao UI - thread safe.
        
        RACE CONDITION FIX: Sử dụng atomic check-and-set pattern.
        Check và set _is_rendering trong cùng một critical section.
        """
        # ========================================
        # RACE CONDITION FIX: Atomic check-and-set
        # Check _is_rendering VÀ set nó trong cùng một lock acquisition
        # Tránh TOCTOU (Time-of-Check to Time-of-Use) vulnerability
        # ========================================
        from core.logging_config import log_info, log_error
        log_info(f"[FileTree] _render_tree START - tree_container={self.tree_container is not None}, tree={self.tree is not None}")
        
        with self._ui_lock:
            if self._is_rendering or self._is_disposed:
                log_info(f"[FileTree] _render_tree SKIP - is_rendering={self._is_rendering}, is_disposed={self._is_disposed}")
                return  # Đang render hoặc đã cleanup, skip
            self._is_rendering = True
        
        # Validate prerequisites NGOÀI lock để tránh hold lock quá lâu
        if not self.tree_container or not self.tree:
            log_info(f"[FileTree] _render_tree SKIP - missing tree_container or tree")
            with self._ui_lock:
                self._is_rendering = False
            return
            
        try:
            log_info(f"[FileTree] Clearing controls, current count: {len(self.tree_container.controls)}")
            self.tree_container.controls.clear()

            # Track rendered count for performance
            self._rendered_count = 0
            self._max_render_items = 1000  # Limit for very large trees

            self._render_tree_item(self.tree, 0)
            
            log_info(f"[FileTree] Rendered {self._rendered_count} items, controls count: {len(self.tree_container.controls)}")

            # Add truncation notice if needed
            if self._rendered_count >= self._max_render_items:
                self.tree_container.controls.append(
                    ft.Text(
                        f"[Showing first {self._max_render_items} items. Use search to find more.]",
                        color=ThemeColors.TEXT_MUTED,
                        italic=True,
                        size=11,
                    )
                )

            # Safety check: only update if page exists and component is attached
            if self.page and hasattr(self, "tree_container") and self.tree_container:
                try:
                    log_info(f"[FileTree] Calling safe_page_update...")
                    safe_page_update(self.page)
                    log_info(f"[FileTree] safe_page_update completed")
                except AssertionError as e:
                    # Control not yet attached to page, skip update
                    log_error(f"[FileTree] AssertionError in page update: {e}")
        except Exception as ex:
            log_error(f"[FileTree] Error in _render_tree: {ex}")
        finally:
            with self._ui_lock:
                self._is_rendering = False

    def _schedule_render(self):
        """Schedule a debounced render to prevent multiple rapid renders - RACE CONDITION SAFE"""
        with self._ui_lock:
            if self._render_timer:
                self._render_timer.dispose()
            
            # Use SafeTimer instead of Timer
            self._render_timer = SafeTimer(
                interval=0.05,  # 50ms debounce
                callback=self._do_render,
                page=getattr(self, 'page', None),
                use_main_thread=True
            )
            self._render_timer.start()
    
    def _do_render(self):
        """
        Actual render - defer to main thread.
        
        RACE CONDITION FIX: Method này được gọi từ Timer thread.
        Phải defer việc render đến main thread qua page.run_task().
        Flet 0.80.5+ yêu cầu async function cho run_task.
        """
        # Skip nếu đã disposed
        if self._is_disposed:
            return
        
        # Tạo async wrapper cho _render_tree
        async def _async_render():
            self._render_tree()
        
        if self.page:
            try:
                # Defer đến main thread với async function
                self.page.run_task(_async_render)
            except Exception:
                pass  # Page not available
        else:
            # Fallback: run trực tiếp (không lý tưởng nhưng tốt hơn không làm gì)
            self._render_tree()

    def _render_tree_item(self, item: TreeItem, depth: int):
        """Render mot item voi search highlighting"""

        # Check render limit
        if (
            hasattr(self, "_rendered_count")
            and self._rendered_count >= self._max_render_items
        ):
            return

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
                # Line count display (cho ca files va folders)
                (
                    self._create_line_count_badge(item)
                    if self.show_lines
                    else ft.Container()
                ),
                # Token count display (cho ca files va folders)
                self._create_token_badge(item) if self.show_tokens else ft.Container(),
            ],
            spacing=2,
        )

        assert self.tree_container is not None
        self.tree_container.controls.append(row)

        # Increment render count
        if hasattr(self, "_rendered_count"):
            self._rendered_count += 1

        # Render children if expanded
        if item.is_dir and is_expanded:
            for child in item.children:
                self._render_tree_item(child, depth + 1)

    def _toggle_expand(self, path: str):
        """Toggle expand/collapse - thread safe"""
        with self._ui_lock:
            if path in self.expanded_paths:
                self.expanded_paths.discard(path)
            else:
                self.expanded_paths.add(path)
        self._schedule_render()

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
        """
        Xu ly khi item duoc tick/untick - thread safe.
        
        RACE CONDITION FIX: Sử dụng atomic check pattern.
        Check _is_rendering VÀ thao tác selection trong cùng một lock.
        """
        # ========================================
        # RACE CONDITION FIX: Atomic check trong lock
        # Check _is_rendering và _is_disposed BÊN TRONG lock
        # để tránh TOCTOU vulnerability
        # ========================================
        with self._ui_lock:
            # Skip nếu đang render hoặc đã cleanup
            if self._is_rendering or self._is_disposed:
                return
            
            # Thực hiện selection changes BÊN TRONG lock
            if e.control.value:
                self.selected_paths.add(path)
                if is_dir:
                    self._select_all_children(children)
            else:
                self.selected_paths.discard(path)
                if is_dir:
                    self._deselect_all_children(children)

        # Schedule render NGOÀI lock để tránh deadlock
        self._schedule_render()

        # Notify parent NGOÀI lock
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
    # LINE COUNT & TOKEN DISPLAY
    # =========================================================================

    def _create_line_count_badge(self, item: TreeItem) -> ft.Container:
        """
        Tao badge hien thi line count cho file hoac folder.
        - File: hien thi line count cua file
        - Folder: hien thi tong lines cua tat ca files ben trong
        """
        if item.is_dir:
            # Folder: tinh tong tu children
            assert self.tree is not None
            folder_lines = self._line_service.get_folder_lines(item.path, self.tree)
            if folder_lines is None:
                # Chua tinh xong - return empty
                return ft.Container(width=0)
            if folder_lines == 0:
                # Empty folder hoac chi chua folders
                return ft.Container(width=0)
            line_text = self._line_service._format_lines(folder_lines)
        else:
            # File: lay tu cache
            line_text = self._line_service.get_line_display(item.path)
            if not line_text:
                # Chua co - request va return empty
                self._line_service.request_line_count(item.path)
                return ft.Container(width=0)

        # Format với suffix "L" để dễ phân biệt với tokens
        return ft.Container(
            content=ft.Text(
                f"{line_text} lines",  # L = Lines
                size=11,
                color=ThemeColors.PRIMARY,  # Màu xanh dương để phân biệt với token (SUCCESS - xanh lá)
                weight=ft.FontWeight.W_500,
            ),
            margin=ft.margin.only(left=8),
        )

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
                self._token_service.request_token_count(item.path, self.page)
                return ft.Container(width=0)

        return ft.Container(
            content=ft.Text(
                token_text,
                size=11,
                color=ThemeColors.SUCCESS,
                weight=ft.FontWeight.W_500,
            ),
            margin=ft.margin.only(left=8),
        )

    def _on_metrics_updated(self):
        """
        Callback khi TokenService hoac LineService update cache - re-render tree.

        RACE CONDITION FIX: Callback này có thể được gọi từ background context.
        Sử dụng page.run_task() để đảm bảo UI update trên main thread.
        """
        # Re-render de cap nhat token/line displays
        # Su dung page.update thay vi _render_tree de tranh re-render toan bo
        try:
            if self.page:
                # ========================================
                # RACE CONDITION FIX: Defer UI update đến main thread
                # Flet 0.80.5+ yêu cầu async function cho run_task
                # ========================================
                async def _do_update():
                    try:
                        safe_page_update(self.page)
                    except Exception:
                        pass

                try:
                    self.page.run_task(_do_update)
                except Exception:
                    # Fallback nếu run_task không khả dụng
                    safe_page_update(self.page)
        except Exception as e:
            logging.debug(f"Error updating page from metrics service: {e}")
            pass  # Ignore errors khi page chua san sang

    def _request_visible_tokens(self):
        """Request tokens cho cac files dang hien thi"""
        if not self.tree:
            return

        # Collect visible paths
        visible = self.matched_paths if self.search_query else None
        self._token_service.request_tokens_for_tree(
            self.tree,
            page=self.page,
            visible_only=bool(self.search_query),
            visible_paths=visible,
        )

    def _request_visible_lines(self):
        """Request line counts cho cac files dang hien thi"""
        if not self.tree:
            return

        # Collect visible paths
        visible = self.matched_paths if self.search_query else None
        self._line_service.request_lines_for_tree(
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
