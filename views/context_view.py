"""
Context View - Tab de chon files va copy context

Refactored version using extracted dialog components.
"""

import flet as ft
import threading
from threading import Timer
from pathlib import Path
from typing import Callable, Optional, Set, Union

from core.utils.file_utils import scan_directory, scan_directory_shallow, TreeItem
from core.utils.ui_utils import safe_page_update
from services.clipboard_utils import copy_to_clipboard
from core.token_counter import count_tokens_batch_parallel, count_tokens
from core.prompt_generator import (
    generate_prompt, generate_file_map, generate_file_contents,
    generate_file_contents_xml, generate_file_contents_json,
    generate_file_contents_plain, generate_smart_context,
)
from core.utils.git_utils import get_git_diffs, get_git_logs, DiffOnlyResult
from core.tree_map_generator import generate_tree_map_only
from components.file_tree import FileTreeComponent
from components.virtual_file_tree import VirtualFileTreeComponent
from components.file_preview import FilePreviewDialog
from components.token_stats import TokenStatsPanel
from components.dialogs import (
    SecurityDialog, DiffOnlyDialog, RemoteRepoDialog, CacheManagementDialog,
)
from core.theme import ThemeColors
from core.security_check import scan_for_secrets, scan_secrets_in_files_cached
from views.settings_view import add_excluded_patterns, remove_excluded_patterns, get_excluded_patterns, get_use_gitignore
from services.settings_manager import get_setting, set_setting
from services.file_watcher import FileWatcher, WatcherCallbacks
from core.utils.safe_timer import SafeTimer
from config.output_format import (
    OutputStyle, OUTPUT_FORMATS, get_format_tooltip, get_style_by_id, DEFAULT_OUTPUT_STYLE,
)
from core.utils.repo_manager import RepoManager
from core.dependency_resolver import DependencyResolver


class ContextView:
    """View cho Context tab - refactored with extracted components."""

    VIRTUAL_TREE_THRESHOLD = 5000

    def __init__(self, page: ft.Page, get_workspace: Callable[[], Optional[Path]]):
        self.page = page
        self.get_workspace = get_workspace
        
        # UI components
        self.tree: Optional[TreeItem] = None
        self.file_tree_component: Optional[Union[FileTreeComponent, VirtualFileTreeComponent]] = None
        self.left_panel: Optional[ft.Container] = None
        self.token_count_text: Optional[ft.Text] = None
        self.instructions_field: Optional[ft.TextField] = None
        self.status_text: Optional[ft.Text] = None
        self.token_stats_panel: Optional[TokenStatsPanel] = None
        self._tree_container: Optional[ft.Container] = None
        self.format_dropdown: Optional[ft.Dropdown] = None
        self.format_info_icon: Optional[ft.Icon] = None
        self._select_related_button: Optional[ft.Control] = None

        # Timers
        self._token_update_timer: Optional[Union[Timer, SafeTimer]] = None
        self._selection_update_timer: Optional[SafeTimer] = None
        self._status_clear_timer: Optional[Timer] = None

        # State
        self._last_ignored_patterns: list[str] = []
        self._selected_output_style: OutputStyle = DEFAULT_OUTPUT_STYLE
        self._last_added_related_files: Set[str] = set()
        self._related_mode_active: bool = False
        
        # Threading
        self._loading_lock = threading.Lock()
        self._is_loading = False
        self._pending_refresh = False
        self._is_disposed = False

        # Services
        self._file_watcher: Optional[FileWatcher] = FileWatcher()
        self._repo_manager: Optional[RepoManager] = None

    def cleanup(self):
        """Cleanup resources when view is destroyed."""
        self._is_disposed = True
        
        from core.utils.file_scanner import stop_scanning
        from services.token_display import stop_token_counting
        stop_scanning()
        stop_token_counting()

        for timer in [self._token_update_timer, self._selection_update_timer, self._status_clear_timer]:
            if timer:
                try:
                    if hasattr(timer, 'dispose'):
                        timer.dispose()
                    else:
                        timer.cancel()
                except Exception:
                    pass
        
        self._token_update_timer = None
        self._selection_update_timer = None
        self._status_clear_timer = None

        if self.file_tree_component:
            self.file_tree_component.cleanup()
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

    def build(self) -> ft.Container:
        """Build UI cho Context view."""
        self.token_count_text = ft.Text("0 tokens", size=13, weight=ft.FontWeight.W_600, color=ThemeColors.PRIMARY)
        self.status_text = ft.Text("", color=ThemeColors.SUCCESS, size=12)
        self.token_stats_panel = TokenStatsPanel()
        
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

        self.left_panel = self._build_left_panel()
        self.right_panel = self._build_right_panel()

        self.layout_container = ft.Container(content=None, expand=True, padding=16, bgcolor=ThemeColors.BG_PAGE)
        self.update_layout(self.page.window.width if self.page.window.width else 1000)
        return self.layout_container

    def _build_left_panel(self) -> ft.Container:
        """Build the left panel with file tree."""
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Files", weight=ft.FontWeight.W_600, size=14, color=ThemeColors.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    self.token_count_text,
                ]),
                self._build_toolbar(),
                ft.Divider(height=1, color=ThemeColors.BORDER),
                self._create_tree_container(),
            ], expand=True),
            padding=16,
            expand=True,
            bgcolor=ThemeColors.BG_SURFACE,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=8,
        )

    def _build_toolbar(self) -> ft.Container:
        """Build the toolbar with action buttons."""
        def icon_btn(icon, tooltip, on_click):
            return ft.IconButton(icon=icon, icon_size=20, icon_color=ThemeColors.TEXT_SECONDARY, tooltip=tooltip, on_click=on_click)
        
        def separator():
            return ft.Container(width=1, height=20, bgcolor=ThemeColors.BORDER, margin=ft.margin.symmetric(horizontal=4))

        return ft.Container(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.END,
                controls=[
                    ft.Row([
                        icon_btn(ft.Icons.SELECT_ALL, "Select All", lambda _: self._select_all()),
                        icon_btn(ft.Icons.DESELECT, "Deselect All", lambda _: self._deselect_all()),
                    ], spacing=0),
                    separator(),
                    self._create_select_related_button(),
                    separator(),
                    ft.Row([
                        icon_btn(ft.Icons.UNFOLD_MORE, "Expand All", lambda _: self._expand_all()),
                        icon_btn(ft.Icons.UNFOLD_LESS, "Collapse All", lambda _: self._collapse_all()),
                    ], spacing=0),
                    separator(),
                    icon_btn(ft.Icons.REFRESH, "Refresh", lambda _: self._refresh_tree()),
                    separator(),
                    self._build_remote_repos_menu(),
                    separator(),
                    icon_btn(ft.Icons.BLOCK, "Add selected to ignore list", lambda _: self._add_to_ignore()),
                    icon_btn(ft.Icons.UNDO, "Undo last ignore", lambda _: self._undo_ignore()),
                ],
                spacing=0,
            ),
            padding=ft.padding.only(bottom=8),
        )

    def _build_remote_repos_menu(self) -> ft.PopupMenuButton:
        """Build the remote repos popup menu."""
        return ft.PopupMenuButton(
            content=ft.Row([
                ft.Icon(ft.Icons.CLOUD, size=18, color=ThemeColors.PRIMARY),
                ft.Text("Remote Repos", size=13, color=ThemeColors.TEXT_PRIMARY, weight=ft.FontWeight.W_500),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=18, color=ThemeColors.TEXT_SECONDARY),
            ], spacing=4),
            items=[
                ft.PopupMenuItem(
                    content=ft.Row([ft.Icon(ft.Icons.CLOUD_DOWNLOAD, size=16, color=ThemeColors.PRIMARY), ft.Text("Clone Repository", size=13)], spacing=8),
                    on_click=lambda _: self._open_remote_repo_dialog(),
                ),
                ft.PopupMenuItem(
                    content=ft.Row([ft.Icon(ft.Icons.FOLDER_OPEN, size=16, color=ThemeColors.TEXT_SECONDARY), ft.Text("Manage Cache", size=13)], spacing=8),
                    on_click=lambda _: self._open_cache_management_dialog(),
                ),
            ],
            tooltip="Remote Repository Actions",
        )

    def _build_right_panel(self) -> ft.Container:
        """Build the right panel with instructions and actions."""
        return ft.Container(
            content=ft.Column([
                ft.Text("Instructions", weight=ft.FontWeight.W_600, size=14, color=ThemeColors.TEXT_PRIMARY),
                ft.Container(height=8),
                self.instructions_field,
                ft.Container(height=12),
                self._build_format_selector(),
                ft.Container(height=8),
                self._build_action_buttons(),
                ft.Container(height=8),
                self.status_text,
                ft.Container(height=12),
                self.token_stats_panel.build(),
            ], expand=True, scroll=ft.ScrollMode.AUTO),
            padding=16,
            expand=False,
            bgcolor=ThemeColors.BG_SURFACE,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=8,
        )

    def _build_format_selector(self) -> ft.Row:
        """Build the output format selector."""
        saved_format_id = get_setting("output_format", DEFAULT_OUTPUT_STYLE.value)
        try:
            self._selected_output_style = get_style_by_id(saved_format_id)
        except ValueError:
            self._selected_output_style = DEFAULT_OUTPUT_STYLE

        self.format_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(key=cfg.id, text=cfg.name) for cfg in OUTPUT_FORMATS.values()],
            value=self._selected_output_style.value,
            on_select=self._on_format_changed,
            width=160,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=0),
            border_color="#525252",
            focused_border_color=ThemeColors.PRIMARY,
            bgcolor=ThemeColors.BG_SURFACE,
        )
        self.format_info_icon = ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ThemeColors.TEXT_SECONDARY, tooltip=get_format_tooltip(self._selected_output_style))
        
        return ft.Row([
            ft.Text("Output Format:", size=12, color=ThemeColors.TEXT_SECONDARY),
            ft.Container(width=8),
            self.format_dropdown,
            ft.Container(width=4),
            self.format_info_icon,
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _build_action_buttons(self) -> ft.Column:
        """Build the action buttons."""
        btn_style_outline = ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY, side=ft.BorderSide(1, ThemeColors.BORDER))
        btn_style_warning = ft.ButtonStyle(color=ThemeColors.WARNING, side=ft.BorderSide(1, ThemeColors.WARNING))
        
        return ft.Column([
            ft.Row([
                ft.ElevatedButton("Copy Diff Only", icon=ft.Icons.DIFFERENCE, on_click=lambda _: self._show_diff_only_dialog(), expand=True, tooltip="Copy only git diff", style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#8B5CF6")),
            ], spacing=12),
            ft.Container(height=8),
            ft.Row([
                ft.OutlinedButton("Copy Tree Map", icon=ft.Icons.ACCOUNT_TREE, on_click=lambda _: self._copy_tree_map_only(), expand=True, tooltip="Copy only file structure", style=btn_style_outline),
                ft.OutlinedButton("Copy Smart", icon=ft.Icons.AUTO_AWESOME, on_click=lambda _: self._copy_smart_context(), expand=True, tooltip="Copy code structure only", style=btn_style_warning),
            ], spacing=12),
            ft.Container(height=8),
            ft.Row([
                ft.OutlinedButton("Copy Context", icon=ft.Icons.CONTENT_COPY, on_click=lambda _: self._copy_context(include_xml=False), expand=True, tooltip="Copy context with basic formatting", style=ft.ButtonStyle(color=ThemeColors.TEXT_PRIMARY, side=ft.BorderSide(1, ThemeColors.BORDER))),
                ft.ElevatedButton("Copy + OPX", icon=ft.Icons.CODE, on_click=lambda _: self._copy_context(include_xml=True), expand=True, tooltip="Copy context with OPX instructions", style=ft.ButtonStyle(color="#FFFFFF", bgcolor=ThemeColors.PRIMARY)),
            ], spacing=12),
        ])

    def _create_tree_container(self) -> ft.Container:
        """Create tree container with direct reference."""
        content = self.file_tree_component.build() if self.file_tree_component else ft.Text("Loading...", color=ThemeColors.TEXT_SECONDARY)
        self._tree_container = ft.Container(content=content, expand=True)
        return self._tree_container

    def _create_select_related_button(self) -> ft.Control:
        """Create Select Related button with toggle support."""
        self._select_related_button = ft.PopupMenuButton(
            content=ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ACCOUNT_TREE, size=16, color=ThemeColors.BG_PAGE),
                    ft.Text("Select Related", size=12, weight=ft.FontWeight.W_500, color=ThemeColors.BG_PAGE),
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=14, color=ThemeColors.BG_PAGE),
                ], spacing=2, alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border_radius=4,
                bgcolor=ThemeColors.PRIMARY,
            ),
            items=self._build_related_menu_items(),
            tooltip="Select imported files with depth options",
        )
        return self._select_related_button

    def _build_related_menu_items(self) -> list:
        """Build menu items for Select Related popup."""
        if self._related_mode_active:
            return [ft.PopupMenuItem(
                content=ft.Row([ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, size=16, color=ThemeColors.ERROR), ft.Text(f"Clear {len(self._last_added_related_files)} related files", size=13)], spacing=8),
                on_click=lambda _: self._deselect_related_files(),
            )]
        return [
            ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.LOOKS_ONE, size=16, color=ThemeColors.PRIMARY), ft.Text("Direct imports only", size=13)], spacing=8), on_click=lambda _: self._select_related_files(depth=1)),
            ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.LOOKS_TWO, size=16, color=ThemeColors.WARNING), ft.Text("Include 1-level nested", size=13)], spacing=8), on_click=lambda _: self._select_related_files(depth=2)),
            ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.LOOKS_3, size=16, color=ThemeColors.ERROR), ft.Text("Include 2-levels nested", size=13)], spacing=8), on_click=lambda _: self._select_related_files(depth=3)),
        ]

    def update_layout(self, width: float):
        """Update layout based on window width."""
        if not hasattr(self, "left_panel"):
            return
        if width < 800:
            self.layout_container.content = ft.Column([ft.Container(content=self.left_panel, expand=True), ft.Container(content=self.right_panel, height=350)], expand=True, spacing=16)
        else:
            self.layout_container.content = ft.Row([ft.Container(content=self.left_panel, expand=2), ft.Container(content=self.right_panel, expand=1, alignment=ft.Alignment.TOP_CENTER)], expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.START)

    # === Workspace and Tree Management ===
    
    def on_workspace_changed(self, workspace_path: Path):
        """Handle workspace change."""
        from core.logging_config import log_info
        from core.utils.file_scanner import stop_scanning
        from services.token_display import stop_token_counting
        import time

        current_time = time.time()
        if (hasattr(self, '_last_workspace_change_time') and hasattr(self, '_last_workspace_path') and
            self._last_workspace_path == str(workspace_path) and current_time - self._last_workspace_change_time < 1.0):
            return
        
        self._last_workspace_change_time = current_time
        self._last_workspace_path = str(workspace_path)
        log_info(f"[ContextView] Workspace changing to: {workspace_path}")

        stop_scanning()
        stop_token_counting()
        self._cancel_timers()

        if self._file_watcher:
            self._file_watcher.stop()
        if self.file_tree_component:
            self.file_tree_component.reset_for_new_tree()

        self._load_tree(workspace_path)

        if self._file_watcher:
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

    def _cancel_timers(self):
        """Cancel all pending timers."""
        for timer_attr in ['_token_update_timer', '_selection_update_timer']:
            timer = getattr(self, timer_attr, None)
            if timer:
                try:
                    timer.dispose() if hasattr(timer, 'dispose') else timer.cancel()
                except Exception:
                    pass
            setattr(self, timer_attr, None)

    def _load_tree(self, workspace_path: Path, preserve_selection: bool = False):
        """Load file tree with progress updates."""
        from core.logging_config import log_info, log_error

        with self._loading_lock:
            if self._is_loading:
                self._pending_refresh = True
                return
            self._is_loading = True
            self._pending_refresh = False

        old_selection: Set[str] = set()
        if preserve_selection and self.file_tree_component:
            old_selection = self.file_tree_component.get_selected_paths()

        from core.utils.file_scanner import stop_scanning
        from services.token_display import stop_token_counting
        stop_scanning()
        stop_token_counting()
        self._cancel_timers()

        self._show_status("Loading...", is_error=False, auto_clear=False)
        if self.token_count_text:
            self.token_count_text.value = "0 tokens"
        if self.token_stats_panel:
            self.token_stats_panel.set_loading(False)
            self.token_stats_panel.update_stats(file_count=0, file_tokens=0, instruction_tokens=0)
        safe_page_update(self.page)

        try:
            excluded_patterns = get_excluded_patterns()
            use_gitignore = get_use_gitignore()
            
            log_info(f"[ContextView] Starting shallow scan for: {workspace_path}")
            self.tree = scan_directory_shallow(workspace_path, depth=1, excluded_patterns=excluded_patterns, use_gitignore=use_gitignore)
            log_info(f"[ContextView] Shallow scan complete")

            self._ensure_file_tree_component()
            self.file_tree_component.set_tree(self.tree, preserve_selection=preserve_selection)

            self._show_status("")
            safe_page_update(self.page)
            log_info("[ContextView] Load tree finished successfully")

        except Exception as e:
            log_error(f"[ContextView] Error loading tree: {e}")
            self._show_status(f"Error: {e}", is_error=True)
            if preserve_selection and old_selection and self.file_tree_component:
                self.file_tree_component.selected_paths = old_selection
        finally:
            if self.token_stats_panel:
                self.token_stats_panel.set_loading(False)
            safe_page_update(self.page)

            should_refresh = False
            with self._loading_lock:
                self._is_loading = False
                if self._pending_refresh:
                    should_refresh = True
                    self._pending_refresh = False

            if should_refresh and self.page:
                async def _deferred_refresh():
                    self._load_tree(workspace_path, preserve_selection=True)
                self.page.run_task(_deferred_refresh)

    def _ensure_file_tree_component(self):
        """Ensure file tree component exists and is appropriate type."""
        if not self.file_tree_component:
            self.file_tree_component = self._create_file_tree_component()
            self._rebuild_tree_container()
        else:
            total_items = self._count_total_items(self.tree) if self.tree else 0
            current_is_virtual = isinstance(self.file_tree_component, VirtualFileTreeComponent)
            should_be_virtual = total_items > self.VIRTUAL_TREE_THRESHOLD
            
            if current_is_virtual != should_be_virtual:
                old_selection = self.file_tree_component.get_selected_paths()
                self.file_tree_component.cleanup()
                self.file_tree_component = self._create_file_tree_component()
                self._rebuild_tree_container()
                if old_selection:
                    self.file_tree_component.selected_paths = old_selection

    def _create_file_tree_component(self) -> Union[FileTreeComponent, VirtualFileTreeComponent]:
        """
        Create appropriate file tree component based on tree size.
        
        FIX #3: Register callback để context_view re-calculate khi token cache updates.
        """
        total_items = self._count_total_items(self.tree) if self.tree else 0
        if total_items > self.VIRTUAL_TREE_THRESHOLD:
            component = VirtualFileTreeComponent(page=self.page, on_selection_changed=self._on_selection_changed, show_tokens=True, show_lines=False)
        else:
            component = FileTreeComponent(page=self.page, on_selection_changed=self._on_selection_changed, on_preview=self._preview_file, show_tokens=True, show_lines=False)
        
        # FIX #3: Register callback để re-calculate token count khi cache updates
        # Khi background counting hoàn thành, token service sẽ gọi callback này
        # để context_view update header token count và stats panel
        if hasattr(component, '_token_service'):
            original_callback = component._token_service.on_update
            
            def combined_callback():
                # Gọi callback gốc (update tree badges)
                if original_callback:
                    original_callback()
                # Re-calculate token count cho header và stats panel
                self._update_token_count()
            
            component._token_service.on_update = combined_callback
        
        return component

    def _rebuild_tree_container(self):
        """Rebuild tree container with new component."""
        if self._tree_container and self.file_tree_component:
            self._tree_container.content = self.file_tree_component.build()
            safe_page_update(self.page)

    def _count_total_items(self, tree: TreeItem) -> int:
        """Count total items in tree recursively."""
        if not tree:
            return 0
        count = 1
        if hasattr(tree, 'children') and tree.children:
            for child in tree.children:
                count += self._count_total_items(child)
        return count

    # === Selection Actions ===

    def _on_selection_changed(self, selected_paths: Set[str]):
        """
        Handle selection change with adaptive debouncing.
        
        FIX #4: Generation counter để invalidate stale results.
        Mỗi lần selection thay đổi, increment generation để các token counting
        đang chạy biết rằng kết quả của chúng đã stale.
        """
        # Increment generation để invalidate stale counting results
        self._token_generation = getattr(self, '_token_generation', 0) + 1
        
        if self._selection_update_timer:
            self._selection_update_timer.dispose()
            self._selection_update_timer = None

        selection_size = len(selected_paths)
        if selection_size < 5:
            self._update_token_count()
            return

        debounce_ms = 150 if selection_size < 20 else 250 if selection_size < 100 else 400 if selection_size < 500 else 700
        self._selection_update_timer = SafeTimer(interval=debounce_ms / 1000.0, callback=self._update_token_count, page=self.page, use_main_thread=True)
        self._selection_update_timer.start()

    def _select_all(self):
        """Select all visible files."""
        if self.file_tree_component and self.tree:
            self._select_all_recursive(self.tree)
            self.file_tree_component._render_tree()
            self._update_token_count()

    def _select_all_recursive(self, item: TreeItem):
        """Recursively select all files."""
        if not self.file_tree_component:
            return
        is_visible = not self.file_tree_component.search_query or item.path in self.file_tree_component.matched_paths
        if is_visible:
            self.file_tree_component.selected_paths.add(item.path)
            for child in item.children:
                self._select_all_recursive(child)

    def _deselect_all(self):
        """Deselect all files."""
        if self.file_tree_component:
            self.file_tree_component.selected_paths.clear()
            self.file_tree_component._render_tree()
            if self._related_mode_active:
                self._last_added_related_files.clear()
                self._related_mode_active = False
                self._update_related_button_state()
            if self.token_stats_panel:
                instruction_tokens = count_tokens(self.instructions_field.value) if self.instructions_field and self.instructions_field.value else 0
                self.token_stats_panel.update_stats(file_count=0, file_tokens=0, instruction_tokens=instruction_tokens)
            self._update_token_count()

    def _select_related_files(self, depth: int = 1):
        """Select files imported by selected files."""
        if self._related_mode_active:
            self._last_added_related_files.clear()
            self._related_mode_active = False

        if not self.file_tree_component or not self.tree:
            self._show_status("No files selected", is_error=True)
            return

        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        selected_paths = self.file_tree_component.get_selected_paths()
        if not selected_paths:
            self._show_status("Select at least one file first", is_error=True)
            return

        selected_files = [Path(p) for p in selected_paths if Path(p).is_file() and Path(p).suffix in [".py", ".js", ".jsx", ".ts", ".tsx"]]
        if not selected_files:
            self._show_status("No supported files selected (Python/JS/TS)", is_error=True)
            return

        try:
            from config.paths import get_excluded_patterns, get_use_gitignore
            full_tree = scan_directory(
                workspace,
                excluded_patterns=get_excluded_patterns(),
                use_gitignore=get_use_gitignore(),
            )
            resolver = DependencyResolver(workspace)
            resolver.build_file_index(full_tree)
            
            all_related: Set[Path] = set()
            for file_path in selected_files:
                all_related.update(resolver.get_related_files(file_path, max_depth=depth))

            if not all_related:
                self._show_status("No related files found", is_error=False)
                return

            added_count = 0
            self._last_added_related_files.clear()
            for related_path in all_related:
                path_str = str(related_path)
                if path_str not in self.file_tree_component.selected_paths:
                    self.file_tree_component.selected_paths.add(path_str)
                    self._last_added_related_files.add(path_str)
                    added_count += 1

            if added_count > 0:
                self._related_mode_active = True
                self._update_related_button_state()

            self.file_tree_component._render_tree()
            self._update_token_count()
            self._show_status(f"Added {added_count} related files (click again to undo)", is_error=False)

        except Exception as e:
            self._show_status(f"Error finding related files: {e}", is_error=True)

    def _deselect_related_files(self):
        """Remove related files added by select related."""
        if not self.file_tree_component or not self._last_added_related_files:
            return

        removed_count = 0
        for path_str in self._last_added_related_files:
            if path_str in self.file_tree_component.selected_paths:
                self.file_tree_component.selected_paths.discard(path_str)
                removed_count += 1

        self._last_added_related_files.clear()
        self._related_mode_active = False
        self._update_related_button_state()
        self.file_tree_component._render_tree()
        self._update_token_count()
        self._show_status(f"Removed {removed_count} related files", is_error=False)

    def _update_related_button_state(self):
        """Update Select Related button appearance."""
        if not self._select_related_button:
            return
        self._select_related_button.items = self._build_related_menu_items()
        btn_container = self._select_related_button.content
        if isinstance(btn_container, ft.Container):
            btn_row = btn_container.content
            if isinstance(btn_row, ft.Row) and len(btn_row.controls) >= 2:
                icon, text = btn_row.controls[0], btn_row.controls[1]
                if self._related_mode_active:
                    btn_container.bgcolor = ThemeColors.SUCCESS
                    if isinstance(icon, ft.Icon):
                        icon.name = ft.Icons.CHECK_CIRCLE
                    if isinstance(text, ft.Text):
                        text.value = f"Related ({len(self._last_added_related_files)})"
                else:
                    btn_container.bgcolor = ThemeColors.PRIMARY
                    if isinstance(icon, ft.Icon):
                        icon.name = ft.Icons.ACCOUNT_TREE
                    if isinstance(text, ft.Text):
                        text.value = "Select Related"
        safe_page_update(self.page)

    def _expand_all(self):
        if self.file_tree_component:
            self.file_tree_component.expand_all()

    def _collapse_all(self):
        if self.file_tree_component:
            self.file_tree_component.collapse_all()

    def _refresh_tree(self):
        """Refresh tree with hard reset."""
        workspace = self.get_workspace()
        if not workspace:
            return
        from core.utils.file_scanner import stop_scanning
        from services.token_display import stop_token_counting
        stop_scanning()
        stop_token_counting()
        self._cancel_timers()
        if self.file_tree_component:
            self.file_tree_component.reset_for_new_tree()
        self._load_tree(workspace, preserve_selection=False)

    def _add_to_ignore(self):
        """Add selected files/folders to ignore list."""
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

        patterns_to_add = []
        for path_str in selected:
            path = Path(path_str)
            try:
                rel_path = path.relative_to(workspace)
                patterns_to_add.append(rel_path.name)
            except ValueError:
                continue

        if not patterns_to_add:
            self._show_status("No valid patterns to add", is_error=True)
            return

        unique_patterns = list(set(patterns_to_add))
        if add_excluded_patterns(unique_patterns):
            self._last_ignored_patterns = unique_patterns
            self._show_status(f"Added {len(unique_patterns)} pattern(s). Click Undo to revert.")
            self._refresh_tree()
        else:
            self._show_status("Failed to save settings", is_error=True)

    def _undo_ignore(self):
        """Undo last ignore action."""
        if not self._last_ignored_patterns:
            self._show_status("Nothing to undo", is_error=True)
            return
        if remove_excluded_patterns(self._last_ignored_patterns):
            self._show_status(f"Removed {len(self._last_ignored_patterns)} pattern(s) from ignore list")
            self._last_ignored_patterns = []
            self._refresh_tree()
        else:
            self._show_status("Failed to undo", is_error=True)

    # === File Watcher Callbacks ===

    def _on_file_modified(self, path: str):
        from core.token_counter import clear_file_from_cache
        from core.security_check import invalidate_security_cache
        clear_file_from_cache(path)
        invalidate_security_cache(path)

    def _on_file_created(self, path: str):
        pass

    def _on_file_deleted(self, path: str):
        from core.token_counter import clear_file_from_cache
        from core.security_check import invalidate_security_cache
        clear_file_from_cache(path)
        invalidate_security_cache(path)
        if self.file_tree_component:
            self.file_tree_component.selected_paths.discard(path)

    def _on_file_system_changed(self):
        try:
            workspace = self.get_workspace()
            if workspace and self.page:
                async def _do_refresh():
                    current_workspace = self.get_workspace()
                    if current_workspace and current_workspace == workspace:
                        self._load_tree(workspace, preserve_selection=True)
                        self._show_status("File changes detected - tree updated")
                self.page.run_task(_do_refresh)
        except Exception:
            pass

    # === Token Counting ===

    def _on_instructions_changed(self):
        if self._token_update_timer:
            self._token_update_timer.cancel()
        self._token_update_timer = SafeTimer(0.15, self._update_token_count, page=self.page)
        self._token_update_timer.start()

    def _update_token_count(self):
        """
        Update token count display.
        
        FIX #4: Check generation counter để skip stale results.
        FIX #2: Đây là nguồn DUY NHẤT trigger token counting.
        """
        import os
        if not self.file_tree_component:
            return

        # Capture current generation
        current_gen = getattr(self, '_token_generation', 0)

        selected_paths = self.file_tree_component.get_visible_selected_paths()
        file_paths = [Path(p) for p in selected_paths if os.path.isfile(p)]
        file_count = len(file_paths)

        file_tokens = 0
        is_estimate = False

        if file_count > 0:
            token_service = self.file_tree_component._token_service
            cached_total = 0
            uncached_count = 0

            for fp in file_paths:
                cached = token_service.get_token_count(str(fp))
                if cached is not None:
                    cached_total += cached
                else:
                    uncached_count += 1

            MAX_IMMEDIATE = 20
            if uncached_count > 0:
                if uncached_count <= MAX_IMMEDIATE:
                    from services.token_display import start_token_counting
                    start_token_counting()
                    uncached_paths = [fp for fp in file_paths if token_service.get_token_count(str(fp)) is None]
                    token_results = count_tokens_batch_parallel(uncached_paths, max_workers=2)
                    
                    # Check generation before updating
                    if current_gen != getattr(self, '_token_generation', 0):
                        return  # Selection changed, result is stale
                    
                    with token_service._lock:
                        token_service._cache.update(token_results)
                    file_tokens = cached_total + sum(token_results.values())
                else:
                    is_estimate = True
                    file_tokens = cached_total + (uncached_count * 150)
                    uncached_paths = [str(fp) for fp in file_paths if token_service.get_token_count(str(fp)) is None]
                    from services.token_display import start_token_counting
                    start_token_counting()
                    token_service._schedule_deferred_counting(uncached_paths)
            else:
                file_tokens = cached_total

        prefix = "~" if is_estimate else ""
        suffix = " (filtered)" if self.file_tree_component.is_searching() else ""
        self.token_count_text.value = f"{prefix}{file_tokens:,} tokens{suffix}"

        instruction_tokens = count_tokens(self.instructions_field.value) if self.instructions_field and self.instructions_field.value else 0
        if self.token_stats_panel:
            self.token_stats_panel.update_stats(file_count=file_count, file_tokens=file_tokens, instruction_tokens=instruction_tokens)

        safe_page_update(self.page)

    # === Copy Actions ===

    def _on_format_changed(self, e):
        if e.control.value:
            try:
                self._selected_output_style = get_style_by_id(e.control.value)
                set_setting("output_format", e.control.value)
                if self.format_info_icon:
                    self.format_info_icon.tooltip = get_format_tooltip(self._selected_output_style)
                    if self.format_info_icon.page:
                        self.format_info_icon.update()
                self._show_status(f"Output format: {OUTPUT_FORMATS[self._selected_output_style].name}")
            except ValueError:
                pass

    def _preview_file(self, file_path: str):
        FilePreviewDialog.show(page=self.page, file_path=file_path)

    def _copy_context(self, include_xml: bool):
        """Copy context to clipboard with security check."""
        if not self.tree or not self.file_tree_component:
            self._show_status("No files selected", is_error=True)
            return

        selected_paths = self.file_tree_component.get_visible_selected_paths()
        if not selected_paths:
            msg = "No matching files selected. Clear search or select files." if self.file_tree_component.is_searching() else "Select files from the tree first"
            self._show_status(msg, is_error=True)
            return

        try:
            file_count = sum(1 for p in selected_paths if Path(p).is_file())
            if file_count > 10:
                self._show_status(f"Scanning {file_count} files...", is_error=False, auto_clear=False)
                safe_page_update(self.page)

            enable_security = get_setting("enable_security_check", True)
            secret_matches = scan_secrets_in_files_cached(selected_paths) if enable_security else []

            include_git = get_setting("include_git_changes", True)
            git_diffs, git_logs = None, None
            if include_git:
                workspace = self.get_workspace()
                if workspace:
                    git_diffs = get_git_diffs(workspace)
                    git_logs = get_git_logs(workspace)

            file_map = generate_file_map(self.tree, selected_paths)
            file_contents = self._generate_file_contents(selected_paths)
            instructions = self.instructions_field.value or ""
            prompt = generate_prompt(file_map, file_contents, instructions, include_xml, git_diffs=git_diffs, git_logs=git_logs, output_style=self._selected_output_style)

            if secret_matches:
                dialog = SecurityDialog(self.page, prompt, secret_matches, lambda p: self._do_copy(p, include_xml))
                dialog.show()
            else:
                self._do_copy(prompt, include_xml)

        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    def _generate_file_contents(self, selected_paths: Set[str]) -> str:
        """Generate file contents based on selected output style."""
        if self._selected_output_style == OutputStyle.XML:
            return generate_file_contents_xml(selected_paths)
        elif self._selected_output_style == OutputStyle.JSON:
            return generate_file_contents_json(selected_paths)
        elif self._selected_output_style == OutputStyle.PLAIN:
            return generate_file_contents_plain(selected_paths)
        return generate_file_contents(selected_paths)

    def _copy_tree_map_only(self):
        """Copy only tree map without file contents."""
        if not self.tree or not self.file_tree_component:
            self._show_status("No files selected", is_error=True)
            return

        selected_paths = self.file_tree_component.get_visible_selected_paths()
        if not selected_paths:
            self._show_status("No files selected", is_error=True)
            return

        try:
            instructions = self.instructions_field.value or ""
            prompt = generate_tree_map_only(self.tree, selected_paths, instructions)
            success, message = copy_to_clipboard(prompt)
            if success:
                self._show_status(f"Tree map copied! ({count_tokens(prompt):,} tokens)")
            else:
                self._show_status(message, is_error=True)
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    def _copy_smart_context(self):
        """Copy Smart Context with code structure only."""
        if not self.tree or not self.file_tree_component:
            self._show_status("No files selected", is_error=True)
            return

        selected_paths = self.file_tree_component.get_visible_selected_paths()
        if not selected_paths:
            self._show_status("No files selected", is_error=True)
            return

        try:
            file_count = sum(1 for p in selected_paths if Path(p).is_file())
            if file_count > 5:
                self._show_status(f"Parsing {file_count} files...", is_error=False, auto_clear=False)
                safe_page_update(self.page)

            smart_contents = generate_smart_context(selected_paths, include_relationships=True)
            file_map = generate_file_map(self.tree, selected_paths)
            instructions = self.instructions_field.value or ""

            prompt = f"<file_map>\n{file_map}\n</file_map>\n\n<file_contents>\n{smart_contents}\n</file_contents>\n"
            if instructions.strip():
                prompt += f"\n<user_instructions>\n{instructions.strip()}\n</user_instructions>\n"

            secret_matches = scan_for_secrets(prompt)
            if secret_matches:
                dialog = SecurityDialog(self.page, prompt, secret_matches, lambda p: self._do_copy(p, is_smart=True))
                dialog.show()
            else:
                self._do_copy(prompt, is_smart=True)

        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    def _do_copy(self, prompt: str, include_xml: bool = False, is_smart: bool = False):
        """Execute copy to clipboard."""
        success, message = copy_to_clipboard(prompt)
        if success:
            token_count = count_tokens(prompt)
            suffix = " + OPX" if include_xml else ""
            prefix = "Smart Context" if is_smart else ""
            self._show_status(f"{prefix} Copied! ({token_count:,} tokens){suffix}".strip())
        else:
            self._show_status(message, is_error=True)

    def _show_diff_only_dialog(self):
        """Show diff only options dialog."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        instructions = self.instructions_field.value or ""
        dialog = DiffOnlyDialog(
            self.page,
            workspace,
            self._build_diff_only_prompt,
            instructions,
            on_success=lambda msg: self._show_status(msg),
        )
        dialog.show()

    def _build_diff_only_prompt(self, diff_result: DiffOnlyResult, instructions: str, include_changed_content: bool, include_tree_structure: bool) -> str:
        """Build prompt for Copy Diff Only."""
        workspace = self.get_workspace()
        workspace_name = workspace.name if workspace else "unknown"

        parts = [
            "<diff_context>",
            f"Project: {workspace_name}",
            f"Files changed: {diff_result.files_changed}",
            f"Lines: +{diff_result.insertions} / -{diff_result.deletions}",
        ]
        if diff_result.commits_included > 0:
            parts.append(f"Commits included: {diff_result.commits_included}")
        parts.extend(["</diff_context>", ""])

        if include_tree_structure and diff_result.changed_files:
            tree_str = self._build_tree_from_paths(diff_result.changed_files[:50], workspace_name)
            parts.extend(["<project_structure>", tree_str, "</project_structure>", ""])

        parts.extend(["<git_diff>", diff_result.diff_content, "</git_diff>"])

        if include_changed_content and diff_result.changed_files and workspace:
            parts.extend(["", "<changed_files_content>"])
            for file_path in diff_result.changed_files[:20]:
                full_path = workspace / file_path
                if full_path.exists() and full_path.is_file():
                    try:
                        content = full_path.read_text(encoding='utf-8', errors='replace')
                        if len(content) <= 50000:
                            from core.utils.language_utils import get_language_from_path
                            lang = get_language_from_path(str(full_path))
                            parts.extend([f'<file path="{file_path}">', f"```{lang}", content, "```", "</file>"])
                    except Exception:
                        pass
            parts.append("</changed_files_content>")

        if instructions.strip():
            parts.extend(["", "<user_instructions>", instructions.strip(), "</user_instructions>"])

        return "\n".join(parts)

    def _build_tree_from_paths(self, file_paths: list, root_name: str) -> str:
        """Build tree hierarchy from file paths."""
        tree_dict: dict = {}
        for file_path in file_paths:
            parts = file_path.replace("\\", "/").split("/")
            current = tree_dict
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    current[part] = None
                else:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

        lines = [f"{root_name}/"]
        self._render_tree_dict(tree_dict, lines, indent=1)
        return "\n".join(lines)

    def _render_tree_dict(self, tree_dict: dict, lines: list, indent: int = 0):
        """Render tree dict to lines."""
        indent_str = "    " * indent
        items = sorted(tree_dict.items(), key=lambda x: (x[1] is None, x[0]))
        for name, children in items:
            if children is None:
                lines.append(f"{indent_str}{name}  [modified]")
            else:
                lines.append(f"{indent_str}{name}/")
                self._render_tree_dict(children, lines, indent + 1)

    # === Remote Repo Dialogs ===

    def _open_remote_repo_dialog(self):
        """Open dialog to clone remote repository."""
        if self._repo_manager is None:
            self._repo_manager = RepoManager()
        
        def on_success(repo_path: Path):
            self._show_status(f"Cloned: {repo_path.name}")
            self.on_workspace_changed(repo_path)

        dialog = RemoteRepoDialog(self.page, self._repo_manager, on_success)
        dialog.show()

    def _open_cache_management_dialog(self):
        """Open dialog to manage cached repositories."""
        if self._repo_manager is None:
            self._repo_manager = RepoManager()

        def on_open(repo_path: Path):
            self._show_status(f"Opened: {repo_path.name}")
            self.on_workspace_changed(repo_path)

        dialog = CacheManagementDialog(self.page, self._repo_manager, on_open)
        dialog.show()

    # === Status Display ===

    def _show_status(self, message: str, is_error: bool = False, auto_clear: bool = True):
        """Show status message with optional auto-clear."""
        if self._status_clear_timer:
            self._status_clear_timer.cancel()
            self._status_clear_timer = None

        self.status_text.value = message
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        safe_page_update(self.page)

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