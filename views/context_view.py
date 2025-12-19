"""
Context View - Tab de chon files va copy context

Su dung FileTreeComponent tu components/file_tree.py
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional, Set

from core.file_utils import scan_directory, TreeItem
from services.clipboard_utils import copy_to_clipboard
from core.token_counter import count_tokens_for_file, count_tokens
from core.prompt_generator import (
    generate_file_map,
    generate_file_contents,
    generate_prompt,
)
from core.tree_map_generator import generate_tree_map_only
from components.file_tree import FileTreeComponent
from components.token_stats import TokenStatsPanel
from core.theme import ThemeColors
from threading import Timer
from typing import Set


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
        self._token_debounce_ms: float = 300  # 300ms debounce
        
        # Status auto-clear timer
        self._status_clear_timer: Optional[Timer] = None

    def cleanup(self):
        """Cleanup resources when view is destroyed"""
        if self._token_update_timer is not None:
            self._token_update_timer.cancel()
            self._token_update_timer = None
        if self._status_clear_timer is not None:
            self._status_clear_timer.cancel()
            self._status_clear_timer = None
        if self.file_tree_component:
            self.file_tree_component.cleanup()

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
                    # Header row
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
                            ft.IconButton(
                                icon=ft.Icons.SELECT_ALL,
                                icon_size=18,
                                icon_color=ThemeColors.TEXT_SECONDARY,
                                tooltip="Select All",
                                on_click=lambda _: self._select_all(),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DESELECT,
                                icon_size=18,
                                icon_color=ThemeColors.TEXT_SECONDARY,
                                tooltip="Deselect All",
                                on_click=lambda _: self._deselect_all(),
                            ),
                            ft.Container(width=8),  # Separator
                            ft.IconButton(
                                icon=ft.Icons.UNFOLD_MORE,
                                icon_size=18,
                                icon_color=ThemeColors.TEXT_SECONDARY,
                                tooltip="Expand All",
                                on_click=lambda _: self._expand_all(),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.UNFOLD_LESS,
                                icon_size=18,
                                icon_color=ThemeColors.TEXT_SECONDARY,
                                tooltip="Collapse All",
                                on_click=lambda _: self._collapse_all(),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                icon_size=18,
                                icon_color=ThemeColors.TEXT_SECONDARY,
                                tooltip="Refresh",
                                on_click=lambda _: self._refresh_tree(),
                            ),
                        ]
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
                                "Copy Context",
                                icon=ft.Icons.CONTENT_COPY,
                                on_click=lambda _: self._copy_context(
                                    include_xml=False
                                ),
                                expand=True,
                                tooltip="Ctrl+Shift+C",
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
                                tooltip="Ctrl+Shift+O",
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
            expand=True,
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
                    ft.Container(content=self.right_panel, expand=1),
                ],
                expand=True,
                spacing=16,
            )

        if self.layout_container.page:
            self.layout_container.update()

    def on_workspace_changed(self, workspace_path: Path):
        """Khi user chon folder moi hoac settings thay doi"""
        # Cleanup old resources before loading new tree
        if self.file_tree_component:
            self.file_tree_component.cleanup()
        self._load_tree(workspace_path)

    def _load_tree(self, workspace_path: Path, preserve_selection: bool = False):
        """
        Load file tree.

        Args:
            workspace_path: Path to workspace folder
            preserve_selection: Neu True, giu lai selection hien tai (cho Refresh)
        """
        # Save current selection before loading
        old_selection: Set[str] = set()
        if preserve_selection and self.file_tree_component:
            old_selection = self.file_tree_component.get_selected_paths()

        # Show loading state
        self._show_status("Loading...", is_error=False)
        if self.token_stats_panel:
            self.token_stats_panel.set_loading(True)
        self.page.update()

        try:
            from views.settings_view import get_excluded_patterns, get_use_gitignore

            excluded_patterns = get_excluded_patterns()
            use_gitignore = get_use_gitignore()

            self.tree = scan_directory(
                workspace_path,
                excluded_patterns=excluded_patterns,
                use_gitignore=use_gitignore,
            )

            # Set tree to component
            assert self.file_tree_component is not None
            self.file_tree_component.set_tree(
                self.tree, preserve_selection=preserve_selection
            )
            self._update_token_count()

            # Clear loading status
            self._show_status("")

        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)
            # Restore old selection on error if possible
            if preserve_selection and old_selection and self.file_tree_component:
                self.file_tree_component.selected_paths = old_selection
        finally:
            if self.token_stats_panel:
                self.token_stats_panel.set_loading(False)
            self.page.update()

    def _on_selection_changed(self, selected_paths: Set[str]):
        """Callback khi selection thay doi"""
        self._update_token_count()

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

    def _on_instructions_changed(self):
        """Handle instructions field change with debounce"""
        # Cancel previous timer if exists
        if self._token_update_timer is not None:
            self._token_update_timer.cancel()
        
        # Schedule token update with debounce
        self._token_update_timer = Timer(
            self._token_debounce_ms / 1000.0,
            self._do_update_token_count
        )
        self._token_update_timer.start()
    
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
        """
        if not self.file_tree_component:
            return

        file_tokens = 0
        file_count = 0

        # Su dung visible paths de hien thi chinh xac khi dang search
        selected_paths = self.file_tree_component.get_visible_selected_paths()

        for path_str in selected_paths:
            path = Path(path_str)
            if path.is_file():
                file_tokens += count_tokens_for_file(path)
                file_count += 1

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

        self.page.update()

    def _copy_context(self, include_xml: bool):
        """
        Copy context to clipboard.
        Khi dang search, chi copy cac files dang hien thi (visible).
        """
        if not self.tree or not self.file_tree_component:
            self._show_status("No files selected", is_error=True)
            return

        # Su dung visible paths de chi copy files dang hien thi
        selected_paths = self.file_tree_component.get_visible_selected_paths()
        if not selected_paths:
            # Provide helpful message based on context
            if self.file_tree_component.is_searching():
                self._show_status("No matching files selected. Clear search or select files.", is_error=True)
            else:
                self._show_status("Select files from the tree first", is_error=True)
            return

        try:
            # Show copying state for large selections
            file_count = sum(1 for p in selected_paths if Path(p).is_file())
            if file_count > 10:
                self._show_status(f"Copying {file_count} files...", is_error=False, auto_clear=False)
                self.page.update()
            
            file_map = generate_file_map(self.tree, selected_paths)
            file_contents = generate_file_contents(selected_paths)
            assert self.instructions_field is not None
            instructions = self.instructions_field.value or ""

            prompt = generate_prompt(file_map, file_contents, instructions, include_xml)

            success, message = copy_to_clipboard(prompt)

            if success:
                token_count = count_tokens(prompt)
                suffix = " + OPX" if include_xml else ""
                self._show_status(f"Copied! ({token_count:,} tokens){suffix}")
            else:
                self._show_status(message, is_error=True)

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

    def _show_status(self, message: str, is_error: bool = False, auto_clear: bool = True):
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
        self.page.update()
        
        # Auto-clear success messages after 3 seconds
        if auto_clear and not is_error and message:
            def clear_status():
                try:
                    if self.status_text and self.status_text.value == message:
                        self.status_text.value = ""
                        self.page.update()
                except Exception:
                    pass
            
            self._status_clear_timer = Timer(3.0, clear_status)
            self._status_clear_timer.start()
