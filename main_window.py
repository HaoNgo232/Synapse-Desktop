"""
Synapse Desktop - PySide6 Main Window Entry Point

Theme: Dark Mode OLED (Developer Tools Edition)
"""

import sys
import gc
from pathlib import Path
from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QFileDialog,
    QMenu,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Slot

from core.theme import ThemeColors
from core.theme_qss import generate_app_stylesheet
from core.utils.qt_utils import (
    run_on_main_thread,
    get_signal_bridge,
)
from core.utils.threading_utils import shutdown_all, set_active_view
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


class SynapseMainWindow(QMainWindow):
    """Main application window - PySide6 version."""

    def __init__(self) -> None:
        super().__init__()

        # Load custom fonts FIRST
        from core.theme import ThemeFonts
        from core.stylesheet import get_global_stylesheet

        ThemeFonts.load_fonts()

        self.workspace_path: Optional[Path] = None

        # Session restore data
        self._pending_session_restore: Optional[Dict[str, List[str]]] = None
        self._current_tab_index = 0

        # Memory monitor
        self._memory_monitor = get_memory_monitor()
        self._memory_monitor.on_update = self._on_memory_update

        # Setup window
        self.setWindowTitle("Synapse Desktop")
        self.setMinimumSize(800, 600)
        self.resize(1500, 1000)

        # Apply global stylesheet
        self.setStyleSheet(get_global_stylesheet())

        # Build UI
        self._build_ui()

        # Restore session
        self._restore_session()

        # Start memory monitoring
        self._memory_monitor.start()

    def _build_ui(self) -> None:
        """Xây dựng giao diện chính."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar: App title + Memory display
        top_bar = self._build_top_bar()
        main_layout.addWidget(top_bar)

        # Folder bar: Folder picker + Recent + Open button
        folder_bar = self._build_folder_bar()
        main_layout.addWidget(folder_bar)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Import views (lazy to avoid circular imports)
        from views.context_view_qt import ContextViewQt
        from views.apply_view_qt import ApplyViewQt
        from views.history_view_qt import HistoryViewQt
        from views.logs_view_qt import LogsViewQt
        from views.settings_view_qt import SettingsViewQt

        # Create views
        self.context_view = ContextViewQt(self._get_workspace_path)
        self.apply_view = ApplyViewQt(self._get_workspace_path)
        self.history_view = HistoryViewQt(self._on_reapply_from_history)
        self.logs_view = LogsViewQt()
        self.settings_view = SettingsViewQt(self._on_settings_changed)

        # Add tabs
        self.tab_widget.addTab(self.context_view, "Context")
        self.tab_widget.addTab(self.apply_view, "Apply")
        self.tab_widget.addTab(self.history_view, "History")
        self.tab_widget.addTab(self.logs_view, "Logs")
        self.tab_widget.addTab(self.settings_view, "Settings")

        main_layout.addWidget(self.tab_widget, stretch=1)

    def _build_top_bar(self) -> QFrame:
        """Build top bar với app title và memory display."""
        bar = QFrame()
        bar.setStyleSheet(f"background-color: {ThemeColors.BG_SURFACE};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(8)

        title_label = QLabel("Synapse Desktop")
        title_label.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(title_label)
        layout.addStretch()

        # Memory icon + text
        mem_icon = QLabel("🧠")
        mem_icon.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_MUTED};")
        layout.addWidget(mem_icon)

        self._memory_label = QLabel("Mem: --")
        self._memory_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};"
        )
        self._memory_label.setToolTip("Memory usage | Token cache | Files loaded")
        layout.addWidget(self._memory_label)

        # Clear memory button
        clear_btn = QToolButton()
        clear_btn.setText("🧹")
        clear_btn.setToolTip("Clear cache & free memory")
        clear_btn.clicked.connect(self._clear_memory)
        layout.addWidget(clear_btn)

        return bar

    def _build_folder_bar(self) -> QFrame:
        """Build folder bar với folder picker và recent folders."""
        bar = QFrame()
        bar.setStyleSheet(
            f"background-color: {ThemeColors.BG_PAGE}; "
            f"border-bottom: 1px solid {ThemeColors.BORDER};"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(12)

        # Folder icon
        folder_icon = QLabel("📁")
        folder_icon.setStyleSheet(f"color: {ThemeColors.PRIMARY}; font-size: 16px;")
        layout.addWidget(folder_icon)

        # Folder path text
        self._folder_path_label = QLabel("No folder selected")
        self._folder_path_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 13px; font-weight: 500;"
        )
        self._folder_path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self._folder_path_label, stretch=1)

        # Recent folders menu button
        self._recent_btn = QToolButton()
        self._recent_btn.setText("Recent")
        self._recent_btn.setToolTip("Recent Folders (Ctrl+R)")
        self._recent_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._recent_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recent_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {ThemeColors.BG_SURFACE};
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 500;
            }}
            QToolButton:hover {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border-color: {ThemeColors.BORDER_LIGHT};
            }}
            QToolButton::menu-indicator {{
                width: 0px;
            }}
        """)
        self._recent_menu = QMenu(self._recent_btn)
        self._recent_btn.setMenu(self._recent_menu)
        self._refresh_recent_folders_menu()
        layout.addWidget(self._recent_btn)

        # Open Folder button
        open_btn = QPushButton("📁 Open Folder")
        open_btn.setToolTip("Open workspace folder (Ctrl+O)")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
        """)
        open_btn.clicked.connect(self._open_folder_dialog)
        layout.addWidget(open_btn)

        return bar

    def _refresh_recent_folders_menu(self) -> None:
        """Refresh recent folders menu."""
        self._recent_menu.clear()
        recent = load_recent_folders()

        if not recent:
            action = self._recent_menu.addAction("No recent folders")
            action.setEnabled(False)
            return

        for folder_path in recent:
            display_name = get_folder_display_name(folder_path)
            action = self._recent_menu.addAction(display_name)
            # Capture folder_path bằng default argument
            action.triggered.connect(
                lambda checked=False, p=folder_path: self._open_recent_folder(p)
            )

    @Slot()
    def _open_folder_dialog(self) -> None:
        """Mở dialog chọn folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Workspace Folder",
            str(self.workspace_path or Path.home()),
        )
        if folder_path:
            self._set_workspace(Path(folder_path))

    def _open_recent_folder(self, folder_path: str) -> None:
        """Mở folder từ recent list."""
        path = Path(folder_path)
        if path.exists() and path.is_dir():
            self._set_workspace(path)

    def _set_workspace(self, path: Path) -> None:
        """Set workspace path và notify views."""
        self.workspace_path = path
        self._folder_path_label.setText(str(path))
        self._folder_path_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_PRIMARY}; font-size: 14px;"
        )

        # Save to recent
        add_recent_folder(str(path))
        self._refresh_recent_folders_menu()

        # Notify context view
        self.context_view.on_workspace_changed(path)

    def _get_workspace_path(self) -> Optional[Path]:
        """Getter cho workspace path."""
        return self.workspace_path

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change."""
        self._current_tab_index = index

        view_names = ["context", "apply", "history", "logs", "settings"]
        if 0 <= index < len(view_names):
            set_active_view(view_names[index])

        # Refresh History tab khi chọn (index = 2)
        if index == 2:
            self.history_view.on_view_activated()

        # Refresh Logs tab khi chọn (index = 3)
        if index == 3:
            self.logs_view.on_view_activated()

    def _on_settings_changed(self) -> None:
        """Xử lý khi settings thay đổi."""
        if self.workspace_path:
            self.context_view.on_workspace_changed(self.workspace_path)

    def _on_reapply_from_history(self, opx_content: str) -> None:
        """Callback khi user muốn re-apply OPX từ History."""
        self.apply_view.set_opx_content(opx_content)
        self.tab_widget.setCurrentIndex(1)  # Switch to Apply tab

    def _on_memory_update(self, stats: MemoryStats) -> None:
        """Callback khi memory monitor có update. Chạy từ background thread."""

        def update_ui():
            display_text = format_memory_display(stats)
            self._memory_label.setText(display_text)

            if stats.warning and "Critical" in stats.warning:
                self._memory_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.ERROR};"
                )
            elif stats.warning:
                self._memory_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.WARNING};"
                )
            else:
                self._memory_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};"
                )

        run_on_main_thread(update_ui)

    @Slot()
    def _clear_memory(self) -> None:
        """Clear cache và giải phóng memory."""
        try:
            # Clear token cache từ FileTreeComponent
            if (
                hasattr(self.context_view, "file_tree_widget")
                and self.context_view.file_tree_widget
            ):
                self.context_view.file_tree_widget.clear_token_cache()

            gc.collect()

            stats = self._memory_monitor.get_current_stats()
            self._memory_label.setText(format_memory_display(stats))
            self._memory_label.setStyleSheet(
                f"font-size: 11px; color: {ThemeColors.SUCCESS};"
            )

            from core.logging_config import log_info

            log_info(f"Memory cleared. Current usage: {stats.rss_mb:.0f}MB")
        except Exception as e:
            from core.logging_config import log_error

            log_error(f"Error clearing memory: {e}")

    def _restore_session(self) -> None:
        """
        Khôi phục session từ lần mở trước.

        CLEAN SESSION MODE: Chỉ restore workspace path (từ recent folders) và instructions text.
        Các state khác (selected files, expanded folders, active tab) sẽ bị clear để bắt đầu fresh.
        """
        from services.recent_folders import load_recent_folders

        session = load_session_state()

        # Restore workspace path từ recent folders (workspace gần nhất)
        recent_folders = load_recent_folders()
        if recent_folders:
            workspace = Path(recent_folders[0])
            if workspace.exists() and workspace.is_dir():
                self.workspace_path = workspace
                self._folder_path_label.setText(str(workspace))
                self._folder_path_label.setStyleSheet(
                    f"color: {ThemeColors.TEXT_PRIMARY}; font-size: 14px;"
                )

                # Notify context view to load tree (NO pending restore - fresh start)
                self.context_view.on_workspace_changed(workspace)

        # Restore instructions text only (nếu có session)
        if session and session.instructions_text:
            self.context_view.set_instructions_text(session.instructions_text)

        # Restore window size (nếu có session)
        if session and session.window_width and session.window_height:
            self.resize(session.window_width, session.window_height)

    def _save_session(self) -> None:
        """Lưu session hiện tại."""
        state = SessionState(
            workspace_path=str(self.workspace_path) if self.workspace_path else None,
            selected_files=self.context_view.get_selected_paths(),
            expanded_folders=self.context_view.get_expanded_paths(),
            instructions_text=self.context_view.get_instructions_text(),
            active_tab_index=self._current_tab_index,
            window_width=self.width(),
            window_height=self.height(),
        )
        save_session_state(state)

    def closeEvent(self, event) -> None:
        """Xử lý khi đóng app."""
        from core.utils.file_scanner import stop_scanning
        from services.token_display import stop_token_counting

        stop_scanning()
        stop_token_counting()
        shutdown_all()

        self._save_session()
        self._memory_monitor.stop()

        # Cleanup views
        self.context_view.cleanup()

        # Flush logs
        from core.logging_config import flush_logs, cleanup_old_logs

        flush_logs()
        cleanup_old_logs(max_age_days=7)

        event.accept()


def main() -> None:
    """Entry point."""
    from config.paths import ensure_app_directories

    ensure_app_directories()

    app = QApplication(sys.argv)
    app.setApplicationName("Synapse Desktop")
    app.setOrganizationName("Synapse")

    # Apply global dark stylesheet
    app.setStyleSheet(generate_app_stylesheet())

    # Initialize global signal bridge on main thread
    get_signal_bridge()

    window = SynapseMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
