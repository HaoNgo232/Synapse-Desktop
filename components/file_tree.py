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
from typing import Callable, Optional, Set, Dict

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
        on_preview: Optional[Callable[[str], None]] = None,
        show_tokens: bool = True,
        show_lines: bool = False,  # PERFORMANCE: Disabled by default - đếm lines tốn I/O
    ):
        self.page = page
        self.on_selection_changed = on_selection_changed
        self.on_preview = on_preview  # Callback khi user muốn preview file
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
        
        # PERFORMANCE: Throttle metrics updates để tránh re-render spam với project lớn (700+ files)
        self._last_metrics_update_time: float = 0.0
        self._metrics_update_interval: float = 1.5  # 1500ms minimum between updates
        self._is_disposed = False  # Disposal flag để prevent callbacks sau cleanup
        self._pending_metrics_render: bool = False  # Flag để coalesce multiple updates
        self._metrics_render_scheduled: bool = False  # Prevent multiple scheduled renders
        
        # PERFORMANCE: Path to TreeItem index cho O(1) lookup
        self._path_index: Dict[str, TreeItem] = {}

    def cleanup(self):
        """Cleanup resources when component is destroyed"""
        # Set disposal flag FIRST để prevent race với Timer callbacks
        self._is_disposed = True
        
        # Cancel search timer safely
        timer = self._search_timer
        self._search_timer = None
        if timer is not None:
            try:
                timer.cancel()  # Use cancel for Timer
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
        
        AGGRESSIVE CLEANUP: Stop ALL background operations IMMEDIATELY.
        """
        from services.token_display import stop_token_counting
        from core.logging_config import log_info, log_debug
        
        log_info("[FileTree] reset_for_new_tree START - aggressive cleanup")
        
        # Stop global token counting FIRST - this sets the cancellation flag
        stop_token_counting()
        
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

        # Stop token service COMPLETELY - this cancels ALL deferred timers
        # CRITICAL: Phải gọi stop() để cancel tất cả pending operations
        self._token_service.stop()
        
        # Reset disposed flag vì service sẽ được reuse cho tree mới
        self._token_service._is_disposed = False

        # Clear line count service cache
        self._line_service.clear_cache()

        # Reset rendering state - prevent any pending render operations
        with self._ui_lock:
            self._is_rendering = False
        
        # Clear all selection state for clean slate
        with self._selection_lock:
            self.selected_paths.clear()
            self.expanded_paths.clear()
            self.matched_paths.clear()
        
        # Reset search state
        self.search_query = ""
        self.tree = None
        
        # Ensure component is not disposed (will be reused)
        self._is_disposed = False
        
        log_info("[FileTree] reset_for_new_tree COMPLETE")

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

        # Tree container - sử dụng ListView với virtual scrolling
        # build_controls_on_demand=True chỉ render items trong viewport
        self.tree_container = ft.ListView(
            controls=[
                ft.Text(
                    "Open a folder to see files",
                    color=ThemeColors.TEXT_MUTED,
                    italic=True,
                    size=14,
                )
            ],
            spacing=0,
            padding=0,
            expand=True,
            item_extent=32,  # Fixed height cho virtual scrolling
            build_controls_on_demand=True,  # KEY: Chỉ render visible items
            cache_extent=200,  # Pre-render 200px trước/sau viewport
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

        LAZY LOADING: KHÔNG tự động request tokens/lines.
        Tokens/lines sẽ được count khi user select files.

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
        
        # PERFORMANCE: Build path index cho O(1) lookup
        self._path_index.clear()
        self._build_path_index(tree)

        if preserve_selection:
            # Lay tat ca paths trong tree moi - dùng path_index thay vì traverse
            valid_paths = set(self._path_index.keys())

            # Giu lai cac paths van ton tai
            self.selected_paths = old_selected & valid_paths

            # Auto-select files moi trong cac folders da duoc chon
            for folder_path in old_selected_folders:
                self._auto_select_children_in_folder(tree, folder_path)
        else:
            self.selected_paths.clear()

        # Clear token cache - DO NOT request tokens automatically
        # Tokens will be counted LAZILY when user selects files
        self._token_service.clear_cache()
        self._line_service.clear_cache()
        
        # Render tree immediately - no token/line counting
        self._render_tree()

        # ========================================
        # LAZY LOADING: NO automatic token/line counting
        # This makes folder switching INSTANT
        # Tokens/lines will be displayed as user selects files
        # ========================================
    
    def _build_path_index(self, item: TreeItem):
        """
        Build path -> TreeItem index cho O(1) lookup.
        
        Gọi khi set_tree() hoặc khi lazy load children.
        """
        self._path_index[item.path] = item
        for child in item.children:
            self._build_path_index(child)

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
        
        PERFORMANCE: Sử dụng os.path.isdir thay vì Path.is_dir() để nhanh hơn.
        """
        import os
        
        if not self.search_query:
            # Khong co search -> tra ve tat ca (behavior goc)
            return self.selected_paths.copy()

        # Co search -> chi tra ve paths dang hien thi
        # Chi lay files (khong lay folders) de tranh duplicate
        visible_selected: Set[str] = set()

        for path in self.selected_paths:
            # Path phai nam trong matched_paths (dang hien thi)
            if path in self.matched_paths:
                # PERFORMANCE: Dùng os.path.isdir thay vì Path().is_dir()
                if not os.path.isdir(path):
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
        if self.search_field.suffix and hasattr(self.search_field.suffix, 'visible'):
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
        if self.search_field.suffix and hasattr(self.search_field.suffix, 'visible'):
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
        Render tree vao UI - thread safe với virtual scrolling support.
        
        Với ListView.build_controls_on_demand=True, Flet sẽ chỉ thực sự
        render những controls trong viewport. Ta vẫn cần tạo tất cả
        controls nhưng chúng sẽ được lazy-built.
        
        RACE CONDITION FIX: Sử dụng atomic check-and-set pattern.
        """
        from core.logging_config import log_info, log_error, log_debug
        log_debug(f"[FileTree] _render_tree START")
        
        with self._ui_lock:
            if self._is_rendering or self._is_disposed:
                log_debug(f"[FileTree] _render_tree SKIP - is_rendering={self._is_rendering}")
                return
            self._is_rendering = True
        
        if not self.tree_container or not self.tree:
            log_debug(f"[FileTree] _render_tree SKIP - missing tree_container or tree")
            with self._ui_lock:
                self._is_rendering = False
            return
            
        try:
            self.tree_container.controls.clear()

            # Track rendered count - với virtual scrolling có thể tăng limit
            self._rendered_count = 0
            self._max_render_items = 50000  # Tăng limit vì virtual scrolling

            self._render_tree_item(self.tree, 0)
            
            log_debug(f"[FileTree] Created {self._rendered_count} controls (virtual scroll enabled)")

            # Add truncation notice if still exceeds
            if self._rendered_count >= self._max_render_items:
                self.tree_container.controls.append(
                    ft.Text(
                        f"[Showing first {self._max_render_items} items. Use search to find more.]",
                        color=ThemeColors.TEXT_MUTED,
                        italic=True,
                        size=11,
                    )
                )

            if self.page and self.tree_container:
                try:
                    safe_page_update(self.page)
                except AssertionError as e:
                    log_debug(f"[FileTree] AssertionError in page update: {e}")
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
            # PERFORMANCE: Tăng debounce lên 250ms để giảm render spam với project lớn (700+ files)
            self._render_timer = SafeTimer(
                interval=0.25,  # 250ms debounce (tăng từ 150ms)
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

    # Reusable empty container to reduce allocations
    _EMPTY_CONTAINER = None
    
    @classmethod
    def _get_empty_container(cls) -> ft.Container:
        """Get cached empty container to reduce allocations."""
        if cls._EMPTY_CONTAINER is None:
            cls._EMPTY_CONTAINER = ft.Container(width=0)
        return cls._EMPTY_CONTAINER

    def _render_tree_item(self, item: TreeItem, depth: int):
        """Render mot item voi search highlighting - optimized version"""

        # Check render limit
        if (
            hasattr(self, "_rendered_count")
            and self._rendered_count >= self._max_render_items
        ):
            return

        # Neu dang search, chi hien thi matched items
        if self.search_query and item.path not in self.matched_paths:
            return

        # Pre-compute commonly used values
        indent = depth * 16
        is_selected = item.path in self.selected_paths
        is_expanded = item.path in self.expanded_paths
        is_dir = item.is_dir
        # LAZY LOADING FIX: Hiển thị mũi tên cho folders chưa loaded
        # Folder có is_loaded=False có thể có children chưa được scan
        has_children = is_dir and (len(item.children) > 0 or not item.is_loaded)
        is_match = self.search_query and self.search_query in item.label.lower()
        
        # Cache item path for closures (avoid repeated attribute access)
        item_path = item.path
        item_children = item.children

        # Expand/Collapse arrow - optimized
        expand_icon: ft.Control
        if has_children:
            # Only count visible children if searching (lazy evaluation)
            has_visible = True
            if self.search_query:
                has_visible = any(c.path in self.matched_paths for c in item_children)

            if has_visible:
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
                    on_click=lambda e, p=item_path: self._toggle_expand(p),
                )
            else:
                expand_icon = ft.Container(width=24)
        else:
            expand_icon = ft.Container(width=24)

        # Checkbox with captured path
        checkbox = ft.Checkbox(
            value=is_selected,
            active_color=ThemeColors.PRIMARY,
            check_color="#FFFFFF",
            on_change=lambda e, p=item_path, d=is_dir, c=item_children: self._on_item_toggled(
                e, p, d, c
            ),
        )

        # Icon selection
        if is_dir:
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

        # Preview button cho files (khong phai folders)
        preview_btn: ft.Control = ft.Container(width=0)  # Default empty
        if not item.is_dir and self.on_preview:
            # Tao wrapper function de tranh lambda closure warning
            def make_preview_handler(file_path: str):
                def handler(e):
                    self._handle_preview(file_path)

                return handler

            preview_btn = ft.IconButton(
                icon=ft.Icons.VISIBILITY,
                icon_size=16,
                icon_color=ThemeColors.TEXT_MUTED,
                tooltip="Preview file",
                width=24,
                height=24,
                padding=0,
                on_click=make_preview_handler(item.path),
            )

        # GestureDetector de xu ly double-click
        # Tao wrapper function de tranh lambda closure warning
        def make_double_tap_handler(file_path: str, is_directory: bool):
            def handler(e):
                self._handle_double_tap(file_path, is_directory)

            return handler

        label_with_gesture = ft.GestureDetector(
            content=label_container,
            on_double_tap=make_double_tap_handler(item.path, item.is_dir),
        )

        # Build row controls list efficiently
        row_controls: list[ft.Control] = [
            ft.Container(width=indent),
            expand_icon,
            checkbox,
            ft.Icon(icon, size=18, color=icon_color),
            label_with_gesture,
            preview_btn,
        ]
        
        # Add optional badges only if enabled
        # PERFORMANCE: Truyền depth để chỉ hiển thị badges cho root level
        if self.show_lines:
            line_badge = self._create_line_count_badge(item, depth)
            if line_badge:
                row_controls.append(line_badge)
        
        if self.show_tokens:
            token_badge = self._create_token_badge(item, depth)
            if token_badge:
                row_controls.append(token_badge)

        row = ft.Row(row_controls, spacing=2)

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
        """Toggle expand/collapse - thread safe với lazy loading support"""
        with self._ui_lock:
            if path in self.expanded_paths:
                self.expanded_paths.discard(path)
            else:
                self.expanded_paths.add(path)
                # Check if folder needs lazy loading
                self._maybe_lazy_load(path)
        self._schedule_render()
    
    def _maybe_lazy_load(self, folder_path: str):
        """
        Lazy load children của folder nếu chưa được load.
        
        Kiểm tra TreeItem.is_loaded flag.
        Nếu False, trigger load children on-demand.
        """
        if not self.tree:
            return
        
        folder_item = self._find_item_by_path(self.tree, folder_path)
        if not folder_item or not folder_item.is_dir:
            return
        
        # Check is_loaded flag
        if not folder_item.is_loaded:
            from core.logging_config import log_info
            log_info(f"[FileTree] Lazy loading children for expand: {folder_path}")
            from core.utils.file_utils import load_folder_children
            load_folder_children(folder_item)
            log_info(f"[FileTree] Loaded {len(folder_item.children)} children")
            
            # PERFORMANCE: Update path index với newly loaded children
            for child in folder_item.children:
                self._build_path_index(child)
    
    def _load_folder_children(self, folder_item: TreeItem):
        """
        Load children của folder on-demand.
        
        Gọi từ _maybe_lazy_load khi user expand folder chưa được load.
        """
        from pathlib import Path
        from core.utils.file_scanner import scan_directory_lazy, start_scanning, stop_scanning
        from views.settings_view import get_excluded_patterns, get_use_gitignore
        
        folder_path = Path(folder_item.path)
        if not folder_path.exists() or not folder_path.is_dir():
            return
        
        # Get root path từ tree
        root_path = Path(self.tree.path) if self.tree else folder_path
        
        try:
            start_scanning()
            
            excluded = get_excluded_patterns()
            use_gitignore = get_use_gitignore()
            
            loaded_item = scan_directory_lazy(
                folder_path,
                root_path,
                excluded_patterns=excluded,
                use_gitignore=use_gitignore,
            )
            
            # Update children
            folder_item.children = loaded_item.children
            folder_item._lazy_loaded = True  # type: ignore
            
            # Request tokens cho newly loaded children
            if self.show_tokens:
                for child in folder_item.children:
                    if not child.is_dir:
                        self._token_service.request_token_count(child.path, self.page)
            
            if self.show_lines:
                for child in folder_item.children:
                    if not child.is_dir:
                        self._line_service.request_line_count(child.path)
                        
        except Exception as e:
            from core.logging_config import log_error
            log_error(f"[FileTree] Lazy load failed for {folder_path}: {e}")
        finally:
            stop_scanning()

    def _collect_all_folder_paths(self, item: TreeItem):
        """Collect all folder paths for expand all"""
        if item.is_dir:
            self.expanded_paths.add(item.path)
            for child in item.children:
                self._collect_all_folder_paths(child)

    # =========================================================================
    # FILE PREVIEW
    # =========================================================================

    def _handle_preview(self, file_path: str):
        """
        Xu ly khi user click preview button.
        Goi callback on_preview neu duoc cung cap.
        """
        if self.on_preview and not Path(file_path).is_dir():
            self.on_preview(file_path)

    def _handle_double_tap(self, file_path: str, is_dir: bool):
        """
        Xu ly khi user double-click vao item.
        - Folder: toggle expand/collapse
        - File: goi preview callback
        """
        if is_dir:
            self._toggle_expand(file_path)
        elif self.on_preview:
            self.on_preview(file_path)

    # =========================================================================
    # SELECTION
    # =========================================================================

    def _on_item_toggled(self, e, path: str, is_dir: bool, children: list):
        """
        Xu ly khi item duoc tick/untick - thread safe.
        
        RACE CONDITION FIX: Sử dụng atomic check pattern.
        Check _is_rendering VÀ thao tác selection trong cùng một lock.
        
        LAZY LOADING: Khi check folder, lazy load children nếu chưa loaded.
        """
        from core.logging_config import log_info
        log_info(f"[FileTree] _on_item_toggled: path={path}, is_dir={is_dir}, value={e.control.value}")
        
        # LAZY LOADING: Nếu check folder chưa loaded, load children trước
        if e.control.value and is_dir:
            # Tìm item trong tree
            item = self._find_item_by_path(self.tree, path) if self.tree else None
            if item and not item.is_loaded:
                log_info(f"[FileTree] Lazy loading children for: {path}")
                from core.utils.file_utils import load_folder_children
                load_folder_children(item)
                # Update children reference
                children = item.children
                log_info(f"[FileTree] Loaded {len(children)} children")
        
        # ========================================
        # RACE CONDITION FIX: Atomic check trong lock
        # Check _is_rendering và _is_disposed BÊN TRONG lock
        # để tránh TOCTOU vulnerability
        # ========================================
        with self._ui_lock:
            # Skip nếu đang render hoặc đã cleanup
            if self._is_rendering or self._is_disposed:
                log_info(f"[FileTree] _on_item_toggled SKIP - is_rendering={self._is_rendering}, is_disposed={self._is_disposed}")
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
        
        log_info(f"[FileTree] Selection updated. Total selected: {len(self.selected_paths)}")

        # LAZY LOADING + TOKEN DISPLAY FIX:
        # Khi check folder, cần re-render để hiển thị:
        # 1. Mũi tên expand (vì children đã được loaded)
        # 2. Token count cho folder
        if is_dir and e.control.value:
            # Trigger token counting cho files trong folder đã loaded
            self._trigger_folder_token_counting_for_selected(path)
            # Re-render để hiển thị mũi tên và tokens
            self._schedule_render()

        # Notify parent NGOÀI lock
        if self.on_selection_changed:
            self.on_selection_changed(self.selected_paths)

    def _select_all_children(self, children: list):
        """
        Chon tat ca children recursively.
        
        LAZY LOADING: Nếu folder chưa loaded, load trước rồi mới select.
        PERFORMANCE: Dùng iteration thay vì recursion để tránh stack overflow với folder sâu.
        """
        from core.utils.file_utils import load_folder_children
        
        # PERFORMANCE: Dùng stack-based iteration thay vì recursion
        stack = list(children)
        
        while stack:
            child = stack.pop()
            self.selected_paths.add(child.path)
            
            # Nếu là folder chưa loaded → load children trước
            if child.is_dir and not child.is_loaded:
                load_folder_children(child)
            
            # Add children vào stack (đã loaded)
            if child.children:
                stack.extend(child.children)

    def _deselect_all_children(self, children: list):
        """Bo chon tat ca children - stack-based để tránh stack overflow"""
        # PERFORMANCE: Dùng stack-based iteration thay vì recursion
        stack = list(children)
        
        while stack:
            child = stack.pop()
            self.selected_paths.discard(child.path)
            if child.children:
                stack.extend(child.children)

    # =========================================================================
    # LINE COUNT & TOKEN DISPLAY
    # =========================================================================

    def _create_line_count_badge(self, item: TreeItem, depth: int = 0) -> ft.Container:
        """
        Tao badge hien thi line count cho file hoac folder.
        - File: hien thi line count cua file
        - Folder: hien thi tong lines cua tat ca files ben trong (co the la partial)
        
        OPTIMIZED:
        - Chỉ hiển thị line badge cho root level (depth <= 1) folders
        - Folders sâu hơn chỉ hiện badge khi được expand
        """
        if item.is_dir:
            # PERFORMANCE: Chỉ tính và hiển thị lines cho:
            # 1. Root level items (depth <= 1)
            # 2. Folders đang được expand
            is_expanded = item.path in self.expanded_paths
            should_show_folder_lines = depth <= 1 or is_expanded
            
            if not should_show_folder_lines:
                return ft.Container(width=0)
            
            # Folder: lay tong va status tu service
            assert self.tree is not None
            folder_lines, is_complete = self._line_service.get_folder_lines_status(
                item.path, self.tree
            )
            
            if folder_lines == 0:
                # Empty folder hoac chua co files nao duoc cache
                # Chỉ trigger counting cho root level hoặc expanded folders
                if should_show_folder_lines:
                    self._trigger_folder_line_counting(item)
                return ft.Container(width=0)
            
            # Format line text voi indicator "~" neu chua complete
            line_text = self._line_service._format_lines(folder_lines)
            if not is_complete:
                line_text = f"~{line_text}"  # ~ chi partial sum
        else:
            # File: lay tu cache
            line_text = self._line_service.get_line_display(item.path)
            if not line_text:
                # Chua co - request va return empty
                self._line_service.request_line_count(item.path)
                return ft.Container(width=0)

        # Format voi suffix "lines" de de phan biet voi tokens
        return ft.Container(
            content=ft.Text(
                f"{line_text} lines",  # lines suffix
                size=11,
                color=ThemeColors.PRIMARY,  # Mau xanh duong de phan biet voi token (SUCCESS - xanh la)
                weight=ft.FontWeight.W_500,
            ),
            margin=ft.margin.only(left=8),
        )
    
    def _trigger_folder_line_counting(self, folder_item: TreeItem):
        """
        Trigger line counting cho tat ca files trong folder.
        
        Goi khi folder hien thi nhung chua co lines cached.
        Chi request cho files chua duoc cached.
        """
        if not folder_item.is_dir:
            return
        
        # Collect all files in folder va request counting
        def collect_and_request(item: TreeItem):
            for child in item.children:
                if child.is_dir:
                    collect_and_request(child)
                else:
                    # Request line count cho file
                    self._line_service.request_line_count(child.path)
        
        collect_and_request(folder_item)

    def _create_token_badge(self, item: TreeItem, depth: int = 0) -> ft.Container:
        """
        Tao badge hien thi token count cho file hoac folder.
        - File: hien thi token count cua file
        - Folder: hien thi tong tokens cua tat ca files ben trong (co the la partial)
        
        OPTIMIZED: 
        - Chỉ hiển thị token badge cho root level (depth <= 1) folders
        - Folders sâu hơn chỉ hiện badge khi được expand
        - Sử dụng folder cache để tránh tính toán lại
        """
        if item.is_dir:
            # PERFORMANCE: Chỉ tính và hiển thị tokens cho:
            # 1. Root level items (depth <= 1)
            # 2. Folders đang được expand
            is_expanded = item.path in self.expanded_paths
            should_show_folder_tokens = depth <= 1 or is_expanded
            
            if not should_show_folder_tokens:
                return ft.Container(width=0)
            
            # Folder: lay tong va status tu service (sử dụng cache)
            assert self.tree is not None
            folder_tokens, is_complete = self._token_service.get_folder_tokens_status(
                item.path, self.tree
            )
            
            if folder_tokens == 0:
                # Empty folder hoac chua co files nao duoc cache
                # Chỉ trigger counting cho root level hoặc expanded folders
                if should_show_folder_tokens:
                    self._trigger_folder_token_counting(item)
                return ft.Container(width=0)
            
            # Format token text voi indicator "~" neu chua complete
            token_text = self._token_service._format_tokens(folder_tokens)
            if not is_complete:
                token_text = f"~{token_text}"  # ~ chi partial sum
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
    
    def _trigger_folder_token_counting(self, folder_item: TreeItem):
        """
        Trigger token counting cho tat ca files trong folder.
        
        Goi khi folder hien thi nhung chua co tokens cached.
        Chi request cho files chua duoc cached.
        """
        if not folder_item.is_dir:
            return
        
        # Collect all files in folder va request counting
        def collect_and_request(item: TreeItem):
            for child in item.children:
                if child.is_dir:
                    collect_and_request(child)
                else:
                    # Request token count cho file
                    self._token_service.request_token_count(child.path, self.page)
        
        collect_and_request(folder_item)

    def _trigger_folder_token_counting_for_selected(self, folder_path: str):
        """
        Trigger token counting cho folder được check.
        
        Khác với _trigger_folder_token_counting, method này:
        1. Tìm folder trong tree theo path
        2. Đếm tokens cho tất cả files đã loaded trong folder
        3. Dùng parallel counting để nhanh hơn
        
        Args:
            folder_path: Path của folder được check
        """
        from core.logging_config import log_info
        from services.token_display import start_token_counting, is_counting_tokens
        from core.token_counter import count_tokens_batch_parallel
        from pathlib import Path
        
        if not self.tree:
            return
        
        folder_item = self._find_item_by_path(self.tree, folder_path)
        if not folder_item or not folder_item.is_dir:
            return
        
        # Collect all files trong folder đã loaded
        files_to_count: list[str] = []
        
        def collect_files(item: TreeItem):
            for child in item.children:
                if child.is_dir:
                    # Recurse vào folder đã loaded
                    if child.is_loaded:
                        collect_files(child)
                else:
                    # Chỉ add files chưa có trong cache
                    if self._token_service.get_token_count(child.path) is None:
                        files_to_count.append(child.path)
        
        collect_files(folder_item)
        
        if not files_to_count:
            log_info(f"[FileTree] No files to count for folder: {folder_path}")
            return
        
        log_info(f"[FileTree] Counting tokens for {len(files_to_count)} files in {folder_path}")
        
        # Start counting
        start_token_counting()
        
        # Count in background để không block UI
        def do_count():
            if not is_counting_tokens():
                return
            
            # Parallel counting
            file_paths = [Path(p) for p in files_to_count]
            results = count_tokens_batch_parallel(file_paths, max_workers=4)
            
            # Update cache
            if results and is_counting_tokens():
                with self._token_service._lock:
                    self._token_service._cache.update(results)
                
                # Trigger UI update
                if self._token_service.on_update:
                    self._token_service.on_update()
        
        # Run in background thread
        import threading
        thread = threading.Thread(target=do_count, daemon=True)
        thread.start()


    def _on_metrics_updated(self):
        """
        Callback khi TokenService hoac LineService update cache.

        RACE CONDITION FIX: Callback này có thể được gọi từ background context.
        
        PERFORMANCE FIX v4: 
        - Coalesce multiple updates với pending flag
        - Chỉ schedule 1 render cho nhiều metric updates
        - Giảm main thread blocking đáng kể với project lớn (700+ files)
        - KHÔNG render ngay - chỉ schedule deferred render
        """
        import time
        import threading
        
        # Skip nếu đã disposed
        if self._is_disposed:
            return
        
        # PERFORMANCE: Throttle với coalescing - KHÔNG render ngay
        current_time = time.time()
        time_since_last = current_time - self._last_metrics_update_time
        
        if time_since_last < self._metrics_update_interval:
            # Mark pending và schedule deferred render nếu chưa có
            self._pending_metrics_render = True
            if not self._metrics_render_scheduled:
                self._metrics_render_scheduled = True
                def deferred_metrics_render():
                    self._metrics_render_scheduled = False
                    if self._pending_metrics_render and not self._is_disposed:
                        self._pending_metrics_render = False
                        self._last_metrics_update_time = time.time()
                        self._schedule_render()
                timer = threading.Timer(self._metrics_update_interval, deferred_metrics_render)
                timer.daemon = True
                timer.start()
            return
        
        self._last_metrics_update_time = current_time
        self._pending_metrics_render = False
        
        # Schedule debounced render (không render trực tiếp)
        self._schedule_render()

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
        
        OPTIMIZED: Sử dụng path_index cho O(1) lookup.

        Args:
            item: TreeItem hien tai (ignored, kept for backward compatibility)
            target_path: Path can tim

        Returns:
            TreeItem neu tim thay, None neu khong
        """
        # PERFORMANCE: O(1) lookup từ index
        return self._path_index.get(target_path)
