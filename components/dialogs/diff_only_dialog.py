"""
Diff Only Dialog - Options for copying git diff only.
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional

from components.dialogs.base_dialog import BaseDialog
from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update
from core.utils.git_utils import get_diff_only, DiffOnlyResult
from core.token_counter import count_tokens
from services.clipboard_utils import copy_to_clipboard


class DiffOnlyDialog(BaseDialog):
    """Dialog for Copy Diff Only options."""
    
    def __init__(
        self,
        page: ft.Page,
        workspace: Path,
        build_prompt_callback: Callable[[DiffOnlyResult, str, bool, bool], str],
        instructions: str = "",
        on_success: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(page)
        self.workspace = workspace
        self.build_prompt_callback = build_prompt_callback
        self.instructions = instructions
        self.on_success = on_success
        self._build()
    
    def _build(self):
        """Build the dialog UI."""
        self.num_commits = ft.TextField(
            value="0",
            label="Recent commits to include",
            hint_text="0 = uncommitted only",
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
        )
        
        self.include_staged = ft.Checkbox(
            label="Include staged changes",
            value=True,
            active_color=ThemeColors.PRIMARY,
        )
        
        self.include_unstaged = ft.Checkbox(
            label="Include unstaged changes",
            value=True,
            active_color=ThemeColors.PRIMARY,
        )
        
        self.include_file_content = ft.Checkbox(
            label="Include changed file content",
            value=False,
            active_color=ThemeColors.WARNING,
            tooltip="Include full content of modified files for better AI context",
        )
        
        self.include_tree = ft.Checkbox(
            label="Include project tree structure",
            value=False,
            active_color=ThemeColors.PRIMARY,
            tooltip="Include file tree to help AI understand project structure",
        )
        
        self.file_pattern = ft.TextField(
            value="",
            label="Filter files (optional)",
            hint_text="e.g., *.py, src/*.ts",
            width=200,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
        )
        
        self.status_text = self.create_status_text()
        
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Copy Diff Only", weight=ft.FontWeight.BOLD, color=ThemeColors.TEXT_PRIMARY),
            content=ft.Container(
                content=ft.Column([
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
                    ft.Row([self.num_commits, self.file_pattern], spacing=16),
                    ft.Container(height=8),
                    self.include_staged,
                    self.include_unstaged,
                    ft.Divider(height=16, color=ThemeColors.BORDER),
                    ft.Text(
                        "Enhanced context (larger output):",
                        size=12,
                        weight=ft.FontWeight.W_500,
                        color=ThemeColors.TEXT_SECONDARY,
                    ),
                    self.include_file_content,
                    self.include_tree,
                    ft.Container(height=12),
                    self.status_text,
                ], tight=True),
                width=450,
            ),
            actions=[
                self.secondary_button("Cancel", self.close),
                ft.ElevatedButton(
                    "Copy Diff",
                    icon=ft.Icons.CONTENT_COPY,
                    on_click=self._do_copy,
                    style=ft.ButtonStyle(color="#FFFFFF", bgcolor="#8B5CF6"),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    
    def _do_copy(self, e):
        """Execute the diff copy."""
        try:
            commits = int(self.num_commits.value or "0")
            if commits < 0:
                commits = 0
        except ValueError:
            commits = 0
        
        self.status_text.value = "Getting diff..."
        safe_page_update(self.page)
        
        result = get_diff_only(
            self.workspace,
            num_commits=commits,
            include_staged=self.include_staged.value or False,
            include_unstaged=self.include_unstaged.value or False,
        )
        
        if result.error:
            self.status_text.value = f"Error: {result.error}"
            self.status_text.color = ThemeColors.ERROR
            safe_page_update(self.page)
            return
        
        if not result.diff_content.strip():
            self.status_text.value = "No changes found"
            self.status_text.color = ThemeColors.WARNING
            safe_page_update(self.page)
            return
        
        prompt = self.build_prompt_callback(
            result,
            self.instructions,
            self.include_file_content.value or False,
            self.include_tree.value or False,
        )
        
        success, message = copy_to_clipboard(prompt)
        
        if success:
            self.close()
            token_count = count_tokens(prompt)
            if self.on_success:
                self.on_success(
                    f"Diff copied! ({token_count:,} tokens, "
                    f"+{result.insertions}/-{result.deletions} lines, "
                    f"{result.files_changed} files)"
                )
        else:
            self.status_text.value = f"Copy failed: {message}"
            self.status_text.color = ThemeColors.ERROR
            safe_page_update(self.page)