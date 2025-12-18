"""
Context View - Tab de chon files va copy context

Theme: Swiss Professional (Light)
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional
import pyperclip

from core.file_utils import scan_directory, TreeItem, flatten_tree_files
from core.token_counter import count_tokens_for_file, count_tokens
from core.prompt_generator import generate_file_map, generate_file_contents, generate_prompt


# Import theme colors from main
class ThemeColors:
    """Swiss Professional Light Theme Colors"""
    PRIMARY = "#2563EB"
    BG_PAGE = "#F8FAFC"
    BG_SURFACE = "#FFFFFF"
    BG_ELEVATED = "#F1F5F9"
    TEXT_PRIMARY = "#0F172A"
    TEXT_SECONDARY = "#475569"
    TEXT_MUTED = "#94A3B8"
    BORDER = "#E2E8F0"
    SUCCESS = "#10B981"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"
    ICON_FOLDER = "#F59E0B"
    ICON_FILE = "#64748B"


class ContextView:
    """View cho Context tab"""
    
    def __init__(self, page: ft.Page, get_workspace: Callable[[], Optional[Path]]):
        self.page = page
        self.get_workspace = get_workspace
        
        self.tree: Optional[TreeItem] = None
        self.selected_paths: set[str] = set()
        self.tree_container: Optional[ft.Column] = None
        self.token_count_text: Optional[ft.Text] = None
        self.instructions_field: Optional[ft.TextField] = None
        self.status_text: Optional[ft.Text] = None
    
    def build(self) -> ft.Container:
        """Build UI cho Context view voi Swiss Professional styling"""
        
        # Left panel: File tree
        self.tree_container = ft.Column(
            controls=[
                ft.Text(
                    "Open a folder to see files",
                    color=ThemeColors.TEXT_MUTED,
                    italic=True,
                    size=14
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
        
        # Token count display
        self.token_count_text = ft.Text(
            "0 tokens",
            size=13,
            weight=ft.FontWeight.W_600,
            color=ThemeColors.PRIMARY
        )
        
        left_panel = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Files", weight=ft.FontWeight.W_600, size=14, color=ThemeColors.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    self.token_count_text,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_size=18,
                        icon_color=ThemeColors.TEXT_SECONDARY,
                        tooltip="Refresh",
                        on_click=lambda _: self._refresh_tree()
                    )
                ]),
                ft.Divider(height=1, color=ThemeColors.BORDER),
                self.tree_container
            ], expand=True),
            padding=16,
            expand=True,
            bgcolor=ThemeColors.BG_SURFACE,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=8
        )
        
        # Right panel: Instructions and actions
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
        
        self.status_text = ft.Text(
            "",
            color=ThemeColors.SUCCESS,
            size=12
        )
        
        right_panel = ft.Container(
            content=ft.Column([
                ft.Text("Instructions", weight=ft.FontWeight.W_600, size=14, color=ThemeColors.TEXT_PRIMARY),
                ft.Container(height=8),
                self.instructions_field,
                ft.Container(height=16),
                ft.Row([
                    ft.OutlinedButton(
                        "Copy Context",
                        icon=ft.Icons.CONTENT_COPY,
                        on_click=lambda _: self._copy_context(include_xml=False),
                        expand=True,
                        style=ft.ButtonStyle(
                            color=ThemeColors.TEXT_PRIMARY,
                            side=ft.BorderSide(1, ThemeColors.BORDER),
                        )
                    ),
                    ft.ElevatedButton(
                        "Copy + OPX",
                        icon=ft.Icons.CODE,
                        on_click=lambda _: self._copy_context(include_xml=True),
                        expand=True,
                        style=ft.ButtonStyle(
                            color="#FFFFFF",
                            bgcolor=ThemeColors.PRIMARY,
                        )
                    )
                ], spacing=12),
                ft.Container(height=8),
                self.status_text
            ], expand=True),
            padding=16,
            expand=True,
            bgcolor=ThemeColors.BG_SURFACE,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=8
        )
        
        # Main layout: split view
        return ft.Container(
            content=ft.Row([
                ft.Container(content=left_panel, expand=2, margin=ft.margin.only(right=8)),
                ft.Container(content=right_panel, expand=1, margin=ft.margin.only(left=8))
            ], expand=True),
            expand=True,
            padding=16,
            bgcolor=ThemeColors.BG_PAGE
        )
    
    def on_workspace_changed(self, workspace_path: Path):
        """Duoc goi khi user chon folder moi hoac settings thay doi"""
        self._load_tree(workspace_path)
    
    def _load_tree(self, workspace_path: Path):
        """Load file tree tu workspace, su dung settings cho excluded patterns"""
        try:
            # Import settings
            from views.settings_view import get_excluded_patterns, get_use_gitignore
            
            excluded_patterns = get_excluded_patterns()
            use_gitignore = get_use_gitignore()
            
            self.tree = scan_directory(
                workspace_path,
                excluded_patterns=excluded_patterns,
                use_gitignore=use_gitignore
            )
            self.selected_paths.clear()
            self._render_tree()
            self._update_token_count()
        except Exception as e:
            self.tree_container.controls = [
                ft.Text(f"Error loading folder: {e}", color=ThemeColors.ERROR)
            ]
            self.page.update()
    
    def _render_tree(self):
        """Render file tree vao UI"""
        if not self.tree:
            return
        
        self.tree_container.controls.clear()
        self._render_tree_item(self.tree, 0)
        self.page.update()
    
    def _render_tree_item(self, item: TreeItem, depth: int):
        """Render mot item trong tree voi Swiss Professional styling"""
        indent = depth * 20
        
        # Checkbox cho selection
        checkbox = ft.Checkbox(
            value=item.path in self.selected_paths,
            active_color=ThemeColors.PRIMARY,
            check_color="#FFFFFF",
            on_change=lambda e, p=item.path, is_dir=item.is_dir, children=item.children: 
                self._on_item_toggled(e, p, is_dir, children)
        )
        
        # Icon voi theme colors
        icon = ft.Icons.FOLDER if item.is_dir else ft.Icons.INSERT_DRIVE_FILE
        icon_color = ThemeColors.ICON_FOLDER if item.is_dir else ThemeColors.ICON_FILE
        
        # Text styling
        text_weight = ft.FontWeight.W_500 if item.is_dir else ft.FontWeight.NORMAL
        
        row = ft.Row([
            ft.Container(width=indent),
            checkbox,
            ft.Icon(icon, size=18, color=icon_color),
            ft.Text(
                item.label, 
                size=13, 
                color=ThemeColors.TEXT_PRIMARY,
                weight=text_weight
            )
        ], spacing=6)
        
        self.tree_container.controls.append(row)
        
        # Render children
        for child in item.children:
            self._render_tree_item(child, depth + 1)
    
    def _on_item_toggled(self, e, path: str, is_dir: bool, children: list):
        """Xu ly khi user tick/untick mot item"""
        if e.control.value:
            self.selected_paths.add(path)
            # Neu la folder, them tat ca children
            if is_dir:
                self._select_all_children(children)
        else:
            self.selected_paths.discard(path)
            # Neu la folder, bo chon tat ca children
            if is_dir:
                self._deselect_all_children(children)
        
        self._render_tree()
        self._update_token_count()
    
    def _select_all_children(self, children: list):
        """Chon tat ca children"""
        for child in children:
            self.selected_paths.add(child.path)
            if child.children:
                self._select_all_children(child.children)
    
    def _deselect_all_children(self, children: list):
        """Bo chon tat ca children"""
        for child in children:
            self.selected_paths.discard(child.path)
            if child.children:
                self._deselect_all_children(child.children)
    
    def _update_token_count(self):
        """Cap nhat hien thi token count"""
        total_tokens = 0
        
        for path_str in self.selected_paths:
            path = Path(path_str)
            if path.is_file():
                total_tokens += count_tokens_for_file(path)
        
        self.token_count_text.value = f"{total_tokens:,} tokens"
        self.page.update()
    
    def _refresh_tree(self):
        """Refresh file tree"""
        workspace = self.get_workspace()
        if workspace:
            self._load_tree(workspace)
    
    def _copy_context(self, include_xml: bool):
        """Copy context vao clipboard"""
        if not self.tree or not self.selected_paths:
            self._show_status("No files selected", is_error=True)
            return
        
        try:
            # Generate prompt
            file_map = generate_file_map(self.tree, self.selected_paths)
            file_contents = generate_file_contents(self.selected_paths)
            instructions = self.instructions_field.value or ""
            
            prompt = generate_prompt(file_map, file_contents, instructions, include_xml)
            
            # Copy to clipboard
            pyperclip.copy(prompt)
            
            # Count tokens
            token_count = count_tokens(prompt)
            
            suffix = " + OPX" if include_xml else ""
            self._show_status(f"Copied! ({token_count:,} tokens){suffix}")
            
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)
    
    def _show_status(self, message: str, is_error: bool = False):
        """Hien thi status message"""
        self.status_text.value = message
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self.page.update()
