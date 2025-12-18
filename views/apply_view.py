"""
Apply View - Tab de paste OPX va apply changes

Chua:
- Text area de paste OPX response
- Preview button de xem truoc changes
- Apply button de thuc thi changes
- Result table
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional

from core.opx_parser import parse_opx_response
from core.file_actions import apply_file_actions, ActionResult


class ApplyView:
    """View cho Apply tab"""
    
    def __init__(self, page: ft.Page, get_workspace: Callable[[], Optional[Path]]):
        self.page = page
        self.get_workspace = get_workspace
        
        self.opx_input: Optional[ft.TextField] = None
        self.results_column: Optional[ft.Column] = None
        self.status_text: Optional[ft.Text] = None
    
    def build(self) -> ft.Container:
        """Build UI cho Apply view"""
        
        # OPX Input
        self.opx_input = ft.TextField(
            label="Paste OPX Response",
            multiline=True,
            min_lines=10,
            max_lines=15,
            hint_text="Paste the LLM's OPX XML response here...\n\nExample:\n<edit file=\"src/main.py\" op=\"patch\">\n  <find>\n<<<\nold code\n>>>\n  </find>\n  <put>\n<<<\nnew code\n>>>\n  </put>\n</edit>",
            expand=True
        )
        
        # Status
        self.status_text = ft.Text("", size=12)
        
        # Results table
        self.results_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
        
        return ft.Container(
            content=ft.Column([
                # Input section
                ft.Container(
                    content=ft.Column([
                        ft.Text("OPX Response", weight=ft.FontWeight.BOLD),
                        self.opx_input,
                        ft.Row([
                            ft.ElevatedButton(
                                "Preview",
                                icon=ft.Icons.VISIBILITY,
                                on_click=lambda _: self._preview_changes()
                            ),
                            ft.ElevatedButton(
                                "Apply Changes",
                                icon=ft.Icons.PLAY_ARROW,
                                on_click=lambda _: self._apply_changes(),
                                bgcolor=ft.Colors.GREEN_700
                            ),
                            ft.Container(expand=True),
                            self.status_text
                        ], spacing=10)
                    ]),
                    padding=10
                ),
                
                ft.Divider(height=1, color=ft.Colors.GREY_800),
                
                # Results section
                ft.Container(
                    content=ft.Column([
                        ft.Text("Results", weight=ft.FontWeight.BOLD),
                        self.results_column
                    ], expand=True),
                    padding=10,
                    expand=True,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
                )
            ], expand=True),
            expand=True
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
                description = f"→ {action.new_path}"
            
            self.results_column.controls.append(
                self._create_result_row(
                    action.action.upper(),
                    action.path,
                    description,
                    success=True,
                    is_preview=True
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
                    success=result.success
                )
            )
            if result.success:
                success_count += 1
        
        total = len(results)
        if success_count == total:
            self._show_status(f"Applied all {total} action(s) successfully!")
        else:
            self._show_status(f"Applied {success_count}/{total} action(s)", is_error=True)
        
        self.page.update()
    
    def _create_result_row(
        self,
        action: str,
        path: str,
        message: str,
        success: bool,
        is_preview: bool = False
    ) -> ft.Container:
        """Tao mot row trong results"""
        
        # Action badge color
        action_colors = {
            "CREATE": ft.Colors.GREEN_700,
            "MODIFY": ft.Colors.BLUE_700,
            "REWRITE": ft.Colors.ORANGE_700,
            "DELETE": ft.Colors.RED_700,
            "RENAME": ft.Colors.PURPLE_700,
            "ERROR": ft.Colors.RED_900
        }
        
        badge_color = action_colors.get(action, ft.Colors.GREY_700)
        
        # Status icon
        if is_preview:
            status_icon = ft.Icon(ft.Icons.VISIBILITY, size=16, color=ft.Colors.GREY_400)
        elif success:
            status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=ft.Colors.GREEN_400)
        else:
            status_icon = ft.Icon(ft.Icons.ERROR, size=16, color=ft.Colors.RED_400)
        
        return ft.Container(
            content=ft.Row([
                status_icon,
                ft.Container(
                    content=ft.Text(action, size=11, weight=ft.FontWeight.BOLD),
                    bgcolor=badge_color,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    border_radius=3
                ),
                ft.Text(path, size=12, weight=ft.FontWeight.W_500, expand=True),
                ft.Text(
                    message[:50] + "..." if len(message) > 50 else message,
                    size=11,
                    color=ft.Colors.GREY_400
                )
            ], spacing=10),
            padding=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER if success else ft.Colors.ERROR_CONTAINER,
            border_radius=5,
            margin=ft.margin.only(bottom=5)
        )
    
    def _show_status(self, message: str, is_error: bool = False):
        """Hien thi status message"""
        self.status_text.value = message
        self.status_text.color = ft.Colors.RED_400 if is_error else ft.Colors.GREEN_400
        self.page.update()
