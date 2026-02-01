"""
Apply View - Tab de paste OPX va apply changes

Theme: Swiss Professional (Light)
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


class ApplyView:
    """View cho Apply tab"""

    def __init__(self, page: ft.Page, get_workspace: Callable[[], Optional[Path]]):
        self.page = page
        self.get_workspace = get_workspace

        self.opx_input: Optional[ft.TextField] = None
        self.results_column: Optional[ft.Column] = None
        self.status_text: Optional[ft.Text] = None
        self.copy_error_btn: Optional[ft.OutlinedButton] = None

        # State for error copying
        self.last_preview_data: Optional[PreviewData] = None
        self.last_apply_results: List[ApplyRowResult] = []
        self.last_opx_text: str = ""

    def _detect_cascade_failure(self, action, results):
        """Detect if this failure might cause cascade failures"""
        if action.action in ["create", "modify"] and "Permission denied" in str(action.error):
            return True
        if action.action == "delete" and len([r for r in results if not r.success]) > 1:
            return True
        return False

        # State for diff expansion
        self.expanded_diffs: set = set()  # Set of row indices that are expanded

    def build(self) -> ft.Container:
        """Build UI cho Apply view voi Swiss Professional styling"""

        # OPX Input - Compact de danh khong gian cho Results
        self.opx_input = ft.TextField(
            label="Paste OPX Response",
            multiline=True,
            min_lines=4,
            max_lines=6,
            hint_text="Paste the LLM's OPX XML response here...",
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            label_style=ft.TextStyle(color=ThemeColors.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY, size=13),
        )

        # Status
        self.status_text = ft.Text("", size=12)

        # Copy Error button (hidden by default, shown when errors occur)
        self.copy_error_btn = ft.OutlinedButton(
            "Copy Error for AI",
            icon=ft.Icons.CONTENT_COPY,
            on_click=lambda _: self._copy_error_for_ai(),
            visible=False,
            style=ft.ButtonStyle(
                color=ThemeColors.ERROR,
                side=ft.BorderSide(1, ThemeColors.ERROR),
            ),
        )

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
                                            "Paste",
                                            icon=ft.Icons.CONTENT_PASTE,
                                            on_click=lambda _: self._paste_from_clipboard(),
                                            tooltip="Paste OPX from clipboard",
                                            style=ft.ButtonStyle(
                                                color=ThemeColors.TEXT_SECONDARY,
                                                side=ft.BorderSide(
                                                    1, ThemeColors.BORDER
                                                ),
                                            ),
                                        ),
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
                                ft.Row(
                                    [
                                        ft.Text(
                                            "Results",
                                            weight=ft.FontWeight.W_600,
                                            size=14,
                                            color=ThemeColors.TEXT_PRIMARY,
                                        ),
                                        ft.Container(expand=True),
                                        ft.OutlinedButton(
                                            "Clear",
                                            icon=ft.Icons.CLEAR_ALL,
                                            on_click=lambda _: self._clear_results(),
                                            style=ft.ButtonStyle(
                                                color=ThemeColors.TEXT_SECONDARY,
                                                side=ft.BorderSide(
                                                    1, ThemeColors.BORDER
                                                ),
                                            ),
                                        ),
                                        ft.OutlinedButton(
                                            "View Backups",
                                            icon=ft.Icons.HISTORY,
                                            on_click=lambda _: self._show_backups_dialog(),
                                            tooltip="View and restore from backups",
                                            style=ft.ButtonStyle(
                                                color=ThemeColors.TEXT_SECONDARY,
                                                side=ft.BorderSide(
                                                    1, ThemeColors.BORDER
                                                ),
                                            ),
                                        ),
                                        self.copy_error_btn,
                                    ],
                                    spacing=8,
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
        """
        Preview changes without applying.
        Hien thi diff stats (+lines/-lines) cho moi action.
        """
        # Type assertions - dam bao cac controls da duoc khoi tao
        assert self.opx_input is not None
        assert self.results_column is not None

        opx_text = self.opx_input.value
        if not opx_text:
            self._show_status("Please paste OPX response first", is_error=True)
            return

        # Basic validation - check for edit tags
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

        # Show parse errors if any
        if result.errors:
            for error in result.errors:
                self.results_column.controls.append(
                    self._create_result_row("ERROR", "", error, success=False)
                )

        # Analyze file actions to get diff stats
        workspace = self.get_workspace()
        preview_data = analyze_file_actions(result.file_actions, workspace)

        # Show analysis errors
        for error in preview_data.errors:
            self.results_column.controls.append(
                self._create_result_row("ERROR", "", error, success=False)
            )

        # Show parsed actions with diff stats
        for idx, row in enumerate(preview_data.rows):
            self.results_column.controls.append(
                self._create_preview_row(
                    row,
                    idx,
                    (
                        result.file_actions[idx]
                        if idx < len(result.file_actions)
                        else None
                    ),
                )
            )

        if preview_data.rows:
            total_added = sum(r.changes.added for r in preview_data.rows)
            total_removed = sum(r.changes.removed for r in preview_data.rows)
            self._show_status(
                f"Preview: {len(preview_data.rows)} action(s) | +{total_added} / -{total_removed} lines"
            )
        else:
            self._show_status("No actions found in OPX", is_error=True)

        safe_page_update(self.page)

    def _apply_changes(self):
        """Apply changes to files"""
        # Type assertions - dam bao cac controls da duoc khoi tao
        assert self.opx_input is not None
        assert self.results_column is not None
        assert self.copy_error_btn is not None

        opx_text = self.opx_input.value
        if not opx_text:
            self._show_status("Please paste OPX response first", is_error=True)
            return

        # Parse first to count actions
        parse_result = parse_opx_response(opx_text)
        if parse_result.file_actions:
            action_count = len(parse_result.file_actions)
            # Count unique files
            unique_files = set(a.path for a in parse_result.file_actions)
            file_count = len(unique_files)
            # Show confirmation dialog
            self._show_confirmation_dialog(
                f"Apply {action_count} change(s) to {file_count} file(s)?",
                "This will modify files in your workspace. Backups will be created automatically.",
                lambda: self._do_apply_changes(opx_text),
            )
        else:
            self._do_apply_changes(opx_text)

    def _show_confirmation_dialog(self, title: str, message: str, on_confirm: Callable):
        """Hiển thị confirmation dialog"""

        def close_dialog(e):
            dialog.open = False
            safe_page_update(self.page)

        def confirm_action(e):
            dialog.open = False
            safe_page_update(self.page)
            on_confirm()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.W_600),
            content=ft.Text(message, color=ThemeColors.TEXT_SECONDARY),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton(
                    "Apply",
                    on_click=confirm_action,
                    style=ft.ButtonStyle(
                        color="#FFFFFF",
                        bgcolor=ThemeColors.SUCCESS,
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
        """Thực hiện apply changes sau khi confirm"""
        workspace = self.get_workspace()
        workspace_roots = [workspace] if workspace else None

        # Parse OPX
        parse_result = parse_opx_response(opx_text)

        # Clear previous results and state
        assert self.results_column is not None
        assert self.copy_error_btn is not None

        self.results_column.controls.clear()
        self.last_apply_results = []
        self.last_opx_text = opx_text
        self.copy_error_btn.visible = False

        # Show parse errors if any
        if parse_result.errors:
            for error in parse_result.errors:
                self.results_column.controls.append(
                    self._create_result_row("ERROR", "", error, success=False)
                )
            self._show_status("Parse errors occurred", is_error=True)
            # Show copy error button for parse errors
            self.copy_error_btn.visible = True
            safe_page_update(self.page)
            return

        if not parse_result.file_actions:
            self._show_status("No actions found in OPX", is_error=True)
            safe_page_update(self.page)
            return

        # Analyze for preview data (used in error context)
        self.last_preview_data = analyze_file_actions(
            parse_result.file_actions, workspace
        )

        # Apply actions
        results = apply_file_actions(parse_result.file_actions, workspace_roots)

        # Convert to ApplyRowResult and save
        self.last_apply_results = []
        for i, result in enumerate(results):
            self.last_apply_results.append(
                ApplyRowResult(
                    row_index=i,
                    path=result.path,
                    action=result.action,
                    success=result.success,
                    message=result.message,
                    is_cascade_failure=self._detect_cascade_failure(action, results),
                )
            )

        # Display results
        assert self.results_column is not None
        assert self.copy_error_btn is not None

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
        failed_count = total - success_count

        if success_count == total:
            self._show_status(f"Applied all {total} action(s) successfully!")
            self.copy_error_btn.visible = False
        else:
            self._show_status(
                f"Applied {success_count}/{total} action(s)", is_error=True
            )
            # Show copy error button when there are failures
            self.copy_error_btn.visible = True

        # Save to history
        workspace = self.get_workspace()
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

    def _create_result_row(
        self,
        action: str,
        path: str,
        message: str,
        success: bool,
        is_preview: bool = False,
    ) -> ft.Container:
        """
        Tạo một row trong results với Swiss Professional styling.

        Args:
            action: Loại action (CREATE, MODIFY, DELETE, etc.)
            path: Đường dẫn file
            message: Message kết quả
            success: True nếu thành công
            is_preview: True nếu đang ở chế độ preview

        Returns:
            Container chứa row UI
        """

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

    def _create_preview_row(
        self, row: PreviewRow, row_idx: int = 0, file_action=None
    ) -> ft.Container:
        """
        Tạo một preview row với diff stats (+lines/-lines) và expandable visual diff.
        Hiển thị chi tiết thay đổi trước khi apply.

        Args:
            row: PreviewRow data chứa thông tin về file action
            row_idx: Index của row (dùng để track expand state)
            file_action: FileAction gốc (dùng để generate diff lines)

        Returns:
            Container chứa preview row UI với:
            - Action badge (CREATE, MODIFY, etc.)
            - File path
            - Diff stats (+X / -Y lines)
            - Description
            - Expandable diff viewer
        """
        # Action badge color
        action_colors = {
            "create": ThemeColors.SUCCESS,
            "modify": ThemeColors.PRIMARY,
            "rewrite": ThemeColors.WARNING,
            "delete": ThemeColors.ERROR,
            "rename": "#8B5CF6",  # Purple
        }
        badge_color = action_colors.get(row.action, ThemeColors.TEXT_SECONDARY)

        # Diff stats
        diff_text = format_change_summary(row.changes)
        diff_color = get_change_color(row.changes)

        # Error handling
        if row.has_error:
            status_icon = ft.Icon(ft.Icons.ERROR, size=16, color=ThemeColors.ERROR)
            row_bg = "#FEF2F2"
        else:
            status_icon = ft.Icon(
                ft.Icons.VISIBILITY, size=16, color=ThemeColors.TEXT_MUTED
            )
            row_bg = ThemeColors.BG_ELEVATED

        # Generate diff lines neu chua co
        workspace = self.get_workspace()
        diff_lines = []
        if file_action and row.action != "rename":
            try:
                diff_lines = generate_preview_diff_lines(file_action, workspace)
            except Exception:
                pass

        # Check expand state
        is_expanded = row_idx in self.expanded_diffs

        # Show diff button (chi hien thi neu co diff lines)
        show_diff_btn = None
        if diff_lines:
            show_diff_btn = ft.IconButton(
                icon=ft.Icons.EXPAND_MORE if not is_expanded else ft.Icons.EXPAND_LESS,
                icon_size=18,
                icon_color=ThemeColors.TEXT_SECONDARY,
                tooltip="Show Diff" if not is_expanded else "Hide Diff",
                on_click=lambda e: self._toggle_diff_expand(row_idx),
            )

        # Header row
        header_row = ft.Row(
            [
                status_icon,
                # Action badge
                ft.Container(
                    content=ft.Text(
                        row.action.upper(),
                        size=11,
                        weight=ft.FontWeight.W_600,
                        color="#FFFFFF",
                    ),
                    bgcolor=badge_color,
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    border_radius=4,
                ),
                # File path
                ft.Text(
                    row.path,
                    size=12,
                    weight=ft.FontWeight.W_500,
                    color=ThemeColors.TEXT_PRIMARY,
                    expand=True,
                ),
                # Diff stats badge (+X / -Y)
                ft.Container(
                    content=ft.Text(
                        diff_text,
                        size=11,
                        weight=ft.FontWeight.W_600,
                        color=diff_color,
                    ),
                    bgcolor=ThemeColors.BG_ELEVATED,
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    border_radius=4,
                    border=ft.border.all(1, ThemeColors.BORDER),
                ),
                # Description
                ft.Text(
                    (
                        row.description[:40] + "..."
                        if len(row.description) > 40
                        else row.description
                    ),
                    size=11,
                    color=ThemeColors.TEXT_SECONDARY,
                    width=180,
                ),
                # Show diff button
                show_diff_btn if show_diff_btn else ft.Container(width=0),
            ],
            spacing=12,
        )

        # Column content - List of Controls (Row or Container)
        column_content: list[ft.Control] = [header_row]

        # Diff viewer (neu expanded)
        if is_expanded and diff_lines:
            diff_viewer = DiffViewer(
                diff_lines=diff_lines,
                max_height=250,
                show_line_numbers=True,
            )
            column_content.append(
                ft.Container(
                    content=diff_viewer,
                    margin=ft.margin.only(top=8),
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=column_content,
                spacing=0,
            ),
            padding=12,
            bgcolor=row_bg,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=6,
            margin=ft.margin.only(bottom=8),
        )

    def _toggle_diff_expand(self, row_idx: int):
        """
        Toggle expand/collapse cua diff viewer cho row.

        Args:
            row_idx: Index cua row
        """
        if row_idx in self.expanded_diffs:
            self.expanded_diffs.discard(row_idx)
        else:
            self.expanded_diffs.add(row_idx)

        # Re-render preview
        self._preview_changes()

    def _clear_results(self):
        """Clear tất cả results và reset input"""
        assert self.results_column is not None
        assert self.opx_input is not None
        assert self.copy_error_btn is not None

        self.results_column.controls.clear()
        self.results_column.controls.append(
            ft.Text(
                "Results will appear here after Preview or Apply",
                color=ThemeColors.TEXT_MUTED,
                italic=True,
                size=14,
            )
        )

        self.opx_input.value = ""
        self.copy_error_btn.visible = False
        self.expanded_diffs.clear()
        self.last_preview_data = None
        self.last_apply_results = []
        self.last_opx_text = ""

        self._show_status("")
        safe_page_update(self.page)

    def _paste_from_clipboard(self):
        """Paste OPX content từ clipboard vào input field"""
        success, result = get_clipboard_text()

        if success and result:
            assert self.opx_input is not None
            self.opx_input.value = result
            safe_page_update(self.page)
            self._show_status("Pasted from clipboard")
        else:
            self._show_status(result or "Clipboard is empty", is_error=True)

    def _show_status(self, message: str, is_error: bool = False):
        """Hien thi status message"""
        assert self.status_text is not None
        self.status_text.value = message
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
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
            # Extract original filename from backup name (format: filename.timestamp.bak)
            parts = backup_path.name.rsplit(".", 2)
            if len(parts) >= 3:
                original_name = parts[0]
                # Ask user for restore location
                workspace = self.get_workspace()
                if workspace:
                    # Simple restore to workspace root for now
                    # In future, could add file picker
                    target = workspace / original_name
                    if restore_backup(backup_path, target):
                        self._show_status(f"Restored: {original_name}")
                    else:
                        self._show_status("Restore failed", is_error=True)
            dialog.open = False
            safe_page_update(self.page)

        def rollback_last_batch(e):
            """Restore files from the most recent backup batch (within 60s window)"""
            workspace = self.get_workspace()
            if not workspace:
                self._show_status("No workspace selected", is_error=True)
                return

            if not backups:
                return

            from datetime import datetime

            # Helper checks timestamp
            def get_time(backup_path):
                 parts = backup_path.name.rsplit(".", 2)
                 if len(parts) >= 3:
                     try:
                         return datetime.strptime(parts[1], "%Y%m%d_%H%M%S")
                     except ValueError:
                         pass
                 return None

            # Sort backups by time desc
            backup_data = []
            for b in backups:
                t = get_time(b)
                if t:
                    backup_data.append((b, t))
            
            # list_backups usually sorted, but ensure desc
            backup_data.sort(key=lambda x: x[1], reverse=True)

            if not backup_data:
                self._show_status("No valid backups found", is_error=True)
                return

            # Identify latest batch (cluster of backups within 60s of the newest one)
            latest_time = backup_data[0][1]
            batch_backups = []
            BATCH_THRESHOLD = 60.0 # seconds

            for b, t in backup_data:
                delta = (latest_time - t).total_seconds()
                if delta <= BATCH_THRESHOLD:
                    batch_backups.append(b)
                else:
                    break # Gap detected, end of batch

            # Restore batch
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
            
            self._show_status(f"Undid changes for {count} files (Last Batch)")
            dialog.open = False
            safe_page_update(self.page)

        # Build backup list
        backup_items = []
        for backup in backups[:20]:  # Show max 20
            # Parse timestamp from name
            parts = backup.name.rsplit(".", 2)
            if len(parts) >= 3:
                file_name = parts[0]
                timestamp = parts[1]
                # Format timestamp for display
                try:
                    from datetime import datetime

                    dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    time_str = timestamp

                backup_items.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.RESTORE, color=ThemeColors.PRIMARY),
                        title=ft.Text(file_name, size=13),
                        subtitle=ft.Text(
                            time_str, size=11, color=ThemeColors.TEXT_MUTED
                        ),
                        on_click=(lambda b: lambda e: restore_selected(b))(backup),
                    )
                )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Backup Files", weight=ft.FontWeight.W_600),
            content=ft.Container(
                content=ft.Column(
                    backup_items,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=0,
                ),
                width=400,
                height=300,
            ),
            actions=[
                ft.TextButton(
                    "Undo Last Apply",
                    on_click=rollback_last_batch,
                    style=ft.ButtonStyle(color=ThemeColors.ERROR),
                    tooltip="Revert all files from the most recent patch apply",
                ),
                ft.TextButton("Close", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(self.page)

    def _copy_error_for_ai(self):
        """
        Copy error context for AI de fix.
        Bao gom context day du: errors, search patterns, instructions.
        """
        try:
            # Build error context
            if self.last_preview_data and self.last_apply_results:
                # Full context from apply results
                context = build_error_context_for_ai(
                    preview_data=self.last_preview_data,
                    row_results=self.last_apply_results,
                    original_opx=self.last_opx_text,
                    include_opx=True,
                )
            else:
                # Fallback for parse errors or other errors
                error_msg = (
                    self.status_text.value if self.status_text else "Unknown error"
                )
                context = build_general_error_context(
                    error_type="OPX Apply Error",
                    error_message=error_msg or "Unknown error",
                    additional_context=f"Original OPX:\\n```xml\\n{self.last_opx_text}\\n```",
                )

            # Copy to clipboard with fallback handling
            success, message = copy_to_clipboard(context)

            if success:
                self._show_status(
                    "Error context copied! Paste to AI for fix.", is_error=False
                )
            else:
                self._show_status(f"Failed to copy: {message}", is_error=True)

        except Exception as e:
            self._show_status(f"Failed to copy: {e}", is_error=True)
