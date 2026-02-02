"""
Context View - Tab de chon files va copy context

Su dung FileTreeComponent tu components/file_tree.py
"""

import flet as ft
import threading
from threading import Timer
from pathlib import Path
from typing import Callable, Optional, Set

from core.utils.file_utils import scan_directory, TreeItem
from core.utils.ui_utils import safe_page_update
from services.clipboard_utils import copy_to_clipboard
from core.token_counter import count_tokens_batch, count_tokens
from core.prompt_generator import (
    generate_prompt,
    generate_file_map,
    generate_file_contents,
    generate_file_contents_xml,
    generate_file_contents_xml,
    generate_file_contents_json,
    generate_file_contents_plain,
    generate_smart_context,
)
from core.utils.git_utils import get_git_diffs, get_git_logs
from core.tree_map_generator import generate_tree_map_only
from components.file_tree import FileTreeComponent
from components.token_stats import TokenStatsPanel
from core.theme import ThemeColors
from core.security_check import (
    scan_for_secrets,
    scan_secrets_in_files_cached,
    format_security_warning,
)
from views.settings_view import add_excluded_patterns, remove_excluded_patterns
from services.settings_manager import get_setting, set_setting
from services.file_watcher import FileWatcher
from core.utils.safe_timer import SafeTimer
from typing import Set
from config.output_format import (
    OutputStyle,
    OUTPUT_FORMATS,
    get_format_tooltip,
    get_style_by_id,
    DEFAULT_OUTPUT_STYLE,
)


class ContextView:
    """View cho Context tab - su dung FileTreeComponent"""

    def __init__(self, page: ft.Page, get_workspace: Callable[[], Optional[Path]]):
        self.page = page
        self.get_workspace = get_workspace

        self.tree: Optional[TreeItem] = None
        self.file_tree_component: Optional[FileTreeComponent] = None
        self.token_count_text: Optional[ft.Text] = None
        self.instructions_field: Optional[ft.TextField] = None
        self.status_text: Optional[ft.Text] = None
        self.token_stats_panel: Optional[TokenStatsPanel] = None

        # Debounce timer for token counting
        self._token_update_timer: Optional[Timer] = None
        self._token_debounce_ms: float = (
            150  # 150ms debounce (reduced for responsiveness)
        )

        # Selection change debounce
        self._selection_update_timer: Optional[SafeTimer] = None
        self._selection_debounce_ms: float = 50  # 50ms debounce for selection

        # Status auto-clear timer
        self._status_clear_timer: Optional[Timer] = None

        # Last ignored patterns for undo
        self._last_ignored_patterns: list[str] = []

        # File watcher for auto-refresh
        self._file_watcher: Optional[FileWatcher] = FileWatcher()

        # Output format selection
        self._selected_output_style: OutputStyle = DEFAULT_OUTPUT_STYLE
        self.format_dropdown: Optional[ft.Dropdown] = None
        self.format_info_icon: Optional[ft.Icon] = None
        
        # Race condition prevention
        self._loading_lock = threading.Lock()
        self._is_loading = False

        # ========================================
        # RACE CONDITION FIX: Loading state management
        # Ngăn chặn multiple concurrent _load_tree calls
        # ========================================
        self._pending_refresh: bool = False  # Flag để queue refresh request khi đang load
        self._is_disposed: bool = False  # Disposal flag để prevent callbacks sau cleanup

    def cleanup(self):
        """Cleanup resources when view is destroyed"""
        # RACE CONDITION FIX: Set disposal flag FIRST
        self._is_disposed = True
        
        # Stop any ongoing operations first
        from core.utils.file_scanner import stop_scanning
        from services.token_display import stop_token_counting

        stop_scanning()
        stop_token_counting()

        if self._token_update_timer is not None:
            try:
                self._token_update_timer.cancel()
            except Exception:
                pass
            self._token_update_timer = None

        if self._selection_update_timer is not None:
            try:
                self._selection_update_timer.dispose()  # Use dispose instead of cancel
            except Exception:
                pass
            self._selection_update_timer = None

        if self._status_clear_timer is not None:
            try:
                self._status_clear_timer.cancel()
            except Exception:
                pass
            self._status_clear_timer = None
        if self.file_tree_component:
            self.file_tree_component.cleanup()
        # Stop file watcher
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

    def build(self) -> ft.Container:
        """Build UI cho Context view"""

        # File tree component voi search
        self.file_tree_component = FileTreeComponent(
            page=self.page, on_selection_changed=self._on_selection_changed
        )

        # Token count display
        self.token_count_text = ft.Text(
            "0 tokens", size=13, weight=ft.FontWeight.W_600, color=ThemeColors.PRIMARY
        )

        self.left_panel = ft.Container(
            content=ft.Column(
                [
                    # Header với title và token count
                    ft.Row(
                        [
                            ft.Text(
                                "Files",
                                weight=ft.FontWeight.W_600,
                                size=14,
                                color=ThemeColors.TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            self.token_count_text,
                        ]
                    ),
                    # Toolbar với grouped buttons
                    ft.Container(
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            controls=[
                                # Selection group
                                ft.Row(
                                    [
                                        ft.IconButton(
                                            icon=ft.Icons.SELECT_ALL,
                                            icon_size=20,
                                            icon_color=ThemeColors.TEXT_SECONDARY,
                                            tooltip="Select All",
                                            on_click=lambda _: self._select_all(),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DESELECT,
                                            icon_size=20,
                                            icon_color=ThemeColors.TEXT_SECONDARY,
                                            tooltip="Deselect All",
                                            on_click=lambda _: self._deselect_all(),
                                        ),
                                    ],
                                    spacing=0,
                                ),
                                # Separator
                                ft.Container(
                                    width=1,
                                    height=20,
                                    bgcolor=ThemeColors.BORDER,
                                    margin=ft.margin.symmetric(horizontal=4),
                                ),
                                # Expand/Collapse group
                                ft.Row(
                                    [
                                        ft.IconButton(
                                            icon=ft.Icons.UNFOLD_MORE,
                                            icon_size=20,
                                            icon_color=ThemeColors.TEXT_SECONDARY,
                                            tooltip="Expand All",
                                            on_click=lambda _: self._expand_all(),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.UNFOLD_LESS,
                                            icon_size=20,
                                            icon_color=ThemeColors.TEXT_SECONDARY,
                                            tooltip="Collapse All",
                                            on_click=lambda _: self._collapse_all(),
                                        ),
                                    ],
                                    spacing=0,
                                ),
                                # Separator
                                ft.Container(
                                    width=1,
                                    height=20,
                                    bgcolor=ThemeColors.BORDER,
                                    margin=ft.margin.symmetric(horizontal=4),
                                ),
                                # Refresh
                                ft.IconButton(
                                    icon=ft.Icons.REFRESH,
                                    icon_size=20,
                                    icon_color=ThemeColors.TEXT_SECONDARY,
                                    tooltip="Refresh",
                                    on_click=lambda _: self._refresh_tree(),
                                ),
                                # Separator
                                ft.Container(
                                    width=1,
                                    height=20,
                                    bgcolor=ThemeColors.BORDER,
                                    margin=ft.margin.symmetric(horizontal=4),
                                ),
                                # Add to Ignore
                                ft.IconButton(
                                    icon=ft.Icons.BLOCK,
                                    icon_size=20,
                                    icon_color=ThemeColors.TEXT_SECONDARY,
                                    tooltip="Add selected to ignore list",
                                    on_click=lambda _: self._add_to_ignore(),
                                ),
                                # Undo Ignore
                                ft.IconButton(
                                    icon=ft.Icons.UNDO,
                                    icon_size=20,
                                    icon_color=ThemeColors.TEXT_SECONDARY,
                                    tooltip="Undo last ignore",
                                    on_click=lambda _: self._undo_ignore(),
                                ),
                            ],
                            spacing=0,
                        ),
                        padding=ft.padding.only(bottom=8),
                    ),
                    ft.Divider(height=1, color=ThemeColors.BORDER),
                    # File tree component
                    self.file_tree_component.build(),
                ],
                expand=True,
            ),
            padding=16,
            expand=True,
            bgcolor=ThemeColors.BG_SURFACE,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=8,
        )

        # Right panel: Instructions
        self.instructions_field = ft.TextField(
            label="User Instructions",
            multiline=True,
            min_lines=3,
            max_lines=6,
            hint_text="Enter your task instructions here...",
            expand=True,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            label_style=ft.TextStyle(color=ThemeColors.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY),
            on_change=lambda _: self._on_instructions_changed(),
        )

        self.status_text = ft.Text("", color=ThemeColors.SUCCESS, size=12)

        # Token stats panel
        self.token_stats_panel = TokenStatsPanel()

        self.right_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Instructions",
                        weight=ft.FontWeight.W_600,
                        size=14,
                        color=ThemeColors.TEXT_PRIMARY,
                    ),
                    ft.Container(height=8),
                    self.instructions_field,
                    ft.Container(height=12),
                    # Output Format Selector với tooltip
                    ft.Row(
                        [
                            ft.Text(
                                "Output Format:",
                                size=12,
                                color=ThemeColors.TEXT_SECONDARY,
                            ),
                            ft.Container(width=8),
                            self._build_format_dropdown(),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=8),
                    # Row 1: Tree Map và Smart Context
                    ft.Row(
                        [
                            ft.OutlinedButton(
                                "Copy Tree Map",
                                icon=ft.Icons.ACCOUNT_TREE,
                                on_click=lambda _: self._copy_tree_map_only(),
                                expand=True,
                                tooltip="Copy only file structure without contents",
                                style=ft.ButtonStyle(
                                    color=ThemeColors.TEXT_SECONDARY,
                                    side=ft.BorderSide(1, ThemeColors.BORDER),
                                ),
                            ),
                            ft.OutlinedButton(
                                "Copy Smart",
                                icon=ft.Icons.AUTO_AWESOME,
                                on_click=lambda _: self._copy_smart_context(),
                                expand=True,
                                tooltip="Copy code structure only (signatures, docstrings)",
                                style=ft.ButtonStyle(
                                    color=ThemeColors.WARNING,
                                    side=ft.BorderSide(1, ThemeColors.WARNING),
                                ),
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Container(height=8),
                    # Row 2: Copy Context và Copy + OPX
                    ft.Row(
                        [
                            ft.OutlinedButton(
                                "Copy Context",
                                icon=ft.Icons.CONTENT_COPY,
                                on_click=lambda _: self._copy_context(
                                    include_xml=False
                                ),
                                expand=True,
                                tooltip="Copy context with basic formatting",
                                style=ft.ButtonStyle(
                                    color=ThemeColors.TEXT_PRIMARY,
                                    side=ft.BorderSide(1, ThemeColors.BORDER),
                                ),
                            ),
                            ft.ElevatedButton(
                                "Copy + OPX",
                                icon=ft.Icons.CODE,
                                on_click=lambda _: self._copy_context(include_xml=True),
                                expand=True,
                                tooltip="Copy context with OPX optimization instructions",
                                style=ft.ButtonStyle(
                                    color="#FFFFFF",
                                    bgcolor=ThemeColors.PRIMARY,
                                ),
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Container(height=8),
                    self.status_text,
                    ft.Container(height=12),
                    # Token stats panel
                    self.token_stats_panel.build(),
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=16,
            expand=False,
            bgcolor=ThemeColors.BG_SURFACE,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=8,
        )

        self.layout_container = ft.Container(
            content=None,  # Will be set by update_layout
            expand=True,
            padding=16,
            bgcolor=ThemeColors.BG_PAGE,
        )

        # Initial layout
        self.update_layout(self.page.window.width if self.page.window.width else 1000)

        return self.layout_container

    def update_layout(self, width: float):
        """Update layout based on window width"""
        if not hasattr(self, "left_panel"):
            return

        if width < 800:
            # Vertical layout
            self.layout_container.content = ft.Column(
                [
                    ft.Container(content=self.left_panel, expand=True),
                    ft.Container(content=self.right_panel, height=350),
                ],
                expand=True,
                spacing=16,
            )
        else:
            # Horizontal layout
            self.layout_container.content = ft.Row(
                [
                    ft.Container(content=self.left_panel, expand=2),
                    ft.Container(
                        content=self.right_panel,
                        expand=1,
                        alignment=ft.Alignment.TOP_CENTER,
                    ),
                ],
                expand=True,
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )

    def on_workspace_changed(self, workspace_path: Path):
        """Khi user chon folder moi hoac settings thay doi"""
        # Stop any ongoing scanning
        from core.utils.file_scanner import stop_scanning

        stop_scanning()

        # Stop token counting
        from services.token_display import stop_token_counting

        stop_token_counting()

        # Cleanup old resources before loading new tree
        # Chỉ clear caches, không dispose component vì nó sẽ được reuse
        if self.file_tree_component:
            self.file_tree_component.reset_for_new_tree()
        self._load_tree(workspace_path)

        # Start file watcher for auto-refresh with incremental updates
        if self._file_watcher:
            from services.file_watcher import WatcherCallbacks

            self._file_watcher.start(
                path=workspace_path,
                callbacks=WatcherCallbacks(
                    on_file_modified=self._on_file_modified,
                    on_file_created=self._on_file_created,
                    on_file_deleted=self._on_file_deleted,
                    on_batch_change=self._on_file_system_changed,
                ),
                debounce_seconds=0.5,
            )

    def _load_tree(self, workspace_path: Path, preserve_selection: bool = False):
        """
        Load file tree với progress updates.

        RACE CONDITION FIX: Sử dụng loading lock để ngăn concurrent loads.
        Nếu đang load, request sẽ được queue và thực hiện sau.

        Args:
            workspace_path: Path to workspace folder
            preserve_selection: Neu True, giu lai selection hien tai (cho Refresh)
        """
        # ========================================
        # RACE CONDITION FIX: Check và acquire loading lock
        # ========================================
        with self._loading_lock:
            if self._is_loading:
                # Đang load rồi, queue refresh request cho sau
                self._pending_refresh = True
                from core.logging_config import log_debug
                log_debug("[ContextView] Load request queued - another load in progress")
                return
            # Mark đang loading
            self._is_loading = True
            self._pending_refresh = False

        # Save current selection before loading
        old_selection: Set[str] = set()
        if preserve_selection and self.file_tree_component:
            old_selection = self.file_tree_component.get_selected_paths()

        # Show loading state
        self._show_status("Scanning...", is_error=False, auto_clear=False)
        if self.token_stats_panel:
            self.token_stats_panel.set_loading(True)
        safe_page_update(self.page)

        try:
            from views.settings_view import get_excluded_patterns, get_use_gitignore
            from core.utils.file_scanner import scan_directory, ScanProgress

            excluded_patterns = get_excluded_patterns()
            use_gitignore = get_use_gitignore()

            # Progress callback - chỉ update status text, không gọi page.update()
            # để tránh race condition với các UI updates khác
            def on_progress(progress: ScanProgress):
                if self.status_text:
                    self.status_text.value = (
                        f"Scanning: {progress.directories} dirs, {progress.files} files"
                    )
                    # Không gọi safe_page_update() ở đây để tránh race condition

            # Scan với progress (sử dụng global cancellation flag)
            from core.logging_config import log_info
            log_info(f"[ContextView] Starting scan for: {workspace_path}")
            
            self.tree = scan_directory(
                workspace_path,
                excluded_patterns=excluded_patterns,
                use_gitignore=use_gitignore,
                progress_callback=on_progress,
            )
            
            log_info(f"[ContextView] Scan complete. Tree: {self.tree.label if self.tree else 'None'}")

            # Set tree to component
            assert self.file_tree_component is not None
            log_info(f"[ContextView] Setting tree to component...")
            self.file_tree_component.set_tree(
                self.tree, preserve_selection=preserve_selection
            )
            log_info(f"[ContextView] Tree set complete")

            # Update token count sau khi tree đã set xong
            self._update_token_count()

            # Clear loading status
            self._show_status("")
            log_info(f"[ContextView] Load tree finished successfully")

        except Exception as e:
            from core.logging_config import log_error

            log_error(f"[ContextView] Error loading tree: {e}")
            self._show_status(f"Error: {e}", is_error=True)
            # Restore old selection on error if possible
            if preserve_selection and old_selection and self.file_tree_component:
                self.file_tree_component.selected_paths = old_selection
        finally:
            if self.token_stats_panel:
                self.token_stats_panel.set_loading(False)
            safe_page_update(self.page)

            # ========================================
            # RACE CONDITION FIX: Release lock và check pending refresh
            # ========================================
            should_refresh = False
            with self._loading_lock:
                self._is_loading = False
                if self._pending_refresh:
                    should_refresh = True
                    self._pending_refresh = False

            # Nếu có pending refresh, thực hiện sau khi release lock
            if should_refresh:
                from core.logging_config import log_debug
                log_debug("[ContextView] Executing pending refresh request")
                # Defer để tránh recursion quá sâu
                # Flet 0.80.5+ yêu cầu async function cho run_task
                if self.page:
                    async def _deferred_refresh():
                        self._load_tree(workspace_path, preserve_selection=True)
                    self.page.run_task(_deferred_refresh)

    def _on_selection_changed(self, selected_paths: Set[str]):
        """Callback khi selection thay doi - debounced with SafeTimer"""
        # Cancel previous timer if exists
        if self._selection_update_timer is not None:
            self._selection_update_timer.dispose()

        # For small selections, update immediately
        if len(selected_paths) < 10:
            self._update_token_count()
            return

        # For larger selections, debounce with SafeTimer
        self._selection_update_timer = SafeTimer(
            interval=self._selection_debounce_ms / 1000.0,
            callback=self._do_update_token_count,
            page=self.page,
            use_main_thread=True
        )
        self._selection_update_timer.start()

    def _expand_all(self):
        """Expand all folders"""
        if self.file_tree_component:
            self.file_tree_component.expand_all()

    def _collapse_all(self):
        """Collapse all folders"""
        if self.file_tree_component:
            self.file_tree_component.collapse_all()

    def _select_all(self):
        """Select all visible files"""
        if self.file_tree_component and self.tree:
            self._select_all_recursive(self.tree)
            self.file_tree_component._render_tree()
            self._update_token_count()

    def _deselect_all(self):
        """Deselect all files"""
        if self.file_tree_component:
            self.file_tree_component.selected_paths.clear()
            self.file_tree_component._render_tree()
            # Immediately update token stats to zero
            if self.token_stats_panel:
                instruction_tokens = 0
                if self.instructions_field and self.instructions_field.value:
                    instruction_tokens = count_tokens(self.instructions_field.value)
                self.token_stats_panel.update_stats(
                    file_count=0,
                    file_tokens=0,
                    instruction_tokens=instruction_tokens,
                )
            self._update_token_count()

    def _add_to_ignore(self):
        """
        Them cac file/folder dang duoc chon vao danh sach excluded folders.

        Chi lay ten folder/file (khong phai full path) de them vao ignore list.
        Sau do refresh tree de an cac items da ignore.
        """
        if not self.file_tree_component:
            return

        selected = self.file_tree_component.selected_paths
        if not selected:
            self._show_status("No files selected", is_error=True)
            return

        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        # Convert absolute paths to relative paths (lay ten file/folder)
        patterns_to_add = []
        for path_str in selected:
            path = Path(path_str)
            try:
                # Lay relative path tu workspace
                rel_path = path.relative_to(workspace)
                # Chi lay ten cuoi cung (file hoac folder name)
                # Neu la folder con, co the lay full relative path
                if len(rel_path.parts) == 1:
                    # Root level item - chi lay ten
                    patterns_to_add.append(rel_path.name)
                else:
                    # Nested item - lay relative path day du hoac chi ten
                    # Dung ten de ignore tat ca instances cua folder/file do
                    patterns_to_add.append(rel_path.name)
            except ValueError:
                # Path khong nam trong workspace
                continue

        if not patterns_to_add:
            self._show_status("No valid patterns to add", is_error=True)
            return

        # Loc trung lap
        unique_patterns = list(set(patterns_to_add))

        # Them vao settings
        if add_excluded_patterns(unique_patterns):
            # Luu lai patterns de ho tro undo
            self._last_ignored_patterns = unique_patterns
            count = len(unique_patterns)
            self._show_status(f"Added {count} pattern(s). Click Undo to revert.")
            # Refresh tree de an cac items da ignore
            self._refresh_tree()
        else:
            self._show_status("Failed to save settings", is_error=True)

    def _undo_ignore(self):
        """
        Undo hanh dong ignore cuoi cung.
        Xoa cac patterns vua them va refresh tree.
        """
        if not self._last_ignored_patterns:
            self._show_status("Nothing to undo", is_error=True)
            return

        patterns = self._last_ignored_patterns
        if remove_excluded_patterns(patterns):
            count = len(patterns)
            self._show_status(f"Removed {count} pattern(s) from ignore list")
            self._last_ignored_patterns = []  # Clear sau khi undo
            self._refresh_tree()
        else:
            self._show_status("Failed to undo", is_error=True)

    def _select_all_recursive(self, item: TreeItem):
        """Recursively select all files in tree"""
        if not self.file_tree_component:
            return

        # Only select if visible (when searching)
        is_visible = (
            not self.file_tree_component.search_query
            or item.path in self.file_tree_component.matched_paths
        )

        if is_visible:
            self.file_tree_component.selected_paths.add(item.path)
            for child in item.children:
                self._select_all_recursive(child)

    def _refresh_tree(self):
        """Refresh tree - giu lai selection hien tai"""
        workspace = self.get_workspace()
        if workspace:
            self._load_tree(workspace, preserve_selection=True)

    def _on_file_modified(self, path: str):
        """
        Callback khi 1 file bị sửa - chỉ invalidate cache cho file đó.

        Không re-scan toàn bộ tree, chỉ xóa cache entries.
        Tree refresh được xử lý bởi on_batch_change.
        """
        from core.token_counter import clear_file_from_cache
        from core.security_check import invalidate_security_cache

        # Invalidate caches for this specific file
        clear_file_from_cache(path)
        invalidate_security_cache(path)

        from core.logging_config import log_debug

        log_debug(f"[ContextView] Invalidated cache for modified file: {path}")

    def _on_file_created(self, path: str):
        """
        Callback khi file mới được tạo.

        Hiện tại không cần xử lý đặc biệt vì on_batch_change
        sẽ refresh tree. Có thể mở rộng sau để add item trực tiếp.
        """
        from core.logging_config import log_debug

        log_debug(f"[ContextView] New file created: {path}")

    def _on_file_deleted(self, path: str):
        """
        Callback khi file bị xóa.

        Xóa file khỏi cache và selection.
        """
        from core.token_counter import clear_file_from_cache
        from core.security_check import invalidate_security_cache

        # Remove from caches
        clear_file_from_cache(path)
        invalidate_security_cache(path)

        # Remove from selection if selected
        if self.file_tree_component:
            self.file_tree_component.selected_paths.discard(path)

        from core.logging_config import log_debug

        log_debug(f"[ContextView] File deleted: {path}")

    def _on_file_system_changed(self):
        """
        Callback khi FileWatcher phát hiện thay đổi trong workspace.

        RACE CONDITION FIX: Callback này được gọi từ background Timer thread.
        Phải defer việc load tree đến main thread để tránh race condition.

        Sử dụng page.run_task() để schedule execution trên main thread.
        Flet 0.80.5+ yêu cầu async function cho run_task.
        """
        try:
            workspace = self.get_workspace()
            if workspace and self.page:
                # ========================================
                # RACE CONDITION FIX: Defer đến main thread
                # Không gọi _load_tree trực tiếp từ Timer thread
                # Flet 0.80.5+ yêu cầu async function cho run_task
                # ========================================
                async def _do_refresh():
                    try:
                        # Double check workspace vẫn còn valid
                        current_workspace = self.get_workspace()
                        if current_workspace and current_workspace == workspace:
                            self._load_tree(workspace, preserve_selection=True)
                            self._show_status("File changes detected - tree updated")
                    except Exception as ex:
                        from core.logging_config import log_error
                        log_error(f"[ContextView] Error in deferred refresh: {ex}")

                # Schedule trên main thread
                self.page.run_task(_do_refresh)
        except Exception as e:
            from core.logging_config import log_error

            log_error(f"[ContextView] Error refreshing on file change: {e}")

    def _on_instructions_changed(self):
        """Handle instructions field change with debounce"""
        # Cancel previous timer if exists
        if self._token_update_timer is not None:
            self._token_update_timer.dispose()  # Use dispose for SafeTimer

        # Schedule token update with debounce
        self._token_update_timer = SafeTimer(
            self._token_debounce_ms / 1000.0, self._do_update_token_count, page=self.page
        )
        self._token_update_timer.start()

    def _build_format_dropdown(self) -> ft.Control:
        """
        Tạo dropdown chọn output format với tooltip hiển thị lợi ích.

        Returns:
            ft.Dropdown widget
        """
        # Load saved format from settings
        saved_format_id = get_setting("output_format", DEFAULT_OUTPUT_STYLE.value)
        try:
            self._selected_output_style = get_style_by_id(saved_format_id)
        except ValueError:
            self._selected_output_style = DEFAULT_OUTPUT_STYLE

        self.format_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(
                    key=cfg.id,
                    text=cfg.name,
                )
                for cfg in OUTPUT_FORMATS.values()
            ],
            value=self._selected_output_style.value,
            on_select=self._on_format_changed,
            width=160,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=0),
            border_color="#525252",  # Clearer border
            focused_border_color=ThemeColors.PRIMARY,
            bgcolor=ThemeColors.BG_SURFACE,
            # Tooltip chuyen qua icon ben canh
            # tooltip=get_format_tooltip(self._selected_output_style),
        )

        self.format_info_icon = ft.Icon(
            ft.Icons.INFO_OUTLINE,
            size=16,
            color=ThemeColors.TEXT_SECONDARY,
            tooltip=get_format_tooltip(self._selected_output_style),
        )

        return ft.Row(
            [
                self.format_dropdown,
                ft.Container(width=4),
                self.format_info_icon,
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _on_format_changed(self, e):
        """
        Handle khi user đổi output format.

        Cập nhật selected style, lưu vào settings, và update tooltip.
        """
        if e.control.value:
            try:
                self._selected_output_style = get_style_by_id(e.control.value)
                # Lưu vào settings
                set_setting("output_format", e.control.value)

                # Update tooltip cua info icon
                if self.format_info_icon:
                    self.format_info_icon.tooltip = get_format_tooltip(
                        self._selected_output_style
                    )
                    # Check if icon is mounted before updating
                    if self.format_info_icon.page:
                        self.format_info_icon.update()

                # Show status
                format_name = OUTPUT_FORMATS[self._selected_output_style].name
                self._show_status(f"Output format: {format_name}")
            except ValueError:
                pass

    def _do_update_token_count(self):
        """Execute token count update (called after debounce)"""
        try:
            self._update_token_count()
        except Exception:
            pass  # Ignore errors from background timer

    def _update_token_count(self):
        """
        Update token count display va token stats panel.
        Su dung visible paths khi dang search de hien thi chinh xac.
        Su dung parallel batch counting cho hieu suat tot hon.
        """
        if not self.file_tree_component:
            return

        # Su dung visible paths de hien thi chinh xac khi dang search
        selected_paths = self.file_tree_component.get_visible_selected_paths()

        # Loc chi cac files (khong phai directories)
        file_paths = [Path(p) for p in selected_paths if Path(p).is_file()]
        file_count = len(file_paths)

        # Sử dụng batch counting với global cancellation flag
        if file_count > 0:
            from services.token_display import start_token_counting

            start_token_counting()  # Set global flag trước khi count
            token_results = count_tokens_batch(file_paths)
            file_tokens = sum(token_results.values())
        else:
            file_tokens = 0

        # Hien thi indicator khi dang filter
        assert self.token_count_text is not None
        if self.file_tree_component.is_searching():
            self.token_count_text.value = f"{file_tokens:,} tokens (filtered)"
        else:
            self.token_count_text.value = f"{file_tokens:,} tokens"

        # Update token stats panel
        instruction_tokens = 0
        if self.instructions_field and self.instructions_field.value:
            instruction_tokens = count_tokens(self.instructions_field.value)

        if self.token_stats_panel:
            self.token_stats_panel.update_stats(
                file_count=file_count,
                file_tokens=file_tokens,
                instruction_tokens=instruction_tokens,
            )

        safe_page_update(self.page)

    def _copy_context(self, include_xml: bool):
        """
        Copy context to clipboard.
        Khi dang search, chi copy cac files dang hien thi (visible).
        Có security check để cảnh báo nếu phát hiện secrets.
        """
        if not self.tree or not self.file_tree_component:
            self._show_status("No files selected", is_error=True)
            return

        # Su dung visible paths de chi copy files dang hien thi
        selected_paths = self.file_tree_component.get_visible_selected_paths()
        if not selected_paths:
            # Provide helpful message based on context
            if self.file_tree_component.is_searching():
                self._show_status(
                    "No matching files selected. Clear search or select files.",
                    is_error=True,
                )
            else:
                self._show_status("Select files from the tree first", is_error=True)
            return

        try:
            # Show copying state for large selections
            file_count = sum(1 for p in selected_paths if Path(p).is_file())
            if file_count > 10:
                self._show_status(
                    f"Scanning {file_count} files...", is_error=False, auto_clear=False
                )
                safe_page_update(self.page)

            # --- SECURITY CHECK ---
            # Check if security scan is enabled
            enable_security = get_setting("enable_security_check", True)

            # Debug log
            from core.logging_config import log_info

            log_info(f"[SecurityCheck] enable_security_check = {enable_security}")

            if enable_security:
                secret_matches = scan_secrets_in_files_cached(selected_paths)
            else:
                secret_matches = []

            # Get Git Context if enabled
            include_git = get_setting("include_git_changes", True)
            git_diffs = None
            git_logs = None

            if include_git:
                workspace = self.get_workspace()
                if workspace:
                    git_diffs = get_git_diffs(workspace)
                    git_logs = get_git_logs(workspace)

            if secret_matches:
                file_map = generate_file_map(self.tree, selected_paths)
                # Generate file contents based on selected output style
                if self._selected_output_style == OutputStyle.XML:
                    file_contents = generate_file_contents_xml(selected_paths)
                elif self._selected_output_style == OutputStyle.JSON:
                    file_contents = generate_file_contents_json(selected_paths)
                elif self._selected_output_style == OutputStyle.PLAIN:
                    file_contents = generate_file_contents_plain(selected_paths)
                else:
                    file_contents = generate_file_contents(selected_paths)
                assert self.instructions_field is not None
                instructions = self.instructions_field.value or ""

                # Pass git context and output_style here too
                prompt = generate_prompt(
                    file_map,
                    file_contents,
                    instructions,
                    include_xml,
                    git_diffs=git_diffs,
                    git_logs=git_logs,
                    output_style=self._selected_output_style,
                )

                self._show_security_dialog(
                    prompt=prompt,
                    matches=secret_matches,
                    include_xml=include_xml,
                )
                return

            # No secrets found
            file_map = generate_file_map(self.tree, selected_paths)
            # Generate file contents based on selected output style
            if self._selected_output_style == OutputStyle.XML:
                file_contents = generate_file_contents_xml(selected_paths)
            elif self._selected_output_style == OutputStyle.JSON:
                file_contents = generate_file_contents_json(selected_paths)
            elif self._selected_output_style == OutputStyle.PLAIN:
                file_contents = generate_file_contents_plain(selected_paths)
            else:
                file_contents = generate_file_contents(selected_paths)
            assert self.instructions_field is not None
            instructions = self.instructions_field.value or ""

            prompt = generate_prompt(
                file_map,
                file_contents,
                instructions,
                include_xml,
                git_diffs=git_diffs,
                git_logs=git_logs,
                output_style=self._selected_output_style,
            )

            # No secrets found - copy directly
            self._do_copy(prompt, include_xml)

        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    def _copy_tree_map_only(self):
        """
        Copy chi tree map to clipboard (khong co file contents).
        Tiet kiem tokens khi chi can LLM hieu cau truc project.
        """
        if not self.tree or not self.file_tree_component:
            self._show_status("No files selected", is_error=True)
            return

        # Su dung visible paths
        selected_paths = self.file_tree_component.get_visible_selected_paths()
        if not selected_paths:
            self._show_status("No files selected", is_error=True)
            return

        try:
            assert self.instructions_field is not None
            instructions = self.instructions_field.value or ""

            prompt = generate_tree_map_only(self.tree, selected_paths, instructions)

            success, message = copy_to_clipboard(prompt)

            if success:
                token_count = count_tokens(prompt)
                self._show_status(f"Tree map copied! ({token_count:,} tokens)")
            else:
                self._show_status(message, is_error=True)

        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    def _copy_smart_context(self):
        """
        Copy Smart Context to clipboard.
        Dùng Tree-sitter để trích xuất code structure (signatures, docstrings).
        Không fallback sang raw content khi không hỗ trợ.
        """
        if not self.tree or not self.file_tree_component:
            self._show_status("No files selected", is_error=True)
            return

        selected_paths = self.file_tree_component.get_visible_selected_paths()
        if not selected_paths:
            self._show_status("No files selected", is_error=True)
            return

        try:
            # Show processing state
            file_count = sum(1 for p in selected_paths if Path(p).is_file())
            if file_count > 5:
                self._show_status(
                    f"Parsing {file_count} files...", is_error=False, auto_clear=False
                )
                safe_page_update(self.page)

            # Generate smart context
            smart_contents = generate_smart_context(selected_paths)
            file_map = generate_file_map(self.tree, selected_paths)

            assert self.instructions_field is not None
            instructions = self.instructions_field.value or ""

            # Build prompt với smart content
            prompt = f"""<file_map>
{file_map}
</file_map>

<file_contents>
{smart_contents}
</file_contents>
"""
            if instructions.strip():
                prompt += f"\n<user_instructions>\n{instructions.strip()}\n</user_instructions>\n"

            # Security check - scan for secrets
            secret_matches = scan_for_secrets(prompt)
            if secret_matches:
                # Show confirmation dialog
                self._show_security_dialog(
                    prompt=prompt,
                    matches=secret_matches,
                    is_smart=True,
                )
                return

            # No secrets found - copy directly
            self._do_copy(prompt, is_smart=True)

        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    def _do_copy(self, prompt: str, include_xml: bool = False, is_smart: bool = False):
        """
        Thực hiện copy prompt vào clipboard.
        Helper method được gọi sau khi security check pass hoặc user confirm.

        Args:
            prompt: Prompt content to copy
            include_xml: True nếu có OPX instructions
            is_smart: True nếu đây là Smart Context copy
        """
        success, message = copy_to_clipboard(prompt)

        if success:
            token_count = count_tokens(prompt)
            if is_smart:
                self._show_status(f"Smart Context copied! ({token_count:,} tokens)")
            else:
                suffix = " + OPX" if include_xml else ""
                self._show_status(f"Copied! ({token_count:,} tokens){suffix}")
        else:
            self._show_status(message, is_error=True)

    def _show_security_dialog(
        self,
        prompt: str,
        matches: list,
        include_xml: bool = False,
        is_smart: bool = False,
    ):
        """
        Hiển thị confirmation dialog khi phát hiện secrets.

        Args:
            prompt: Prompt content to copy if user confirms
            matches: List of SecretMatch from security scan
            include_xml: True nếu có OPX instructions
            is_smart: True nếu đây là Smart Context copy
        """
        warning_message = format_security_warning(matches)

        def close_dialog(e):
            dialog.open = False
            safe_page_update(self.page)

        def copy_anyway(e):
            dialog.open = False
            safe_page_update(self.page)
            # Proceed with copy
            self._do_copy(prompt, include_xml, is_smart)

        # Prepare details view
        details_col = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            height=200,
            spacing=4,
            width=500,
        )

        for match in matches:
            file_info = f" in {match.file_path}" if match.file_path else ""
            details_col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.SECURITY,
                                        size=14,
                                        color=ThemeColors.WARNING,
                                    ),
                                    ft.Text(
                                        f"{match.secret_type}",
                                        size=12,
                                        weight=ft.FontWeight.W_600,
                                    ),
                                    ft.Text(
                                        f"{file_info} (Line {match.line_number})",
                                        size=12,
                                        color=ThemeColors.TEXT_SECONDARY,
                                    ),
                                ],
                                spacing=6,
                            ),
                            ft.Text(
                                f"Value: {match.redacted_preview}",
                                size=11,
                                color=ThemeColors.TEXT_SECONDARY,
                                font_family="monospace",
                                italic=True,
                            ),
                        ],
                        spacing=2,
                    ),
                    bgcolor=ThemeColors.BG_SURFACE,
                    padding=6,
                    border_radius=4,
                )
            )

        def copy_results(e):
            # Copy scan results to clipboard for debugging
            import json

            results_data = [
                {
                    "type": m.secret_type,
                    "file": m.file_path or "N/A",
                    "line": m.line_number,
                    "preview": m.redacted_preview,
                }
                for m in matches
            ]
            results_json = json.dumps(results_data, indent=2, ensure_ascii=False)
            copy_to_clipboard(results_json)
            self._show_status(f"Copied {len(matches)} results to clipboard")

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ThemeColors.WARNING),
                    ft.Text(
                        "Security Warning",
                        weight=ft.FontWeight.BOLD,
                        color=ThemeColors.WARNING,
                    ),
                ]
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            warning_message,
                            size=14,
                            color=ThemeColors.TEXT_PRIMARY,
                        ),
                        ft.Container(height=8),
                        ft.Text("Details:", size=12, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=details_col,
                            border=ft.border.all(1, ThemeColors.BORDER),
                            border_radius=4,
                            padding=4,
                        ),
                        ft.Container(height=8),
                        ft.Text(
                            "Please review your content before sharing with AI tools.",
                            size=12,
                            color=ThemeColors.TEXT_SECONDARY,
                            italic=True,
                        ),
                    ],
                    tight=True,
                ),
                width=550,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY),
                ),
                ft.OutlinedButton(
                    "Copy Results",
                    on_click=copy_results,
                    icon=ft.Icons.BUG_REPORT,
                    style=ft.ButtonStyle(
                        color=ThemeColors.TEXT_SECONDARY,
                        side=ft.BorderSide(1, ThemeColors.BORDER),
                    ),
                ),
                ft.ElevatedButton(
                    "Copy Anyway",
                    on_click=copy_anyway,
                    style=ft.ButtonStyle(
                        color="#FFFFFF",
                        bgcolor=ThemeColors.WARNING,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(self.page)

    def _show_status(
        self, message: str, is_error: bool = False, auto_clear: bool = True
    ):
        """
        Show status message with optional auto-clear.

        Args:
            message: Status message to display
            is_error: True for error styling
            auto_clear: If True, clear message after 3 seconds (for success messages)
        """
        # Cancel previous auto-clear timer
        if self._status_clear_timer is not None:
            self._status_clear_timer.cancel()
            self._status_clear_timer = None

        assert self.status_text is not None
        self.status_text.value = message
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        safe_page_update(self.page)

        # Auto-clear success messages after 3 seconds
        if auto_clear and not is_error and message:

            def clear_status():
                try:
                    if self.status_text and self.status_text.value == message:
                        self.status_text.value = ""
                        safe_page_update(self.page)
                except Exception:
                    pass

            self._status_clear_timer = Timer(3.0, clear_status)
            self._status_clear_timer.start()
