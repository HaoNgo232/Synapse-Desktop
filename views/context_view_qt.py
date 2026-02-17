"""
Context View (PySide6) - Tab để chọn files và copy context.
"""

import os
import threading
from pathlib import Path
from typing import Optional, Set, List, Callable

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QToolButton,
    QTextEdit,
    QComboBox,
    QFrame,
    QMenu,
    QSpinBox,
)
from PySide6.QtCore import (
    Qt,
    Slot,
    QTimer,
    QSize,
    Signal,
    QRunnable,
    QThreadPool,
    QObject,
)
from PySide6.QtGui import QIcon

from core.theme import ThemeColors
from core.utils.qt_utils import (
    run_on_main_thread,
    schedule_background,
)
from core.utils.file_utils import scan_directory, TreeItem
from core.token_counter import count_tokens
from core.prompt_generator import (
    generate_prompt,
    generate_file_map,
    generate_file_contents_xml,
    generate_file_contents_json,
    generate_file_contents_plain,
    generate_smart_context,
    build_smart_prompt,
)
from core.tree_map_generator import generate_tree_map_only
from core.security_check import scan_secrets_in_files_cached
from core.utils.git_utils import get_git_diffs, get_git_logs
from components.file_tree_widget import FileTreeWidget
from components.token_stats_qt import TokenStatsPanelQt
from services.clipboard_utils import copy_to_clipboard
from services.file_watcher import FileWatcher, WatcherCallbacks
from services.settings_manager import get_setting, set_setting
from views.settings_view_qt import (
    get_excluded_patterns,
    get_use_gitignore,
    get_use_relative_paths,
)
from config.output_format import (
    OutputStyle,
    OUTPUT_FORMATS,
    get_style_by_id,
    DEFAULT_OUTPUT_STYLE,
)
from core.dependency_resolver import DependencyResolver


class CopyTaskWorker(QRunnable):
    """
    Background worker cho cac copy operations nang (scan tree, doc files, count tokens).

    Chay heavy work tren background thread, emit ket qua ve main thread
    qua signals de copy clipboard va cap nhat UI.
    """

    class Signals(QObject):
        """Signals de giao tiep voi main thread."""

        # Emit (prompt_text, token_count) khi task hoan thanh
        finished = Signal(str, int)
        # Emit error message khi co loi
        error = Signal(str)

    def __init__(self, task_fn):
        """
        Khoi tao worker voi mot task function.

        Args:
            task_fn: Callable tra ve prompt string. Chay tren background thread.
        """
        super().__init__()
        self.task_fn = task_fn
        self.signals = self.Signals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        """Chay task function va emit ket qua hoac error."""
        try:
            prompt = self.task_fn()
            from core.token_counter import count_tokens as _count

            token_count = _count(prompt)
            self.signals.finished.emit(prompt, token_count)
        except Exception as e:
            self.signals.error.emit(str(e))


class ContextViewQt(QWidget):
    """View cho Context tab - PySide6 version."""

    def __init__(
        self,
        get_workspace: Callable[[], Optional[Path]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.get_workspace = get_workspace

        # State
        self.tree: Optional[TreeItem] = None
        self._selected_output_style: OutputStyle = DEFAULT_OUTPUT_STYLE
        self._last_ignored_patterns: List[str] = []
        self._related_mode_active: bool = False
        self._last_added_related_files: Set[str] = set()
        self._resolving_related: bool = False  # Guard against recursive triggers
        self._loading_lock = threading.Lock()
        self._is_loading = False
        self._pending_refresh = False
        self._token_generation = 0
        self._status_timer: Optional[QTimer] = None  # Fix race condition
        self._current_copy_worker: Optional[CopyTaskWorker] = None  # Track copy worker

        # Services
        self._file_watcher: Optional[FileWatcher] = FileWatcher()
        self._repo_manager = None  # Lazy init

        # Build UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Xay dung UI voi top toolbar + 3-panel splitter (30:45:25)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Top toolbar: controls + token counter
        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        # Main splitter: files | instructions | actions
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(
            f"""
            QSplitter::handle {{
                background-color: {ThemeColors.BORDER};
                margin: 4px 0;
            }}
            QSplitter::handle:hover {{
                background-color: {ThemeColors.PRIMARY};
            }}
        """
        )

        # Left panel - File tree (~30%)
        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)

        # Center panel - Instructions (~45%)
        center_panel = self._build_instructions_panel()
        splitter.addWidget(center_panel)

        # Right panel - Actions + Token stats (~25%)
        action_panel = self._build_actions_panel()
        splitter.addWidget(action_panel)

        # Ty le 30:45:25 cho 3 panel
        splitter.setStretchFactor(0, 30)
        splitter.setStretchFactor(1, 45)
        splitter.setStretchFactor(2, 25)
        splitter.setSizes([420, 630, 350])

        layout.addWidget(splitter)

    def _build_toolbar(self) -> QFrame:
        """Build top toolbar chua controls va token counter."""
        from PySide6.QtWidgets import QSizePolicy

        toolbar = QFrame()
        toolbar.setFixedHeight(40)
        toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.setStyleSheet(
            f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """
        )
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
        )

        # Style cho toolbar icon buttons
        icon_btn_style = (
            f"QToolButton {{ "
            f"  background: transparent; border: none; "
            f"  border-radius: 6px; padding: 5px; "
            f"  color: {ThemeColors.TEXT_SECONDARY}; "
            f"}} "
            f"QToolButton:hover {{ "
            f"  background: {ThemeColors.BG_HOVER}; "
            f"  color: {ThemeColors.TEXT_PRIMARY}; "
            f"}}"
        )

        # Refresh button
        refresh_btn = QToolButton()
        refresh_btn.setIcon(QIcon(os.path.join(assets_dir, "refresh.svg")))
        refresh_btn.setIconSize(QSize(16, 16))
        refresh_btn.setToolTip("Refresh file tree (F5)")
        refresh_btn.setStyleSheet(icon_btn_style)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_tree)
        layout.addWidget(refresh_btn)

        # Separator nho
        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setFixedHeight(20)
        sep1.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        layout.addWidget(sep1)

        # Ignore button
        ignore_btn = QToolButton()
        ignore_btn.setIcon(QIcon(os.path.join(assets_dir, "ban.svg")))
        ignore_btn.setIconSize(QSize(16, 16))
        ignore_btn.setToolTip("Ignore selected files")
        ignore_btn.setStyleSheet(icon_btn_style)
        ignore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ignore_btn.clicked.connect(self._add_to_ignore)
        layout.addWidget(ignore_btn)

        # Undo ignore button
        undo_btn = QToolButton()
        undo_btn.setIcon(QIcon(os.path.join(assets_dir, "undo.svg")))
        undo_btn.setIconSize(QSize(16, 16))
        undo_btn.setToolTip("Undo last ignore")
        undo_btn.setStyleSheet(icon_btn_style)
        undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        undo_btn.clicked.connect(self._undo_ignore)
        layout.addWidget(undo_btn)

        # Separator
        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(20)
        sep2.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        layout.addWidget(sep2)

        # Remote repos dropdown
        remote_btn = QToolButton()
        remote_btn.setIcon(QIcon(os.path.join(assets_dir, "cloud.png")))
        remote_btn.setIconSize(QSize(16, 16))
        remote_btn.setToolTip("Remote Repositories")
        remote_btn.setStyleSheet(icon_btn_style)
        remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remote_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        remote_menu = QMenu(remote_btn)
        remote_menu.addAction("Clone Repository", self._open_remote_repo_dialog)
        remote_menu.addAction("Manage Cache", self._open_cache_management_dialog)
        remote_btn.setMenu(remote_menu)
        layout.addWidget(remote_btn)

        # Related files dropdown menu with presets
        self._related_menu_btn = QToolButton()
        self._related_menu_btn.setIcon(QIcon(os.path.join(assets_dir, "layers.svg")))
        self._related_menu_btn.setText("Related: Off")
        self._related_menu_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self._related_menu_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._related_menu_btn.setIconSize(QSize(14, 14))
        self._related_menu_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-weight: 500;
            }}
            QToolButton:hover {{
                background: {ThemeColors.BG_HOVER};
            }}
            QToolButton::menu-indicator {{
                width: 0px;
            }}
        """
        )
        self._related_menu_btn.setToolTip(
            "Auto-select related files with depth presets"
        )
        self._related_menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Create menu with presets
        related_menu = QMenu(self._related_menu_btn)
        related_menu.setStyleSheet(
            f"""
            QMenu {{
                background: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QMenu::item:selected {{
                background: {ThemeColors.BG_HOVER};
            }}
            QMenu::separator {{
                height: 1px;
                background: {ThemeColors.BORDER};
                margin: 4px 8px;
            }}
        """
        )

        # Menu actions without icons
        off_action = related_menu.addAction("Off")
        related_menu.addSeparator()

        direct_action = related_menu.addAction("Direct (depth 1)")
        nearby_action = related_menu.addAction("Nearby (depth 2)")
        deep_action = related_menu.addAction("Deep (depth 3)")
        deeper_action = related_menu.addAction("Deeper (depth 4)")
        deepest_action = related_menu.addAction("Deepest (depth 5)")

        # Connect actions
        off_action.triggered.connect(lambda: self._set_related_mode(False, 0))
        direct_action.triggered.connect(lambda: self._set_related_mode(True, 1))
        nearby_action.triggered.connect(lambda: self._set_related_mode(True, 2))
        deep_action.triggered.connect(lambda: self._set_related_mode(True, 3))
        deeper_action.triggered.connect(lambda: self._set_related_mode(True, 4))
        deepest_action.triggered.connect(lambda: self._set_related_mode(True, 5))

        self._related_menu_btn.setMenu(related_menu)
        layout.addWidget(self._related_menu_btn)

        # Track current depth for internal use
        self._related_depth = 1

        # Stretch de day token counter sang ben phai
        layout.addStretch()

        # Selection meta label
        self._selection_meta_label = QLabel("0 selected")
        self._selection_meta_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED}; font-weight: 500;"
        )
        layout.addWidget(self._selection_meta_label)

        # Separator truoc token counter
        sep3 = QFrame()
        sep3.setFixedWidth(1)
        sep3.setFixedHeight(20)
        sep3.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        layout.addWidget(sep3)

        # Token counter noi bat
        self._token_count_label = QLabel("0 tokens")
        self._token_count_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.PRIMARY};"
        )
        layout.addWidget(self._token_count_label)

        return toolbar

    def _build_left_panel(self) -> QFrame:
        """Build left panel chi chua header + file tree (controls da len toolbar)."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header: "Files" title
        header = QHBoxLayout()
        header.setSpacing(6)

        files_label = QLabel("Files")
        files_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(files_label)
        header.addStretch()
        layout.addLayout(header)

        # File tree widget (da co san search bar, select/deselect all)
        self.file_tree_widget = FileTreeWidget()
        self.file_tree_widget.selection_changed.connect(self._on_selection_changed)
        self.file_tree_widget.file_preview_requested.connect(self._preview_file)
        self.file_tree_widget.token_counting_done.connect(self._update_token_display)
        layout.addWidget(self.file_tree_widget, stretch=1)

        return panel

    def _build_instructions_panel(self) -> QFrame:
        """Build center panel voi instructions textarea va format selector."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Header row: title + word count
        header = QHBoxLayout()
        instr_label = QLabel("Instructions")
        instr_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(instr_label)
        header.addStretch()

        # Word/char counter
        self._word_count_label = QLabel("0 words")
        self._word_count_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};"
        )
        header.addWidget(self._word_count_label)
        layout.addLayout(header)

        # Textarea - chiem toan bo khong gian con lai
        self._instructions_field = QTextEdit()
        self._instructions_field.setPlaceholderText(
            "Describe your request here...\n\n"
            "Examples:\n"
            "- Refactor module X to Y\n"
            "- Fix bug: [error description]\n"
            "- Add feature: [functionality description]\n\n"
            "Optional: include output format, constraints, or edge cases."
        )
        self._instructions_field.setStyleSheet(
            f"""
            QTextEdit {{
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 13px;
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
            QTextEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """
        )
        self._instructions_field.textChanged.connect(self._on_instructions_changed)
        layout.addWidget(self._instructions_field, stretch=1)

        # Bottom row: format selector
        format_layout = QHBoxLayout()
        format_layout.setSpacing(6)

        format_label = QLabel("Format:")
        format_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {ThemeColors.TEXT_SECONDARY};"
        )
        format_layout.addWidget(format_label)

        self._format_combo = QComboBox()
        self._format_combo.setFixedWidth(140)
        for cfg in OUTPUT_FORMATS.values():
            self._format_combo.addItem(cfg.name, cfg.id)

        # Restore saved format
        saved_format_id = get_setting("output_format", DEFAULT_OUTPUT_STYLE.value)
        try:
            self._selected_output_style = get_style_by_id(saved_format_id)
            idx = self._format_combo.findData(saved_format_id)
            if idx >= 0:
                self._format_combo.setCurrentIndex(idx)
        except ValueError:
            pass

        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addWidget(self._format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)

        return panel

    def _build_actions_panel(self) -> QFrame:
        """Build right panel: Token stats (top) -> Copy buttons -> Status (bottom)."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Token stats panel (model selector + budget bar) o tren cung
        self._token_stats = TokenStatsPanelQt()
        self._token_stats.model_changed.connect(self._on_model_changed)
        layout.addWidget(self._token_stats)

        # Separator giua stats va buttons
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        layout.addWidget(sep)

        # Action buttons voi visual hierarchy ro rang
        actions = self._build_action_buttons()
        layout.addWidget(actions)

        # Status toast
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: 12px;
                font-weight: 600;
                color: white;
                background-color: transparent;
                border-radius: 6px;
                padding: 8px 12px;
            }}
        """
        )
        self._status_label.hide()
        layout.addWidget(self._status_label)

        layout.addStretch()

        return panel

    def _build_action_buttons(self) -> QWidget:
        """Build copy buttons voi visual hierarchy: CTA -> Secondary -> Tertiary."""
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Style chung cho secondary buttons (ghost style)
        secondary_style = (
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {ThemeColors.TEXT_PRIMARY};"
            f"  border: 1px solid {ThemeColors.BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 8px 12px;"
            f"  font-weight: 600;"
            f"  font-size: 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {ThemeColors.BG_HOVER};"
            f"  border-color: {ThemeColors.BORDER_LIGHT};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {ThemeColors.BG_ELEVATED};"
            f"}}"
            f"QPushButton:disabled {{"
            f"  color: {ThemeColors.TEXT_MUTED};"
            f"  border-color: {ThemeColors.BG_ELEVATED};"
            f"}}"
        )

        # Tertiary style (nhe nhang, border dashed subtle)
        tertiary_style = (
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {ThemeColors.TEXT_SECONDARY};"
            f"  border: 1px dashed {ThemeColors.BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 7px 12px;"
            f"  font-weight: 500;"
            f"  font-size: 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {ThemeColors.BG_HOVER};"
            f"  color: {ThemeColors.TEXT_PRIMARY};"
            f"  border-style: solid;"
            f"}}"
            f"QPushButton:disabled {{"
            f"  color: {ThemeColors.TEXT_MUTED};"
            f"  border-color: {ThemeColors.BG_ELEVATED};"
            f"}}"
        )

        # === PRIMARY CTA: Copy + OPX (lon nhat, noi bat nhat) ===
        self._opx_btn = QPushButton("Copy + OPX")
        self._opx_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
            QPushButton:disabled {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_MUTED};
            }}
        """
        )
        self._opx_btn.setToolTip("Copy context with OPX instructions (Ctrl+Shift+C)")
        self._opx_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._opx_btn.clicked.connect(lambda: self._copy_context(include_xml=True))
        layout.addWidget(self._opx_btn)

        # === SECONDARY: Copy Context ===
        self._copy_btn = QPushButton("Copy Context")
        self._copy_btn.setStyleSheet(secondary_style)
        self._copy_btn.setToolTip("Copy context with basic formatting (Ctrl+C)")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(lambda: self._copy_context(include_xml=False))
        layout.addWidget(self._copy_btn)

        # === SECONDARY: Copy Smart ===
        self._smart_btn = QPushButton("Copy Smart")
        self._smart_btn.setProperty("custom-style", "orange")
        self._smart_btn.setStyleSheet(
            f"""
            QPushButton[custom-style="orange"] {{
                background-color: transparent;
                color: {ThemeColors.WARNING};
                border: 1px solid {ThemeColors.WARNING};
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton[custom-style="orange"]:hover {{
                background-color: {ThemeColors.WARNING};
                color: white;
            }}
            QPushButton[custom-style="orange"]:pressed {{
                background-color: #D97706;
                color: white;
            }}
            QPushButton[custom-style="orange"]:disabled {{
                color: {ThemeColors.TEXT_MUTED};
                border-color: {ThemeColors.BG_ELEVATED};
            }}
        """
        )
        self._smart_btn.setToolTip("Copy code structure only (Smart Context)")
        self._smart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._smart_btn.clicked.connect(self._copy_smart_context)
        layout.addWidget(self._smart_btn)

        # === SECONDARY: Copy Diff Only ===
        self._diff_btn = QPushButton("Copy Diff Only")
        self._diff_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: #A78BFA;
                border: 1px solid #8B5CF6;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #8B5CF6;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: #7C3AED;
                color: white;
            }}
            QPushButton:disabled {{
                color: {ThemeColors.TEXT_MUTED};
                border-color: {ThemeColors.BG_ELEVATED};
            }}
        """
        )
        self._diff_btn.setToolTip("Copy only git diff (Ctrl+Shift+D)")
        self._diff_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._diff_btn.clicked.connect(self._show_diff_only_dialog)
        layout.addWidget(self._diff_btn)

        # === TERTIARY: Copy Tree Map ===
        self._tree_map_btn = QPushButton("Copy Tree Map")
        self._tree_map_btn.setStyleSheet(secondary_style)
        self._tree_map_btn.setToolTip("Copy only file structure")
        self._tree_map_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tree_map_btn.clicked.connect(self._copy_tree_map_only)
        layout.addWidget(self._tree_map_btn)

        return widget

    # ===== Public API =====

    def on_workspace_changed(self, workspace_path: Path) -> None:
        """Handle workspace change."""
        from core.logging_config import log_info

        log_info(f"[ContextView] Workspace changing to: {workspace_path}")

        # 1. Stop file watcher for old workspace
        if self._file_watcher:
            self._file_watcher.stop()

        # 2. Deactivate related mode to clean up state
        if self._related_mode_active:
            self._related_mode_active = False
            self._last_added_related_files.clear()
            self._related_menu_btn.setText("Related: Off")

        # 3. Clear security scan cache for old workspace
        from core.security_check import clear_security_cache

        clear_security_cache()

        # 4. Load new tree (this increments generation counter, cancels old workers)
        self.file_tree_widget.load_tree(workspace_path)
        self.tree = self.file_tree_widget.get_model()._root_node  # type: ignore

        # 5. Reset token display
        self._token_count_label.setText("0 tokens")
        self._token_stats.update_stats(
            file_count=0, file_tokens=0, instruction_tokens=0
        )

        # 6. Start file watcher for new workspace
        if self._file_watcher and workspace_path.exists():
            self._file_watcher.start(
                path=workspace_path,
                callbacks=WatcherCallbacks(
                    on_file_modified=self._on_file_modified,
                    on_file_created=self._on_file_created,
                    on_file_deleted=self._on_file_deleted,
                    on_batch_change=self._on_file_system_changed,
                ),
                debounce_seconds=0.5,
            )

    def restore_tree_state(
        self, selected_files: List[str], expanded_folders: List[str]
    ) -> None:
        """Restore tree state từ session."""
        if selected_files:
            valid = {f for f in selected_files if Path(f).exists()}
            self.file_tree_widget.set_selected_paths(valid)
        if expanded_folders:
            valid = {f for f in expanded_folders if Path(f).exists()}
            self.file_tree_widget.set_expanded_paths(valid)
        self._update_token_display()

    def set_instructions_text(self, text: str) -> None:
        """Set instructions text (session restore)."""
        self._instructions_field.setPlainText(text)

    def get_instructions_text(self) -> str:
        return self._instructions_field.toPlainText()

    def get_selected_paths(self) -> List[str]:
        return self.file_tree_widget.get_selected_paths()

    def get_expanded_paths(self) -> List[str]:
        return self.file_tree_widget.get_expanded_paths()

    def cleanup(self) -> None:
        """Cleanup resources."""
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

        # Cancel status timer
        if self._status_timer is not None:
            try:
                self._status_timer.stop()
                self._status_timer.deleteLater()
            except RuntimeError:
                pass
            self._status_timer = None

        self.file_tree_widget.cleanup()

    # ===== Slots =====

    @Slot(set)
    def _on_selection_changed(self, selected_paths: set) -> None:
        """Handle selection change — update display + trigger related resolution if active."""
        self._token_generation += 1
        self._update_token_display()

        # Auto-resolve related files when mode is active
        if self._related_mode_active and not self._resolving_related:
            self._resolve_related_files()

    @Slot()
    def _on_instructions_changed(self) -> None:
        """Handle instructions text change - cap nhat word count va token display."""
        text = self._instructions_field.toPlainText()
        word_count = len(text.split()) if text.strip() else 0
        self._word_count_label.setText(f"{word_count} words")
        QTimer.singleShot(150, self._update_token_display)

    @Slot(int)
    def _on_format_changed(self, index: int) -> None:
        """Handle format dropdown change."""
        format_id = self._format_combo.currentData()
        if format_id:
            try:
                self._selected_output_style = get_style_by_id(format_id)
                set_setting("output_format", format_id)
            except ValueError:
                pass

    # ===== Token Counting =====

    def _update_token_display(self) -> None:
        """Update token count display tu cached values. Khong trigger counting.

        Hien thi file tokens + instruction tokens tren toolbar.
        Tooltip canh bao rang actual copy se co them overhead
        (tree map, git, OPX, XML structure).
        """
        model = self.file_tree_widget.get_model()
        file_count = model.get_selected_file_count()

        # Count instruction tokens
        instructions = self._instructions_field.toPlainText()
        instruction_tokens = count_tokens(instructions) if instructions else 0

        # Get cached tokens
        total_file_tokens = self.file_tree_widget.get_total_tokens()
        total = total_file_tokens + instruction_tokens

        self._token_count_label.setText(f"{total:,} tokens")

        # Tooltip canh bao overhead khi copy
        self._token_count_label.setToolTip(
            f"{total_file_tokens:,} file tokens + {instruction_tokens:,} instruction tokens\n\n"
            "Note: Actual prompt size will be larger due to:\n"
            "- Tree map (project structure)\n"
            "- Git changes (diff + log)\n"
            "- OPX instructions (if using Copy + OPX)\n"
            "- XML/JSON tags wrapping\n\n"
            "Hover over the status message after copying to see detailed breakdown."
        )

        # Update stats panel
        self._token_stats.update_stats(
            file_count=file_count,
            file_tokens=total_file_tokens,
            instruction_tokens=instruction_tokens,
        )
        self._selection_meta_label.setText(f"{file_count:,} selected")

    @Slot(str)
    def _on_model_changed(self, model_id: str) -> None:
        """
        Handler when user changes model.

        Resets encoder and clears cache to trigger recount with the new tokenizer.
        """
        # Ensure the global encoder is reset immediately for next counts
        from core.token_counter import reset_encoder

        reset_encoder()

        # Clear token cache (since tokenizer has changed)
        model = self.file_tree_widget.get_model()
        model._token_cache.clear()

        # Trigger recount for selected files
        self.file_tree_widget._start_token_counting()

        self._show_status(f"Recounting tokens with {model_id}...")

    # ===== Copy Actions =====

    def _copy_context(self, include_xml: bool = False) -> None:
        """Copy context with selected format."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        selected_files = self.file_tree_widget.get_selected_paths()
        if not selected_files:
            self._show_status("No files selected", is_error=True)
            return

        file_paths = [Path(p) for p in selected_files if Path(p).is_file()]
        instructions = self._instructions_field.toPlainText()

        try:
            # Security check
            security_enabled = get_setting("enable_security_check", True)
            if security_enabled:
                file_path_strs = {str(p) for p in file_paths}
                matches = scan_secrets_in_files_cached(file_path_strs)
                if matches:
                    from components.dialogs_qt import SecurityDialogQt

                    dialog = SecurityDialogQt(
                        parent=self,
                        matches=matches,
                        prompt="",
                        on_copy_anyway=lambda _prompt: self._do_copy_context(
                            workspace, file_paths, instructions, include_xml
                        ),
                    )
                    dialog.exec()
                    return

            self._do_copy_context(workspace, file_paths, instructions, include_xml)
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    # ===== Background Copy Helpers =====

    def _set_copy_buttons_enabled(self, enabled: bool) -> None:
        """
        Enable/disable tat ca copy buttons.

        Goi khi bat dau/ket thuc copy operation de tranh user
        nhan nhieu lan khi dang xu ly.
        """
        for btn in (
            self._diff_btn,
            self._tree_map_btn,
            self._smart_btn,
            self._copy_btn,
            self._opx_btn,
        ):
            btn.setEnabled(enabled)

    def _run_copy_in_background(
        self,
        task_fn,
        success_template: str = "Copied! ({token_count:,} tokens)",
        pre_snapshot: Optional[dict] = None,
    ) -> None:
        """
        Chay mot copy task tren background thread.

        Flow:
        1. Disable tat ca copy buttons
        2. Hien thi "Dang chuan bi..."
        3. Start CopyTaskWorker tren QThreadPool
        4. Khi xong: copy to clipboard, show breakdown (neu co snapshot), enable buttons

        Args:
            task_fn: Callable tra ve prompt string (chay tren background thread)
            success_template: Template cho status message, co {token_count}
            pre_snapshot: Dict snapshot cac gia tri token truoc khi copy.
                Keys: file_tokens, instruction_tokens, include_opx, copy_mode.
                Dung de tinh overhead = total - file_tokens - instruction_tokens.
        """
        self._set_copy_buttons_enabled(False)
        self._show_status("Preparing context...")

        worker = CopyTaskWorker(task_fn)
        self._current_copy_worker = worker

        def on_finished(prompt: str, token_count: int):
            """Callback khi worker hoan thanh (chay tren main thread qua signal)."""
            self._current_copy_worker = None
            copy_to_clipboard(prompt)

            if pre_snapshot:
                # Tinh breakdown tu snapshot va total tokens
                self._show_copy_breakdown(token_count, pre_snapshot)
            else:
                self._show_status(success_template.format(token_count=token_count))

            self._set_copy_buttons_enabled(True)

        def on_error(error_msg: str):
            """Callback khi worker gap loi."""
            self._current_copy_worker = None
            self._show_status(f"Error: {error_msg}", is_error=True)
            self._set_copy_buttons_enabled(True)

        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)

    def _do_copy_context(
        self,
        workspace: Path,
        file_paths: List[Path],
        instructions: str,
        include_xml: bool,
    ) -> None:
        """
        Execute copy context tren background thread.

        Heavy work (scan tree, doc files, generate prompt, count tokens)
        chay background de UI khong bi freeze.
        """
        # Snapshot tat ca inputs truoc khi chuyen sang background thread
        selected_path_strs = {str(p) for p in file_paths}
        use_rel = get_use_relative_paths()
        output_style = self._selected_output_style
        include_git = get_setting("include_git_changes", True)

        def task():
            """Heavy work - chay tren background thread."""
            # Scan full tree tu disk (I/O bound)
            tree_item = self._scan_full_tree(workspace)
            file_map = (
                generate_file_map(
                    tree_item,
                    selected_path_strs,
                    workspace_root=workspace,
                    use_relative_paths=use_rel,
                )
                if tree_item
                else ""
            )

            # Doc noi dung files (I/O bound)
            if output_style == OutputStyle.XML:
                file_contents = generate_file_contents_xml(
                    selected_path_strs,
                    workspace_root=workspace,
                    use_relative_paths=use_rel,
                )
            elif output_style == OutputStyle.JSON:
                file_contents = generate_file_contents_json(
                    selected_path_strs,
                    workspace_root=workspace,
                    use_relative_paths=use_rel,
                )
            else:
                file_contents = generate_file_contents_plain(
                    selected_path_strs,
                    workspace_root=workspace,
                    use_relative_paths=use_rel,
                )

            # Git diff/log (subprocess)
            git_diffs = None
            git_logs = None
            if include_git:
                git_diffs = get_git_diffs(workspace)
                git_logs = get_git_logs(workspace, max_commits=5)

            # Generate prompt (CPU bound)
            return generate_prompt(
                file_map=file_map,
                file_contents=file_contents,
                user_instructions=instructions,
                output_style=output_style,
                include_xml_formatting=include_xml,
                git_diffs=git_diffs,
                git_logs=git_logs,
            )

        # Snapshot token values truoc khi background task chay
        # de tinh overhead sau khi copy hoan thanh
        pre_snapshot = {
            "file_tokens": self.file_tree_widget.get_total_tokens(),
            "instruction_tokens": count_tokens(instructions) if instructions else 0,
            "include_opx": include_xml,
            "copy_mode": "Copy + OPX" if include_xml else "Copy Context",
        }

        self._run_copy_in_background(
            task,
            "Copied! ({token_count:,} tokens)",
            pre_snapshot=pre_snapshot,
        )

    def _copy_smart_context(self) -> None:
        """
        Copy smart context (code structure only) tren background thread.

        Smart context chi generate code structure (symbols, relationships)
        thay vi noi dung file day du.
        """
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        selected_files = self.file_tree_widget.get_selected_paths()
        if not selected_files:
            self._show_status("No files selected", is_error=True)
            return

        # Snapshot inputs truoc khi chuyen sang background
        file_paths = [Path(p) for p in selected_files if Path(p).is_file()]
        selected_path_strs = {str(p) for p in file_paths}
        instructions = self._instructions_field.toPlainText()
        use_rel = get_use_relative_paths()
        include_git = get_setting("include_git_changes", True)

        def task():
            """Heavy work - chay tren background thread."""
            assert workspace is not None  # Type narrowing
            tree_item = self._scan_full_tree(workspace)
            file_map = (
                generate_file_map(
                    tree_item,
                    selected_path_strs,
                    workspace_root=workspace,
                    use_relative_paths=use_rel,
                )
                if tree_item
                else ""
            )
            smart_contents = generate_smart_context(
                selected_paths=selected_path_strs,
                include_relationships=True,
                workspace_root=workspace,
                use_relative_paths=use_rel,
            )
            git_diffs = None
            git_logs = None
            if include_git:
                git_diffs = get_git_diffs(workspace)
                git_logs = get_git_logs(workspace, max_commits=5)
            return build_smart_prompt(
                smart_contents=smart_contents,
                file_map=file_map,
                user_instructions=instructions,
                git_diffs=git_diffs,
                git_logs=git_logs,
            )

        # Snapshot token values truoc khi chay background task
        pre_snapshot = {
            "file_tokens": self.file_tree_widget.get_total_tokens(),
            "instruction_tokens": count_tokens(instructions) if instructions else 0,
            "include_opx": False,
            "copy_mode": "Copy Smart",
        }

        self._run_copy_in_background(
            task,
            "Smart context copied! ({token_count:,} tokens)",
            pre_snapshot=pre_snapshot,
        )

    def _copy_tree_map_only(self) -> None:
        """
        Copy tree map only tren background thread.

        Generate cau truc cay thu muc va copy clipboard.
        """
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        # Snapshot inputs
        selected_files = self.file_tree_widget.get_selected_paths()
        selected_strs = set(selected_files) if selected_files else set()
        instructions = (
            self._instructions_field.toPlainText()
            if hasattr(self, "_instructions_field")
            else ""
        )
        use_rel = get_use_relative_paths()

        def task():
            """Heavy work - chay tren background thread."""
            assert workspace is not None  # Type narrowing
            tree_item = self._scan_full_tree(workspace)
            if not tree_item:
                raise ValueError("No file tree loaded")

            # Collect valid paths from scanned tree (respect gitignore/excluded)
            valid_paths = self._collect_all_tree_paths(tree_item)

            # Filter selected paths to only include valid ones
            paths = selected_strs & valid_paths if selected_strs else valid_paths

            return generate_tree_map_only(
                tree_item,
                paths,
                instructions,
                workspace_root=workspace,
                use_relative_paths=use_rel,
            )

        # Snapshot (tree map chi co instruction tokens, khong co file content)
        pre_snapshot = {
            "file_tokens": 0,
            "instruction_tokens": count_tokens(instructions) if instructions else 0,
            "include_opx": False,
            "copy_mode": "Copy Tree Map",
        }

        self._run_copy_in_background(
            task,
            "Tree map copied! ({token_count:,} tokens)",
            pre_snapshot=pre_snapshot,
        )

    def _collect_all_tree_paths(self, root: TreeItem) -> Set[str]:
        """Collect all node paths from a TreeItem tree."""
        paths: Set[str] = set()

        def _walk(node: TreeItem) -> None:
            paths.add(node.path)
            for child in node.children:
                _walk(child)

        _walk(root)
        return paths

    def _scan_full_tree(self, workspace: Path) -> TreeItem:
        """Scan full workspace tree with current exclude settings."""
        return scan_directory(
            workspace,
            excluded_patterns=get_excluded_patterns(),
            use_gitignore=get_use_gitignore(),
        )

    def _show_diff_only_dialog(self) -> None:
        """Show diff only dialog."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return

        try:
            from components.dialogs_qt import DiffOnlyDialogQt
            from core.utils.git_utils import build_diff_only_prompt

            def _build_diff_prompt(
                diff_result, instructions, include_content, include_tree
            ):
                return build_diff_only_prompt(
                    diff_result,
                    instructions,
                    include_content,
                    include_tree,
                    workspace_root=workspace,
                    use_relative_paths=get_use_relative_paths(),
                )

            dialog = DiffOnlyDialogQt(
                parent=self,
                workspace=workspace,
                build_prompt_callback=_build_diff_prompt,
                instructions=self._instructions_field.toPlainText(),
                on_success=lambda msg: self._show_status(msg),
            )
            dialog.exec()
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

    # ===== Tree Management =====

    @Slot()
    def _refresh_tree(self) -> None:
        """Refresh file tree."""
        workspace = self.get_workspace()
        if workspace:
            self.file_tree_widget.load_tree(workspace)

    def _add_to_ignore(self) -> None:
        """Add selected to ignore list."""
        selected = self.file_tree_widget.get_all_selected_paths()
        if not selected:
            self._show_status("No files selected", is_error=True)
            return

        workspace = self.get_workspace()
        if not workspace:
            return

        from views.settings_view_qt import add_excluded_patterns

        patterns = []
        for p in selected:
            try:
                rel = Path(p).relative_to(workspace)
                # Use full relative path for gitignore-style matching
                patterns.append(str(rel))
            except ValueError:
                continue

        unique = list(set(patterns))
        if unique and add_excluded_patterns(unique):
            self._last_ignored_patterns = unique
            self._show_status(f"Added {len(unique)} pattern(s). Click Undo to revert.")
            self._refresh_tree()

    def _undo_ignore(self) -> None:
        """Undo last ignore."""
        if not self._last_ignored_patterns:
            self._show_status("Nothing to undo", is_error=True)
            return

        from views.settings_view_qt import remove_excluded_patterns

        if remove_excluded_patterns(self._last_ignored_patterns):
            self._show_status(f"Removed {len(self._last_ignored_patterns)} pattern(s)")
            self._last_ignored_patterns = []
            self._refresh_tree()

    @Slot(str)
    def _preview_file(self, file_path: str) -> None:
        """Preview file in dialog."""
        from components.dialogs_qt import FilePreviewDialogQt

        FilePreviewDialogQt.show_preview(self, file_path)

    def _open_remote_repo_dialog(self) -> None:
        """Open remote repo clone dialog."""
        from core.utils.repo_manager import RepoManager
        from components.dialogs_qt import RemoteRepoDialogQt

        if self._repo_manager is None:
            self._repo_manager = RepoManager()

        def on_clone_success(repo_path):
            """Handle successful clone — open the cloned repo as workspace."""
            self._show_status(f"Cloned to {repo_path}")
            self.on_workspace_changed(repo_path)

        dialog = RemoteRepoDialogQt(self, self._repo_manager, on_clone_success)
        dialog.exec()

    def _open_cache_management_dialog(self) -> None:
        """Open cache management dialog for cloned repos."""
        from core.utils.repo_manager import RepoManager
        from components.dialogs_qt import CacheManagementDialogQt

        if self._repo_manager is None:
            self._repo_manager = RepoManager()

        def on_open_repo(repo_path):
            """Handle opening a cached repo."""
            self.on_workspace_changed(repo_path)

        dialog = CacheManagementDialogQt(self, self._repo_manager, on_open_repo)
        dialog.exec()

    # ===== File Watcher Callbacks =====

    def _on_file_modified(self, path: str) -> None:
        """Handle file modified — invalidate caches for the changed file."""
        from core.token_counter import clear_file_from_cache
        from core.security_check import invalidate_security_cache

        clear_file_from_cache(path)
        invalidate_security_cache(path)

    def _on_file_created(self, path: str) -> None:
        """Handle file created — no cache invalidation needed for new files."""

    def _on_file_deleted(self, path: str) -> None:
        """Handle file deleted — delegates to _on_file_modified for cache cleanup."""
        self._on_file_modified(path)

    def _on_file_system_changed(self) -> None:
        """Handle batch file system changes."""
        workspace = self.get_workspace()
        if workspace:
            run_on_main_thread(lambda: self._refresh_tree())

    # ===== Related Files =====

    def _set_related_mode(self, active: bool, depth: int) -> None:
        """Set related mode with specific depth preset."""
        if active:
            self._related_depth = depth
            self._activate_related_mode()
        else:
            self._deactivate_related_mode()

    def _activate_related_mode(self) -> None:
        """Activate related mode and resolve for current selection."""
        self._related_mode_active = True
        self._update_related_button_text()
        self._resolve_related_files()

    def _deactivate_related_mode(self) -> None:
        """Deactivate related mode and remove auto-added files."""
        if self._last_added_related_files:
            removed = self.file_tree_widget.remove_paths_from_selection(
                self._last_added_related_files
            )
            self._show_status(f"Removed {removed} related files")

        self._last_added_related_files.clear()
        self._related_mode_active = False
        self._related_menu_btn.setText("Related: Off")

    def _update_related_button_text(self) -> None:
        """Update button text based on current depth and count."""
        if not self._related_mode_active:
            self._related_menu_btn.setText("Related: Off")
            return

        depth_names = {1: "Direct", 2: "Nearby", 3: "Deep", 4: "Deeper", 5: "Deepest"}
        depth_name = depth_names.get(
            self._related_depth, f"Depth {self._related_depth}"
        )
        count = len(self._last_added_related_files)

        if count > 0:
            self._related_menu_btn.setText(f"Related: {depth_name} ({count})")
        else:
            self._related_menu_btn.setText(f"Related: {depth_name}")

    def _resolve_related_files(self) -> None:
        """Resolve related files for all currently selected files."""
        workspace = self.get_workspace()
        if not workspace:
            return

        assert workspace is not None  # Type narrowing for pyrefly

        # Get user-selected files only (exclude auto-added related files)
        all_selected = self.file_tree_widget.get_all_selected_paths()
        user_selected = all_selected - self._last_added_related_files

        # Filter to supported file types
        supported_exts = {".py", ".js", ".jsx", ".ts", ".tsx"}
        source_files = [
            Path(p)
            for p in user_selected
            if Path(p).is_file() and Path(p).suffix in supported_exts
        ]

        if not source_files:
            if self._last_added_related_files:
                self.file_tree_widget.remove_paths_from_selection(
                    self._last_added_related_files
                )
                self._last_added_related_files.clear()
            self._update_related_button_text()
            return

        depth = self._related_depth

        # Resolve in background to avoid UI freeze
        def resolve():
            assert workspace is not None  # Type narrowing for nested function
            try:
                # Dùng full scan thay vì lazy UI tree — đảm bảo file index đầy đủ
                full_tree = self._scan_full_tree(workspace)
                resolver = DependencyResolver(workspace)
                resolver.build_file_index(full_tree)

                all_related: Set[Path] = set()
                for file_path in source_files:
                    related = resolver.get_related_files(file_path, max_depth=depth)
                    all_related.update(related)

                # Convert to string paths
                related_strs = {str(p) for p in all_related if p.exists()}
                # Exclude files already selected by user
                new_related = related_strs - user_selected

                # Apply on main thread
                run_on_main_thread(
                    lambda: self._apply_related_results(new_related, user_selected)
                )
            except Exception as err:
                error_msg = f"Related files error: {err}"
                run_on_main_thread(lambda: self._show_status(error_msg, is_error=True))

        schedule_background(resolve)

    def _apply_related_results(
        self, new_related: Set[str], user_selected: Set[str]
    ) -> None:
        """Apply resolved related files to selection (main thread)."""
        if not self._related_mode_active:
            return  # Mode was deactivated while resolving

        self._resolving_related = True
        try:
            # Remove previously auto-added files that are no longer related
            old_to_remove = self._last_added_related_files - new_related
            if old_to_remove:
                self.file_tree_widget.remove_paths_from_selection(old_to_remove)

            # Add new related files
            to_add = new_related - self._last_added_related_files
            if to_add:
                self.file_tree_widget.add_paths_to_selection(to_add)

            self._last_added_related_files = new_related

            count = len(new_related)
            self._update_related_button_text()
            if count > 0:
                self._show_status(
                    f"Found {count} related files (depth={self._related_depth})"
                )
            else:
                self._show_status("No related files found")
        finally:
            self._resolving_related = False

    # ===== Helpers =====

    def _show_copy_breakdown(self, total_tokens: int, pre_snapshot: dict) -> None:
        """Hien thi token breakdown than thien voi user sau khi copy.

        Dung cac tu de hieu: "noi dung" (file content), "yeu cau" (instructions),
        "cau truc prompt" (tree map + git + XML tags). Tuy theo copy mode
        se hien thi cac thanh phan khac nhau.

        Args:
            total_tokens: Tong so tokens cua prompt da copy (tu CopyTaskWorker)
            pre_snapshot: Dict snapshot tu truoc khi copy:
                - file_tokens: Token count tu UI cache
                - instruction_tokens: Token count tu textarea
                - include_opx: Co bao gom OPX instructions khong
                - copy_mode: Ten copy mode ("Copy + OPX", "Copy Context", ...)
        """
        file_t = pre_snapshot.get("file_tokens", 0)
        instr_t = pre_snapshot.get("instruction_tokens", 0)
        include_opx = pre_snapshot.get("include_opx", False)
        copy_mode = pre_snapshot.get("copy_mode", "Copied")

        # Uoc luong OPX tokens tu constant (chi tinh 1 lan)
        opx_t = 0
        if include_opx:
            try:
                from core.opx_instruction import XML_FORMATTING_INSTRUCTIONS

                opx_t = count_tokens(XML_FORMATTING_INSTRUCTIONS)
            except ImportError:
                opx_t = 0

        # Calculate structure/overhead
        # If model just changed, snapshot counts might be from old tokenizer
        # In that case, we normalize the breakdown to always add up to total_tokens
        sum_parts = file_t + instr_t + opx_t
        if sum_parts > total_tokens:
            # Tokenizer changed or race condition: reduce parts proportionally
            ratio = total_tokens / sum_parts if sum_parts > 0 else 1.0
            file_t = int(file_t * ratio)
            instr_t = int(instr_t * ratio)
            opx_t = int(opx_t * ratio)
            structure_t = 0
        else:
            structure_t = total_tokens - file_t - instr_t - opx_t
            structure_t = max(0, structure_t)

        # Build breakdown with friendly labels
        parts = []
        if file_t > 0:
            parts.append(f"{file_t:,} content")
        if instr_t > 0:
            parts.append(f"{instr_t:,} instructions")
        if opx_t > 0:
            parts.append(f"{opx_t:,} OPX")
        if structure_t > 0:
            parts.append(f"{structure_t:,} system prompt")

        breakdown_text = " + ".join(parts) if parts else ""

        # Dong 1: tong tokens (don gian, noi bat)
        # Dong 2: breakdown cho biet cai gi tieu hao
        main_msg = f"Copied! {total_tokens:,} tokens"

        # Cancel timer cu
        if self._status_timer is not None:
            try:
                self._status_timer.stop()
                self._status_timer.deleteLater()
            except RuntimeError:
                pass
            self._status_timer = None

        bg_color = "#6EE7B7"
        text_color = "#022C22"
        border_color = "#059669"

        self._status_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: 12px;
                font-weight: 600;
                color: {text_color};
                background-color: {bg_color};
                border-radius: 6px;
                padding: 10px 14px;
                border: 2px solid {border_color};
            }}
        """
        )

        if breakdown_text:
            self._status_label.setText(f"\u2713 {main_msg}\n{breakdown_text}")
        else:
            self._status_label.setText(f"\u2713 {main_msg}")

        # Tooltip giai thich chi tiet tung thanh phan
        tooltip_lines = [
            f"Tong cong: {total_tokens:,} tokens",
            f"",
            f"Noi dung file: {file_t:,} tokens",
            f"Yeu cau (instructions): {instr_t:,} tokens",
        ]
        if opx_t > 0:
            tooltip_lines.append(f"OPX instructions: {opx_t:,} tokens")
        tooltip_lines.extend(
            [
                f"Cau truc prompt: {structure_t:,} tokens",
                f"  (gom: tree map, git diff/log, XML tags)",
            ]
        )
        self._status_label.setToolTip("\n".join(tooltip_lines))

        self._status_label.show()

        # Timer 12 giay (dai hon binh thuong de user doc breakdown)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._status_label.hide)
        self._status_timer.start(12000)

    def _show_status(self, message: str, is_error: bool = False) -> None:
        """Show status message as subtle notification."""
        # Cancel timer cũ để tránh race condition
        if self._status_timer is not None:
            try:
                self._status_timer.stop()
                self._status_timer.deleteLater()
            except RuntimeError:
                pass  # Timer already deleted
            self._status_timer = None

        if not message:
            self._status_label.hide()
            return

        if is_error:
            bg_color = "#FCA5A5"  # Brighter red background
            text_color = "#450A0A"  # Very dark red text — high contrast
            border_color = "#DC2626"  # Solid red border
            icon = "⚠"
        else:
            bg_color = "#6EE7B7"  # Brighter green background
            text_color = "#022C22"  # Very dark green text — high contrast
            border_color = "#059669"  # Solid green border
            icon = "✓"

        self._status_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: 13px;
                font-weight: 700;
                color: {text_color};
                background-color: {bg_color};
                border-radius: 6px;
                padding: 10px 14px;
                border: 2px solid {border_color};
            }}
        """
        )
        self._status_label.setText(f"{icon} {message}")
        self._status_label.show()

        # Tạo timer mới — parented to self for automatic cleanup
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._status_label.hide)
        self._status_timer.start(8000)  # 8 giây
