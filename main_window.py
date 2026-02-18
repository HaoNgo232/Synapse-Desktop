"""
Synapse Desktop — PySide6 Main Window Entry Point

Phase 1 Redesign: Global Layout + Theme System + Tab Bar + Status Bar
Design System: Dark theme inspired by VS Code / JetBrains
"""

import sys
import gc
import subprocess
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
    QStatusBar,
)
from PySide6.QtCore import Qt, Slot, QTimer, QSize
from PySide6.QtGui import QIcon

from core.theme import ThemeColors, ThemeFonts, apply_theme
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


# ── Tab configuration: icon (emoji) + label ───────────────────────
_TAB_CONFIG = [
    ("📁", "Context"),
    ("⚡", "Apply"),
    ("🕐", "History"),
    ("📋", "Logs"),
    ("⚙️", "Settings"),
]


class SynapseMainWindow(QMainWindow):
    """Main application window — Phase 1 redesigned."""

    APP_VERSION = "1.0.0"

    def __init__(self) -> None:
        super().__init__()

        # Load custom fonts FIRST
        ThemeFonts.load_fonts()

        self.workspace_path: Optional[Path] = None

        # Session restore data
        self._pending_session_restore: Optional[Dict[str, List[str]]] = None
        self._current_tab_index = 0

        # Memory monitor
        self._memory_monitor = get_memory_monitor()
        self._memory_monitor.on_update = self._on_memory_update

        # Setup window
        self._update_window_title()
        self.setMinimumSize(900, 640)
        self.resize(1500, 1000)

        # Build UI
        self._build_ui()

        # Khoi tao Global Toast Notification System
        from components.toast_qt import init_toast_manager

        self._toast_manager = init_toast_manager(self)

        # Keep status footer metrics fresh without coupling to view internals.
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1200)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start()

        # Restore session
        self._restore_session()

        # Start memory monitoring
        self._memory_monitor.start()

    # ── Window title (dynamic) ────────────────────────────────────
    def _update_window_title(self) -> None:
        """Set window title: 'Synapse Desktop — [Folder Name]'."""
        if self.workspace_path:
            self.setWindowTitle(f"Synapse Desktop — {self.workspace_path.name}")
        else:
            self.setWindowTitle("Synapse Desktop — No project open")

    # ── Build UI ──────────────────────────────────────────────────
    def _build_ui(self) -> None:
        """Build the main UI: header → tabs → content → status bar."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1) Top bar: app branding + folder path + memory + actions
        top_bar = self._build_top_bar()
        main_layout.addWidget(top_bar)

        # 2) Tab widget with icon+text tabs
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

        # Add tabs with icon + text
        views = [
            self.context_view,
            self.apply_view,
            self.history_view,
            self.logs_view,
            self.settings_view,
        ]
        for (icon, label), view in zip(_TAB_CONFIG, views):
            self.tab_widget.addTab(view, f"{icon}  {label}")

        main_layout.addWidget(self.tab_widget, stretch=1)

        # 3) Status bar (footer)
        self._build_status_bar()

    # ── Top Bar ───────────────────────────────────────────────────
    def _build_top_bar(self) -> QFrame:
        """
        Build the unified top bar (48px height):
        [App Icon + "Synapse"] — [Breadcrumb path] — [RAM] — [Recent ▾] [Open Folder]
        """
        bar = QFrame()
        bar.setFixedHeight(48)
        bar.setStyleSheet(
            f"background-color: {ThemeColors.BG_SURFACE};"
            f"border-bottom: 1px solid {ThemeColors.BORDER};"
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # ── App branding ──
        app_icon = QLabel("💎")
        app_icon.setStyleSheet("font-size: 18px;")
        app_icon.setToolTip("Synapse Desktop")
        layout.addWidget(app_icon)

        app_title = QLabel("Synapse")
        app_title.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_SUBTITLE}px; "
            f"font-weight: 700; "
            f"color: {ThemeColors.TEXT_PRIMARY}; "
            f"letter-spacing: 0.5px;"
        )
        layout.addWidget(app_title)

        # ── Separator ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(24)
        sep.setStyleSheet(f"background-color: {ThemeColors.BORDER}; max-width: 1px;")
        layout.addWidget(sep)

        # ── Folder breadcrumb (mono font) ──
        folder_icon = QLabel("📁")
        folder_icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(folder_icon)

        self._folder_path_label = QLabel("No folder selected")
        self._folder_path_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        self._folder_path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._folder_path_label.setToolTip("Current workspace folder")
        layout.addWidget(self._folder_path_label, stretch=1)

        # ── Memory indicator (compact) ──
        self._memory_label = QLabel("🧠 --")
        self._memory_label.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"color: {ThemeColors.TEXT_MUTED};"
        )
        self._memory_label.setToolTip("Memory usage | Token cache | Files loaded")
        layout.addWidget(self._memory_label)

        # ── Clear memory button ──
        clear_btn = QToolButton()
        clear_btn.setText("🧹")
        clear_btn.setToolTip("Clear cache & free memory")
        clear_btn.setStyleSheet(
            f"QToolButton {{ font-size: 14px; padding: 4px 6px; border-radius: 4px; }}"
            f"QToolButton:hover {{ background-color: {ThemeColors.BG_ELEVATED}; }}"
        )
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_memory)
        layout.addWidget(clear_btn)

        # ── Recent folders button (outline style with dropdown) ──
        assets_dir = Path(__file__).parent / "assets"
        self._recent_btn = QToolButton()
        self._recent_btn.setIcon(QIcon(str(assets_dir / "clock-arrow-down.svg")))
        self._recent_btn.setIconSize(QSize(18, 18))
        self._recent_btn.setToolTip("Recent folders (Ctrl+R)")
        self._recent_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._recent_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recent_btn.setStyleSheet(
            f"""
            QToolButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: {ThemeFonts.SIZE_BODY // 2}px;
                padding: 6px 10px;
                font-size: {ThemeFonts.SIZE_BODY}px;
                font-weight: 500;
            }}
            QToolButton:hover {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border-color: {ThemeColors.BORDER_LIGHT};
            }}
            QToolButton::menu-indicator {{ width: 0px; }}
        """
        )
        self._recent_menu = QMenu(self._recent_btn)
        self._recent_btn.setMenu(self._recent_menu)
        self._refresh_recent_folders_menu()
        layout.addWidget(self._recent_btn)

        # ── Open Folder button (primary accent) ──
        open_btn = QPushButton("📁 Open Folder")
        open_btn.setToolTip("Open workspace folder (Ctrl+O)")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setProperty("class", "primary")
        open_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-size: {ThemeFonts.SIZE_BODY}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
        """
        )
        open_btn.clicked.connect(self._open_folder_dialog)
        layout.addWidget(open_btn)

        return bar

    # ── Status Bar (Footer 28-32px) ──────────────────────────────
    def _build_status_bar(self) -> None:
        """
        Build the status bar footer:
        [Workspace path] — [Git branch] — [Version]
        """
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Workspace path
        self._status_workspace = QLabel("No workspace")
        self._status_workspace.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        status_bar.addWidget(self._status_workspace, stretch=1)

        # Git branch
        self._status_git = QLabel("")
        self._status_git.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        status_bar.addWidget(self._status_git)
        self._status_git.setVisible(False)

        # Token summary (selected files + token total)
        self._status_tokens = QLabel("0 files | 0 tokens")
        self._status_tokens.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        self._status_tokens.setToolTip("Selected files and estimated token total")
        status_bar.addWidget(self._status_tokens)

        # Version
        version_label = QLabel(f"v{self.APP_VERSION}")
        version_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        version_label.setToolTip("Synapse Desktop version")
        status_bar.addPermanentWidget(version_label)

        self._update_status_bar()

    def _update_status_bar(self) -> None:
        """Update status bar with current workspace + git info."""
        if self.workspace_path:
            self._status_workspace.setText(f"📁 {self.workspace_path}")
            # Detect git branch
            branch = self._detect_git_branch()
            if branch:
                self._status_git.setText(f"⎇ {branch}")
                self._status_git.setVisible(True)
            else:
                self._status_git.setVisible(False)
        else:
            self._status_workspace.setText("No workspace")
            self._status_git.setVisible(False)

        self._status_tokens.setText(self._build_token_status_text())

    def _build_token_status_text(self) -> str:
        """Return compact token summary for the footer."""
        try:
            if not hasattr(self, "context_view"):
                return "0 files | 0 tokens"

            selected_count = len(self.context_view.get_selected_paths())
            total_tokens = 0

            if hasattr(self.context_view, "file_tree_widget"):
                total_tokens = self.context_view.file_tree_widget.get_total_tokens()

            return f"{selected_count} files | {total_tokens:,} tokens"
        except Exception:
            return "0 files | 0 tokens"

    def _detect_git_branch(self) -> Optional[str]:
        """Detect current git branch for the workspace (returns None if not a git repo)."""
        if not self.workspace_path:
            return None
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    # ── Recent folders ────────────────────────────────────────────
    def _refresh_recent_folders_menu(self) -> None:
        """Refresh the recent folders dropdown menu."""
        self._recent_menu.clear()
        recent = load_recent_folders()

        if not recent:
            action = self._recent_menu.addAction("No recent folders")
            action.setEnabled(False)
            return

        for folder_path in recent:
            display_name = get_folder_display_name(folder_path)
            action = self._recent_menu.addAction(f"📁 {display_name}")
            action.triggered.connect(
                lambda checked=False, p=folder_path: self._open_recent_folder(p)
            )

    # ── Folder operations ─────────────────────────────────────────
    @Slot()
    def _open_folder_dialog(self) -> None:
        """Open dialog to select a workspace folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Workspace Folder",
            str(self.workspace_path or Path.home()),
        )
        if folder_path:
            self._set_workspace(Path(folder_path))

    def _open_recent_folder(self, folder_path: str) -> None:
        """Open a folder from the recent list."""
        path = Path(folder_path)
        if path.exists() and path.is_dir():
            self._set_workspace(path)

    def _set_workspace(self, path: Path) -> None:
        """Set workspace path and notify all views."""
        self.workspace_path = path

        # Update top bar breadcrumb
        self._folder_path_label.setText(str(path))
        self._folder_path_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_PRIMARY}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )

        # Update window title
        self._update_window_title()

        # Save to recent
        add_recent_folder(str(path))
        self._refresh_recent_folders_menu()

        # Update status bar
        self._update_status_bar()

        # Notify context view
        self.context_view.on_workspace_changed(path)

    def _get_workspace_path(self) -> Optional[Path]:
        """Getter for workspace path."""
        return self.workspace_path

    # ── Tab changes ───────────────────────────────────────────────
    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change — refresh relevant views."""
        self._current_tab_index = index

        view_names = ["context", "apply", "history", "logs", "settings"]
        if 0 <= index < len(view_names):
            set_active_view(view_names[index])

        if index == 2:
            self.history_view.on_view_activated()
        if index == 3:
            self.logs_view.on_view_activated()

    def _on_settings_changed(self) -> None:
        """Handle settings change — reload context view."""
        if self.workspace_path:
            self.context_view.on_workspace_changed(self.workspace_path)

    def _on_reapply_from_history(self, opx_content: str) -> None:
        """Callback when user wants to re-apply OPX from History."""
        self.apply_view.set_opx_content(opx_content)
        self.tab_widget.setCurrentIndex(1)

    # ── Memory monitor callback ───────────────────────────────────
    def _on_memory_update(self, stats: MemoryStats) -> None:
        """Update memory display (called from background thread)."""

        def update_ui():
            display_text = f"🧠 {format_memory_display(stats)}"
            self._memory_label.setText(display_text)

            if stats.warning and "Critical" in stats.warning:
                color = ThemeColors.ERROR
            elif stats.warning:
                color = ThemeColors.WARNING
            else:
                color = ThemeColors.TEXT_MUTED

            self._memory_label.setStyleSheet(
                f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
                f"font-family: {ThemeFonts.FAMILY_MONO}; "
                f"color: {color};"
            )

        run_on_main_thread(update_ui)

    @Slot()
    def _clear_memory(self) -> None:
        """Clear cache and free memory."""
        try:
            if (
                hasattr(self.context_view, "file_tree_widget")
                and self.context_view.file_tree_widget
            ):
                self.context_view.file_tree_widget.clear_token_cache()

            gc.collect()

            stats = self._memory_monitor.get_current_stats()
            display_text = f"🧠 {format_memory_display(stats)}"
            self._memory_label.setText(display_text)
            self._memory_label.setStyleSheet(
                f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
                f"font-family: {ThemeFonts.FAMILY_MONO}; "
                f"color: {ThemeColors.SUCCESS};"
            )

            from core.logging_config import log_info

            log_info(f"Memory cleared. Current usage: {stats.rss_mb:.0f}MB")
        except Exception as e:
            from core.logging_config import log_error

            log_error(f"Error clearing memory: {e}")

    # ── Session management ────────────────────────────────────────
    def _restore_session(self) -> None:
        """
        Restore session from previous run.

        CLEAN SESSION MODE: Only restore workspace path and instructions text.
        Other state (selected files, expanded folders) starts fresh.
        """
        from services.recent_folders import load_recent_folders

        session = load_session_state()

        # Restore workspace from most recent folder
        recent_folders = load_recent_folders()
        if recent_folders:
            workspace = Path(recent_folders[0])
            if workspace.exists() and workspace.is_dir():
                self.workspace_path = workspace

                self._folder_path_label.setText(str(workspace))
                self._folder_path_label.setStyleSheet(
                    f"color: {ThemeColors.TEXT_PRIMARY}; "
                    f"font-family: {ThemeFonts.FAMILY_MONO}; "
                    f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
                )

                self._update_window_title()
                self._update_status_bar()

                self.context_view.on_workspace_changed(workspace)

        # Restore instructions text
        if session and session.instructions_text:
            self.context_view.set_instructions_text(session.instructions_text)

        # Restore window geometry
        if session and session.window_width and session.window_height:
            self.resize(session.window_width, session.window_height)

    def _save_session(self) -> None:
        """Save current session state."""
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

    def resizeEvent(self, event) -> None:
        """Cap nhat vi tri toast khi window resize."""
        super().resizeEvent(event)
        if hasattr(self, "_toast_manager") and self._toast_manager:
            self._toast_manager.reposition_on_resize()

    def closeEvent(self, event) -> None:
        """Handle app close — cleanup resources and save session."""
        from core.utils.file_scanner import stop_scanning
        from services.token_display import stop_token_counting

        stop_scanning()
        stop_token_counting()
        shutdown_all()

        # Dong tat ca toast truoc khi thoat
        if hasattr(self, "_toast_manager") and self._toast_manager:
            self._toast_manager.dismiss_all()

        if hasattr(self, "_status_timer"):
            self._status_timer.stop()

        self._save_session()
        self._memory_monitor.stop()

        self.context_view.cleanup()

        from core.logging_config import flush_logs, cleanup_old_logs

        flush_logs()
        cleanup_old_logs(max_age_days=7)

        event.accept()


def main() -> None:
    """Entry point for Synapse Desktop."""
    from config.paths import ensure_app_directories
    from services.encoder_registry import initialize_encoder

    ensure_app_directories()

    # Initialize encoder config (inject settings into core layer)
    initialize_encoder()

    app = QApplication(sys.argv)
    app.setApplicationName("Synapse Desktop")
    app.setOrganizationName("Synapse")

    # Apply global dark stylesheet (single source of truth)
    apply_theme(app)

    # Initialize global signal bridge on main thread
    get_signal_bridge()

    window = SynapseMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
