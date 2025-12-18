"""
Context View - Tab de chon files va copy context

Chua:
- File tree voi checkbox selection
- Token count display
- User instructions input
- Copy Context buttons
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional
import pyperclip

from core.file_utils import scan_directory, TreeItem, flatten_tree_files
from core.token_counter import count_tokens_for_file, count_tokens
from core.prompt_generator import generate_file_map, generate_file_contents, generate_prompt


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
        """Build UI cho Context view"""
        
        # Left panel: File tree
        self.tree_container = ft.Column(
            controls=[
                ft.Text(
                    "Open a folder to see files",
                    color=ft.Colors.GREY_500,
                    italic=True
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
        
        # Token count display
        self.token_count_text = ft.Text(
            "0 tokens",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.BLUE_400
        )
        
        left_panel = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Files", weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    self.token_count_text,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="Refresh",
                        on_click=lambda _: self._refresh_tree()
                    )
                ]),
                ft.Divider(height=1),
                self.tree_container
            ], expand=True),
            padding=10,
            expand=True,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
        )
        
        # Right panel: Instructions and actions
        self.instructions_field = ft.TextField(
            label="User Instructions",
            multiline=True,
            min_lines=5,
            max_lines=10,
            hint_text="Enter your task instructions here...",
            expand=True
        )
        
        self.status_text = ft.Text(
            "",
            color=ft.Colors.GREEN_400,
            size=12
        )
        
        right_panel = ft.Container(
            content=ft.Column([
                ft.Text("Instructions", weight=ft.FontWeight.BOLD),
                self.instructions_field,
                ft.Container(height=10),
                ft.Row([
                    ft.ElevatedButton(
                        "Copy Context",
                        icon=ft.Icons.CONTENT_COPY,
                        on_click=lambda _: self._copy_context(include_xml=False),
                        expand=True
                    ),
                    ft.ElevatedButton(
                        "Copy Context + OPX",
                        icon=ft.Icons.CODE,
                        on_click=lambda _: self._copy_context(include_xml=True),
                        expand=True,
                        bgcolor=ft.Colors.BLUE_700
                    )
                ], spacing=10),
                ft.Container(height=5),
                self.status_text
            ], expand=True),
            padding=10,
            expand=True
        )
        
        # Main layout: split view
        return ft.Container(
            content=ft.Row([
                ft.Container(content=left_panel, expand=2),
                ft.VerticalDivider(width=1, color=ft.Colors.GREY_800),
                ft.Container(content=right_panel, expand=1)
            ], expand=True),
            expand=True
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
                ft.Text(f"Error loading folder: {e}", color=ft.Colors.RED_400)
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
        """Render mot item trong tree"""
        indent = depth * 20
        
        # Checkbox cho selection
        checkbox = ft.Checkbox(
            value=item.path in self.selected_paths,
            on_change=lambda e, p=item.path, is_dir=item.is_dir, children=item.children: 
                self._on_item_toggled(e, p, is_dir, children)
        )
        
        # Icon
        icon = ft.Icons.FOLDER if item.is_dir else ft.Icons.INSERT_DRIVE_FILE
        icon_color = ft.Colors.YELLOW_700 if item.is_dir else ft.Colors.GREY_400
        
        row = ft.Row([
            ft.Container(width=indent),
            checkbox,
            ft.Icon(icon, size=18, color=icon_color),
            ft.Text(item.label, size=13)
        ], spacing=5)
        
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
            
            suffix = " + OPX Instructions" if include_xml else ""
            self._show_status(f"Copied! ({token_count:,} tokens){suffix}")
            
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)
    
    def _show_status(self, message: str, is_error: bool = False):
        """Hien thi status message"""
        self.status_text.value = message
        self.status_text.color = ft.Colors.RED_400 if is_error else ft.Colors.GREEN_400
        self.page.update()
