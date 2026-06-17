"""
Synapse Desktop — PySide6 Main Window Entry Point

Phase 1 Redesign: Global Layout + Theme System + Tab Bar + Status Bar
Design System: Dark theme inspired by VS Code / JetBrains
"""

# ruff: noqa: E402
# Suppress Hugging Face warnings before imports

import gc
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, List

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

# Add project root to sys.path to support 'from presentation...' imports when run directly as a script
# Only applied in development mode (non-frozen) to avoid side effects on Windows EXE/AppImage.
if not getattr(sys, "frozen", False):
    _project_root = str(Path(__file__).resolve().parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

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

from presentation.config.theme import ThemeColors, ThemeFonts
from presentation.components.qt_utils import create_colored_icon
from domain.ports.registry import DomainRegistry
from domain.ports.session_state_port import SessionState
from domain.ports.memory_port import MemoryStats, format_memory_display


# ── Tab configuration: icon (SVG filename) + label ────────────────
_TAB_CONFIG = [
    ("folder.svg", "Context"),
    ("zap.svg", "Apply"),
    ("clock-arrow-down.svg", "History"),
    ("settings.svg", "Settings"),
]


class SynapseMainWindow(QMainWindow):
    """Main application window — Phase 1 redesigned."""

    APP_VERSION = "1.0.0"

    def __init__(self) -> None:
        super().__init__()

        # Xác định đường dẫn thư mục assets (hỗ trợ cả chạy dev và chạy bundle)
        from shared.utils.path_utils import get_assets_dir

        self.assets_dir = get_assets_dir()

        # Load custom fonts FIRST
        ThemeFonts.load_fonts()

        self.workspace_path: Optional[Path] = None

        # Session restore data
        self._pending_session_restore: Optional[Dict[str, List[str]]] = None
        self._current_tab_index = 0

        # Memory monitor
        self._memory_monitor = DomainRegistry.memory_monitor()
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

        # Khoi tao Global Toast Notification System
        from presentation.components.toast.toast_qt import init_toast_manager

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

    # ── Window icon ───────────────────────────────────────────────
    def _set_window_icon(self) -> None:
        """Thiết lập window icon từ assets/icon.ico hoặc icon.png.

        Hỗ trợ cả môi trường chạy từ mã nguồn (development) và đóng gói (PyInstaller bundle).
        """
        # Tìm icon file: ưu tiên .ico, sau đó .png
        icon_path = None
        if (self.assets_dir / "icon.ico").exists():
            icon_path = self.assets_dir / "icon.ico"
        elif (self.assets_dir / "icon.png").exists():
            icon_path = self.assets_dir / "icon.png"

        # Set icon nếu tìm thấy
        if icon_path:
            icon = QIcon(str(icon_path))
            self.setWindowIcon(icon)

    # ── Window title (dynamic) ────────────────────────────────────
    def _update_window_title(self) -> None:
        """Đặt window title hiển thị: 'Synapse Desktop — [Folder Name]'."""
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
            from presentation.service_container import ServiceContainer

            self._services = ServiceContainer()

        self.context_view = ContextViewQt(
            self._get_workspace_path,
            prompt_builder=self._services.prompt_builder,
            clipboard_service=self._services.clipboard,
            ignore_engine=self._services.ignore_engine,
            tokenization_service=self._services.tokenization,
        )
        self.apply_view = ApplyViewQt(self._get_workspace_path)
        self.history_view = HistoryViewQt(self._on_reapply_from_history)
        self.settings_view = SettingsViewQt(
            self._on_settings_changed, self._get_workspace_path
        )

        # Add tabs with icon + text
        views = [
            self.context_view,
            self.apply_view,
            self.history_view,
            self.settings_view,
        ]
        for (icon_name, label), view in zip(_TAB_CONFIG, views):
            icon_path = self.assets_dir / icon_name
            # Render icon SVG và đổi màu primary để hiển thị đẹp mắt và đồng bộ trên UI
            tab_icon = create_colored_icon(str(icon_path), ThemeColors.PRIMARY)
            self.tab_widget.addTab(view, tab_icon, f" {label}")

        main_layout.addWidget(self.tab_widget, stretch=1)

        # 3) Status bar (footer)
        self._build_status_bar()

    # ── Top Bar ───────────────────────────────────────────────────
    def _build_top_bar(self) -> QFrame:
        """Xây dựng thanh công cụ phía trên (top bar 48px height).

        Bao gồm: [App Icon + "Synapse Desktop"] — [Đường dẫn thư mục] — [Thông số RAM] — [Recent ▾] [Open Folder].
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
        app_icon = QLabel()
        icon_gem = create_colored_icon(
            str(self.assets_dir / "gem.svg"), ThemeColors.PRIMARY
        )
        app_icon.setPixmap(icon_gem.pixmap(QSize(18, 18)))
        app_icon.setToolTip("Synapse Desktop")
        layout.addWidget(app_icon)

        app_title = QLabel("Synapse Desktop")
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
        folder_icon = QLabel()
        icon_folder = create_colored_icon(
            str(self.assets_dir / "folder.svg"), ThemeColors.TEXT_SECONDARY
        )
        folder_icon.setPixmap(icon_folder.pixmap(QSize(14, 14)))
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
        self._memory_icon_label = QLabel()
        icon_brain = create_colored_icon(
            str(self.assets_dir / "brain.svg"), ThemeColors.TEXT_MUTED
        )
        self._memory_icon_label.setPixmap(icon_brain.pixmap(QSize(14, 14)))
        self._memory_icon_label.setToolTip("Memory usage | Token cache | Files loaded")
        layout.addWidget(self._memory_icon_label)

        self._memory_label = QLabel("--")
        self._memory_label.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"color: {ThemeColors.TEXT_MUTED};"
        )
        self._memory_label.setToolTip("Memory usage | Token cache | Files loaded")
        layout.addWidget(self._memory_label)

        # ── Clear memory button ──
        clear_btn = QToolButton()
        clear_btn.setIcon(
            create_colored_icon(
                str(self.assets_dir / "broom.svg"), ThemeColors.TEXT_SECONDARY
            )
        )
        clear_btn.setIconSize(QSize(14, 14))
        clear_btn.setToolTip("Clear cache & free memory")
        clear_btn.setStyleSheet(
            f"QToolButton {{ padding: 4px 6px; border-radius: 4px; }}"
            f"QToolButton:hover {{ background-color: {ThemeColors.BG_ELEVATED}; }}"
        )
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_memory)
        layout.addWidget(clear_btn)

        # ── Recent folders button (outline style with dropdown) ──
        self._recent_btn = QToolButton()
        self._recent_btn.setIcon(
            create_colored_icon(
                str(self.assets_dir / "clock-arrow-down.svg"),
                ThemeColors.TEXT_SECONDARY,
            )
        )
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
        open_btn = QPushButton(" Open Folder")
        open_btn.setIcon(
            create_colored_icon(str(self.assets_dir / "folder.svg"), "#FFFFFF")
        )
        open_btn.setIconSize(QSize(14, 14))
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
        self._status_workspace_icon = QLabel()
        self._status_workspace_icon.setVisible(False)
        status_bar.addWidget(self._status_workspace_icon)

        self._status_workspace = QLabel("No workspace")
        self._status_workspace.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; "
            f"font-family: {ThemeFonts.FAMILY_MONO}; "
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
        )
        status_bar.addWidget(self._status_workspace, stretch=1)

        # Git branch
        self._status_git_icon = QLabel()
        self._status_git_icon.setVisible(False)
        status_bar.addWidget(self._status_git_icon)

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
        """Cập nhật thông tin thanh trạng thái (workspace, git branch, tokens).

        Git branch được đọc từ cache (không gây nghẽn UI) và làm mới bất đồng bộ.
        """
        if self.workspace_path:
            self._status_workspace.setText(str(self.workspace_path))
            if not self._status_workspace_icon.pixmap():
                icon_folder = create_colored_icon(
                    str(self.assets_dir / "folder.svg"), ThemeColors.TEXT_MUTED
                )
                self._status_workspace_icon.setPixmap(icon_folder.pixmap(QSize(12, 12)))
            self._status_workspace_icon.setVisible(True)

            # Trigger async refresh (result available on next cycle)
            self._refresh_git_branch_async()

            # Read cached value (may be from previous cycle — acceptable for status bar)
            branch = self._detect_git_branch()
            if branch:
                self._status_git.setText(branch)
                if not self._status_git_icon.pixmap():
                    icon_git = create_colored_icon(
                        str(self.assets_dir / "git-branch.svg"),
                        ThemeColors.TEXT_SECONDARY,
                    )
                    self._status_git_icon.setPixmap(icon_git.pixmap(QSize(12, 12)))
                self._status_git_icon.setVisible(True)
                self._status_git.setVisible(True)
            else:
                self._status_git_icon.setVisible(False)
                self._status_git.setVisible(False)
        else:
            self._status_workspace.setText("No workspace")
            self._status_workspace_icon.setVisible(False)
            self._status_git_icon.setVisible(False)
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

        from presentation.utils.qt_utils import schedule_background

        schedule_background(_detect, on_result=_on_result)

    # ── Recent folders ────────────────────────────────────────────
    def _refresh_recent_folders_menu(self) -> None:
        """Làm mới danh sách thư mục mở gần đây (recent folders)."""
        self._recent_menu.clear()
        recent = DomainRegistry.recent_folders().load_recent_folders()

        if not recent:
            action = self._recent_menu.addAction("No recent folders")
            action.setEnabled(False)
            return

        for folder_path in recent:
            display_name = DomainRegistry.recent_folders().get_folder_display_name(
                folder_path
            )
            action = self._recent_menu.addAction(display_name)
            icon_folder = create_colored_icon(
                str(self.assets_dir / "folder.svg"), ThemeColors.TEXT_SECONDARY
            )
            action.setIcon(icon_folder)
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
        self._cached_git_branch = None  # Clear stale branch
        self._git_branch_pending = False  # Allow immediate re-detection

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
        DomainRegistry.recent_folders().add_recent_folder(str(path))
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

        view_names = ["context", "apply", "history", "settings"]
        if 0 <= index < len(view_names):
            DomainRegistry.app_lifecycle().set_active_view(view_names[index])

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

    # ── Memory monitor callback ───────────────────────────────────
    def _on_memory_update(self, stats: MemoryStats) -> None:
        """Update memory display.

        Called on main thread (QTimer-based MemoryMonitor) — safe to
        update UI widgets directly without marshalling.
        """
        display_text = format_memory_display(stats)
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
            display_text = format_memory_display(stats)
            self._memory_label.setText(display_text)
            self._memory_label.setStyleSheet(
                f"font-size: {ThemeFonts.SIZE_CAPTION}px; "
                f"font-family: {ThemeFonts.FAMILY_MONO}; "
                f"color: {ThemeColors.SUCCESS};"
            )

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
        session = DomainRegistry.session_state().load_session_state()

        # Restore workspace from most recent folder
        recent_folders = DomainRegistry.recent_folders().load_recent_folders()
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
            selected_files=list(self.context_view.get_selected_paths()),
            expanded_folders=list(self.context_view.get_expanded_paths()),
            instructions_text=self.context_view.get_instructions_text(),
            active_tab_index=self._current_tab_index,
            window_width=self.width(),
            window_height=self.height(),
        )
        save_session_state = DomainRegistry.session_state().save_session_state
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
            DomainRegistry.app_lifecycle().stop_scanning()
        except Exception as e:
            log_error("closeEvent: stop_scanning failed", e)

        # 2. Stop token counting
        try:
            DomainRegistry.app_lifecycle().stop_token_counting()
        except Exception as e:
            log_error("closeEvent: stop_token_counting failed", e)

        # 3. Shutdown thread pools
        try:
            DomainRegistry.app_lifecycle().shutdown_all()
            # Don dep va cho doi cac thread trong global QThreadPool de tranh bi treo ung dung khi close
            from PySide6.QtCore import QThreadPool

            pool = QThreadPool.globalInstance()
            pool.clear()
            pool.waitForDone(1000)  # Timeout 1s tranh treo vo han
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


# main() was moved to root main.py
