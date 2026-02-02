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


class SettingsView:
    """View cho Settings tab"""

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
        """Build UI cho Settings view voi Swiss Professional styling"""

        settings = load_settings()

        # Excluded folders textarea
        # Excluded folders textarea - Fix: Removed label to prevent overlap, better styling
        self.excluded_field = ft.TextField(
            multiline=True,
            min_lines=15,
            max_lines=15,
            value=settings.get("excluded_folders", ""),
            hint_text="node_modules\ndist\nbuild\n__pycache__",
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            text_style=ft.TextStyle(
                color=ThemeColors.TEXT_PRIMARY, size=13, font_family="monospace"
            ),
            content_padding=15,
            cursor_color=ThemeColors.PRIMARY,
            bgcolor=ThemeColors.BG_PAGE,
            on_change=lambda e: self._mark_changed(),
        )

        # Respect .gitignore checkbox
        self.gitignore_checkbox = ft.Checkbox(
            label="Respect .gitignore",
            value=settings.get("use_gitignore", True),
            active_color=ThemeColors.PRIMARY,
            check_color="#FFFFFF",
            label_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY, size=14),
            on_change=lambda e: self._mark_changed(),
        )

        # Security Check checkbox
        self.security_check_checkbox = ft.Checkbox(
            label="Enable Security Check",
            value=settings.get("enable_security_check", True),
            active_color=ThemeColors.WARNING,
            check_color="#FFFFFF",
            label_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY, size=14),
            on_change=lambda e: self._mark_changed(),
        )

        # Git Include Checkbox
        self.git_include_checkbox = ft.Checkbox(
            label="Include Git Diff/Log",
            value=settings.get("include_git_changes", True),
            active_color=ThemeColors.PRIMARY,
            check_color="#FFFFFF",
            label_style=ft.TextStyle(color=ThemeColors.TEXT_PRIMARY, size=14),
            on_change=lambda e: self._mark_changed(),
        )

        # Store initial values for comparison
        self._initial_values = {
            "excluded_folders": settings.get("excluded_folders", ""),
            "use_gitignore": settings.get("use_gitignore", True),
            "enable_security_check": settings.get("enable_security_check", True),
            "include_git_changes": settings.get("include_git_changes", True),
        }
        self._has_unsaved_changes = False

        # Status
        self.status_text = ft.Text("", size=12)

        return ft.Container(
            content=ft.Column(
                [
                    # Header
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.SETTINGS,
                                color=ThemeColors.TEXT_PRIMARY,
                                size=24,
                            ),
                            ft.Text(
                                "Settings",
                                size=20,
                                weight=ft.FontWeight.W_600,
                                color=ThemeColors.TEXT_PRIMARY,
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Divider(height=1, color=ThemeColors.BORDER),
                    ft.Container(height=16),
                    # Main content in Grid Layout
                    ft.Container(
                        content=ft.ResponsiveRow(
                            [
                                # LEFT COLUMN: Options & Controls
                                ft.Column(
                                    col={"sm": 12, "md": 5},
                                    controls=[
                                        # File Tree Options
                                        ft.Text(
                                            "File Tree Options",
                                            weight=ft.FontWeight.W_600,
                                            size=14,
                                            color=ThemeColors.TEXT_PRIMARY,
                                        ),
                                        ft.Container(height=4),
                                        self.gitignore_checkbox,
                                        ft.Text(
                                            "When enabled, files matching .gitignore patterns will be hidden.",
                                            size=12,
                                            color=ThemeColors.TEXT_SECONDARY,
                                        ),
                                        ft.Container(height=24),
                                        # Git Options
                                        ft.Text(
                                            "Context Generation",
                                            weight=ft.FontWeight.W_600,
                                            size=14,
                                            color=ThemeColors.TEXT_PRIMARY,
                                        ),
                                        ft.Container(height=4),
                                        self.git_include_checkbox,
                                        ft.Text(
                                            "Include git diffs and recent logs in prompt.",
                                            size=12,
                                            color=ThemeColors.TEXT_SECONDARY,
                                        ),
                                        ft.Container(height=24),
                                        # Security Check
                                        ft.Text(
                                            "Security",
                                            weight=ft.FontWeight.W_600,
                                            size=14,
                                            color=ThemeColors.TEXT_PRIMARY,
                                        ),
                                        ft.Container(height=4),
                                        self.security_check_checkbox,
                                        ft.Text(
                                            "When enabled, scan for secrets (API Keys, etc) before copying.",
                                            size=12,
                                            color=ThemeColors.TEXT_SECONDARY,
                                        ),
                                        ft.Container(height=24),
                                        # Presets
                                        ft.Text(
                                            "Quick Presets",
                                            weight=ft.FontWeight.W_600,
                                            size=14,
                                            color=ThemeColors.TEXT_PRIMARY,
                                        ),
                                        ft.Container(height=4),
                                        ft.Text(
                                            "Load standard exclusion patterns:",
                                            size=12,
                                            color=ThemeColors.TEXT_SECONDARY,
                                        ),
                                        ft.Container(height=8),
                                        ft.Dropdown(
                                            options=[
                                                ft.dropdown.Option(key=name, text=name)
                                                for name in PRESET_PROFILES.keys()
                                            ],
                                            on_select=lambda e: self._load_preset(
                                                e.control.value
                                            ),
                                            hint_text="Select a preset...",
                                            text_size=13,
                                            border_color=ThemeColors.BORDER,
                                            focused_border_color=ThemeColors.PRIMARY,
                                            dense=True,
                                            width=220,  # Compact fixed width
                                        ),
                                        ft.Container(height=32),
                                        # Action Buttons Grouped
                                        ft.ElevatedButton(
                                            "Save Settings",
                                            icon=ft.Icons.SAVE,
                                            on_click=lambda _: self._save_settings(),
                                            style=ft.ButtonStyle(
                                                color="#FFFFFF",
                                                bgcolor=ThemeColors.SUCCESS,
                                                shape=ft.RoundedRectangleBorder(
                                                    radius=6
                                                ),
                                            ),
                                            width=float("inf"),  # Full width
                                        ),
                                        ft.Container(height=8),
                                        ft.Row(
                                            [
                                                ft.OutlinedButton(
                                                    "Reset",
                                                    icon=ft.Icons.RESTORE,
                                                    on_click=lambda _: self._reset_settings(),
                                                    style=ft.ButtonStyle(
                                                        color=ThemeColors.TEXT_PRIMARY,
                                                        side=ft.BorderSide(
                                                            1, ThemeColors.BORDER
                                                        ),
                                                    ),
                                                    expand=True,
                                                ),
                                                ft.OutlinedButton(
                                                    "Export",
                                                    icon=ft.Icons.DOWNLOAD,
                                                    on_click=lambda _: self._export_settings(),
                                                    style=ft.ButtonStyle(
                                                        color=ThemeColors.TEXT_SECONDARY,
                                                        side=ft.BorderSide(
                                                            1, ThemeColors.BORDER
                                                        ),
                                                    ),
                                                    expand=True,
                                                ),
                                            ],
                                            spacing=8,
                                        ),
                                        ft.OutlinedButton(
                                            "Import Settings",
                                            icon=ft.Icons.UPLOAD,
                                            on_click=lambda _: self._import_settings(),
                                            style=ft.ButtonStyle(
                                                color=ThemeColors.TEXT_SECONDARY,
                                                side=ft.BorderSide(
                                                    1, ThemeColors.BORDER
                                                ),
                                            ),
                                            width=float("inf"),
                                        ),
                                        ft.Container(height=16),
                                        self.status_text,
                                    ],
                                ),
                                # RIGHT COLUMN: Excluded Folders Input
                                ft.Column(
                                    col={"sm": 12, "md": 7},
                                    controls=[
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    "Excluded Folders",
                                                    weight=ft.FontWeight.W_600,
                                                    size=14,
                                                    color=ThemeColors.TEXT_PRIMARY,
                                                ),
                                                ft.Container(expand=True),
                                                ft.IconButton(
                                                    icon=ft.Icons.REFRESH,
                                                    icon_size=18,
                                                    icon_color=ThemeColors.TEXT_SECONDARY,
                                                    tooltip="Reload from file",
                                                    on_click=lambda _: self._reload_settings(),
                                                ),
                                            ],
                                        ),
                                        ft.Text(
                                            "One pattern per line. Lines starting with # are comments.",
                                            size=12,
                                            color=ThemeColors.TEXT_SECONDARY,
                                        ),
                                        ft.Container(height=8),
                                        self.excluded_field,
                                    ],
                                ),
                            ],
                            spacing=40,
                        ),
                        padding=24,
                        bgcolor=ThemeColors.BG_SURFACE,
                        border=ft.border.all(1, ThemeColors.BORDER),
                        border_radius=8,
                    ),
                    ft.Container(height=16),
                    # Session section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "Session",
                                    weight=ft.FontWeight.W_600,
                                    size=14,
                                    color=ThemeColors.TEXT_PRIMARY,
                                ),
                                ft.Container(height=8),
                                ft.Row(
                                    [
                                        ft.Text(
                                            "Your workspace and selected files are automatically saved when closing the app.",
                                            size=12,
                                            color=ThemeColors.TEXT_SECONDARY,
                                            expand=True,
                                        ),
                                        ft.OutlinedButton(
                                            "Clear Session",
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            on_click=lambda _: self._clear_session(),
                                            tooltip="Clear saved workspace and selections",
                                            style=ft.ButtonStyle(
                                                color=ThemeColors.TEXT_SECONDARY,
                                                side=ft.BorderSide(
                                                    1, ThemeColors.BORDER
                                                ),
                                            ),
                                        ),
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
                    # Info section
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.INFO_OUTLINE,
                                    color=ThemeColors.TEXT_SECONDARY,
                                    size=18,
                                ),
                                ft.Text(
                                    "Default excluded: .git, .hg, .svn (Version control folders are always excluded)",
                                    size=12,
                                    color=ThemeColors.TEXT_SECONDARY,
                                ),
                            ],
                            spacing=8,
                        ),
                        bgcolor=ThemeColors.BG_ELEVATED,
                        padding=12,
                        border_radius=6,
                        border=ft.border.all(1, ThemeColors.BORDER),
                    ),
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=20,
            expand=True,
            bgcolor=ThemeColors.BG_PAGE,
        )

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
            self._show_status("Settings saved!")
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

        # Reset UI but don't save yet to match previous behavior
        # But wait, logic changed. Let's just load defaults from manager manually?
        # Actually default in manager is internal.
        # Replicating defaults here for UI consistency or exposing from manager.
        # Let's keep hardcoded here for now as view-specific defaults if needed,
        # or better, just rely on visual reset.

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
        self.status_text.color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
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

        Args:
            on_discard: Callback khi user chọn discard changes
            on_cancel: Callback khi user chọn cancel (ở lại Settings)
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
                color=ThemeColors.WARNING,
            ),
            content=ft.Text(
                "You have unsaved changes in Settings. What would you like to do?",
                size=14,
            ),
            actions=[
                ft.TextButton(
                    "Discard",
                    on_click=close_and_discard,
                    style=ft.ButtonStyle(color=ThemeColors.ERROR),
                ),
                ft.TextButton(
                    "Stay",
                    on_click=close_and_stay,
                    style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY),
                ),
                ft.ElevatedButton(
                    "Save & Leave",
                    on_click=save_and_leave,
                    style=ft.ButtonStyle(
                        color="#FFFFFF",
                        bgcolor=ThemeColors.SUCCESS,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
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
