"""
Overwrite Desktop - Main Application Entry Point

Flet-based desktop app ke thua tinh nang Copy Context va OPX Apply
tu Overwrite VS Code extension.

Theme: Dark Mode OLED (Developer Tools Edition)
"""

import flet as ft
from pathlib import Path
from typing import Optional

from views.context_view import ContextView
from views.apply_view import ApplyView
from views.settings_view import SettingsView
from views.history_view import HistoryView
from views.logs_view import LogsView
from core.theme import ThemeColors
from services.recent_folders import (
    load_recent_folders,
    add_recent_folder,
    get_folder_display_name,
)
from services.session_state import (
    SessionState,
    save_session_state,
    load_session_state,
)
from services.memory_monitor import (
    get_memory_monitor,
    format_memory_display,
    MemoryStats,
)


class OverwriteApp:
    """Main application class"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.workspace_path: Optional[Path] = None

        # Memory monitor
        self._memory_monitor = get_memory_monitor()
        self._memory_monitor.on_update = self._on_memory_update
        self._memory_text: Optional[ft.Text] = None

        # Apply Swiss Professional Light Theme
        self._apply_theme()

        # Configure page
        self.page.title = "Overwrite Desktop"
        self.page.padding = 0

        # Resize handler for responsive layout
        self.page.on_resized = self._on_resize

        # Window config
        self.page.window.min_width = 800
        self.page.window.min_height = 600
        self.page.window.width = 1500
        self.page.window.height = 1000

        # Keyboard shortcuts
        self.page.on_keyboard_event = self._on_keyboard_event

        # Drag and drop support (Tắt tạm thời do Flet chưa hỗ trợ API này trong version hiện tại)
        # self.page.on_drop = self._on_drop

        # Build UI
        self._build_ui()

        # Restore previous session
        self._restore_session()

        # Save session on close
        self.page.on_close = self._on_app_close

    def _on_resize(self, e):
        """Handle window resize"""
        if hasattr(self, "context_view"):
            # Pass width to context view for responsive layout
            width = self.page.window.width
            # Fallback if width is None/0 (sometimes happens on init)
            if not width:
                width = 1000
            self.context_view.update_layout(width)

    def _apply_theme(self):
        """Apply Dark Mode OLED Theme for Developer Tools"""
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = ThemeColors.BG_PAGE

        self.page.theme = ft.Theme(
            color_scheme_seed=ThemeColors.PRIMARY,
            color_scheme=ft.ColorScheme(
                primary=ThemeColors.PRIMARY,
                on_primary="#FFFFFF",
                secondary=ThemeColors.TEXT_SECONDARY,
                on_secondary="#FFFFFF",
                surface=ThemeColors.BG_SURFACE,
                on_surface=ThemeColors.TEXT_PRIMARY,
                background=ThemeColors.BG_PAGE,
                on_background=ThemeColors.TEXT_PRIMARY,
                error=ThemeColors.ERROR,
                on_error="#FFFFFF",
                outline=ThemeColors.BORDER,
            ),
        )

    def _build_ui(self):
        """Xay dung giao dien chinh voi Swiss Professional styling"""

        # Header voi folder picker
        self.folder_path_text = ft.Text(
            "No folder selected",
            size=14,
            color=ThemeColors.TEXT_MUTED,
            expand=True,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        folder_picker = ft.FilePicker(on_result=self._on_folder_picked)
        self.page.overlay.append(folder_picker)

        # Recent folders dropdown
        self.recent_folders_btn = ft.PopupMenuButton(
            icon=ft.Icons.HISTORY,
            icon_color=ThemeColors.TEXT_SECONDARY,
            tooltip="Recent Folders",
            items=self._build_recent_folders_menu(),
        )

        # Memory display
        self._memory_text = ft.Text(
            "Mem: --",
            size=11,
            color=ThemeColors.TEXT_MUTED,
            tooltip="Memory usage | Token cache | Files loaded",
        )

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.FOLDER_OPEN, color=ThemeColors.PRIMARY, size=20),
                    self.folder_path_text,
                    self.recent_folders_btn,
                    ft.ElevatedButton(
                        "Open Folder",
                        icon=ft.Icons.FOLDER,
                        style=ft.ButtonStyle(
                            color="#FFFFFF",
                            bgcolor=ThemeColors.PRIMARY,
                        ),
                        on_click=lambda _: folder_picker.get_directory_path(
                            dialog_title="Select Workspace Folder"
                        ),
                    ),
                    ft.Container(width=20),  # Spacer
                    ft.Icon(ft.Icons.MEMORY, size=14, color=ThemeColors.TEXT_MUTED),
                    self._memory_text,
                ],
                spacing=12,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=12),
            bgcolor=ThemeColors.BG_SURFACE,
            border=ft.border.only(bottom=ft.BorderSide(1, ThemeColors.BORDER)),
        )

        # Views
        self.context_view = ContextView(self.page, self._get_workspace_path)
        self.apply_view = ApplyView(self.page, self._get_workspace_path)
        self.settings_view = SettingsView(self.page, self._on_settings_changed)
        self.history_view = HistoryView(self.page, self._on_reapply_from_history)
        self.logs_view = LogsView(self.page)

        # Tabs voi Swiss styling
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            indicator_color=ThemeColors.PRIMARY,
            indicator_tab_size=True,
            label_color=ThemeColors.TEXT_PRIMARY,
            unselected_label_color=ThemeColors.TEXT_SECONDARY,
            divider_color=ThemeColors.BORDER,
            on_change=self._on_tab_changed,
            tabs=[
                ft.Tab(
                    text="Context",
                    icon=ft.Icons.CONTENT_COPY,
                    content=self.context_view.build(),
                ),
                ft.Tab(
                    text="Apply",
                    icon=ft.Icons.PLAY_ARROW,
                    content=self.apply_view.build(),
                ),
                ft.Tab(
                    text="History",
                    icon=ft.Icons.HISTORY,
                    content=self.history_view.build(),
                ),
                ft.Tab(
                    text="Logs",
                    icon=ft.Icons.TERMINAL,
                    content=self.logs_view.build(),
                ),
                ft.Tab(
                    text="Settings",
                    icon=ft.Icons.SETTINGS,
                    content=self.settings_view.build(),
                ),
            ],
            expand=True,
        )

        tabs = self.tabs

        # Layout
        self.page.add(ft.Column([header, tabs], spacing=0, expand=True))

        # Start memory monitoring
        self._memory_monitor.start()

    def _build_recent_folders_menu(self) -> list:
        """Build menu items cho recent folders dropdown"""
        recent = load_recent_folders()

        if not recent:
            return [
                ft.PopupMenuItem(
                    text="No recent folders",
                    disabled=True,
                )
            ]

        items = []
        for folder_path in recent:
            display_name = get_folder_display_name(folder_path)
            # Dùng IIFE pattern để capture folder_path tại thời điểm tạo
            # Tránh lỗi late binding của closure trong loop
            items.append(
                ft.PopupMenuItem(
                    text=display_name,
                    on_click=(lambda p: lambda e: self._open_recent_folder(p))(
                        folder_path
                    ),
                )
            )

        return items

    def _open_recent_folder(self, folder_path: str):
        """Mở folder từ recent list"""
        path = Path(folder_path)
        if path.exists() and path.is_dir():
            self.workspace_path = path
            self.folder_path_text.value = str(self.workspace_path)
            self.folder_path_text.color = ThemeColors.TEXT_PRIMARY

            # Update recent list
            add_recent_folder(folder_path)
            self._refresh_recent_folders_menu()

            self.page.update()
            self.context_view.on_workspace_changed(self.workspace_path)

    def _refresh_recent_folders_menu(self):
        """Refresh recent folders menu"""
        if hasattr(self, "recent_folders_btn"):
            self.recent_folders_btn.items = self._build_recent_folders_menu()

    def _on_folder_picked(self, e: ft.FilePickerResultEvent):
        """Xu ly khi user chon folder"""
        if e.path:
            self.workspace_path = Path(e.path)
            self.folder_path_text.value = str(self.workspace_path)
            self.folder_path_text.color = ThemeColors.TEXT_PRIMARY

            # Save to recent folders
            add_recent_folder(e.path)
            self._refresh_recent_folders_menu()

            self.page.update()

            # Notify views
            self.context_view.on_workspace_changed(self.workspace_path)

    def _on_settings_changed(self):
        """Xu ly khi settings thay doi - refresh file tree"""
        if self.workspace_path:
            self.context_view.on_workspace_changed(self.workspace_path)

    def _get_workspace_path(self) -> Optional[Path]:
        """Getter cho workspace path"""
        return self.workspace_path

    def _restore_session(self):
        """Khôi phục session từ lần mở trước"""
        session = load_session_state()
        if not session:
            return

        # Restore workspace
        if session.workspace_path:
            workspace = Path(session.workspace_path)
            if workspace.exists() and workspace.is_dir():
                self.workspace_path = workspace
                self.folder_path_text.value = str(self.workspace_path)
                self.folder_path_text.color = ThemeColors.TEXT_PRIMARY

                # Notify context view to load tree
                self.context_view.on_workspace_changed(self.workspace_path)

                # Restore selected files after tree is loaded
                if session.selected_files and self.context_view.file_tree_component:
                    self.context_view.file_tree_component.selected_paths = set(
                        f for f in session.selected_files if Path(f).exists()
                    )
                    self.context_view.file_tree_component._render_tree()
                    self.context_view._update_token_count()

                # Restore expanded folders
                if session.expanded_folders and self.context_view.file_tree_component:
                    self.context_view.file_tree_component.expanded_paths = set(
                        f for f in session.expanded_folders if Path(f).exists()
                    )
                    self.context_view.file_tree_component._render_tree()

        # Restore instructions
        if session.instructions_text and self.context_view.instructions_field:
            self.context_view.instructions_field.value = session.instructions_text

        # Restore window size
        if session.window_width and session.window_height:
            self.page.window.width = session.window_width
            self.page.window.height = session.window_height

        self.page.update()

    def _save_session(self):
        """Lưu session hiện tại"""
        state = SessionState(
            workspace_path=str(self.workspace_path) if self.workspace_path else None,
            selected_files=(
                list(self.context_view.file_tree_component.selected_paths)
                if self.context_view.file_tree_component
                else []
            ),
            expanded_folders=(
                list(self.context_view.file_tree_component.expanded_paths)
                if self.context_view.file_tree_component
                else []
            ),
            instructions_text=(
                (self.context_view.instructions_field.value or "")
                if self.context_view.instructions_field
                else ""
            ),
            active_tab_index=0,  # TODO: track active tab
            window_width=(
                int(self.page.window.width) if self.page.window.width else None
            ),
            window_height=(
                int(self.page.window.height) if self.page.window.height else None
            ),
        )
        save_session_state(state)

    def _on_app_close(self, e):
        """Xử lý khi đóng app - lưu session và cleanup"""
        self._save_session()

        # Stop memory monitor
        self._memory_monitor.stop()

        # Cleanup file tree resources
        if hasattr(self, "context_view") and self.context_view:
            self.context_view.cleanup()

        # Flush and cleanup logs
        from core.logging_config import flush_logs, cleanup_old_logs

        flush_logs()
        cleanup_old_logs(max_age_days=7)

    def _on_memory_update(self, stats: MemoryStats):
        """
        Callback khi memory monitor có update mới.
        Cập nhật memory display trong header.

        Args:
            stats: MemoryStats object với thông tin memory usage
        """
        if not self._memory_text:
            return

        try:
            # Update memory display text
            display_text = format_memory_display(stats)
            self._memory_text.value = display_text

            # Change color based on warning level
            if stats.warning and "Critical" in stats.warning:
                self._memory_text.color = ThemeColors.ERROR
            elif stats.warning:
                self._memory_text.color = ThemeColors.WARNING
            else:
                self._memory_text.color = ThemeColors.TEXT_MUTED

            # Update UI (safe call from background thread)
            self.page.update()
        except Exception:
            pass  # Ignore errors during update

    # def _on_drop(self, e: ft.DropEvent):
    #     """Handle drag and drop of folders"""
    #     if e.files:
    #         # Get first dropped item
    #         dropped_path = Path(e.files[0].path)

    #         # Check if it's a directory
    #         if dropped_path.is_dir():
    #             self.workspace_path = dropped_path
    #             self.folder_path_text.value = str(self.workspace_path)
    #             self.folder_path_text.color = ThemeColors.TEXT_PRIMARY

    #             # Save to recent folders
    #             add_recent_folder(str(dropped_path))
    #             self._refresh_recent_folders_menu()

    #             self.page.update()
    #             self.context_view.on_workspace_changed(self.workspace_path)
    #         else:
    #             # If file was dropped, use its parent directory
    #             parent_dir = dropped_path.parent
    #             if parent_dir.is_dir():
    #                 self.workspace_path = parent_dir
    #                 self.folder_path_text.value = str(self.workspace_path)
    #                 self.folder_path_text.color = ThemeColors.TEXT_PRIMARY

    #                 add_recent_folder(str(parent_dir))
    #                 self._refresh_recent_folders_menu()

    #                 self.page.update()
    #                 self.context_view.on_workspace_changed(self.workspace_path)

    def _on_tab_changed(self, e):
        """Handle tab change - refresh History/Logs khi chọn"""
        if e.control.selected_index == 2:  # History tab
            self.history_view.on_view_activated()
        elif e.control.selected_index == 3:  # Logs tab
            self.logs_view.on_view_activated()

    def _on_reapply_from_history(self, opx_content: str):
        """Callback khi user muốn re-apply OPX từ History"""
        # Fill OPX vào Apply tab
        if self.apply_view.opx_input:
            self.apply_view.opx_input.value = opx_content
        # Chuyển sang Apply tab
        self.tabs.selected_index = 1
        self.page.update()

    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        """
        Handle keyboard shortcuts.

        Shortcuts:
        - Ctrl+Shift+C: Copy Context
        - Ctrl+Shift+O: Copy + OPX
        - Ctrl+R: Refresh file tree
        - Ctrl+F: Focus search field
        - Escape: Clear search
        """
        # Let file tree component handle its own keyboard events first
        if hasattr(self, "context_view") and self.context_view.file_tree_component:
            if self.context_view.file_tree_component.handle_keyboard_event(e):
                self.page.update()
                return

        if e.ctrl and e.shift and e.key == "C":
            # Copy Context
            if hasattr(self, "context_view"):
                self.context_view._copy_context(include_xml=False)
        elif e.ctrl and e.shift and e.key == "O":
            # Copy + OPX
            if hasattr(self, "context_view"):
                self.context_view._copy_context(include_xml=True)
        elif e.ctrl and e.key == "R":
            # Refresh tree
            if hasattr(self, "context_view"):
                self.context_view._refresh_tree()
        elif e.ctrl and e.key == "F":
            # Focus search field
            if hasattr(self, "context_view") and self.context_view.file_tree_component:
                search_field = self.context_view.file_tree_component.search_field
                if search_field:
                    search_field.focus()
                    self.page.update()


def main(page: ft.Page):
    """Entry point"""
    OverwriteApp(page)


if __name__ == "__main__":
    ft.app(target=main)
