"""
Settings View - Tab de cau hinh excluded folders va gitignore

Theme: Swiss Professional (Light)
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional
import json


# Settings file path
SETTINGS_FILE = Path.home() / ".overwrite-desktop" / "settings.json"


# Theme colors
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
        """Build UI cho Settings view voi Swiss Professional styling"""
        
        settings = load_settings()
        
        # Excluded folders textarea
        self.excluded_field = ft.TextField(
            label="Excluded Folders",
            multiline=True,
            min_lines=8,
            max_lines=12,
            value=settings.get("excluded_folders", ""),
            hint_text="node_modules\ndist\nbuild\n__pycache__",
            expand=True,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            label_style=ft.TextStyle(color=ThemeColors.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY, size=13),
        )
        
        # Respect .gitignore checkbox
        self.gitignore_checkbox = ft.Checkbox(
            label="Respect .gitignore",
            value=settings.get("use_gitignore", True),
            active_color=ThemeColors.PRIMARY,
            check_color="#FFFFFF",
            label_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY, size=14),
        )
        
        # Status
        self.status_text = ft.Text("", size=12)
        
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.Icon(ft.Icons.SETTINGS, color=ThemeColors.TEXT_PRIMARY, size=24),
                    ft.Text("Settings", size=20, weight=ft.FontWeight.W_600, color=ThemeColors.TEXT_PRIMARY),
                ], spacing=12),
                ft.Divider(height=1, color=ThemeColors.BORDER),
                ft.Container(height=16),
                
                # Main content in card
                ft.Container(
                    content=ft.Column([
                        # Gitignore toggle section
                        ft.Container(
                            content=ft.Column([
                                ft.Text("File Tree Options", weight=ft.FontWeight.W_600, size=14, color=ThemeColors.TEXT_PRIMARY),
                                ft.Container(height=8),
                                self.gitignore_checkbox,
                                ft.Text(
                                    "When enabled, files matching patterns in .gitignore will be hidden from the file tree.",
                                    size=12,
                                    color=ThemeColors.TEXT_SECONDARY,
                                )
                            ]),
                            padding=ft.padding.only(bottom=24)
                        ),
                        
                        # Excluded folders section
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Excluded Folders", weight=ft.FontWeight.W_600, size=14, color=ThemeColors.TEXT_PRIMARY),
                                ft.Text(
                                    "Enter folder patterns to exclude from the file tree. One pattern per line. Lines starting with # are comments.",
                                    size=12,
                                    color=ThemeColors.TEXT_SECONDARY,
                                ),
                                ft.Container(height=8),
                                self.excluded_field,
                            ]),
                            expand=True
                        ),
                        
                        ft.Container(height=16),
                        
                        # Action buttons
                        ft.Row([
                            ft.ElevatedButton(
                                "Save Settings",
                                icon=ft.Icons.SAVE,
                                on_click=lambda _: self._save_settings(),
                                style=ft.ButtonStyle(
                                    color="#FFFFFF",
                                    bgcolor=ThemeColors.SUCCESS,
                                )
                            ),
                            ft.OutlinedButton(
                                "Reset to Default",
                                icon=ft.Icons.RESTORE,
                                on_click=lambda _: self._reset_settings(),
                                style=ft.ButtonStyle(
                                    color=ThemeColors.TEXT_PRIMARY,
                                    side=ft.BorderSide(1, ThemeColors.BORDER),
                                )
                            ),
                            ft.Container(expand=True),
                            self.status_text
                        ], spacing=12),
                    ], expand=True),
                    padding=20,
                    bgcolor=ThemeColors.BG_SURFACE,
                    border=ft.border.all(1, ThemeColors.BORDER),
                    border_radius=8,
                    expand=True
                ),
                
                ft.Container(height=16),
                
                # Info section
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE, color=ThemeColors.TEXT_SECONDARY, size=18),
                        ft.Text(
                            "Default excluded: .git, .hg, .svn (Version control folders are always excluded)",
                            size=12,
                            color=ThemeColors.TEXT_SECONDARY
                        )
                    ], spacing=8),
                    bgcolor=ThemeColors.BG_ELEVATED,
                    padding=12,
                    border_radius=6,
                    border=ft.border.all(1, ThemeColors.BORDER)
                )
                
            ], expand=True),
            padding=20,
            expand=True,
            bgcolor=ThemeColors.BG_PAGE
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
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self.page.update()
