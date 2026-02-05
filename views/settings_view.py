"""
Settings View - Tab de cau hinh excluded folders va gitignore

Theme: Swiss Professional (Light)
"""

import flet as ft
from pathlib import Path
from typing import Callable, Optional
import json

from core.theme import ThemeColors
from core.utils.ui_utils import safe_page_update
from services.clipboard_utils import copy_to_clipboard, get_clipboard_text
from services.session_state import clear_session_state, get_session_age_hours

# Use shared settings manager
from services.settings_manager import load_settings, save_settings


# Preset profiles for different project types
PRESET_PROFILES = {
    "Python": "__pycache__\n.pytest_cache\n.venv\nvenv\n.eggs\n*.egg-info\ndist\nbuild\n.mypy_cache\n.tox\ncoverage\nhtmlcov\n.coverage",
    "Node.js": "node_modules\ndist\nbuild\n.next\ncoverage\n.cache\n.parcel-cache\npnpm-lock.yaml\npackage-lock.json\nyarn.lock",
    "Rust": "target\nCargo.lock",
    "Go": "vendor\nbin",
    "Java": "target\n*.class\n.gradle\nbuild\nout",
    "General": "dist\nbuild\ncoverage\n.cache\ntmp\ntemp\nlogs\n*.log",
}


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


def add_excluded_patterns(patterns: list[str]) -> bool:
    """
    Them cac pattern vao danh sach excluded folders.

    Args:
        patterns: List cac pattern can them (relative paths hoac glob patterns)

    Returns:
        True neu save thanh cong
    """
    if not patterns:
        return True

    settings = load_settings()
    current = settings.get("excluded_folders", "")

    # Loc bo cac pattern da ton tai
    existing_patterns = set(
        line.strip()
        for line in current.split("\n")
        if line.strip() and not line.strip().startswith("#")
    )

    new_patterns = [p for p in patterns if p not in existing_patterns]

    if not new_patterns:
        return True  # Khong co pattern moi can them

    # Append new patterns
    new_content = "\n".join(new_patterns)
    if current.strip():
        settings["excluded_folders"] = current.rstrip() + "\n" + new_content
    else:
        settings["excluded_folders"] = new_content

    return save_settings(settings)


def remove_excluded_patterns(patterns: list[str]) -> bool:
    """
    Xoa cac pattern khoi danh sach excluded folders.
    Dung cho chuc nang Undo khi add nhiem.

    Args:
        patterns: List cac pattern can xoa

    Returns:
        True neu save thanh cong
    """
    if not patterns:
        return True

    settings = load_settings()
    current = settings.get("excluded_folders", "")

    # Tach thanh cac dong va loc bo patterns can xoa
    lines = current.split("\n")
    patterns_set = set(patterns)

    # Giu lai cac dong khong nam trong patterns can xoa
    remaining_lines = [line for line in lines if line.strip() not in patterns_set]

    settings["excluded_folders"] = "\n".join(remaining_lines)
    return save_settings(settings)


class SettingsViewColors:
    """Enhanced colors for Settings View to match Apply View style"""
    BG_CARD = "#1E293B"  # Slate 800
    BG_EXPANDED = "#0F172A"  # Slate 900
    
    TEXT_PRIMARY = "#F8FAFC"  # Slate 50
    TEXT_SECONDARY = "#CBD5E1"  # Slate 300
    TEXT_MUTED = "#94A3B8"  # Slate 400
    
    BORDER = "#334155"  # Slate 700
    PRIMARY = "#3B82F6"  # Blue 500
    SUCCESS = "#10B981"  # Emerald 500
    WARNING = "#F59E0B"  # Amber 500
    ERROR = "#EF4444"  # Red 500
    
    # Action colors
    BTN_PRIMARY_BG = "#3B82F6"
    BTN_PRIMARY_TEXT = "#FFFFFF"


class SettingsView:
    """View cho Settings tab voi improved UI (2 columns)"""

    def __init__(
        self, page: ft.Page, on_settings_changed: Optional[Callable[[], None]] = None
    ):
        self.page = page
        self.on_settings_changed = on_settings_changed

        self.excluded_field: Optional[ft.TextField] = None
        self.gitignore_checkbox: Optional[ft.Checkbox] = None
        self.security_check_checkbox: Optional[ft.Checkbox] = None
        self.git_include_checkbox: Optional[ft.Checkbox] = None
        self.status_text: Optional[ft.Text] = None

        # Track unsaved changes
        self._has_unsaved_changes: bool = False
        self._initial_values: dict = {}

    def build(self) -> ft.Container:
        """Build UI cho Settings view voi 2 column layout"""

        settings = load_settings()

        # --- CONTROLS SETUP ---

        # Excluded folders textarea
        self.excluded_field = ft.TextField(
            multiline=True,
            expand=True,
            value=settings.get("excluded_folders", ""),
            hint_text="node_modules\ndist\nbuild\n__pycache__",
            border_color=SettingsViewColors.BORDER,
            focused_border_color=SettingsViewColors.PRIMARY,
            text_style=ft.TextStyle(
                color=SettingsViewColors.TEXT_PRIMARY, size=13, font_family="monospace"
            ),
            content_padding=15,
            cursor_color=SettingsViewColors.PRIMARY,
            bgcolor=SettingsViewColors.BG_EXPANDED,
            on_change=lambda e: self._mark_changed(),
        )

        # Checkboxes style
        checkbox_style = ft.TextStyle(color=SettingsViewColors.TEXT_PRIMARY, size=14)

        self.gitignore_checkbox = ft.Checkbox(
            label="Respect .gitignore",
            value=settings.get("use_gitignore", True),
            active_color=SettingsViewColors.PRIMARY,
            check_color="#FFFFFF",
            label_style=checkbox_style,
            on_change=lambda e: self._mark_changed(),
        )

        self.security_check_checkbox = ft.Checkbox(
            label="Enable Security Check",
            value=settings.get("enable_security_check", True),
            active_color=SettingsViewColors.WARNING,
            check_color="#FFFFFF",
            label_style=checkbox_style,
            on_change=lambda e: self._mark_changed(),
        )

        self.git_include_checkbox = ft.Checkbox(
            label="Include Git Diff/Log",
            value=settings.get("include_git_changes", True),
            active_color=SettingsViewColors.PRIMARY,
            check_color="#FFFFFF",
            label_style=checkbox_style,
            on_change=lambda e: self._mark_changed(),
        )

        # Store initial values
        self._initial_values = {
            "excluded_folders": settings.get("excluded_folders", ""),
            "use_gitignore": settings.get("use_gitignore", True),
            "enable_security_check": settings.get("enable_security_check", True),
            "include_git_changes": settings.get("include_git_changes", True),
        }
        self._has_unsaved_changes = False

        # Status
        self.status_text = ft.Text("", size=12)

        # --- LEFT COLUMN: CONFIGURATION ---
        left_column = ft.Container(
            content=ft.Column(
                [
                    # Header
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TUNE, color=SettingsViewColors.PRIMARY, size=20),
                            ft.Text(
                                "Configuration",
                                size=16,
                                weight=ft.FontWeight.W_600,
                                color=SettingsViewColors.TEXT_PRIMARY,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Divider(color=SettingsViewColors.BORDER, height=1),
                    ft.Container(height=10),
                    
                    # Scrollable Settings Group
                    ft.Column(
                        [
                            # File Tree Section
                            self._build_section_header("File Tree Options"),
                            self.gitignore_checkbox,
                            ft.Text(
                                "Hide files matching .gitignore patterns",
                                size=12,
                                color=SettingsViewColors.TEXT_MUTED,
                            ),
                            ft.Container(height=16),

                            # Context Section
                            self._build_section_header("AI Context"),
                            self.git_include_checkbox,
                            ft.Text(
                                "Include recent git changes in context",
                                size=12,
                                color=SettingsViewColors.TEXT_MUTED,
                            ),
                            ft.Container(height=16),

                            # Security Section
                            self._build_section_header("Security"),
                            self.security_check_checkbox,
                            ft.Text(
                                "Scan for secrets before copying to clipboard",
                                size=12,
                                color=SettingsViewColors.TEXT_MUTED,
                            ),
                            ft.Container(height=16),

                            # Presets Section
                            self._build_section_header("Quick Presets"),
                            ft.Dropdown(
                                options=[
                                    ft.dropdown.Option(key=name, text=name)
                                    for name in PRESET_PROFILES.keys()
                                ],
                                on_select=lambda e: self._load_preset(e.control.value or ""),
                                hint_text="Select a profile...",
                                text_size=13,
                                border_color=SettingsViewColors.BORDER,
                                focused_border_color=SettingsViewColors.PRIMARY,
                                bgcolor=SettingsViewColors.BG_EXPANDED,
                                width=float("inf"),
                                dense=True,
                                height=40,
                            ),
                            ft.Container(height=16),

                            # Session Section
                            self._build_section_header("Session"),
                            ft.OutlinedButton(
                                "Clear Saved Session",
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=lambda _: self._clear_session(),
                                style=ft.ButtonStyle(
                                    color=SettingsViewColors.TEXT_SECONDARY,
                                    side=ft.BorderSide(1, SettingsViewColors.BORDER),
                                ),
                                width=float("inf"),
                            ),
                            ft.Text(
                                "Resets workspace and open files state",
                                size=11,
                                color=SettingsViewColors.TEXT_SECONDARY,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=24),  # Prevent bottom clipping
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),

                    ft.Container(height=10),
                    ft.Divider(color=SettingsViewColors.BORDER),
                    ft.Container(height=10),

                    # Action Buttons
                    ft.ElevatedButton(
                        "Save Settings",
                        icon=ft.Icons.SAVE,
                        on_click=lambda _: self._save_settings(),
                        style=ft.ButtonStyle(
                            color=SettingsViewColors.BTN_PRIMARY_TEXT,
                            bgcolor=SettingsViewColors.BTN_PRIMARY_BG,
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=16,
                        ),
                        width=float("inf"),
                    ),
                    ft.Container(height=8),
                    ft.Row(
                        [
                            ft.OutlinedButton(
                                "Reset",
                                icon=ft.Icons.RESTORE,
                                on_click=lambda _: self._reset_settings(),
                                style=ft.ButtonStyle(
                                    color=SettingsViewColors.TEXT_SECONDARY,
                                    side=ft.BorderSide(1, SettingsViewColors.BORDER),
                                ),
                                expand=True,
                            ),
                            ft.OutlinedButton(
                                "Share",
                                icon=ft.Icons.SHARE,
                                on_click=lambda _: self._show_share_menu(),
                                style=ft.ButtonStyle(
                                    color=SettingsViewColors.TEXT_SECONDARY,
                                    side=ft.BorderSide(1, SettingsViewColors.BORDER),
                                ),
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Container(height=4),
                    self.status_text,
                ],
                spacing=0,
            ),
            expand=2,
            padding=20,
            bgcolor=SettingsViewColors.BG_CARD,
            border=ft.border.all(1, SettingsViewColors.BORDER),
            border_radius=10,
        )

        # --- RIGHT COLUMN: EXCLUDED FOLDERS ---
        right_column = ft.Container(
            content=ft.Column(
                [
                    # Header
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.FOLDER_OFF, color=SettingsViewColors.TEXT_SECONDARY, size=20),
                            ft.Text(
                                "Excluded Patterns",
                                size=16,
                                weight=ft.FontWeight.W_600,
                                color=SettingsViewColors.TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                icon_size=18,
                                icon_color=SettingsViewColors.TEXT_MUTED,
                                tooltip="Reload from file",
                                on_click=lambda _: self._reload_settings(),
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Divider(color=SettingsViewColors.BORDER, height=1),
                    ft.Container(height=10),
                    
                    # Helper Text
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=SettingsViewColors.TEXT_MUTED),
                                ft.Text(
                                    "Exclude files/folders from File Tree & AI Context. One pattern per line.",
                                    size=12,
                                    color=SettingsViewColors.TEXT_MUTED,
                                    expand=True,
                                ),
                            ],
                            spacing=6,
                        ),
                        margin=ft.margin.only(bottom=10),
                    ),

                    # Editor
                    self.excluded_field,
                ],
                spacing=0,
            ),
            expand=3,
            padding=20,
            bgcolor=SettingsViewColors.BG_CARD,
            border=ft.border.all(1, SettingsViewColors.BORDER),
            border_radius=10,
        )

        # --- MAIN LAYOUT ---
        return ft.Container(
            content=ft.Row(
                [left_column, right_column],
                spacing=16,
                expand=True,
            ),
            padding=16,
            expand=True,
            bgcolor=ThemeColors.BG_PAGE,
        )

    def _build_section_header(self, title: str) -> ft.Text:
        return ft.Text(
            title,
            size=13,
            weight=ft.FontWeight.W_600,
            color=SettingsViewColors.TEXT_SECONDARY,
        )
    
    def _show_share_menu(self):
        """Show Export/Import menu"""
        def close_menu(e):
            bs.open = False
            bs.update()

        bs = ft.BottomSheet(
            ft.Container(
                ft.Column(
                    [
                        ft.Text("Share Settings", weight=ft.FontWeight.BOLD),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.DOWNLOAD),
                            title=ft.Text("Export to Clipboard"),
                            subtitle=ft.Text("Copy settings JSON"),
                            on_click=lambda e: [self._export_settings(), close_menu(e)],
                        ),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.UPLOAD),
                            title=ft.Text("Import from Clipboard"),
                            subtitle=ft.Text("Load settings JSON"),
                            on_click=lambda e: [self._import_settings(), close_menu(e)],
                        ),
                    ],
                    tight=True,
                ),
                padding=10,
            ),
        )
        self.page.overlay.append(bs)
        bs.open = True
        self.page.update()

    def _save_settings(self):
        """Save settings va notify"""
        assert self.excluded_field is not None
        assert self.gitignore_checkbox is not None
        assert self.security_check_checkbox is not None
        assert self.git_include_checkbox is not None

        settings = {
            "excluded_folders": self.excluded_field.value or "",
            "use_gitignore": self.gitignore_checkbox.value or False,
            "enable_security_check": self.security_check_checkbox.value or False,
            "include_git_changes": self.git_include_checkbox.value or False,
        }

        if save_settings(settings):
            self._show_status("Settings saved!", is_error=False)
            self.reset_unsaved_state()  # Reset unsaved state after successful save
            if self.on_settings_changed:
                self.on_settings_changed()
        else:
            self._show_status("Error saving settings", is_error=True)

    def _reset_settings(self):
        """Reset ve default settings"""
        assert self.excluded_field is not None
        assert self.gitignore_checkbox is not None
        assert self.security_check_checkbox is not None
        assert self.git_include_checkbox is not None

        default_excluded = "node_modules\ndist\nbuild\n.next\n__pycache__\n.pytest_cache\npnpm-lock.yaml\npackage-lock.json\ncoverage"

        self.excluded_field.value = default_excluded
        self.gitignore_checkbox.value = True
        self.security_check_checkbox.value = True
        self.git_include_checkbox.value = True
        safe_page_update(self.page)

        self._show_status("Reset to defaults (not saved yet)", is_error=False)

    def _export_settings(self):
        """Export settings to clipboard as JSON"""
        assert self.excluded_field is not None
        assert self.gitignore_checkbox is not None
        assert self.git_include_checkbox is not None

        settings = {
            "excluded_folders": self.excluded_field.value or "",
            "use_gitignore": self.gitignore_checkbox.value or False,
            "include_git_changes": self.git_include_checkbox.value or False,
            "export_version": "1.0",
        }

        settings_json = json.dumps(settings, indent=2, ensure_ascii=False)
        success, message = copy_to_clipboard(settings_json)

        if success:
            self._show_status("Settings exported to clipboard!")
        else:
            self._show_status(f"Export failed: {message}", is_error=True)

    def _import_settings(self):
        """Import settings from clipboard JSON"""
        success, clipboard_text = get_clipboard_text()

        if not success or not clipboard_text:
            self._show_status("Clipboard is empty", is_error=True)
            return

        try:
            imported = json.loads(clipboard_text)

            # Validate structure
            if "excluded_folders" not in imported:
                self._show_status("Invalid settings format", is_error=True)
                return

            assert self.excluded_field is not None
            assert self.gitignore_checkbox is not None
            assert self.git_include_checkbox is not None

            self.excluded_field.value = imported.get("excluded_folders", "")
            self.gitignore_checkbox.value = imported.get("use_gitignore", True)
            self.git_include_checkbox.value = imported.get("include_git_changes", True)

            safe_page_update(self.page)
            self._show_status("Settings imported! Click Save to apply.")

        except json.JSONDecodeError:
            self._show_status("Invalid JSON in clipboard", is_error=True)

    def _clear_session(self):
        """Clear saved session state"""
        if clear_session_state():
            self._show_status("Session cleared. Restart app to see effect.")
        else:
            self._show_status("Failed to clear session", is_error=True)

    def _load_preset(self, preset_name: str):
        """Load a preset profile into excluded folders field"""
        if not preset_name or preset_name not in PRESET_PROFILES:
            return

        assert self.excluded_field is not None

        # Append to existing or replace?
        current = self.excluded_field.value or ""
        preset_content = PRESET_PROFILES[preset_name]

        if current.strip():
            # Append with separator
            self.excluded_field.value = (
                current.rstrip() + "\n# " + preset_name + " preset\n" + preset_content
            )
        else:
            self.excluded_field.value = (
                "# " + preset_name + " preset\n" + preset_content
            )

        safe_page_update(self.page)
        self._show_status(f"Loaded {preset_name} preset (not saved yet)")

    def _show_status(self, message: str, is_error: bool = False):
        """Hien thi status message"""
        assert self.status_text is not None
        self.status_text.value = message
        self.status_text.color = SettingsViewColors.ERROR if is_error else SettingsViewColors.SUCCESS
        safe_page_update(self.page)

    def _reload_settings(self):
        """
        Reload settings tu file va cap nhat UI.
        Dung de refresh khi settings bi thay doi tu ben ngoai (vd: Context tab).
        """
        assert self.excluded_field is not None
        assert self.gitignore_checkbox is not None
        assert self.git_include_checkbox is not None

        settings = load_settings()
        self.excluded_field.value = settings.get("excluded_folders", "")
        self.gitignore_checkbox.value = settings.get("use_gitignore", True)
        self.git_include_checkbox.value = settings.get("include_git_changes", True)

        safe_page_update(self.page)
        self._show_status("Settings reloaded from file")

    def _mark_changed(self):
        """
        Đánh dấu có thay đổi chưa save.
        Được gọi bởi on_change handlers của các form fields.
        """
        self._has_unsaved_changes = True

    def has_unsaved_changes(self) -> bool:
        """
        Kiểm tra có thay đổi chưa save không.
        So sánh giá trị hiện tại với initial values.
        """
        if not self._has_unsaved_changes:
            return False

        # Double check by comparing actual values
        if (
            self.excluded_field
            and self.gitignore_checkbox
            and self.security_check_checkbox
            and self.git_include_checkbox
        ):
            current_excluded = self.excluded_field.value or ""
            current_gitignore = self.gitignore_checkbox.value or False
            current_security = self.security_check_checkbox.value or False
            current_git = self.git_include_checkbox.value or False

            return (
                current_excluded != self._initial_values.get("excluded_folders", "")
                or current_gitignore != self._initial_values.get("use_gitignore", True)
                or current_security
                != self._initial_values.get("enable_security_check", True)
                or current_git != self._initial_values.get("include_git_changes", True)
            )

        return self._has_unsaved_changes

    def show_unsaved_dialog(
        self, on_discard: Callable[[], None], on_cancel: Callable[[], None]
    ):
        """
        Hiển thị dialog cảnh báo có thay đổi chưa save.
        Using simple Flet AlertDialog
        """

        def close_and_discard(e):
            dialog.open = False
            safe_page_update(self.page)
            on_discard()

        def close_and_stay(e):
            dialog.open = False
            safe_page_update(self.page)
            on_cancel()

        def save_and_leave(e):
            dialog.open = False
            self._save_settings()
            safe_page_update(self.page)
            on_discard()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Unsaved Changes",
                weight=ft.FontWeight.BOLD,
                color=SettingsViewColors.WARNING,
            ),
            content=ft.Text(
                "You have unsaved changes in Settings. What would you like to do?",
                size=14,
            ),
            actions=[
                ft.TextButton(
                    "Discard",
                    on_click=close_and_discard,
                    style=ft.ButtonStyle(color=SettingsViewColors.ERROR),
                ),
                ft.TextButton(
                    "Stay",
                    on_click=close_and_stay,
                    style=ft.ButtonStyle(color=SettingsViewColors.TEXT_SECONDARY),
                ),
                ft.ElevatedButton(
                    "Save & Leave",
                    on_click=save_and_leave,
                    style=ft.ButtonStyle(
                        color="#FFFFFF",
                        bgcolor=SettingsViewColors.SUCCESS,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=SettingsViewColors.BG_CARD,
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        safe_page_update(self.page)

    def reset_unsaved_state(self):
        """Reset trạng thái unsaved sau khi save hoặc load."""
        self._has_unsaved_changes = False
        if (
            self.excluded_field
            and self.gitignore_checkbox
            and self.security_check_checkbox
            and self.git_include_checkbox
        ):
            self._initial_values = {
                "excluded_folders": self.excluded_field.value or "",
                "use_gitignore": self.gitignore_checkbox.value or False,
                "enable_security_check": self.security_check_checkbox.value or False,
                "include_git_changes": self.git_include_checkbox.value or False,
            }
