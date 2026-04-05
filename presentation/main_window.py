"""
Synapse Desktop — PySide6 Main Window Entry Point

Phase 1 Redesign: Global Layout + Theme System + Tab Bar + Status Bar
Design System: Dark theme inspired by VS Code / JetBrains
"""

import sys
import os

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
    QFileDialog,
)
from PySide6.QtCore import Slot, QTimer
from PySide6.QtGui import QIcon

from presentation.config.theme import ThemeFonts, apply_theme
from infrastructure.adapters.qt_utils import (
    get_signal_bridge,
)
from infrastructure.adapters.threading_utils import shutdown_all, set_active_view
from infrastructure.persistence.recent_folders import (
    load_recent_folders,
    add_recent_folder,
)
from infrastructure.persistence.session_state import (
    SessionState,
    save_session_state,
    load_session_state,
)
from infrastructure.adapters.memory_monitor import (
    get_memory_monitor,
    MemoryStats,
)
from presentation.components.app_layout.top_bar import TopBar
from presentation.components.app_layout.status_bar import SynapseStatusBar

# Filter noise from external libs BEFORE they execute
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import logging

logging.getLogger("huggingface_hub").setLevel(logging.ERROR)


# ── Tab configuration: icon (emoji) + label ───────────────────────
_TAB_CONFIG = [
    ("📁", "Context"),
    ("⚡", "Apply"),
    ("🕐", "History"),
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

        # Cached git branch (refreshed asynchronously by _refresh_git_branch_async)
        self._cached_git_branch: Optional[str] = None
        self._git_branch_pending = False

        # Set window icon (de hien thi icon tren taskbar)
        self._set_window_icon()

        # Setup window
        self._update_window_title()
        self.setMinimumSize(900, 640)
        self.resize(1500, 1000)

        # Build UI
        self._build_ui()

        # Connect signals from components
        self.top_bar.open_folder_requested.connect(self._open_folder_dialog)
        self.top_bar.recent_folder_selected.connect(self._open_recent_folder)
        self.top_bar.clear_memory_requested.connect(self._clear_memory)

        # Khoi tao Global Toast Notification System
        from presentation.components.toast.toast_qt import init_toast_manager

        self._toast_manager = init_toast_manager(self)

        # Keep status footer metrics fresh
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1200)
        self._status_timer.timeout.connect(self._refresh_ui_stats)
        self._status_timer.start()

        # Restore session
        self._restore_session()

        # Start memory monitoring
        self._memory_monitor.start()

    # ── Window icon ───────────────────────────────────────────────
    def _set_window_icon(self) -> None:
        """Set window icon tu assets/icon.ico hoac icon.png."""
        # Tim icon file: uu tien .ico, sau do .png
        # Xu ly ca truong hop chay tu source code va tu EXE (PyInstaller bundle)
        base_path = Path(__file__).parent

        # Neu la PyInstaller bundle, icon co the o trong _MEIPASS
        if hasattr(sys, "_MEIPASS"):
            assets_dir = Path(sys._MEIPASS) / "assets"
        else:
            assets_dir = base_path / "assets"

        # Tim icon file
        icon_path = None
        if (assets_dir / "icon.ico").exists():
            icon_path = assets_dir / "icon.ico"
        elif (assets_dir / "icon.png").exists():
            icon_path = assets_dir / "icon.png"

        # Set icon neu tim thay
        if icon_path:
            icon = QIcon(str(icon_path))
            self.setWindowIcon(icon)

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

        # 1) Top bar
        self.top_bar = TopBar(self)
        main_layout.addWidget(self.top_bar)

        # 2) Tab widget with icon+text tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        from presentation.views.context.context_view_qt import ContextViewQt
        from presentation.views.apply.apply_view_qt import ApplyViewQt
        from presentation.views.history.history_view_qt import HistoryViewQt
        from presentation.views.settings.settings_view_qt import SettingsViewQt

        # Tao ServiceContainer tai composition root de quan ly lifecycle cua tat ca services
        # Reuse boot container from QApplication instance (created in main())
        app = QApplication.instance()
        if hasattr(app, "_service_container"):
            self._services = app._service_container
        else:
            # Fallback if not set (shouldn't happen in normal flow)
            from application.services.service_container import ServiceContainer

            self._services = ServiceContainer()

        self.context_view = ContextViewQt(
            self._get_workspace_path,
            prompt_builder=self._services.prompt_builder,
            clipboard_service=self._services.clipboard,
            ignore_engine=self._services.ignore_engine,
            tokenization_service=self._services.tokenization,
            graph_provider=self._services.graph_service,
        )
        self.apply_view = ApplyViewQt(self._get_workspace_path)
        self.history_view = HistoryViewQt(self._on_reapply_from_history)
        self.settings_view = SettingsViewQt(self._on_settings_changed)

        # Add tabs with icon + text
        views = [
            self.context_view,
            self.apply_view,
            self.history_view,
            self.settings_view,
        ]
        for (icon, label), view in zip(_TAB_CONFIG, views):
            self.tab_widget.addTab(view, f"{icon}  {label}")

        main_layout.addWidget(self.tab_widget, stretch=1)

        # 3) Status bar (footer)
        self.status_bar = SynapseStatusBar(self.APP_VERSION, self)
        self.setStatusBar(self.status_bar)

        self._refresh_ui_stats()

    def _refresh_ui_stats(self) -> None:
        """Refresh dynamic stats in top bar and status bar."""
        if self.workspace_path:
            # Trigger async refresh for Git
            self._refresh_git_branch_async()
            branch = self._detect_git_branch()
            self.status_bar.set_git_branch(branch)

        # Update token stats
        selected_count, total_tokens = self._get_token_metrics()
        self.status_bar.set_token_stats(selected_count, total_tokens)

    def _get_token_metrics(self) -> tuple[int, int]:
        """Lấy thông số token từ context view."""
        try:
            if not hasattr(self, "context_view"):
                return 0, 0

            selected_count = len(self.context_view.get_selected_paths())
            total_tokens = 0

            if hasattr(self.context_view, "file_tree_widget"):
                total_tokens = self.context_view.file_tree_widget.get_total_tokens()

            return selected_count, total_tokens
        except Exception:
            return 0, 0

    def _detect_git_branch(self) -> Optional[str]:
        """Return cached git branch name. Updated asynchronously by background timer.

        Returns the last known branch name immediately (non-blocking).
        A background thread refreshes the value periodically.
        """
        return getattr(self, "_cached_git_branch", None)

    def _refresh_git_branch_async(self) -> None:
        """Spawn a background thread to detect the current git branch.

        Called by _update_status_bar(). The result is cached in
        _cached_git_branch and picked up on the next UI refresh cycle.

        WINDOWS EXE FIX: Uses CREATE_NO_WINDOW flag to prevent a console
        window from flashing every time this method is called.
        """
        workspace = self.workspace_path
        if not workspace:
            self._cached_git_branch = None
            self._git_branch_pending = False
            return
        if self._git_branch_pending:
            return  # Previous detection still running
        self._git_branch_pending = True

        # Capture workspace at schedule time to detect stale results
        expected_workspace = workspace

        def _detect() -> Optional[str]:
            try:
                import platform as _platform

                creationflags = 0
                if _platform.system() == "Windows":
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(workspace),
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=creationflags,
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                pass
            return None

        def _on_result(branch: object) -> None:
            self._git_branch_pending = False
            # Discard result if workspace changed while detection was running
            if self.workspace_path != expected_workspace:
                return
            # branch is Optional[str] but signal emits object
            self._cached_git_branch = branch if isinstance(branch, str) else None

        from infrastructure.adapters.qt_utils import schedule_background

        schedule_background(_detect, on_result=_on_result)

    # ── Recent folders ────────────────────────────────────────────
    def _refresh_recent_folders_menu(self) -> None:
        """Refresh the recent folders in TopBar."""

        self.top_bar.refresh_recent_menu(load_recent_folders())

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
        self._cached_git_branch = None  # Clear stale branch
        self._git_branch_pending = False  # Allow immediate re-detection

        # Update top bar breadcrumb is handled by TopBar component automatically
        # which is notified via set_workspace_path below.

        # Update window title
        self._update_window_title()

        # Save to recent

        add_recent_folder(str(path))
        self.top_bar.refresh_recent_menu(load_recent_folders())

        # Update components
        self.top_bar.set_workspace_path(path)
        self.status_bar.set_workspace(path)
        self._refresh_ui_stats()

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

        view_names = ["context", "apply", "history", "settings"]
        if 0 <= index < len(view_names):
            set_active_view(view_names[index])

        if index == 2:
            self.history_view.on_view_activated()

    def _on_settings_changed(self) -> None:
        """Handle settings change — reload context view."""
        if self.workspace_path:
            self.context_view.on_workspace_changed(self.workspace_path)

    def _on_reapply_from_history(self, opx_content: str) -> None:
        """Callback when user wants to re-apply OPX from History."""
        self.apply_view.set_opx_content(opx_content)
        self.tab_widget.setCurrentIndex(1)

    def _on_memory_update(self, stats: MemoryStats) -> None:
        """Cập nhật thông số memory lên UI."""
        self.top_bar.update_memory_stats(stats)

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
            self.top_bar.update_memory_stats(stats)

            from shared.logging_config import log_info

            log_info(f"Memory cleared. Current usage: {stats.rss_mb:.0f}MB")
        except Exception as e:
            from shared.logging_config import log_error

            log_error(f"Error clearing memory: {e}")

    # ── Session management ────────────────────────────────────────
    def _restore_session(self) -> None:
        """
        Restore session from previous run.

        CLEAN SESSION MODE: Only restore workspace path and instructions text.
        Other state (selected files, expanded folders) starts fresh.
        """

        session = load_session_state()

        # Restore workspace from most recent folder
        recent_folders = load_recent_folders()
        if recent_folders:
            workspace = Path(recent_folders[0])
            if workspace.exists() and workspace.is_dir():
                self.workspace_path = workspace

                self._update_window_title()

                self.top_bar.set_workspace_path(workspace)
                self.top_bar.refresh_recent_menu(load_recent_folders())
                self.status_bar.set_workspace(workspace)
                self._refresh_ui_stats()

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
            selected_files=list(self.context_view.get_selected_paths()),
            expanded_folders=list(self.context_view.get_expanded_paths()),
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
        """Handle app close — cleanup resources and save session.

        Each step is wrapped individually so that a failure in one
        does not prevent subsequent cleanup from running.
        """
        from shared.logging_config import log_error

        # 1. Stop background scanning
        try:
            from infrastructure.filesystem.file_scanner import stop_scanning

            stop_scanning()
        except Exception as e:
            log_error("closeEvent: stop_scanning failed", e)

        # 2. Stop token counting
        try:
            from infrastructure.adapters.token_display import stop_token_counting

            stop_token_counting()
        except Exception as e:
            log_error("closeEvent: stop_token_counting failed", e)

        # 3. Shutdown thread pools
        try:
            shutdown_all()
        except Exception as e:
            log_error("closeEvent: shutdown_all failed", e)

        # 4. Dismiss toasts
        try:
            if hasattr(self, "_toast_manager") and self._toast_manager:
                self._toast_manager.dismiss_all()
        except Exception as e:
            log_error("closeEvent: dismiss_all failed", e)

        # 5. Stop status timer
        try:
            if hasattr(self, "_status_timer"):
                self._status_timer.stop()
        except Exception as e:
            log_error("closeEvent: status_timer.stop failed", e)

        # 6. Save session (important — should survive earlier failures)
        try:
            self._save_session()
        except Exception as e:
            log_error("closeEvent: _save_session failed", e)

        # 7. Stop memory monitor
        try:
            self._memory_monitor.stop()
        except Exception as e:
            log_error("closeEvent: memory_monitor.stop failed", e)

        # 8. Cleanup context view
        try:
            self.context_view.cleanup()
        except Exception as e:
            log_error("closeEvent: context_view.cleanup failed", e)

        # 9. Shutdown service container (caches, etc.)
        try:
            if hasattr(self, "_services"):
                self._services.shutdown()
        except Exception as e:
            log_error("closeEvent: services.shutdown failed", e)

        # 10. Flush and cleanup logs (last — so earlier errors get logged)
        try:
            from shared.logging_config import flush_logs, cleanup_old_logs

            flush_logs()
            cleanup_old_logs(max_age_days=7)
        except Exception:
            pass  # Nothing we can do if logging itself fails

        event.accept()


def main() -> None:
    """Entry point for Synapse Desktop."""
    # CRITICAL for Windows EXE: Prevent fork bomb when using multiprocessing.
    # Without this, each spawned process re-executes main(), creating infinite
    # window spawning loops (the "flashing windows" issue).
    import multiprocessing

    multiprocessing.freeze_support()

    # ===== MCP Server Mode =====
    # Neu co co --run-mcp, khoi dong MCP Server thay vi giao dien PySide6.
    # Cho phep AI clients (Cursor, Copilot, Antigravity) giao tiep qua stdio.
    # Cach su dung: python main_window.py --run-mcp [workspace_path]
    if "--run-mcp" in sys.argv:
        idx = sys.argv.index("--run-mcp")
        workspace = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        from infrastructure.mcp.server import run_mcp_server

        run_mcp_server(workspace)
        return

    # CRITICAL for Windows taskbar icon: Set AppUserModelID TRƯỚC KHI tạo QApplication
    # Windows nhóm app theo AppUserModelID - nếu không set, Windows sẽ dùng icon của Python
    from infrastructure.adapters.windows_utils import (
        set_app_user_model_id,
        get_default_app_user_model_id,
    )

    set_app_user_model_id(get_default_app_user_model_id())

    from presentation.config.paths import ensure_app_directories
    from infrastructure.adapters.encoder_registry import initialize_encoder

    ensure_app_directories()

    # Khoi tao encoder config (inject settings vao core layer)
    # NOTE: Cach moi nen dung ServiceContainer.tokenization thay the.
    # initialize_encoder() van duoc goi o day de backward compat voi cac module
    # chua duoc migrate sang DI injection pattern.
    initialize_encoder()

    # Register all cache adapters into CacheRegistry
    # NOTE: Sau khi Phase 2 hoan tat, cac adapters se dang ky vao container.cache_registry
    # Tao ServiceContainer truoc de co ignore_engine
    # (container se duoc dung lai khi tao views ben duoi)
    from application.services.service_container import ServiceContainer as _SC
    from infrastructure.adapters.cache_adapters import register_all_caches

    _boot_container = _SC()
    register_all_caches(
        ignore_engine=_boot_container.ignore_engine,
        tokenization_service=_boot_container.tokenization,
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Synapse Desktop")
    app.setOrganizationName("Synapse")

    # Store boot container on app instance for reuse
    app._service_container = _boot_container  # type: ignore[attr-defined]

    # Set application icon (de hien thi icon tren taskbar)
    # Tim icon file: uu tien .ico, sau do .png
    base_path = Path(__file__).parent
    if hasattr(sys, "_MEIPASS"):
        assets_dir = Path(sys._MEIPASS) / "assets"
    else:
        assets_dir = base_path / "assets"

    icon_path = None
    if (assets_dir / "icon.ico").exists():
        icon_path = assets_dir / "icon.ico"
    elif (assets_dir / "icon.png").exists():
        icon_path = assets_dir / "icon.png"

    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))

    # Apply global dark stylesheet (single source of truth)
    apply_theme(app)

    # Initialize global signal bridge on main thread
    get_signal_bridge()

    window = SynapseMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
