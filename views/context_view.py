"""
Context View - Tab de chon files va copy context

Su dung FileTreeComponent tu components/file_tree.py
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional, Set
import pyperclip

from core.file_utils import scan_directory, TreeItem
from core.token_counter import count_tokens_for_file, count_tokens
from core.prompt_generator import (
    generate_file_map,
    generate_file_contents,
    generate_prompt,
)
from components.file_tree import FileTreeComponent, ThemeColors


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

        left_panel = ft.Container(
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
            min_lines=5,
            max_lines=10,
            hint_text="Enter your task instructions here...",
            expand=True,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            label_style=ft.TextStyle(color=ThemeColors.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY),
        )

        self.status_text = ft.Text("", color=ThemeColors.SUCCESS, size=12)

        right_panel = ft.Container(
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
                    ft.Container(height=16),
                    ft.Row(
                        [
                            ft.OutlinedButton(
                                "Copy Context",
                                icon=ft.Icons.CONTENT_COPY,
                                on_click=lambda _: self._copy_context(
                                    include_xml=False
                                ),
                                expand=True,
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
                ],
                expand=True,
            ),
            padding=16,
            expand=True,
            bgcolor=ThemeColors.BG_SURFACE,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=8,
        )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=left_panel, expand=2, margin=ft.margin.only(right=8)
                    ),
                    ft.Container(
                        content=right_panel, expand=1, margin=ft.margin.only(left=8)
                    ),
                ],
                expand=True,
            ),
            expand=True,
            padding=16,
            bgcolor=ThemeColors.BG_PAGE,
        )

    def on_workspace_changed(self, workspace_path: Path):
        """Khi user chon folder moi hoac settings thay doi"""
        self._load_tree(workspace_path)

    def _load_tree(self, workspace_path: Path):
        """Load file tree"""
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
            self.file_tree_component.set_tree(self.tree)
            self._update_token_count()

        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

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

    def _refresh_tree(self):
        """Refresh tree"""
        workspace = self.get_workspace()
        if workspace:
            self._load_tree(workspace)

    def _update_token_count(self):
        """
        Update token count display.
        Su dung visible paths khi dang search de hien thi chinh xac.
        """
        if not self.file_tree_component:
            return

        total_tokens = 0
        # Su dung visible paths de hien thi chinh xac khi dang search
        selected_paths = self.file_tree_component.get_visible_selected_paths()

        for path_str in selected_paths:
            path = Path(path_str)
            if path.is_file():
                total_tokens += count_tokens_for_file(path)

        # Hien thi indicator khi dang filter
        if self.file_tree_component.is_searching():
            self.token_count_text.value = f"{total_tokens:,} tokens (filtered)"
        else:
            self.token_count_text.value = f"{total_tokens:,} tokens"
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
            self._show_status("No files selected", is_error=True)
            return

        try:
            file_map = generate_file_map(self.tree, selected_paths)
            file_contents = generate_file_contents(selected_paths)
            instructions = self.instructions_field.value or ""

            prompt = generate_prompt(file_map, file_contents, instructions, include_xml)

            pyperclip.copy(prompt)

            token_count = count_tokens(prompt)
            suffix = " + OPX" if include_xml else ""
            self._show_status(f"Copied! ({token_count:,} tokens){suffix}")

        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    def _show_status(self, message: str, is_error: bool = False):
        """Show status message"""
        self.status_text.value = message
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self.page.update()
