"""
Context View - Tab de chon files va copy context

Su dung FileTreeComponent tu components/file_tree.py
"""

import flet as ft
import threading
from threading import Timer
from pathlib import Path
from typing import Callable, Optional, Set, Union

from core.utils.file_utils import scan_directory, TreeItem
from core.utils.ui_utils import safe_page_update
from services.clipboard_utils import copy_to_clipboard
from core.token_counter import count_tokens_batch_parallel, count_tokens
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
from core.utils.git_utils import get_git_diffs, get_git_logs, get_diff_only
from core.tree_map_generator import generate_tree_map_only
from components.file_tree import FileTreeComponent
from components.file_preview import FilePreviewDialog
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
from core.utils.repo_manager import RepoManager, CloneProgress


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
        self._token_update_timer: Optional[Union[Timer, SafeTimer]] = None
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

        # Remote repo manager - quản lý clone và cache repositories
        self._repo_manager: Optional[RepoManager] = None

    def _show_dirty_repo_dialog(
        self, repo_path: Path, repo_name: str, status_text: ft.Text, refresh_callback
    ):
        """
        Hien thi dialog khi repo co thay doi local chua commit.

        Cho phep user chon: Stash & Pull, Discard & Pull, hoac Cancel.
        """
        import threading

        def close_dialog(e=None):
            dirty_dialog.open = False
            safe_page_update(self.page)

        def stash_and_pull(e):
            close_dialog()
            status_text.value = f"Stashing changes in {repo_name}..."
            status_text.color = ThemeColors.PRIMARY
            safe_page_update(self.page)

            def do_stash_pull():
                try:
                    assert self._repo_manager is not None
                    # Stash changes
                    if not self._repo_manager.stash_changes(repo_path):
                        status_text.value = f"Failed to stash changes in {repo_name}"
                        status_text.color = ThemeColors.ERROR
                        safe_page_update(self.page)
                        return

                    # Pull
                    self._repo_manager._update_repo(repo_path, None, None)
                    status_text.value = f"Updated {repo_name} (changes stashed)"
                    status_text.color = ThemeColors.SUCCESS
                except Exception as ex:
                    status_text.value = f"Update failed: {ex}"
                    status_text.color = ThemeColors.ERROR
                refresh_callback()
                safe_page_update(self.page)

            threading.Thread(target=do_stash_pull, daemon=True).start()

        def discard_and_pull(e):
            # Show confirmation dialog for discard
            def confirm_discard(e):
                confirm_dialog.open = False
                dirty_dialog.open = False
                safe_page_update(self.page)

                status_text.value = f"Discarding changes in {repo_name}..."
                status_text.color = ThemeColors.WARNING
                safe_page_update(self.page)

                def do_discard_pull():
                    try:
                        assert self._repo_manager is not None
                        # Discard changes
                        if not self._repo_manager.discard_changes(repo_path):
                            status_text.value = (
                                f"Failed to discard changes in {repo_name}"
                            )
                            status_text.color = ThemeColors.ERROR
                            safe_page_update(self.page)
                            return

                        # Pull
                        self._repo_manager._update_repo(repo_path, None, None)
                        status_text.value = f"Updated {repo_name} (changes discarded)"
                        status_text.color = ThemeColors.SUCCESS
                    except Exception as ex:
                        status_text.value = f"Update failed: {ex}"
                        status_text.color = ThemeColors.ERROR
                    refresh_callback()
                    safe_page_update(self.page)

                threading.Thread(target=do_discard_pull, daemon=True).start()

            def cancel_confirm(e):
                confirm_dialog.open = False
                safe_page_update(self.page)

            confirm_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(
                    "Confirm Discard",
                    weight=ft.FontWeight.BOLD,
                    color=ThemeColors.ERROR,
                ),
                content=ft.Text(
                    f"Ban co chac chan muon XOA VINH VIEN tat ca thay doi local trong '{repo_name}'?\n\n"
                    "Hanh dong nay KHONG THE HOAN TAC!",
                    color=ThemeColors.TEXT_PRIMARY,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=cancel_confirm),
                    ft.TextButton(
                        "Discard & Pull",
                        on_click=confirm_discard,
                        style=ft.ButtonStyle(color=ThemeColors.ERROR),
                    ),
                ],
            )
            self.page.overlay.append(confirm_dialog)
            confirm_dialog.open = True
            safe_page_update(self.page)

        dirty_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Uncommitted Changes",
                weight=ft.FontWeight.BOLD,
                color=ThemeColors.WARNING,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            f"Repository '{repo_name}' co thay doi local chua commit.",
                            color=ThemeColors.TEXT_PRIMARY,
                        ),
                        ft.Container(height=8),
                        ft.Text(
                            "Ban muon lam gi?",
                            size=13,
                            color=ThemeColors.TEXT_SECONDARY,
                        ),
                    ],
                    tight=True,
                ),
                width=400,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.OutlinedButton(
                    "Discard & Pull",
                    icon=ft.Icons.DELETE_FOREVER,
                    on_click=discard_and_pull,
                    style=ft.ButtonStyle(
                        color=ThemeColors.ERROR,
                        side=ft.BorderSide(1, ThemeColors.ERROR),
                    ),
                ),
                ft.OutlinedButton(
                    "Stash & Pull",
                    icon=ft.Icons.SAVE,
                    on_click=stash_and_pull,
                    style=ft.ButtonStyle(
                        color=ThemeColors.SUCCESS,
                        side=ft.BorderSide(1, ThemeColors.SUCCESS),
                    ),
                ),
            ],
        )

        self.page.overlay.append(dirty_dialog)
        dirty_dialog.open = True
        safe_page_update(self.page)

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

        # File tree component voi search and preview
        # PERFORMANCE: Disable line counting mặc định - giảm 50% I/O operations
        self.file_tree_component = FileTreeComponent(
            page=self.page,
            on_selection_changed=self._on_selection_changed,
            on_preview=self._preview_file,  # Enable file preview
            show_tokens=True,
            show_lines=False,  # Disabled for performance with large projects (700+ files)
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
                                # Remote Repos Menu (Dropdown) - Clone va quan ly remote repositories
                                ft.PopupMenuButton(
                                    content=ft.Row(
                                        [
                                            ft.Icon(
                                                ft.Icons.CLOUD,
                                                size=18,
                                                color=ThemeColors.PRIMARY,
                                            ),
                                            ft.Text(
                                                "Remote Repos",
                                                size=13,
                                                color=ThemeColors.TEXT_PRIMARY,
                                                weight=ft.FontWeight.W_500,
                                            ),
                                            ft.Icon(
                                                ft.Icons.ARROW_DROP_DOWN,
                                                size=18,
                                                color=ThemeColors.TEXT_SECONDARY,
                                            ),
                                        ],
                                        spacing=4,
                                    ),
                                    items=[
                                        ft.PopupMenuItem(
                                            content=ft.Row(
                                                [
                                                    ft.Icon(
                                                        ft.Icons.CLOUD_DOWNLOAD,
                                                        size=16,
                                                        color=ThemeColors.PRIMARY,
                                                    ),
                                                    ft.Text(
                                                        "Clone Repository",
                                                        size=13,
                                                    ),
                                                ],
                                                spacing=8,
                                            ),
                                            on_click=lambda _: self._open_remote_repo_dialog(),
                                        ),
                                        ft.PopupMenuItem(
                                            content=ft.Row(
                                                [
                                                    ft.Icon(
                                                        ft.Icons.FOLDER_OPEN,
                                                        size=16,
                                                        color=ThemeColors.TEXT_SECONDARY,
                                                    ),
                                                    ft.Text(
                                                        "Manage Cache",
                                                        size=13,
                                                    ),
                                                ],
                                                spacing=8,
                                            ),
                                            on_click=lambda _: self._open_cache_management_dialog(),
                                        ),
                                    ],
                                    tooltip="Remote Repository Actions",
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
                    # Row 0: Copy Diff Only - Chỉ copy git changes
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "Copy Diff Only",
                                icon=ft.Icons.DIFFERENCE,
                                on_click=lambda _: self._show_diff_only_dialog(),
                                expand=True,
                                tooltip="Copy only git diff (uncommitted + recent commits)",
                                style=ft.ButtonStyle(
                                    color="#FFFFFF",
                                    bgcolor="#8B5CF6",  # Purple
                                ),
                            ),
                        ],
                        spacing=12,
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
        """
        Khi user chon folder moi hoac settings thay doi.
        
        DEBOUNCE: Tránh gọi liên tiếp khi startup.
        """
        from core.logging_config import log_info, log_debug
        import time
        
        # Debounce: Nếu cùng workspace và gọi trong vòng 1 giây, bỏ qua
        current_time = time.time()
        if (hasattr(self, '_last_workspace_change_time') and 
            hasattr(self, '_last_workspace_path') and
            self._last_workspace_path == str(workspace_path) and
            current_time - self._last_workspace_change_time < 1.0):
            log_debug(f"[ContextView] Debouncing workspace change for: {workspace_path}")
            return
        
        self._last_workspace_change_time = current_time
        self._last_workspace_path = str(workspace_path)
        
        log_info(f"[ContextView] Workspace changing to: {workspace_path}")
        
        # ========================================
        # AGGRESSIVE CLEANUP: Stop ALL operations IMMEDIATELY
        # Phải stop triệt để trước khi load folder mới
        # KHÔNG CẦN YIELD - các operations phải tự check cancellation flag
        # ========================================
        from core.utils.file_scanner import stop_scanning
        from services.token_display import stop_token_counting

        # Stop scanning and token counting FIRST
        stop_scanning()
        stop_token_counting()

        # Cancel any pending timers IMMEDIATELY
        if self._token_update_timer is not None:
            try:
                self._token_update_timer.cancel()
            except Exception:
                pass
            self._token_update_timer = None
        
        if self._selection_update_timer is not None:
            try:
                self._selection_update_timer.dispose()
            except Exception:
                pass
            self._selection_update_timer = None

        # Stop file watcher for old folder IMMEDIATELY
        if self._file_watcher:
            self._file_watcher.stop()

        # Cleanup old resources before loading new tree
        # reset_for_new_tree() sẽ cancel tất cả deferred timers
        if self.file_tree_component:
            self.file_tree_component.reset_for_new_tree()
        
        # NO YIELD NEEDED - background tasks check cancellation flags
        # Yield chỉ làm chậm folder switching
        
        # Load new tree (will handle its own loading state)
        self._load_tree(workspace_path)

        # Start file watcher for new folder AFTER tree is loaded
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
        
        PERFORMANCE FIX: KHÔNG tự động count tokens - lazy load khi user select files.

        Args:
            workspace_path: Path to workspace folder
            preserve_selection: Neu True, giu lai selection hien tai (cho Refresh)
        """
        from core.logging_config import log_info, log_error, log_debug
        
        # ========================================
        # RACE CONDITION FIX: Check và acquire loading lock
        # ========================================
        with self._loading_lock:
            if self._is_loading:
                # Đang load rồi, queue refresh request cho sau
                self._pending_refresh = True
                log_debug("[ContextView] Load request queued - another load in progress")
                return
            # Mark đang loading
            self._is_loading = True
            self._pending_refresh = False

        # Save current selection before loading
        old_selection: Set[str] = set()
        if preserve_selection and self.file_tree_component:
            old_selection = self.file_tree_component.get_selected_paths()

        # ========================================
        # AGGRESSIVE CLEANUP: Stop ALL background operations IMMEDIATELY
        # This is CRITICAL for fast folder switching
        # ========================================
        from core.utils.file_scanner import stop_scanning
        from services.token_display import stop_token_counting
        
        stop_scanning()
        stop_token_counting()
        
        # Cancel any pending token update timers
        if self._token_update_timer is not None:
            try:
                self._token_update_timer.cancel()
            except Exception:
                pass
            self._token_update_timer = None
        
        if self._selection_update_timer is not None:
            try:
                self._selection_update_timer.dispose()
            except Exception:
                pass
            self._selection_update_timer = None

        # Show loading state IMMEDIATELY
        self._show_status("Loading...", is_error=False, auto_clear=False)
        
        # Reset token display to show clean state (no loading spinner)
        if self.token_count_text:
            self.token_count_text.value = "0 tokens"
        if self.token_stats_panel:
            self.token_stats_panel.set_loading(False)
            # Reset stats to 0 immediately for visual feedback
            self.token_stats_panel.update_stats(
                file_count=0,
                file_tokens=0,
                instruction_tokens=0,
            )
        
        # Force UI update BEFORE scanning
        safe_page_update(self.page)

        try:
            from views.settings_view import get_excluded_patterns, get_use_gitignore
            from core.utils.file_scanner import scan_directory, ScanProgress, start_scanning

            excluded_patterns = get_excluded_patterns()
            use_gitignore = get_use_gitignore()

            # Progress callback - update status text
            def on_progress(progress: ScanProgress):
                if self.status_text:
                    self.status_text.value = (
                        f"Scanning: {progress.directories} dirs, {progress.files} files"
                    )
                    # Không gọi safe_page_update() ở đây để tránh race condition

            # LAZY LOADING: Scan CHỈ depth=1 (immediate children)
            # Folders sẽ có is_loaded=False, load on-demand khi user click
            log_info(f"[ContextView] Starting SHALLOW scan (depth=1) for: {workspace_path}")
            
            from core.utils.file_utils import scan_directory_shallow
            
            self.tree = scan_directory_shallow(
                workspace_path,
                depth=1,  # Chỉ scan immediate children
                excluded_patterns=excluded_patterns,
                use_gitignore=use_gitignore,
            )
            
            log_info(f"[ContextView] Shallow scan complete. Tree: {self.tree.label if self.tree else 'None'}")

            # Set tree to component - NO TOKEN COUNTING HERE
            assert self.file_tree_component is not None
            log_info(f"[ContextView] Setting tree to component...")
            self.file_tree_component.set_tree(
                self.tree, preserve_selection=preserve_selection
            )
            log_info(f"[ContextView] Tree set complete")

            # ========================================
            # LAZY LOADING: NO automatic token counting
            # Tokens will be counted ONLY when user selects files
            # This makes folder switching INSTANT
            # ========================================
            self._show_status("")
            safe_page_update(self.page)
            log_info(f"[ContextView] Load tree finished successfully (no token counting)")

        except Exception as e:
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
                log_debug("[ContextView] Executing pending refresh request")
                # Defer để tránh recursion quá sâu
                if self.page:
                    async def _deferred_refresh():
                        self._load_tree(workspace_path, preserve_selection=True)
                    self.page.run_task(_deferred_refresh)

    def _on_selection_changed(self, selected_paths: Set[str]):
        """Callback khi selection thay doi - smart debouncing based on selection size"""
        from core.logging_config import log_info
        
        # Cancel previous timer if exists
        if self._selection_update_timer is not None:
            self._selection_update_timer.dispose()
            self._selection_update_timer = None

        selection_size = len(selected_paths)
        log_info(f"[ContextView] _on_selection_changed: {selection_size} paths selected")
        
        # Adaptive debounce based on selection size
        # PERFORMANCE: Tăng debounce cho project lớn để tránh spam
        if selection_size == 0:
            # No selection - update immediately to show zero
            log_info("[ContextView] Calling _update_token_count (0 selection)")
            self._update_token_count()
            return
        elif selection_size < 5:
            # Very small - update immediately
            log_info(f"[ContextView] Calling _update_token_count ({selection_size} files, no debounce)")
            self._update_token_count()
            return
        elif selection_size < 20:
            # Small - short debounce
            debounce_ms = 150
        elif selection_size < 100:
            # Medium - moderate debounce
            debounce_ms = 250
        elif selection_size < 500:
            # Large - longer debounce
            debounce_ms = 400
        else:
            # Very large (700+ files) - much longer debounce
            debounce_ms = 700

        log_info(f"[ContextView] Scheduling _update_token_count in {debounce_ms}ms")
        
        # Debounce with SafeTimer
        self._selection_update_timer = SafeTimer(
            interval=debounce_ms / 1000.0,
            callback=self._do_update_token_count,
            page=self.page,
            use_main_thread=True
        )
        self._selection_update_timer.start()

    def _preview_file(self, file_path: str):
        """
        Preview noi dung mot file trong dialog.

        Duoc goi khi user double-click hoac click preview icon tren file.
        Su dung FilePreviewDialog de hien thi noi dung file.

        Args:
            file_path: Duong dan tuyet doi den file can preview
        """
        FilePreviewDialog.show(page=self.page, file_path=file_path)

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
                        if current_workspace and current_workspace == workspace and workspace is not None:
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
            self._token_update_timer.cancel()  # Use cancel for Timer

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
        
        PERFORMANCE FIX v3: 
        - Sử dụng cache từ TokenDisplayService
        - Giới hạn immediate counting để không block UI (max 20 files)
        - Hiển thị estimate với indicator "~" khi đang count background
        - KHÔNG gọi count_tokens_batch_parallel cho large selections
        """
        from core.logging_config import log_debug
        import time
        
        if not self.file_tree_component:
            return

        # STEP 1: Get selected paths - O(n) với n = số selected
        selected_paths = self.file_tree_component.get_visible_selected_paths()

        # STEP 2: Filter files only (use os.path.isfile - faster than Path.is_file)
        import os
        file_paths = [Path(p) for p in selected_paths if os.path.isfile(p)]
        file_count = len(file_paths)

        # STEP 3: Token counting - OPTIMIZED cho project lớn
        file_tokens = 0
        is_estimate = False  # Flag để hiện "~" prefix
        
        if file_count > 0:
            token_service = self.file_tree_component._token_service
            cached_total = 0
            uncached_count = 0
            
            # Cache lookup only - KHÔNG count ngay
            for fp in file_paths:
                cached = token_service.get_token_count(str(fp))
                if cached is not None:
                    cached_total += cached
                else:
                    uncached_count += 1
            
            # PERFORMANCE FIX: Với >50 uncached files, chỉ hiển thị estimate
            # Background counting sẽ update sau
            MAX_IMMEDIATE = 20  # Giảm từ 30 xuống 20 để không block
            
            if uncached_count > 0:
                if uncached_count <= MAX_IMMEDIATE:
                    # Ít files - count ngay nhưng async
                    from services.token_display import start_token_counting
                    start_token_counting()
                    
                    uncached_paths = [fp for fp in file_paths if token_service.get_token_count(str(fp)) is None]
                    token_results = count_tokens_batch_parallel(uncached_paths, max_workers=2)  # Giảm workers
                    
                    with token_service._lock:
                        token_service._cache.update(token_results)
                    
                    file_tokens = cached_total + sum(token_results.values())
                else:
                    # LARGE PROJECT: Chỉ hiển thị cached + estimate
                    is_estimate = True
                    
                    # Estimate: ~150 tokens/file (average cho code files)
                    estimated_uncached = uncached_count * 150
                    file_tokens = cached_total + estimated_uncached
                    
                    # Schedule background counting (sẽ update UI sau)
                    uncached_paths = [str(fp) for fp in file_paths if token_service.get_token_count(str(fp)) is None]
                    from services.token_display import start_token_counting
                    start_token_counting()
                    token_service._schedule_deferred_counting(uncached_paths)
            else:
                file_tokens = cached_total

        # Update display với estimate indicator
        assert self.token_count_text is not None
        prefix = "~" if is_estimate else ""
        
        if self.file_tree_component.is_searching():
            self.token_count_text.value = f"{prefix}{file_tokens:,} tokens (filtered)"
        else:
            self.token_count_text.value = f"{prefix}{file_tokens:,} tokens"

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
            # match.file_path giờ là absolute path, lấy basename để hiển thị
            display_name = Path(match.file_path).name if match.file_path else ""
            file_info = f" in {display_name}" if display_name else ""

            # Handler để mở preview tại dòng bị cảnh báo
            def make_preview_handler(abs_file_path: str, line_num: int):
                def handler(e):
                    if abs_file_path:
                        # Đóng dialog security warning trước
                        dialog.open = False
                        safe_page_update(self.page)
                        # Mở preview với absolute path
                        FilePreviewDialog.show(
                            page=self.page,
                            file_path=abs_file_path,
                            highlight_line=line_num,
                        )

                return handler

            item_container = ft.Container(
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

            # Wrap với GestureDetector để click mở preview
            if match.file_path:
                clickable_item = ft.GestureDetector(
                    content=ft.Container(
                        content=item_container,
                        ink=True,  # Ripple effect
                    ),
                    on_tap=make_preview_handler(match.file_path, match.line_number),
                    mouse_cursor=ft.MouseCursor.CLICK,
                )
                details_col.controls.append(clickable_item)
            else:
                details_col.controls.append(item_container)

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

    def _show_diff_only_dialog(self):
        """
        Hiển thị dialog để chọn options cho Copy Diff Only.
        
        Options:
        - Số commits cần include (0 = chỉ uncommitted)
        - Include staged changes
        - Include unstaged changes
        - Include changed file content (full content của files bị thay đổi)
        - Include tree structure
        - Filter by file pattern (NEW)
        """
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return
        
        # State variables
        num_commits = ft.TextField(
            value="0",
            label="Recent commits to include",
            hint_text="0 = uncommitted only",
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
        )
        
        include_staged = ft.Checkbox(
            label="Include staged changes",
            value=True,
            active_color=ThemeColors.PRIMARY,
        )
        
        include_unstaged = ft.Checkbox(
            label="Include unstaged changes", 
            value=True,
            active_color=ThemeColors.PRIMARY,
        )
        
        # NEW: Option to include full content of changed files
        include_file_content = ft.Checkbox(
            label="Include changed file content",
            value=False,
            active_color=ThemeColors.WARNING,
            tooltip="Include full content of modified files for better AI context",
        )
        
        # NEW: Option to include tree structure
        include_tree = ft.Checkbox(
            label="Include project tree structure",
            value=False,
            active_color=ThemeColors.PRIMARY,
            tooltip="Include file tree to help AI understand project structure",
        )
        
        # NEW: File pattern filter
        file_pattern = ft.TextField(
            value="",
            label="Filter files (optional)",
            hint_text="e.g., *.py, src/*.ts",
            width=200,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
        )
        
        status_text = ft.Text("", size=12, color=ThemeColors.TEXT_SECONDARY)
        
        def close_dialog(e=None):
            dialog.open = False
            safe_page_update(self.page)
        
        def do_copy(e):
            try:
                commits = int(num_commits.value or "0")
                if commits < 0:
                    commits = 0
            except ValueError:
                commits = 0
            
            status_text.value = "Getting diff..."
            safe_page_update(self.page)
            
            # Get diff
            result = get_diff_only(
                workspace,
                num_commits=commits,
                include_staged=include_staged.value or False,
                include_unstaged=include_unstaged.value or False,
            )
            
            if result.error:
                status_text.value = f"Error: {result.error}"
                status_text.color = ThemeColors.ERROR
                safe_page_update(self.page)
                return
            
            if not result.diff_content.strip():
                status_text.value = "No changes found"
                status_text.color = ThemeColors.WARNING
                safe_page_update(self.page)
                return
            
            # Build context for AI
            assert self.instructions_field is not None
            instructions = self.instructions_field.value or ""
            
            # NEW: Build enhanced prompt with optional file content and tree
            prompt = self._build_diff_only_prompt(
                result, 
                instructions,
                include_changed_content=include_file_content.value or False,
                include_tree_structure=include_tree.value or False,
            )
            
            # Copy to clipboard
            success, message = copy_to_clipboard(prompt)
            
            if success:
                close_dialog()
                token_count = count_tokens(prompt)
                self._show_status(
                    f"Diff copied! ({token_count:,} tokens, "
                    f"+{result.insertions}/-{result.deletions} lines, "
                    f"{result.files_changed} files)"
                )
            else:
                status_text.value = f"Copy failed: {message}"
                status_text.color = ThemeColors.ERROR
                safe_page_update(self.page)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Copy Diff Only",
                weight=ft.FontWeight.BOLD,
                color=ThemeColors.TEXT_PRIMARY,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Copy only git changes instead of full source code.",
                            size=13,
                            color=ThemeColors.TEXT_SECONDARY,
                        ),
                        ft.Text(
                            "Ideal for: code review, bug fixing, feature validation.",
                            size=12,
                            color=ThemeColors.TEXT_MUTED,
                            italic=True,
                        ),
                        ft.Container(height=16),
                        ft.Row([num_commits, file_pattern], spacing=16),
                        ft.Container(height=8),
                        include_staged,
                        include_unstaged,
                        ft.Divider(height=16, color=ThemeColors.BORDER),
                        ft.Text(
                            "Enhanced context (larger output):",
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=ThemeColors.TEXT_SECONDARY,
                        ),
                        include_file_content,
                        include_tree,
                        ft.Container(height=12),
                        status_text,
                    ],
                    tight=True,
                ),
                width=450,  # Tăng width để chứa 2 fields
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY),
                ),
                ft.ElevatedButton(
                    "Copy Diff",
                    icon=ft.Icons.CONTENT_COPY,
                    on_click=do_copy,
                    style=ft.ButtonStyle(
                        color="#FFFFFF",
                        bgcolor="#8B5CF6",
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(self.page)
    
    def _build_diff_only_prompt(
        self, 
        diff_result, 
        instructions: str,
        include_changed_content: bool = False,
        include_tree_structure: bool = False,
    ) -> str:
        """
        Build prompt cho Copy Diff Only - optimized for AI review.
        
        Args:
            diff_result: DiffOnlyResult từ get_diff_only()
            instructions: User instructions
            include_changed_content: Include full content of changed files
            include_tree_structure: Include project tree structure
        
        Returns:
            Formatted prompt string
        """
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
        
        parts.extend([
            "</diff_context>",
            "",
        ])
        
        # Optional: Include tree structure for project context
        if include_tree_structure and self.tree and self.file_tree_component:
            selected_paths = self.file_tree_component.get_selected_paths()
            if selected_paths:
                file_map = generate_file_map(self.tree, selected_paths)
                parts.extend([
                    "<project_structure>",
                    file_map,
                    "</project_structure>",
                    "",
                ])
        
        # Git diff content
        parts.extend([
            "<git_diff>",
            diff_result.diff_content,
            "</git_diff>",
        ])
        
        # Optional: Include full content of changed files
        if include_changed_content and diff_result.changed_files:
            parts.extend([
                "",
                "<changed_files_content>",
            ])
            
            for file_path in diff_result.changed_files[:20]:  # Limit to 20 files
                full_path = workspace / file_path if workspace else Path(file_path)
                if full_path.exists() and full_path.is_file():
                    try:
                        content = full_path.read_text(encoding='utf-8', errors='replace')
                        # Limit file size to 50KB
                        if len(content) <= 50000:
                            from core.utils.language_utils import get_language_from_path
                            lang = get_language_from_path(str(full_path))
                            parts.extend([
                                f"<file path=\"{file_path}\">",
                                f"```{lang}",
                                content,
                                "```",
                                "</file>",
                            ])
                    except Exception:
                        pass
            
            parts.append("</changed_files_content>")
        
        if instructions.strip():
            parts.extend([
                "",
                "<user_instructions>",
                instructions.strip(),
                "</user_instructions>",
            ])
        
        return "\n".join(parts)

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

    # ========================================
    # REMOTE REPO DIALOGS
    # Các dialog để clone và quản lý remote repositories
    # ========================================

    def _open_remote_repo_dialog(self):
        """
        Mở dialog để nhập GitHub URL và clone repository.

        Dialog bao gồm:
        - TextField cho URL input (hỗ trợ owner/repo hoặc full URL)
        - Clone button với progress indicator
        - Error handling và feedback
        """
        # State cho dialog
        url_field = ft.TextField(
            label="GitHub URL",
            hint_text="owner/repo hoặc https://github.com/owner/repo",
            autofocus=True,
            expand=True,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            label_style=ft.TextStyle(color=ThemeColors.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY),
        )

        progress_ring = ft.ProgressRing(
            width=20,
            height=20,
            stroke_width=2,
            color=ThemeColors.PRIMARY,
            visible=False,
        )

        status_text = ft.Text(
            "",
            size=12,
            color=ThemeColors.TEXT_SECONDARY,
        )

        clone_button = ft.ElevatedButton(
            "Clone",
            icon=ft.Icons.DOWNLOAD,
            style=ft.ButtonStyle(
                color="#FFFFFF",
                bgcolor=ThemeColors.PRIMARY,
            ),
        )

        def close_dialog(e=None):
            dialog.open = False
            safe_page_update(self.page)

        def on_clone_click(e):
            url = url_field.value
            if not url or not url.strip():
                status_text.value = "Vui lòng nhập GitHub URL"
                status_text.color = ThemeColors.ERROR
                safe_page_update(self.page)
                return

            # Show progress
            progress_ring.visible = True
            clone_button.disabled = True
            status_text.value = "Đang clone..."
            status_text.color = ThemeColors.TEXT_SECONDARY
            safe_page_update(self.page)

            # Clone in background
            import threading

            def do_clone():
                try:
                    # Initialize repo manager if needed
                    if self._repo_manager is None:
                        self._repo_manager = RepoManager()

                    # Progress callback - cập nhật UI với tiến trình clone
                    def on_progress(progress: CloneProgress):
                        status_text.value = progress.status
                        if progress.percentage is not None and status_text.value:
                            status_text.value = (
                                status_text.value + f" ({progress.percentage}%)"
                            )
                        safe_page_update(self.page)

                    # Clone repository
                    repo_path = self._repo_manager.clone_repo(
                        url.strip() if url else "",
                        on_progress=on_progress,
                    )

                    # Success - close dialog và switch workspace
                    def switch_workspace():
                        close_dialog()
                        self._show_status(f"Cloned: {repo_path.name}")
                        # Trigger workspace change
                        self.on_workspace_changed(repo_path)

                    self.page.run_thread(switch_workspace)

                except Exception as ex:
                    # Show error - capture exception message trước
                    error_msg = str(ex)

                    def show_error():
                        progress_ring.visible = False
                        clone_button.disabled = False
                        status_text.value = error_msg
                        status_text.color = ThemeColors.ERROR
                        safe_page_update(self.page)

                    self.page.run_thread(show_error)

            threading.Thread(target=do_clone, daemon=True).start()

        clone_button.on_click = on_clone_click

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Open Remote Repository",
                weight=ft.FontWeight.BOLD,
                color=ThemeColors.TEXT_PRIMARY,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Nhập GitHub URL hoặc shorthand (owner/repo) để clone repository.",
                            size=13,
                            color=ThemeColors.TEXT_SECONDARY,
                        ),
                        ft.Container(height=12),
                        url_field,
                        ft.Container(height=8),
                        ft.Row(
                            [
                                progress_ring,
                                status_text,
                            ],
                            spacing=8,
                        ),
                    ],
                    tight=True,
                ),
                width=450,
                height=180,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY),
                ),
                clone_button,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(self.page)

    def _open_cache_management_dialog(self):
        """
        Mở dialog quản lý cached repositories.

        Hiển thị list các repos đã clone với:
        - Tên repo và kích thước
        - Thời gian clone
        - Button Open và Delete cho từng repo
        - Button Clear All để xóa tất cả
        """
        # Initialize repo manager if needed
        if self._repo_manager is None:
            self._repo_manager = RepoManager()

        # Get cached repos
        cached_repos = self._repo_manager.get_cached_repos()

        # Status text cho feedback
        status_text = ft.Text(
            "",
            size=12,
            color=ThemeColors.TEXT_SECONDARY,
        )

        # Build repo list container
        repo_list = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
        )

        def refresh_list():
            """Refresh danh sách repos sau khi delete."""
            assert self._repo_manager is not None
            repo_list.controls.clear()
            cached_repos = self._repo_manager.get_cached_repos()

            if not cached_repos:
                repo_list.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "Chưa có repository nào được clone.",
                            size=13,
                            color=ThemeColors.TEXT_SECONDARY,
                            italic=True,
                        ),
                        padding=20,
                        alignment=ft.alignment.center,
                    )
                )
            else:
                for repo in cached_repos:
                    # Format size thành human-readable
                    size_str = self._repo_manager.format_size(repo.size_bytes)

                    # Format thời gian
                    time_str = ""
                    if repo.last_modified:
                        time_str = repo.last_modified.strftime("%Y-%m-%d %H:%M")

                    # Handler cho Open button - closure để capture path
                    def make_open_handler(path):
                        def handler(e):
                            dialog.open = False
                            safe_page_update(self.page)
                            self.on_workspace_changed(path)
                            self._show_status(f"Opened: {path.name}")

                        return handler

                    # Handler cho Delete button - closure để capture name
                    def make_delete_handler(name):
                        def handler(e):
                            assert self._repo_manager is not None
                            if self._repo_manager.delete_repo(name):
                                status_text.value = f"Deleted: {name}"
                                status_text.color = ThemeColors.SUCCESS
                                refresh_list()
                                safe_page_update(self.page)
                            else:
                                status_text.value = f"Failed to delete: {name}"
                                status_text.color = ThemeColors.ERROR
                                safe_page_update(self.page)

                        return handler

                    def make_update_handler(path, name):
                        def handler(e):
                            import threading

                            assert self._repo_manager is not None

                            # Check if .git exists
                            git_dir = path / ".git"
                            if not git_dir.exists():
                                status_text.value = (
                                    f"{name}: Khong co .git, can xoa va clone lai"
                                )
                                status_text.color = ThemeColors.WARNING
                                safe_page_update(self.page)
                                return

                            # Check if repo is dirty
                            repo_mgr = self._repo_manager
                            if repo_mgr.is_dirty(path):
                                # Show dirty dialog with options
                                self._show_dirty_repo_dialog(
                                    path, name, status_text, refresh_list
                                )
                            else:
                                # Clean repo, proceed with update
                                status_text.value = f"Updating {name}..."
                                status_text.color = ThemeColors.PRIMARY
                                safe_page_update(self.page)

                                def do_update():
                                    try:
                                        assert repo_mgr is not None
                                        repo_mgr._update_repo(path, None, None)
                                        status_text.value = f"Updated: {name}"
                                        status_text.color = ThemeColors.SUCCESS
                                    except Exception as ex:
                                        status_text.value = f"Update failed: {ex}"
                                        status_text.color = ThemeColors.ERROR
                                    refresh_list()
                                    safe_page_update(self.page)

                                threading.Thread(target=do_update, daemon=True).start()

                        return handler

                    # Card cho moi repo voi info va actions
                    repo_card = ft.Container(
                        content=ft.Row(
                            [
                                # Repo info column
                                ft.Column(
                                    [
                                        ft.Text(
                                            repo.name,
                                            size=14,
                                            weight=ft.FontWeight.W_600,
                                            color=ThemeColors.TEXT_PRIMARY,
                                        ),
                                        ft.Row(
                                            [
                                                ft.Icon(
                                                    ft.Icons.FOLDER,
                                                    size=12,
                                                    color=ThemeColors.TEXT_SECONDARY,
                                                ),
                                                ft.Text(
                                                    size_str,
                                                    size=12,
                                                    color=ThemeColors.TEXT_SECONDARY,
                                                ),
                                                ft.Container(width=8),
                                                ft.Icon(
                                                    ft.Icons.ACCESS_TIME,
                                                    size=12,
                                                    color=ThemeColors.TEXT_SECONDARY,
                                                ),
                                                ft.Text(
                                                    time_str,
                                                    size=12,
                                                    color=ThemeColors.TEXT_SECONDARY,
                                                ),
                                            ],
                                            spacing=4,
                                        ),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                # Action buttons
                                ft.Row(
                                    [
                                        ft.OutlinedButton(
                                            "Open",
                                            icon=ft.Icons.FOLDER_OPEN,
                                            on_click=make_open_handler(repo.path),
                                            style=ft.ButtonStyle(
                                                color=ThemeColors.PRIMARY,
                                                side=ft.BorderSide(
                                                    1, ThemeColors.PRIMARY
                                                ),
                                            ),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.SYNC,
                                            icon_size=20,
                                            icon_color=ThemeColors.SUCCESS,
                                            tooltip="Update (git pull)",
                                            on_click=make_update_handler(
                                                repo.path, repo.name
                                            ),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            icon_size=20,
                                            icon_color=ThemeColors.ERROR,
                                            tooltip="Delete",
                                            on_click=make_delete_handler(repo.name),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        padding=12,
                        border=ft.border.all(1, ThemeColors.BORDER),
                        border_radius=8,
                        bgcolor=ThemeColors.BG_SURFACE,
                    )

                    repo_list.controls.append(repo_card)

            safe_page_update(self.page)

        # Initial load
        refresh_list()

        # Calculate total cache size
        total_size = self._repo_manager.get_cache_size()
        total_size_str = self._repo_manager.format_size(total_size)

        def close_dialog(e=None):
            dialog.open = False
            safe_page_update(self.page)

        def clear_all(e):
            """Xóa tất cả cached repos."""
            assert self._repo_manager is not None
            count = self._repo_manager.clear_cache()
            status_text.value = f"Cleared {count} repositories"
            status_text.color = ThemeColors.SUCCESS
            refresh_list()
            safe_page_update(self.page)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Text(
                        "Cached Repositories",
                        weight=ft.FontWeight.BOLD,
                        color=ThemeColors.TEXT_PRIMARY,
                    ),
                    ft.Container(expand=True),
                    ft.Text(
                        f"Total: {total_size_str}",
                        size=13,
                        color=ThemeColors.TEXT_SECONDARY,
                    ),
                ],
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            f"Cached repositories: {len(cached_repos)}",
                            size=13,
                            color=ThemeColors.TEXT_SECONDARY,
                        ),
                        ft.Container(height=8),
                        ft.Container(
                            content=repo_list,
                            height=400,
                            border=ft.border.all(1, ThemeColors.BORDER),
                            border_radius=4,
                            padding=8,
                        ),
                        ft.Container(height=8),
                        status_text,
                    ],
                    tight=True,
                ),
                width=600,
            ),
            actions=[
                ft.TextButton(
                    "Close",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY),
                ),
                ft.OutlinedButton(
                    "Clear All",
                    icon=ft.Icons.DELETE_SWEEP,
                    on_click=clear_all,
                    style=ft.ButtonStyle(
                        color=ThemeColors.ERROR,
                        side=ft.BorderSide(1, ThemeColors.ERROR),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(self.page)

