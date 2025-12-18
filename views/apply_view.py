"""
Apply View - Tab de paste OPX va apply changes

Theme: Swiss Professional (Light)
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional

from core.opx_parser import parse_opx_response
from core.file_actions import apply_file_actions, ActionResult
from core.theme import ThemeColors


class ApplyView:
    """View cho Apply tab"""

    def __init__(self, page: ft.Page, get_workspace: Callable[[], Optional[Path]]):
        self.page = page
        self.get_workspace = get_workspace

        self.opx_input: Optional[ft.TextField] = None
        self.results_column: Optional[ft.Column] = None
        self.status_text: Optional[ft.Text] = None

    def build(self) -> ft.Container:
        """Build UI cho Apply view voi Swiss Professional styling"""

        # OPX Input
        self.opx_input = ft.TextField(
            label="Paste OPX Response",
            multiline=True,
            min_lines=10,
            max_lines=15,
            hint_text="Paste the LLM's OPX XML response here...",
            expand=True,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            label_style=ft.TextStyle(color=ThemeColors.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY, size=13),
        )

        # Status
        self.status_text = ft.Text("", size=12)

        # Results table
        self.results_column = ft.Column(
            controls=[
                ft.Text(
                    "Results will appear here after Preview or Apply",
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
                    # Input section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "OPX Response",
                                    weight=ft.FontWeight.W_600,
                                    size=14,
                                    color=ThemeColors.TEXT_PRIMARY,
                                ),
                                ft.Container(height=8),
                                self.opx_input,
                                ft.Container(height=12),
                                ft.Row(
                                    [
                                        ft.OutlinedButton(
                                            "Preview",
                                            icon=ft.Icons.VISIBILITY,
                                            on_click=lambda _: self._preview_changes(),
                                            style=ft.ButtonStyle(
                                                color=ThemeColors.TEXT_PRIMARY,
                                                side=ft.BorderSide(
                                                    1, ThemeColors.BORDER
                                                ),
                                            ),
                                        ),
                                        ft.ElevatedButton(
                                            "Apply Changes",
                                            icon=ft.Icons.PLAY_ARROW,
                                            on_click=lambda _: self._apply_changes(),
                                            style=ft.ButtonStyle(
                                                color="#FFFFFF",
                                                bgcolor=ThemeColors.SUCCESS,
                                            ),
                                        ),
                                        ft.Container(expand=True),
                                        self.status_text,
                                    ],
                                    spacing=12,
                                ),
                            ]
                        ),
                        padding=16,
                        bgcolor=ThemeColors.BG_SURFACE,
                        border=ft.border.all(1, ThemeColors.BORDER),
                        border_radius=8,
                    ),
                    ft.Container(height=16),
                    # Results section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "Results",
                                    weight=ft.FontWeight.W_600,
                                    size=14,
                                    color=ThemeColors.TEXT_PRIMARY,
                                ),
                                ft.Divider(height=1, color=ThemeColors.BORDER),
                                self.results_column,
                            ],
                            expand=True,
                        ),
                        padding=16,
                        expand=True,
                        bgcolor=ThemeColors.BG_SURFACE,
                        border=ft.border.all(1, ThemeColors.BORDER),
                        border_radius=8,
                    ),
                ],
                expand=True,
            ),
            expand=True,
            padding=16,
            bgcolor=ThemeColors.BG_PAGE,
        )

    def _preview_changes(self):
        """Preview changes without applying"""
        opx_text = self.opx_input.value
        if not opx_text:
            self._show_status("Please paste OPX response first", is_error=True)
            return

        result = parse_opx_response(opx_text)

        # Clear previous results
        self.results_column.controls.clear()

        # Show parse errors if any
        if result.errors:
            for error in result.errors:
                self.results_column.controls.append(
                    self._create_result_row("ERROR", "", error, success=False)
                )

        # Show parsed actions
        for action in result.file_actions:
            description = ""
            if action.changes:
                description = action.changes[0].description
            if action.new_path:
                description = f"-> {action.new_path}"

            self.results_column.controls.append(
                self._create_result_row(
                    action.action.upper(),
                    action.path,
                    description,
                    success=True,
                    is_preview=True,
                )
            )

        if result.file_actions:
            self._show_status(f"Preview: {len(result.file_actions)} action(s) parsed")
        else:
            self._show_status("No actions found in OPX", is_error=True)

        self.page.update()

    def _apply_changes(self):
        """Apply changes to files"""
        opx_text = self.opx_input.value
        if not opx_text:
            self._show_status("Please paste OPX response first", is_error=True)
            return

        workspace = self.get_workspace()
        workspace_roots = [workspace] if workspace else None

        # Parse OPX
        parse_result = parse_opx_response(opx_text)

        # Clear previous results
        self.results_column.controls.clear()

        # Show parse errors if any
        if parse_result.errors:
            for error in parse_result.errors:
                self.results_column.controls.append(
                    self._create_result_row("ERROR", "", error, success=False)
                )
            self._show_status("Parse errors occurred", is_error=True)
            self.page.update()
            return

        if not parse_result.file_actions:
            self._show_status("No actions found in OPX", is_error=True)
            self.page.update()
            return

        # Apply actions
        results = apply_file_actions(parse_result.file_actions, workspace_roots)

        # Display results
        success_count = 0
        for result in results:
            self.results_column.controls.append(
                self._create_result_row(
                    result.action.upper(),
                    result.path,
                    result.message,
                    success=result.success,
                )
            )
            if result.success:
                success_count += 1

        total = len(results)
        if success_count == total:
            self._show_status(f"Applied all {total} action(s) successfully!")
        else:
            self._show_status(
                f"Applied {success_count}/{total} action(s)", is_error=True
            )

        self.page.update()

    def _create_result_row(
        self,
        action: str,
        path: str,
        message: str,
        success: bool,
        is_preview: bool = False,
    ) -> ft.Container:
        """Tao mot row trong results voi Swiss Professional styling"""

        # Action badge color
        action_colors = {
            "CREATE": ThemeColors.SUCCESS,
            "MODIFY": ThemeColors.PRIMARY,
            "REWRITE": ThemeColors.WARNING,
            "DELETE": ThemeColors.ERROR,
            "RENAME": "#8B5CF6",  # Purple
            "ERROR": ThemeColors.ERROR,
        }

        badge_color = action_colors.get(action, ThemeColors.TEXT_SECONDARY)

        # Status icon
        if is_preview:
            status_icon = ft.Icon(
                ft.Icons.VISIBILITY, size=16, color=ThemeColors.TEXT_MUTED
            )
        elif success:
            status_icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE, size=16, color=ThemeColors.SUCCESS
            )
        else:
            status_icon = ft.Icon(ft.Icons.ERROR, size=16, color=ThemeColors.ERROR)

        # Background color for row
        row_bg = (
            ThemeColors.BG_ELEVATED if success else "#FEF2F2"
        )  # Light red for errors

        return ft.Container(
            content=ft.Row(
                [
                    status_icon,
                    ft.Container(
                        content=ft.Text(
                            action, size=11, weight=ft.FontWeight.W_600, color="#FFFFFF"
                        ),
                        bgcolor=badge_color,
                        padding=ft.padding.symmetric(horizontal=8, vertical=3),
                        border_radius=4,
                    ),
                    ft.Text(
                        path,
                        size=12,
                        weight=ft.FontWeight.W_500,
                        color=ThemeColors.TEXT_PRIMARY,
                        expand=True,
                    ),
                    ft.Text(
                        message[:60] + "..." if len(message) > 60 else message,
                        size=11,
                        color=ThemeColors.TEXT_SECONDARY,
                    ),
                ],
                spacing=12,
            ),
            padding=12,
            bgcolor=row_bg,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=6,
            margin=ft.margin.only(bottom=8),
        )

    def _show_status(self, message: str, is_error: bool = False):
        """Hien thi status message"""
        self.status_text.value = message
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self.page.update()
