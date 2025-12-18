"""
Settings View - Tab de cau hinh excluded folders va gitignore

Port tu: /home/hao/Desktop/labs/overwrite/src/webview-ui/src/components/settings-tab/
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional
import json


# Settings file path
SETTINGS_FILE = Path.home() / ".overwrite-desktop" / "settings.json"


def load_settings() -> dict:
    """
    Load settings tu file.
    
    Returns:
        Dict voi keys: excluded_folders (str), use_gitignore (bool)
    """
    default = {
        "excluded_folders": "node_modules\ndist\nbuild\n.next\n__pycache__\n.pytest_cache",
        "use_gitignore": True
    }
    
    try:
        if SETTINGS_FILE.exists():
            content = SETTINGS_FILE.read_text(encoding="utf-8")
            saved = json.loads(content)
            # Merge with defaults
            return {**default, **saved}
    except (OSError, json.JSONDecodeError):
        pass
    
    return default


def save_settings(settings: dict) -> bool:
    """
    Save settings ra file.
    
    Args:
        settings: Dict voi keys: excluded_folders, use_gitignore
        
    Returns:
        True neu save thanh cong
    """
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return True
    except (OSError, IOError):
        return False


def get_excluded_patterns() -> list[str]:
    """
    Lay danh sach excluded patterns tu settings.
    
    Returns:
        List cac pattern strings (da filter empty va comment lines)
    """
    settings = load_settings()
    excluded_text = settings.get("excluded_folders", "")
    
    return [
        line.strip()
        for line in excluded_text.split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]


def get_use_gitignore() -> bool:
    """Lay gia tri use_gitignore tu settings"""
    settings = load_settings()
    return settings.get("use_gitignore", True)


class SettingsView:
    """View cho Settings tab"""
    
    def __init__(self, page: ft.Page, on_settings_changed: Optional[Callable[[], None]] = None):
        self.page = page
        self.on_settings_changed = on_settings_changed
        
        self.excluded_field: Optional[ft.TextField] = None
        self.gitignore_checkbox: Optional[ft.Checkbox] = None
        self.status_text: Optional[ft.Text] = None
    
    def build(self) -> ft.Container:
        """Build UI cho Settings view"""
        
        settings = load_settings()
        
        # Excluded folders textarea
        self.excluded_field = ft.TextField(
            label="Excluded Folders (one per line, similar to .gitignore)",
            multiline=True,
            min_lines=8,
            max_lines=15,
            value=settings.get("excluded_folders", ""),
            hint_text="node_modules\ndist\nbuild\n__pycache__",
            expand=True
        )
        
        # Respect .gitignore checkbox
        self.gitignore_checkbox = ft.Checkbox(
            label="Respect .gitignore",
            value=settings.get("use_gitignore", True),
        )
        
        # Status
        self.status_text = ft.Text("", size=12)
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1),
                ft.Container(height=10),
                
                # Gitignore toggle
                ft.Container(
                    content=ft.Column([
                        ft.Text("File Tree Options", weight=ft.FontWeight.BOLD, size=14),
                        self.gitignore_checkbox,
                        ft.Text(
                            "When enabled, files matching patterns in .gitignore will be hidden from the file tree.",
                            size=12,
                            color=ft.Colors.GREY_400,
                            italic=True
                        )
                    ]),
                    padding=ft.padding.only(bottom=20)
                ),
                
                # Excluded folders
                ft.Container(
                    content=ft.Column([
                        ft.Text("Excluded Folders", weight=ft.FontWeight.BOLD, size=14),
                        ft.Text(
                            "Enter folder patterns to exclude from the file tree. One pattern per line. "
                            "Lines starting with # are comments.",
                            size=12,
                            color=ft.Colors.GREY_400,
                            italic=True
                        ),
                        ft.Container(height=5),
                        self.excluded_field,
                    ]),
                    expand=True
                ),
                
                ft.Container(height=10),
                
                # Save button
                ft.Row([
                    ft.ElevatedButton(
                        "Save Settings",
                        icon=ft.Icons.SAVE,
                        on_click=lambda _: self._save_settings(),
                        bgcolor=ft.Colors.GREEN_700
                    ),
                    ft.ElevatedButton(
                        "Reset to Default",
                        icon=ft.Icons.RESTORE,
                        on_click=lambda _: self._reset_settings()
                    ),
                    ft.Container(expand=True),
                    self.status_text
                ], spacing=10),
                
                ft.Container(height=20),
                
                # Info section
                ft.Container(
                    content=ft.Column([
                        ft.Text("Default Excluded", weight=ft.FontWeight.BOLD, size=14),
                        ft.Text(
                            "These folders are always excluded:\n"
                            "• .git, .hg, .svn (Version control)\n",
                            size=12,
                            color=ft.Colors.GREY_400
                        )
                    ]),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    padding=15,
                    border_radius=5
                )
                
            ], expand=True),
            padding=20,
            expand=True
        )
    
    def _save_settings(self):
        """Save settings va notify"""
        settings = {
            "excluded_folders": self.excluded_field.value or "",
            "use_gitignore": self.gitignore_checkbox.value or False
        }
        
        if save_settings(settings):
            self._show_status("Settings saved!", is_error=False)
            if self.on_settings_changed:
                self.on_settings_changed()
        else:
            self._show_status("Error saving settings", is_error=True)
    
    def _reset_settings(self):
        """Reset ve default settings"""
        default = {
            "excluded_folders": "node_modules\ndist\nbuild\n.next\n__pycache__\n.pytest_cache",
            "use_gitignore": True
        }
        
        self.excluded_field.value = default["excluded_folders"]
        self.gitignore_checkbox.value = default["use_gitignore"]
        self.page.update()
        
        self._show_status("Reset to defaults (not saved yet)", is_error=False)
    
    def _show_status(self, message: str, is_error: bool = False):
        """Hien thi status message"""
        self.status_text.value = message
        self.status_text.color = ft.Colors.RED_400 if is_error else ft.Colors.GREEN_400
        self.page.update()
