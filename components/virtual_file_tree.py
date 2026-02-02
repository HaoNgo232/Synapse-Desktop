"""
Virtual File Tree Component - Tối ưu cho >10,000 items

Sử dụng Flet ListView với build_controls_on_demand=True để chỉ render
items trong viewport. Kết hợp incremental updates để tránh full re-render.

Features:
- Virtual scrolling với ListView
- Incremental tree updates (chỉ update items thay đổi)
- Flattened tree structure cho O(1) lookup
- Background token counting với ThreadPoolExecutor
"""

import flet as ft
import threading
from threading import Timer
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Callable, Optional, Set, Dict, List, Tuple
from dataclasses import dataclass

from core.utils.file_utils import TreeItem
from services.token_display import TokenDisplayService
from services.line_count_display import LineCountService
from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update
from core.utils.safe_timer import SafeTimer


@dataclass
class FlatTreeItem:
    """
    Flattened tree item cho virtual scrolling.
    
    Thay vì nested structure, ta flatten tree thành list với depth info.
    Điều này cho phép:
    - O(1) lookup by index
    - Dễ dàng virtual scrolling
    - Incremental updates
    """
    path: str
    label: str
    is_dir: bool
    depth: int
    is_expanded: bool
    has_children: bool
    parent_path: Optional[str]
    # Cached token/line counts
    token_count: Optional[int] = None
    line_count: Optional[int] = None


class VirtualFileTreeComponent:
    """
    High-performance File Tree với Virtual Scrolling.
    
    Tối ưu cho trees với >10,000 items bằng cách:
    1. Sử dụng ListView.build_controls_on_demand để chỉ render visible items
    2. Flatten tree structure để O(1) lookup
    3. Incremental updates thay vì full re-render
    4. Background token counting với ThreadPoolExecutor
    """

    # Config
    ITEM_HEIGHT = 32  # Fixed height cho mỗi row (cần cho virtual scroll)
    MAX_VISIBLE_ITEMS = 100  # Số items tối đa render cùng lúc
    TOKEN_WORKER_COUNT = 4  # Số threads cho token counting
    
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

        # Flattened tree for virtual scrolling
        self._flat_items: List[FlatTreeItem] = []
        self._path_to_index: Dict[str, int] = {}  # O(1) lookup
        self._visible_items: List[FlatTreeItem] = []  # After filtering

        # Token display service
        self._token_service = TokenDisplayService(on_update=self._on_metrics_updated)
        self._line_service = LineCountService(on_update=self._on_metrics_updated)

        # Background workers for heavy operations
        self._token_executor: Optional[ThreadPoolExecutor] = None
        self._pending_token_tasks: Dict[str, Future] = {}

        # UI elements
        self.list_view: Optional[ft.ListView] = None
        self.search_field: Optional[ft.TextField] = None
        self.match_count_text: Optional[ft.Text] = None
        self.loading_indicator: Optional[ft.ProgressRing] = None

        # Threading
        self._selection_lock = threading.Lock()
        self._ui_lock = threading.Lock()
        self._is_disposed = False
        
        # Debounce timers
        self._search_timer: Optional[Timer] = None
        self._render_timer: Optional[SafeTimer] = None
        self._search_debounce_ms: float = 150

    def cleanup(self):
        """Cleanup resources"""
        self._is_disposed = True
        
        # Cancel timers
        if self._search_timer:
            self._search_timer.cancel()
            self._search_timer = None
            
        if self._render_timer:
            self._render_timer.dispose()
            self._render_timer = None

        # Shutdown executor
        if self._token_executor:
            self._token_executor.shutdown(wait=False, cancel_futures=True)
            self._token_executor = None

        # Stop services
        self._token_service.stop()
        self._token_service.clear_cache()
        self._line_service.clear_cache()

    def reset_for_new_tree(self):
        """Reset component để load tree mới"""
        if self._search_timer:
            self._search_timer.cancel()
            self._search_timer = None
            
        if self._render_timer:
            self._render_timer.dispose()
            self._render_timer = None

        self._token_service.stop()
        self._token_service.clear_cache()
        self._line_service.clear_cache()
        
        self._flat_items.clear()
        self._path_to_index.clear()
        self._visible_items.clear()
        
        self._is_disposed = False

    def build(self) -> ft.Container:
        """Build UI với virtual scrolling ListView"""
        
        # Search field
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

        self.loading_indicator = ft.ProgressRing(
            width=20,
            height=20,
            stroke_width=2,
            color=ThemeColors.PRIMARY,
            visible=False,
        )

        # Virtual scrolling ListView
        # build_controls_on_demand=True là key cho virtual scrolling
        # item_extent giúp tính toán scroll position chính xác
        self.list_view = ft.ListView(
            controls=[],
            spacing=0,
            padding=0,
            expand=True,
            item_extent=self.ITEM_HEIGHT,  # Fixed height cho virtual scroll
            build_controls_on_demand=True,  # Chỉ render visible items
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
                    # Virtual ListView
                    self.list_view,
                ],
                expand=True,
            ),
            expand=True,
        )

    def set_tree(self, tree: TreeItem, preserve_selection: bool = False):
        """Set tree data và render với virtual scrolling"""
        old_selected = self.selected_paths.copy() if preserve_selection else set()
        old_selected_folders: Set[str] = set()
        
        if preserve_selection:
            for path in old_selected:
                if Path(path).is_dir():
                    old_selected_folders.add(path)

        self.tree = tree
        self.expanded_paths = {tree.path}
        self.search_query = ""
        self.matched_paths.clear()

        # Flatten tree
        self._flatten_tree(tree)

        if preserve_selection:
            valid_paths = set(self._path_to_index.keys())
            self.selected_paths = old_selected & valid_paths
            
            for folder_path in old_selected_folders:
                self._auto_select_children_in_folder(folder_path)
        else:
            self.selected_paths.clear()

        # Clear caches
        self._token_service.clear_cache()
        self._line_service.clear_cache()

        # Update visible items and render
        self._update_visible_items()
        self._render_virtual_tree()

        # Start background token counting
        if self.show_tokens:
            self._start_background_token_counting()

    def _flatten_tree(self, tree: TreeItem):
        """
        Flatten tree thành list cho virtual scrolling.
        
        Thay vì recursive rendering, ta pre-compute flat list.
        Điều này cho phép O(1) lookup và efficient virtual scrolling.
        """
        self._flat_items.clear()
        self._path_to_index.clear()
        
        self._flatten_recursive(tree, depth=0, parent_path=None)

    def _flatten_recursive(
        self, 
        item: TreeItem, 
        depth: int, 
        parent_path: Optional[str]
    ):
        """Recursive flatten helper"""
        flat_item = FlatTreeItem(
            path=item.path,
            label=item.label,
            is_dir=item.is_dir,
            depth=depth,
            is_expanded=item.path in self.expanded_paths,
            has_children=len(item.children) > 0,
            parent_path=parent_path,
        )
        
        index = len(self._flat_items)
        self._flat_items.append(flat_item)
        self._path_to_index[item.path] = index

        # Recurse into children (nhưng không render ngay)
        for child in item.children:
            self._flatten_recursive(child, depth + 1, item.path)

    def _update_visible_items(self):
        """
        Update danh sách visible items dựa trên:
        - Expanded state của parent folders
        - Search filter
        
        Chỉ những items này sẽ được render.
        """
        self._visible_items.clear()
        
        # Build set of expanded ancestor paths for quick lookup
        expanded_ancestors: Set[str] = set()
        for item in self._flat_items:
            if item.is_dir and item.path in self.expanded_paths:
                expanded_ancestors.add(item.path)

        for item in self._flat_items:
            # Check if item should be visible
            if not self._is_item_visible(item, expanded_ancestors):
                continue
                
            # Check search filter
            if self.search_query and item.path not in self.matched_paths:
                continue
                
            self._visible_items.append(item)

    def _is_item_visible(
        self, 
        item: FlatTreeItem, 
        expanded_ancestors: Set[str]
    ) -> bool:
        """Check if item is visible (all ancestors are expanded)"""
        if item.parent_path is None:
            return True  # Root item
            
        # Walk up the tree to check all ancestors
        current_parent = item.parent_path
        while current_parent:
            if current_parent not in expanded_ancestors:
                return False
            
            # Get parent's parent
            parent_idx = self._path_to_index.get(current_parent)
            if parent_idx is not None:
                current_parent = self._flat_items[parent_idx].parent_path
            else:
                break
                
        return True

    def _render_virtual_tree(self):
        """
        Render virtual tree - chỉ tạo controls cho visible items.
        
        ListView với build_controls_on_demand sẽ chỉ thực sự render
        những items trong viewport.
        """
        if not self.list_view or self._is_disposed:
            return

        with self._ui_lock:
            # Clear và rebuild controls list
            self.list_view.controls.clear()
            
            for item in self._visible_items:
                control = self._create_tree_row(item)
                self.list_view.controls.append(control)

        safe_page_update(self.page)

    def _create_tree_row(self, item: FlatTreeItem) -> ft.Container:
        """Tạo một row cho virtual list"""
        indent = item.depth * 16
        is_expanded = item.is_dir and item.path in self.expanded_paths
        is_match = self.search_query and self.search_query in item.label.lower()

        # Expand/Collapse arrow
        if item.is_dir and item.has_children:
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
                on_click=lambda e, p=item.path: self._toggle_expand(p),
            )
        else:
            expand_icon = ft.Container(width=24)

        # Checkbox
        checkbox = ft.Checkbox(
            value=item.path in self.selected_paths,
            active_color=ThemeColors.PRIMARY,
            check_color="#FFFFFF",
            on_change=lambda e, i=item: self._on_item_toggled(e, i),
        )

        # Icon
        if item.is_dir:
            icon = ft.Icons.FOLDER_OPEN if is_expanded else ft.Icons.FOLDER
            icon_color = ThemeColors.ICON_FOLDER
        else:
            icon = ft.Icons.INSERT_DRIVE_FILE
            icon_color = ThemeColors.ICON_FILE

        # Label với highlight
        text_weight = ft.FontWeight.W_500 if item.is_dir else ft.FontWeight.NORMAL
        text_bgcolor = ThemeColors.SEARCH_HIGHLIGHT if is_match else None

        label_container = ft.Container(
            content=ft.Text(
                item.label, 
                size=13, 
                color=ThemeColors.TEXT_PRIMARY, 
                weight=text_weight
            ),
            bgcolor=text_bgcolor,
            padding=ft.padding.symmetric(horizontal=4, vertical=1) if is_match else 0,
            border_radius=3 if is_match else 0,
        )

        # Token badge (từ cache)
        token_badge = self._create_token_badge(item) if self.show_tokens else ft.Container()
        line_badge = self._create_line_badge(item) if self.show_lines else ft.Container()

        row = ft.Row(
            [
                ft.Container(width=indent),
                expand_icon,
                checkbox,
                ft.Icon(icon, size=18, color=icon_color),
                label_container,
                line_badge,
                token_badge,
            ],
            spacing=2,
        )

        return ft.Container(
            content=row,
            height=self.ITEM_HEIGHT,
            padding=ft.padding.symmetric(vertical=2, horizontal=4),
        )

    def _create_token_badge(self, item: FlatTreeItem) -> ft.Container:
        """Tạo token badge từ cached value"""
        if item.is_dir:
            return ft.Container(width=0)
            
        token_text = self._token_service.get_token_display(item.path)
        if not token_text:
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

    def _create_line_badge(self, item: FlatTreeItem) -> ft.Container:
        """Tạo line count badge"""
        if item.is_dir:
            return ft.Container(width=0)
            
        line_text = self._line_service.get_line_display(item.path)
        if not line_text:
            return ft.Container(width=0)

        return ft.Container(
            content=ft.Text(
                f"{line_text} lines",
                size=11,
                color=ThemeColors.PRIMARY,
                weight=ft.FontWeight.W_500,
            ),
            margin=ft.margin.only(left=8),
        )

    # =========================================================================
    # INCREMENTAL UPDATES - Thay vì full re-render
    # =========================================================================

    def _toggle_expand(self, path: str):
        """Toggle expand với incremental update"""
        with self._ui_lock:
            if path in self.expanded_paths:
                self.expanded_paths.discard(path)
            else:
                self.expanded_paths.add(path)
                
            # Update flat item state
            idx = self._path_to_index.get(path)
            if idx is not None:
                self._flat_items[idx].is_expanded = path in self.expanded_paths

        # Incremental update: chỉ recalculate visible items
        self._update_visible_items()
        self._render_virtual_tree()

    def _on_item_toggled(self, e, item: FlatTreeItem):
        """Handle checkbox toggle với incremental update"""
        with self._selection_lock:
            if e.control.value:
                self.selected_paths.add(item.path)
                if item.is_dir:
                    self._select_descendants(item.path)
            else:
                self.selected_paths.discard(item.path)
                if item.is_dir:
                    self._deselect_descendants(item.path)

        # Incremental update: chỉ update affected controls
        self._update_selection_display()

        if self.on_selection_changed:
            self.on_selection_changed(self.selected_paths)

    def _select_descendants(self, folder_path: str):
        """Select all descendants của folder"""
        folder_idx = self._path_to_index.get(folder_path)
        if folder_idx is None:
            return
            
        folder_depth = self._flat_items[folder_idx].depth
        
        # Scan forward để tìm descendants
        for i in range(folder_idx + 1, len(self._flat_items)):
            item = self._flat_items[i]
            if item.depth <= folder_depth:
                break  # No longer a descendant
            self.selected_paths.add(item.path)

    def _deselect_descendants(self, folder_path: str):
        """Deselect all descendants của folder"""
        folder_idx = self._path_to_index.get(folder_path)
        if folder_idx is None:
            return
            
        folder_depth = self._flat_items[folder_idx].depth
        
        for i in range(folder_idx + 1, len(self._flat_items)):
            item = self._flat_items[i]
            if item.depth <= folder_depth:
                break
            self.selected_paths.discard(item.path)

    def _update_selection_display(self):
        """
        Incremental update: chỉ update checkbox states.
        
        Thay vì re-render toàn bộ tree, ta chỉ update những
        checkboxes bị ảnh hưởng.
        """
        if not self.list_view:
            return

        # Update checkbox values directly
        for i, item in enumerate(self._visible_items):
            if i < len(self.list_view.controls):
                row_container = self.list_view.controls[i]
                if hasattr(row_container, 'content') and hasattr(row_container.content, 'controls'):
                    for control in row_container.content.controls:
                        if isinstance(control, ft.Checkbox):
                            new_value = item.path in self.selected_paths
                            if control.value != new_value:
                                control.value = new_value

        safe_page_update(self.page)

    # =========================================================================
    # BACKGROUND TOKEN COUNTING - Web Worker style
    # =========================================================================

    def _start_background_token_counting(self):
        """Start background threads để count tokens"""
        if self._is_disposed:
            return
            
        # Initialize executor if needed
        if self._token_executor is None:
            self._token_executor = ThreadPoolExecutor(
                max_workers=self.TOKEN_WORKER_COUNT,
                thread_name_prefix="token_worker"
            )

        # Submit tasks for visible files
        from services.token_display import start_token_counting
        start_token_counting()

        for item in self._visible_items[:200]:  # Limit initial batch
            if item.is_dir:
                continue
            if self._token_service.get_token_count(item.path) is not None:
                continue  # Already cached
                
            # Submit to background worker
            future = self._token_executor.submit(
                self._count_tokens_background,
                item.path
            )
            self._pending_token_tasks[item.path] = future

    def _count_tokens_background(self, path: str):
        """
        Background worker để count tokens.
        
        Chạy trên separate thread, không block UI.
        Kết quả được cache và UI được notify để update.
        """
        if self._is_disposed:
            return
            
        try:
            from core.token_counter import count_tokens_for_file
            from services.token_display import is_counting_tokens
            
            if not is_counting_tokens():
                return
                
            tokens = count_tokens_for_file(Path(path))
            
            # Update cache (thread-safe trong TokenDisplayService)
            self._token_service._cache[path] = tokens
            
        except Exception:
            pass
        finally:
            self._pending_token_tasks.pop(path, None)

    def _on_metrics_updated(self):
        """Callback khi token/line cache được update"""
        if self._is_disposed:
            return
            
        # Schedule incremental UI update
        if self.page:
            async def _do_update():
                self._update_metrics_display()
            try:
                self.page.run_task(_do_update)
            except Exception:
                pass

    def _update_metrics_display(self):
        """Incremental update chỉ token/line badges"""
        if not self.list_view or self._is_disposed:
            return
            
        # Chỉ update badges, không re-render toàn bộ rows
        safe_page_update(self.page)

    # =========================================================================
    # SEARCH
    # =========================================================================

    def _on_search_changed(self, e):
        """Handle search với debounce"""
        self.search_query = (e.control.value or "").lower().strip()

        # Update clear button
        if self.search_field and self.search_field.suffix:
            self.search_field.suffix.visible = bool(self.search_query)
            safe_page_update(self.page)

        # Debounce search
        if self._search_timer:
            self._search_timer.cancel()

        self._search_timer = Timer(
            self._search_debounce_ms / 1000.0,
            self._execute_search
        )
        self._search_timer.start()

    def _execute_search(self):
        """Execute search sau debounce"""
        if self._is_disposed:
            return
            
        async def _do_search():
            if self.search_query:
                self._perform_search()
            else:
                self.matched_paths.clear()
                if self.match_count_text:
                    self.match_count_text.value = ""

            self._update_visible_items()
            self._render_virtual_tree()

        if self.page:
            try:
                self.page.run_task(_do_search)
            except Exception:
                pass

    def _perform_search(self):
        """Perform search trên flattened tree"""
        self.matched_paths.clear()
        
        for item in self._flat_items:
            if self.search_query in item.label.lower():
                self.matched_paths.add(item.path)
                # Also add all ancestors
                self._add_ancestors_to_matches(item)

        # Update count
        if self.match_count_text:
            file_count = sum(
                1 for p in self.matched_paths 
                if not Path(p).is_dir()
            )
            self.match_count_text.value = f"{file_count} found"

        # Auto-expand folders containing matches
        for path in self.matched_paths:
            idx = self._path_to_index.get(path)
            if idx is not None:
                item = self._flat_items[idx]
                if item.is_dir:
                    self.expanded_paths.add(path)

    def _add_ancestors_to_matches(self, item: FlatTreeItem):
        """Add all ancestor folders to matched_paths"""
        parent_path = item.parent_path
        while parent_path:
            self.matched_paths.add(parent_path)
            idx = self._path_to_index.get(parent_path)
            if idx is not None:
                parent_path = self._flat_items[idx].parent_path
            else:
                break

    def _clear_search(self, e=None):
        """Clear search"""
        if self._search_timer:
            self._search_timer.cancel()
            self._search_timer = None

        if self.search_field:
            self.search_field.value = ""
        self.search_query = ""
        self.matched_paths.clear()
        
        if self.match_count_text:
            self.match_count_text.value = ""
        if self.search_field and self.search_field.suffix:
            self.search_field.suffix.visible = False

        self._update_visible_items()
        self._render_virtual_tree()

    def _on_search_submit(self, e):
        """Handle Enter trong search"""
        pass  # Could implement jump to first match

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_selected_paths(self) -> Set[str]:
        """Get all selected paths"""
        return self.selected_paths.copy()

    def get_visible_selected_paths(self) -> Set[str]:
        """Get selected paths that are currently visible"""
        if not self.search_query:
            return self.selected_paths.copy()

        visible_selected: Set[str] = set()
        for path in self.selected_paths:
            if path in self.matched_paths:
                if not Path(path).is_dir():
                    visible_selected.add(path)
        return visible_selected

    def is_searching(self) -> bool:
        """Check if currently searching"""
        return bool(self.search_query)

    def expand_all(self):
        """Expand all folders"""
        for item in self._flat_items:
            if item.is_dir:
                self.expanded_paths.add(item.path)
        self._update_visible_items()
        self._render_virtual_tree()

    def collapse_all(self):
        """Collapse all (keep root open)"""
        if self.tree:
            self.expanded_paths = {self.tree.path}
        self._update_visible_items()
        self._render_virtual_tree()

    def set_loading(self, is_loading: bool):
        """Set loading state"""
        if self.loading_indicator:
            self.loading_indicator.visible = is_loading
            safe_page_update(self.page)

    def _auto_select_children_in_folder(self, folder_path: str):
        """Auto-select all children trong folder"""
        self._select_descendants(folder_path)