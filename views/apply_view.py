"""
Apply View - Tab de paste OPX va apply changes

Theme: Dark Mode OLED với High Contrast
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional, List

from core.opx_parser import parse_opx_response
from services.clipboard_utils import copy_to_clipboard
from core.file_actions import apply_file_actions, ActionResult
from services.history_service import add_history_entry
from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update
from services.preview_analyzer import (
    analyze_file_actions,
    format_change_summary,
    get_change_color,
    PreviewRow,
    PreviewData,
    generate_preview_diff_lines,
)
from components.diff_viewer import DiffViewer
from services.error_context import (
    build_error_context_for_ai,
    build_general_error_context,
    ApplyRowResult,
)
from services.clipboard_utils import get_clipboard_text


# High Contrast Colors for Dark Mode
class ApplyViewColors:
    """Enhanced colors for better contrast in Apply View"""
    
    # Backgrounds
    BG_CARD = "#1E293B"  # Slate 800
    BG_CARD_HOVER = "#334155"  # Slate 700
    BG_EXPANDED = "#0F172A"  # Slate 900 - for expanded content
    
    # Action badge colors - vivid for dark mode
    ACTION_CREATE = "#22C55E"  # Green 500
    ACTION_CREATE_BG = "#052E16"  # Green 950
    ACTION_MODIFY = "#3B82F6"  # Blue 500
    ACTION_MODIFY_BG = "#172554"  # Blue 950
    ACTION_REWRITE = "#F59E0B"  # Amber 500
    ACTION_REWRITE_BG = "#422006"  # Amber 950
    ACTION_DELETE = "#EF4444"  # Red 500
    ACTION_DELETE_BG = "#450A0A"  # Red 950
    ACTION_RENAME = "#A855F7"  # Purple 500
    ACTION_RENAME_BG = "#3B0764"  # Purple 950
    
    # Status colors
    SUCCESS_BG = "#052E16"  # Green 950
    SUCCESS_BORDER = "#166534"  # Green 800
    SUCCESS_TEXT = "#4ADE80"  # Green 400
    
    ERROR_BG = "#450A0A"  # Red 950
    ERROR_BORDER = "#991B1B"  # Red 800
    ERROR_TEXT = "#FCA5A5"  # Red 300
    
    # Diff stats
    DIFF_ADD = "#4ADE80"  # Green 400
    DIFF_REMOVE = "#F87171"  # Red 400
    DIFF_NEUTRAL = "#60A5FA"  # Blue 400
    
    # Text
    TEXT_PRIMARY = "#F8FAFC"  # Slate 50
    TEXT_SECONDARY = "#CBD5E1"  # Slate 300
    TEXT_MUTED = "#94A3B8"  # Slate 400
    TEXT_DESCRIPTION = "#E2E8F0"  # Slate 200


class ApplyView:
    """View cho Apply tab với improved UI"""

    def __init__(self, page: ft.Page, get_workspace: Callable[[], Optional[Path]]):
        self.page = page
        self.get_workspace = get_workspace

        self.opx_input: Optional[ft.TextField] = None
        self.results_column: Optional[ft.Column] = None
        self.status_text: Optional[ft.Text] = None
        self.workspace_indicator: Optional[ft.Text] = None

        # State for error copying
        self.last_preview_data: Optional[PreviewData] = None
        self.last_apply_results: List[ApplyRowResult] = []
        self.last_opx_text: str = ""
        
        # State for diff expansion
        self.expanded_diffs: set = set()

    def build(self) -> ft.Container:
        """Build UI cho Apply view với improved styling"""

        # Workspace indicator with better visibility
        current_workspace = self.get_workspace()
        workspace_name = (
            current_workspace.name if current_workspace else "No workspace selected"
        )

        self.workspace_indicator = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.FOLDER_OPEN if current_workspace else ft.Icons.FOLDER_OFF,
                        size=16,
                        color=ApplyViewColors.ACTION_MODIFY if current_workspace else ApplyViewColors.TEXT_MUTED,
                    ),
                    ft.Text(
                        workspace_name,
                        size=12,
                        color=ApplyViewColors.TEXT_SECONDARY if current_workspace else ApplyViewColors.TEXT_MUTED,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            bgcolor=ApplyViewColors.BG_CARD,
            border_radius=6,
            tooltip=str(current_workspace) if current_workspace else "Please select a workspace",
        )

        # OPX Input with better contrast
        self.opx_input = ft.TextField(
            multiline=True,
            expand=True,
            hint_text="Paste the LLM's OPX XML response here...\n\nExample:\n<edit file=\"path/to/file\" op=\"patch\">\n  ...\n</edit>",
            border_color=ThemeColors.BORDER,
            focused_border_color=ApplyViewColors.ACTION_MODIFY,
            text_style=ft.TextStyle(
                color=ApplyViewColors.TEXT_PRIMARY, 
                size=13,
                font_family="monospace",
            ),
            hint_style=ft.TextStyle(color=ApplyViewColors.TEXT_MUTED, size=12),
            bgcolor=ApplyViewColors.BG_EXPANDED,
            cursor_color=ApplyViewColors.ACTION_MODIFY,
            content_padding=15,
        )

        # Status with better visibility
        self.status_text = ft.Text("", size=12, weight=ft.FontWeight.W_500)

        # Results container
        self.results_column = ft.Column(
            controls=[self._create_empty_state()],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=12,
        )

        return ft.Container(
            content=ft.Row(
                [
                    # Left Column: Input section
                    ft.Container(
                        content=ft.Column(
                            [
                                # Header row
                                ft.Row(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.CODE, size=18, color=ApplyViewColors.ACTION_MODIFY),
                                                ft.Text(
                                                    "OPX Input",
                                                    weight=ft.FontWeight.W_600,
                                                    size=15,
                                                    color=ApplyViewColors.TEXT_PRIMARY,
                                                ),
                                            ],
                                            spacing=8,
                                        ),
                                        self.workspace_indicator,
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Container(height=10),
                                ft.Text(
                                    "Paste OPX code from AI chat below:",
                                    size=12,
                                    color=ApplyViewColors.TEXT_MUTED,
                                ),
                                ft.Container(height=5),
                                self.opx_input,
                                ft.Container(height=12),
                                # Action buttons
                                ft.Row(
                                    [
                                        ft.OutlinedButton(
                                            "Paste",
                                            icon=ft.Icons.CONTENT_PASTE,
                                            on_click=lambda _: self._paste_from_clipboard(),
                                            tooltip="Paste from clipboard",
                                            style=ft.ButtonStyle(
                                                color=ApplyViewColors.TEXT_SECONDARY,
                                                side=ft.BorderSide(1, ThemeColors.BORDER),
                                            ),
                                        ),
                                        ft.OutlinedButton(
                                            "Preview",
                                            icon=ft.Icons.VISIBILITY,
                                            on_click=lambda _: self._preview_changes(),
                                            tooltip="Preview changes",
                                            style=ft.ButtonStyle(
                                                color=ApplyViewColors.ACTION_MODIFY,
                                                side=ft.BorderSide(1, ApplyViewColors.ACTION_MODIFY),
                                            ),
                                        ),
                                        ft.ElevatedButton(
                                            "Apply",
                                            icon=ft.Icons.PLAY_ARROW,
                                            on_click=lambda _: self._apply_changes(),
                                            tooltip="Apply all changes",
                                            style=ft.ButtonStyle(
                                                color="#FFFFFF",
                                                bgcolor=ApplyViewColors.ACTION_CREATE,
                                            ),
                                        ),
                                    ],
                                    spacing=8,
                                    wrap=True,
                                ),
                                ft.Container(height=5),
                                self.status_text,
                            ],
                            expand=True,
                        ),
                        expand=2,
                        padding=20,
                        bgcolor=ApplyViewColors.BG_CARD,
                        border=ft.border.all(1, ThemeColors.BORDER),
                        border_radius=10,
                    ),
                    
                    # Right Column: Results section
                    ft.Container(
                        content=ft.Column(
                            [
                                # Results header
                                ft.Row(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.LIST_ALT, size=18, color=ApplyViewColors.TEXT_SECONDARY),
                                                ft.Text(
                                                    "Results & Preview",
                                                    weight=ft.FontWeight.W_600,
                                                    size=15,
                                                    color=ApplyViewColors.TEXT_PRIMARY,
                                                ),
                                            ],
                                            spacing=8,
                                        ),
                                        ft.Container(expand=True),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            icon_size=16,
                                            icon_color=ApplyViewColors.TEXT_MUTED,
                                            on_click=lambda _: self._clear_results(),
                                            tooltip="Clear results",
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.HISTORY,
                                            icon_size=16,
                                            icon_color=ApplyViewColors.TEXT_MUTED,
                                            on_click=lambda _: self._show_backups_dialog(),
                                            tooltip="View backups",
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.CONTENT_COPY,
                                            icon_size=16,
                                            icon_color=ApplyViewColors.ACTION_MODIFY,
                                            on_click=lambda _: self._copy_all_results(),
                                            tooltip="Copy results for AI",
                                        ),
                                    ],
                                    spacing=4,
                                ),
                                ft.Container(height=10),
                                ft.Divider(height=1, color=ThemeColors.BORDER),
                                ft.Container(height=10),
                                self.results_column,
                            ],
                            expand=True,
                        ),
                        expand=3,
                        padding=20,
                        bgcolor=ApplyViewColors.BG_CARD,
                        border=ft.border.all(1, ThemeColors.BORDER),
                        border_radius=10,
                    ),
                ],
                expand=True,
                spacing=16,
            ),
            expand=True,
            padding=16,
            bgcolor=ThemeColors.BG_PAGE,
        )

    def _create_empty_state(self) -> ft.Container:
        """Create empty state placeholder"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(
                        ft.Icons.DESCRIPTION_OUTLINED,
                        size=48,
                        color=ApplyViewColors.TEXT_MUTED,
                    ),
                    ft.Text(
                        "No results yet",
                        size=14,
                        color=ApplyViewColors.TEXT_MUTED,
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Text(
                        "Paste OPX and click Preview or Apply",
                        size=12,
                        color=ApplyViewColors.TEXT_MUTED,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=40,
            alignment=ft.Alignment(0, 0),
        )

    def _preview_changes(self):
        """Preview changes without applying"""
        assert self.opx_input is not None
        assert self.results_column is not None

        self._update_workspace_indicator()

        opx_text = self.opx_input.value
        if not opx_text:
            self._show_status("Please paste OPX response first", is_error=True)
            return

        opx_text_lower = opx_text.lower()
        if "<edit" not in opx_text_lower:
            self._show_status(
                "No <edit> tags found. Paste valid OPX response.", is_error=True
            )
            return

        # Parse OPX
        result = parse_opx_response(opx_text)

        # Clear previous results
        self.results_column.controls.clear()

        # Show parse errors
        if result.errors:
            for error in result.errors:
                self.results_column.controls.append(
                    self._create_error_card("Parse Error", error)
                )

        # Analyze file actions
        workspace = self.get_workspace()
        preview_data = analyze_file_actions(result.file_actions, workspace)

        # Show analysis errors
        for error in preview_data.errors:
            self.results_column.controls.append(
                self._create_error_card("Analysis Error", error)
            )

        # Show preview cards
        for idx, row in enumerate(preview_data.rows):
            file_action = result.file_actions[idx] if idx < len(result.file_actions) else None
            self.results_column.controls.append(
                self._create_preview_card(row, idx, file_action)
            )

        if preview_data.rows:
            total_added = sum(r.changes.added for r in preview_data.rows)
            total_removed = sum(r.changes.removed for r in preview_data.rows)
            self._show_status(
                f"Preview: {len(preview_data.rows)} action(s)  •  +{total_added} / -{total_removed} lines"
            )
        else:
            self._show_status("No actions found in OPX", is_error=True)

        safe_page_update(self.page)

    def _apply_changes(self):
        """Apply changes to files"""
        assert self.opx_input is not None
        assert self.results_column is not None

        opx_text = self.opx_input.value
        if not opx_text:
            self._show_status("Please paste OPX response first", is_error=True)
            return

        parse_result = parse_opx_response(opx_text)
        if parse_result.file_actions:
            action_count = len(parse_result.file_actions)
            unique_files = set(a.path for a in parse_result.file_actions)
            file_count = len(unique_files)
            self._show_confirmation_dialog(
                f"Apply {action_count} change(s) to {file_count} file(s)?",
                "This will modify files in your workspace. Backups will be created automatically.",
                lambda: self._do_apply_changes(opx_text),
            )
        else:
            self._do_apply_changes(opx_text)

    def _show_confirmation_dialog(self, title: str, message: str, on_confirm: Callable):
        """Show confirmation dialog"""

        def close_dialog(e):
            dialog.open = False
            safe_page_update(self.page)

        def confirm_action(e):
            dialog.open = False
            safe_page_update(self.page)
            on_confirm()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.W_600, color=ApplyViewColors.TEXT_PRIMARY),
            content=ft.Text(message, color=ApplyViewColors.TEXT_SECONDARY),
            bgcolor=ApplyViewColors.BG_CARD,
            actions=[
                ft.TextButton(
                    "Cancel", 
                    on_click=close_dialog,
                    style=ft.ButtonStyle(color=ApplyViewColors.TEXT_MUTED),
                ),
                ft.ElevatedButton(
                    "Apply",
                    on_click=confirm_action,
                    style=ft.ButtonStyle(
                        color="#FFFFFF",
                        bgcolor=ApplyViewColors.ACTION_CREATE,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        assert self.page.overlay is not None
        self.page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(self.page)

    def _do_apply_changes(self, opx_text: str):
        """Execute apply changes"""
        self._update_workspace_indicator()

        workspace = self.get_workspace()
        workspace_roots = [workspace] if workspace else None

        parse_result = parse_opx_response(opx_text)

        assert self.results_column is not None

        self.results_column.controls.clear()
        self.last_apply_results = []
        self.last_opx_text = opx_text

        if parse_result.errors:
            for error in parse_result.errors:
                self.results_column.controls.append(
                    self._create_error_card("Parse Error", error)
                )
            self._show_status("Parse errors occurred", is_error=True)
            safe_page_update(self.page)
            return

        if not parse_result.file_actions:
            self._show_status("No actions found in OPX", is_error=True)
            safe_page_update(self.page)
            return

        self.last_preview_data = analyze_file_actions(
            parse_result.file_actions, workspace
        )

        results = apply_file_actions(parse_result.file_actions, workspace_roots)

        # Convert to ApplyRowResult
        self.last_apply_results = []
        for i, result in enumerate(results):
            self.last_apply_results.append(
                ApplyRowResult(
                    row_index=i,
                    path=result.path,
                    action=result.action,
                    success=result.success,
                    message=result.message,
                    is_cascade_failure=self._check_cascade_failure(result, results[:i]),
                )
            )

        # Display results
        success_count = 0
        for i, result in enumerate(results):
            preview_row = self.last_preview_data.rows[i] if i < len(self.last_preview_data.rows) else None
            self.results_column.controls.append(
                self._create_result_card(result, preview_row)
            )
            if result.success:
                success_count += 1

        total = len(results)

        if success_count == total:
            self._show_status(f"✓ Applied all {total} action(s) successfully!")
        else:
            self._show_status(
                f"Applied {success_count}/{total} action(s)", is_error=True
            )

        # Save to history
        action_results_for_history = [
            {
                "action": r.action,
                "path": r.path,
                "success": r.success,
                "message": r.message,
            }
            for r in results
        ]
        add_history_entry(
            workspace_path=str(workspace) if workspace else "",
            opx_content=opx_text,
            action_results=action_results_for_history,
        )

        safe_page_update(self.page)

    def _check_cascade_failure(self, current_result: ActionResult, previous_results: list) -> bool:
        """Check if failure might be caused by previous operations"""
        if current_result.success:
            return False
        for prev in previous_results:
            if prev.path == current_result.path and prev.success:
                return True
        return False

    def _get_action_colors(self, action: str) -> tuple:
        """Get badge color and background for action type"""
        action_lower = action.lower()
        colors = {
            "create": (ApplyViewColors.ACTION_CREATE, ApplyViewColors.ACTION_CREATE_BG),
            "modify": (ApplyViewColors.ACTION_MODIFY, ApplyViewColors.ACTION_MODIFY_BG),
            "rewrite": (ApplyViewColors.ACTION_REWRITE, ApplyViewColors.ACTION_REWRITE_BG),
            "delete": (ApplyViewColors.ACTION_DELETE, ApplyViewColors.ACTION_DELETE_BG),
            "rename": (ApplyViewColors.ACTION_RENAME, ApplyViewColors.ACTION_RENAME_BG),
        }
        return colors.get(action_lower, (ApplyViewColors.TEXT_MUTED, ApplyViewColors.BG_CARD))

    def _create_error_card(self, error_type: str, message: str) -> ft.Container:
        """Create error card with high visibility"""
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=20, color=ApplyViewColors.ERROR_TEXT),
                    ft.Column(
                        [
                            ft.Text(
                                error_type,
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=ApplyViewColors.ERROR_TEXT,
                            ),
                            ft.Text(
                                message,
                                size=12,
                                color=ApplyViewColors.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=12,
            ),
            padding=14,
            bgcolor=ApplyViewColors.ERROR_BG,
            border=ft.border.all(1, ApplyViewColors.ERROR_BORDER),
            border_radius=8,
        )

    def _create_preview_card(
        self, row: PreviewRow, row_idx: int, file_action=None
    ) -> ft.Container:
        """Create expandable preview card with full description and diff"""
        
        badge_color, badge_bg = self._get_action_colors(row.action)
        is_expanded = row_idx in self.expanded_diffs

        # Diff stats color
        if row.changes.added > row.changes.removed:
            diff_color = ApplyViewColors.DIFF_ADD
        elif row.changes.removed > row.changes.added:
            diff_color = ApplyViewColors.DIFF_REMOVE
        else:
            diff_color = ApplyViewColors.DIFF_NEUTRAL

        # Generate diff lines
        workspace = self.get_workspace()
        diff_lines = []
        if file_action and row.action != "rename":
            try:
                diff_lines = generate_preview_diff_lines(file_action, workspace)
            except Exception:
                pass

        # Header content
        header_content = ft.Row(
            [
                # Action badge
                ft.Container(
                    content=ft.Text(
                        row.action.upper(),
                        size=11,
                        weight=ft.FontWeight.W_700,
                        color=badge_color,
                    ),
                    bgcolor=badge_bg,
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    border_radius=6,
                ),
                # File path
                ft.Text(
                    row.path,
                    size=13,
                    weight=ft.FontWeight.W_500,
                    color=ApplyViewColors.TEXT_PRIMARY,
                    expand=True,
                ),
                # Diff stats
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(f"+{row.changes.added}", size=12, color=ApplyViewColors.DIFF_ADD, weight=ft.FontWeight.W_600),
                            ft.Text("/", size=12, color=ApplyViewColors.TEXT_MUTED),
                            ft.Text(f"-{row.changes.removed}", size=12, color=ApplyViewColors.DIFF_REMOVE, weight=ft.FontWeight.W_600),
                        ],
                        spacing=4,
                    ),
                    bgcolor=ApplyViewColors.BG_EXPANDED,
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    border_radius=6,
                ),
                # Expand button
                ft.IconButton(
                    icon=ft.Icons.EXPAND_MORE if not is_expanded else ft.Icons.EXPAND_LESS,
                    icon_size=20,
                    icon_color=ApplyViewColors.TEXT_SECONDARY,
                    tooltip="Show diff preview" if not is_expanded else "Hide diff preview",
                    on_click=lambda e, idx=row_idx: self._toggle_diff_expand(idx),
                ) if diff_lines else ft.Container(width=40),
            ],
            spacing=12,
            alignment=ft.MainAxisAlignment.START,
        )

        # Description row (always visible, full width)
        description_row = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ApplyViewColors.TEXT_MUTED),
                    ft.Text(
                        row.description,
                        size=12,
                        color=ApplyViewColors.TEXT_DESCRIPTION,
                        expand=True,
                    ),
                ],
                spacing=8,
            ),
            margin=ft.margin.only(top=10),
        )

        # Build card content
        card_content: list[ft.Control] = [header_content, description_row]

        # Expanded diff viewer
        if is_expanded and diff_lines:
            diff_viewer = DiffViewer(
                diff_lines=diff_lines,
                max_height=300,
                show_line_numbers=True,
            )
            card_content.append(
                ft.Container(
                    content=diff_viewer,
                    margin=ft.margin.only(top=12),
                    border=ft.border.all(1, ThemeColors.BORDER),
                    border_radius=6,
                )
            )

        # Error state
        if row.has_error:
            card_content.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.WARNING_AMBER, size=14, color=ApplyViewColors.ACTION_REWRITE),
                            ft.Text(
                                row.error_message or "Unknown error",
                                size=12,
                                color=ApplyViewColors.ACTION_REWRITE,
                            ),
                        ],
                        spacing=8,
                    ),
                    margin=ft.margin.only(top=10),
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=card_content,
                spacing=0,
            ),
            padding=16,
            bgcolor=ApplyViewColors.BG_CARD if not row.has_error else ApplyViewColors.ERROR_BG,
            border=ft.border.all(1, ThemeColors.BORDER if not row.has_error else ApplyViewColors.ERROR_BORDER),
            border_radius=10,
        )

    def _create_result_card(self, result: ActionResult, preview_row: Optional[PreviewRow] = None) -> ft.Container:
        """Create result card showing success/failure with details"""
        
        badge_color, badge_bg = self._get_action_colors(result.action)
        
        if result.success:
            status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=22, color=ApplyViewColors.SUCCESS_TEXT)
            card_bg = ApplyViewColors.SUCCESS_BG
            card_border = ApplyViewColors.SUCCESS_BORDER
            message_color = ApplyViewColors.SUCCESS_TEXT
        else:
            status_icon = ft.Icon(ft.Icons.CANCEL, size=22, color=ApplyViewColors.ERROR_TEXT)
            card_bg = ApplyViewColors.ERROR_BG
            card_border = ApplyViewColors.ERROR_BORDER
            message_color = ApplyViewColors.ERROR_TEXT

        # Main content
        card_content: list[ft.Control] = [
            ft.Row(
                [
                    status_icon,
                    # Action badge
                    ft.Container(
                        content=ft.Text(
                            result.action.upper(),
                            size=11,
                            weight=ft.FontWeight.W_700,
                            color=badge_color,
                        ),
                        bgcolor=badge_bg,
                        padding=ft.padding.symmetric(horizontal=10, vertical=5),
                        border_radius=6,
                    ),
                    # File path
                    ft.Text(
                        result.path,
                        size=13,
                        weight=ft.FontWeight.W_500,
                        color=ApplyViewColors.TEXT_PRIMARY,
                        expand=True,
                    ),
                    # Diff stats if available
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Text(f"+{preview_row.changes.added}", size=12, color=ApplyViewColors.DIFF_ADD, weight=ft.FontWeight.W_600),
                                ft.Text("/", size=12, color=ApplyViewColors.TEXT_MUTED),
                                ft.Text(f"-{preview_row.changes.removed}", size=12, color=ApplyViewColors.DIFF_REMOVE, weight=ft.FontWeight.W_600),
                            ],
                            spacing=4,
                        ),
                        bgcolor=ApplyViewColors.BG_EXPANDED,
                        padding=ft.padding.symmetric(horizontal=10, vertical=5),
                        border_radius=6,
                    ) if preview_row else ft.Container(),
                ],
                spacing=12,
            ),
        ]

        # Description from preview
        if preview_row and preview_row.description:
            card_content.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ApplyViewColors.TEXT_MUTED),
                            ft.Text(
                                preview_row.description,
                                size=12,
                                color=ApplyViewColors.TEXT_DESCRIPTION,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    margin=ft.margin.only(top=10),
                )
            )

        # Result message
        card_content.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.ARROW_RIGHT if result.success else ft.Icons.ERROR_OUTLINE, 
                            size=14, 
                            color=message_color
                        ),
                        ft.Text(
                            result.message,
                            size=12,
                            color=message_color,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
                margin=ft.margin.only(top=8),
            )
        )

        return ft.Container(
            content=ft.Column(
                controls=card_content,
                spacing=0,
            ),
            padding=16,
            bgcolor=card_bg,
            border=ft.border.all(1, card_border),
            border_radius=10,
        )

    def _toggle_diff_expand(self, row_idx: int):
        """Toggle expand/collapse of diff viewer"""
        if row_idx in self.expanded_diffs:
            self.expanded_diffs.discard(row_idx)
        else:
            self.expanded_diffs.add(row_idx)
        self._preview_changes()

    def _clear_results(self):
        """Clear all results and reset input"""
        assert self.results_column is not None
        assert self.opx_input is not None

        self.results_column.controls.clear()
        self.results_column.controls.append(self._create_empty_state())

        self.opx_input.value = ""
        self.expanded_diffs.clear()
        self.last_preview_data = None
        self.last_apply_results = []
        self.last_opx_text = ""

        self._show_status("")
        safe_page_update(self.page)

    def _paste_from_clipboard(self):
        """Paste OPX content from clipboard"""
        success, result = get_clipboard_text()

        if success and result:
            assert self.opx_input is not None
            self.opx_input.value = result
            safe_page_update(self.page)
            self._show_status("Pasted from clipboard")
        else:
            self._show_status(result or "Clipboard is empty", is_error=True)

    def _update_workspace_indicator(self):
        """Update workspace indicator"""
        if self.workspace_indicator is None:
            return

        current_workspace = self.get_workspace()
        workspace_name = (
            current_workspace.name if current_workspace else "No workspace selected"
        )

        # Update the container content
        if isinstance(self.workspace_indicator.content, ft.Row):
            row = self.workspace_indicator.content
            if row.controls and len(row.controls) >= 2:
                # Update icon
                icon = row.controls[0]
                if isinstance(icon, ft.Icon):
                    icon.name = ft.Icons.FOLDER_OPEN if current_workspace else ft.Icons.FOLDER_OFF
                    icon.color = ApplyViewColors.ACTION_MODIFY if current_workspace else ApplyViewColors.TEXT_MUTED
                # Update text
                text = row.controls[1]
                if isinstance(text, ft.Text):
                    text.value = workspace_name
                    text.color = ApplyViewColors.TEXT_SECONDARY if current_workspace else ApplyViewColors.TEXT_MUTED

        self.workspace_indicator.tooltip = (
            str(current_workspace) if current_workspace else "Please select a workspace"
        )

    def _show_status(self, message: str, is_error: bool = False):
        """Show status message"""
        assert self.status_text is not None
        self.status_text.value = message
        self.status_text.color = ApplyViewColors.ERROR_TEXT if is_error else ApplyViewColors.SUCCESS_TEXT
        safe_page_update(self.page)

    def _show_backups_dialog(self):
        """Show dialog to view and restore backups"""
        from core.file_actions import list_backups, restore_backup, BACKUP_DIR

        backups = list_backups()

        if not backups:
            self._show_status("No backups available", is_error=True)
            return

        def close_dialog(e):
            dialog.open = False
            safe_page_update(self.page)

        def restore_selected(backup_path: Path):
            parts = backup_path.name.rsplit(".", 2)
            if len(parts) >= 3:
                original_name = parts[0]
                workspace = self.get_workspace()
                if workspace:
                    target = workspace / original_name
                    if restore_backup(backup_path, target):
                        self._show_status(f"Restored: {original_name}")
                    else:
                        self._show_status("Restore failed", is_error=True)
            dialog.open = False
            safe_page_update(self.page)

        def rollback_last_batch(e):
            """Restore files from the most recent backup batch"""
            workspace = self.get_workspace()
            if not workspace:
                self._show_status("No workspace selected", is_error=True)
                return

            if not backups:
                return

            from datetime import datetime

            def get_time(backup_path):
                parts = backup_path.name.rsplit(".", 2)
                if len(parts) >= 3:
                    try:
                        return datetime.strptime(parts[1], "%Y%m%d_%H%M%S")
                    except ValueError:
                        pass
                return None

            backup_data = []
            for b in backups:
                t = get_time(b)
                if t:
                    backup_data.append((b, t))

            backup_data.sort(key=lambda x: x[1], reverse=True)

            if not backup_data:
                self._show_status("No valid backups found", is_error=True)
                return

            latest_time = backup_data[0][1]
            batch_backups = []
            BATCH_THRESHOLD = 60.0

            for b, t in backup_data:
                delta = (latest_time - t).total_seconds()
                if delta <= BATCH_THRESHOLD:
                    batch_backups.append(b)
                else:
                    break

            restored_files = set()
            count = 0
            for backup in batch_backups:
                parts = backup.name.rsplit(".", 2)
                original_name = parts[0]

                if original_name not in restored_files:
                    target = workspace / original_name
                    if restore_backup(backup, target):
                        count += 1
                    restored_files.add(original_name)

            self._show_status(f"Undid changes for {count} files")
            dialog.open = False
            safe_page_update(self.page)

        # Build backup list
        backup_items = []
        for backup in backups[:20]:
            parts = backup.name.rsplit(".", 2)
            if len(parts) >= 3:
                file_name = parts[0]
                timestamp = parts[1]
                try:
                    from datetime import datetime
                    dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    time_str = timestamp

                backup_items.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.RESTORE, color=ApplyViewColors.ACTION_MODIFY),
                        title=ft.Text(file_name, size=13, color=ApplyViewColors.TEXT_PRIMARY),
                        subtitle=ft.Text(time_str, size=11, color=ApplyViewColors.TEXT_MUTED),
                        on_click=(lambda b: lambda e: restore_selected(b))(backup),
                    )
                )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Backup Files", weight=ft.FontWeight.W_600, color=ApplyViewColors.TEXT_PRIMARY),
            content=ft.Container(
                content=ft.Column(
                    controls=backup_items,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=0,
                ),
                width=450,
                height=350,
                bgcolor=ApplyViewColors.BG_EXPANDED,
                border_radius=8,
            ),
            bgcolor=ApplyViewColors.BG_CARD,
            actions=[
                ft.TextButton(
                    "Undo Last Apply",
                    on_click=rollback_last_batch,
                    style=ft.ButtonStyle(color=ApplyViewColors.ACTION_DELETE),
                    tooltip="Revert all files from the most recent apply",
                ),
                ft.TextButton(
                    "Close", 
                    on_click=close_dialog,
                    style=ft.ButtonStyle(color=ApplyViewColors.TEXT_MUTED),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(self.page)

    def _copy_error_for_ai(self):
        """Copy error context for AI to fix"""
        try:
            workspace = self.get_workspace()
            workspace_path = str(workspace) if workspace else None
            
            if self.last_preview_data and self.last_apply_results:
                context = build_error_context_for_ai(
                    preview_data=self.last_preview_data,
                    row_results=self.last_apply_results,
                    original_opx=self.last_opx_text,
                    include_opx=True,
                    workspace_path=workspace_path,
                    include_file_content=True,
                )
            else:
                error_msg = (
                    self.status_text.value if self.status_text else "Unknown error"
                )
                context = build_general_error_context(
                    error_type="OPX Apply Error",
                    error_message=error_msg or "Unknown error",
                    additional_context=f"Original OPX:\\n```xml\\n{self.last_opx_text}\\n```",
                )

            success, message = copy_to_clipboard(context)

            if success:
                self._show_status("Error context copied! Paste to AI for fix.")
            else:
                self._show_status(f"Failed to copy: {message}", is_error=True)

        except Exception as e:
            self._show_status(f"Failed to copy: {e}", is_error=True)

    def _copy_all_results(self):
        """Copy all results for AI debugging"""
        try:
            results = self.last_apply_results or []
            opx_text = self.last_opx_text or (
                self.opx_input.value if self.opx_input else ""
            )

            if not results:
                self._show_status("No results to copy", is_error=True)
                return

            total = len(results)
            success = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            ok_count = len(success)
            bad_count = len(failed)
            workspace = self.get_workspace()

            lines = []
            lines.append(
                "I just applied changes from OPX to the project with the following results:"
            )
            lines.append("")
            lines.append(f"**Workspace**: `{workspace or 'Not set'}`")
            lines.append("")
            lines.append("**About OPX:**")
            lines.append(
                "OPX is an XML format for defining file operations. Structure:"
            )
            lines.append(
                "- `<file_action>`: One operation (modify/create/delete/rewrite)"
            )
            lines.append('- `action="modify"`: Action type')
            lines.append('- `path="file/path"`: Target file path')
            lines.append("- `<search>`: Pattern to find (for modify)")
            lines.append("- `<replace>`: Replacement content")
            lines.append("- `<content>`: Full content (for create/rewrite)")
            lines.append("")
            lines.append("**Applied OPX:**")
            lines.append("```xml")
            lines.append(opx_text if opx_text else "(empty)")
            lines.append("```")
            lines.append("")
            lines.append("**Results:**")
            lines.append(f"- Total: {total} operations")
            lines.append(f"- Successful: {ok_count} files")
            lines.append(f"- Failed: {bad_count} files")
            lines.append("")

            if success:
                lines.append("**Success details:**")
                for idx, r in enumerate(success, 1):
                    lines.append(f"{idx}. {r.action} `{r.path}` - {r.message}")
                lines.append("")

            if failed:
                lines.append("**Failure details:**")
                for idx, r in enumerate(failed, 1):
                    lines.append(f"{idx}. {r.action} `{r.path}` - ERROR: {r.message}")
                lines.append("")

            lines.append("---")
            lines.append("")
            lines.append("Please confirm you've received this context.")

            full_context = "\n".join(lines)
            copy_to_clipboard(full_context)

            self._show_status(
                f"Copied {total} operations ({ok_count} OK, {bad_count} failed)"
            )
        except Exception as e:
            self._show_status(f"Copy failed: {e}", is_error=True)
