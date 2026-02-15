"""
Context View (PySide6) - Tab để chọn files và copy context.
"""

import threading
from pathlib import Path
from typing import Optional, Set, List, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QToolButton, QTextEdit,
    QComboBox, QFrame, QMenu, QSpinBox,
)
from PySide6.QtCore import Qt, Slot, QTimer

from core.theme import ThemeColors
from core.utils.qt_utils import (
    run_on_main_thread, schedule_background,
)
from core.utils.file_utils import scan_directory, TreeItem
from core.token_counter import count_tokens
from core.prompt_generator import (
    generate_prompt, generate_file_map, generate_file_contents_xml, generate_file_contents_json,
    generate_file_contents_plain, generate_smart_context,
)
from core.tree_map_generator import generate_tree_map_only
from core.security_check import scan_secrets_in_files_cached
from components.file_tree_widget import FileTreeWidget
from components.token_stats_qt import TokenStatsPanelQt
from services.clipboard_utils import copy_to_clipboard
from services.file_watcher import FileWatcher, WatcherCallbacks
from services.settings_manager import get_setting, set_setting
from views.settings_view_qt import get_excluded_patterns, get_use_gitignore
from config.output_format import (
    OutputStyle, OUTPUT_FORMATS, get_style_by_id, DEFAULT_OUTPUT_STYLE,
)
from core.dependency_resolver import DependencyResolver


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
        
        # Services
        self._file_watcher: Optional[FileWatcher] = FileWatcher()
        self._repo_manager = None  # Lazy init
        
        # Build UI
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Xây dựng UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)
        
        # Main splitter: left (file tree) | right (instructions + actions)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - File Tree
        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Instructions + Actions
        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)
        
        # Set stretch: left=2, right=1
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
    
    def _build_left_panel(self) -> QFrame:
        """Build left panel với file tree."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # Header: "Files" + actions + token count
        header = QHBoxLayout()
        header.setSpacing(6)
        
        files_label = QLabel("Files")
        files_label.setStyleSheet(
            f"font-weight: 600; font-size: 14px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(files_label)
        header.addSpacing(8)
        
        # --- Action buttons (compact, icon-only with tooltips) ---
        btn_style = (
            f"QToolButton {{ "
            f"  background: {ThemeColors.BG_SURFACE}; border: 1px solid {ThemeColors.BORDER}; "
            f"  border-radius: 8px; padding: 6px 10px; font-size: 12px; "
            f"  color: {ThemeColors.TEXT_SECONDARY}; min-width: 32px; min-height: 32px; "
            f"  font-weight: 500; "
            f"}} "
            f"QToolButton:hover {{ "
            f"  background: {ThemeColors.PRIMARY}; color: #FFFFFF; "
            f"  border-color: {ThemeColors.PRIMARY}; "
            f"}}"
        )
        
        # Refresh
        refresh_btn = QToolButton()
        refresh_btn.setText("↻")
        refresh_btn.setToolTip("Refresh file tree (F5)")
        refresh_btn.setStyleSheet(btn_style)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_tree)
        header.addWidget(refresh_btn)
        
        # Remote repos (dropdown)
        remote_btn = QToolButton()
        remote_btn.setText("☁")
        remote_btn.setToolTip("Remote Repositories")
        remote_btn.setStyleSheet(btn_style)
        remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remote_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        remote_menu = QMenu(remote_btn)
        remote_menu.addAction("Clone Repository", self._open_remote_repo_dialog)
        remote_menu.addAction("Manage Cache", self._open_cache_management_dialog)
        remote_btn.setMenu(remote_menu)
        header.addWidget(remote_btn)
        
        # Ignore
        ignore_btn = QToolButton()
        ignore_btn.setText("⊘")
        ignore_btn.setToolTip("Ignore selected files")
        ignore_btn.setStyleSheet(btn_style)
        ignore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ignore_btn.clicked.connect(self._add_to_ignore)
        header.addWidget(ignore_btn)
        
        # Undo ignore
        undo_btn = QToolButton()
        undo_btn.setText("↩")
        undo_btn.setToolTip("Undo last ignore")
        undo_btn.setStyleSheet(btn_style)
        undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        undo_btn.clicked.connect(self._undo_ignore)
        header.addWidget(undo_btn)
        
        header.addSpacing(8)
        
        # --- Related files toggle ---
        related_active_style = (
            f"QToolButton {{ "
            f"  background: {ThemeColors.SUCCESS}; border: 1px solid {ThemeColors.SUCCESS}; "
            f"  border-radius: 8px; padding: 6px 12px; font-size: 12px; "
            f"  color: #FFFFFF; min-height: 32px; font-weight: 600; "
            f"}} "
            f"QToolButton:hover {{ "
            f"  background: #059669; border-color: #059669; "
            f"}}"
        )
        related_inactive_style = (
            f"QToolButton {{ "
            f"  background: {ThemeColors.BG_SURFACE}; border: 1px solid {ThemeColors.BORDER}; "
            f"  border-radius: 8px; padding: 6px 12px; font-size: 12px; "
            f"  color: {ThemeColors.TEXT_SECONDARY}; min-height: 32px; font-weight: 500; "
            f"}} "
            f"QToolButton:hover {{ "
            f"  background: {ThemeColors.PRIMARY}; color: #FFFFFF; "
            f"  border-color: {ThemeColors.PRIMARY}; "
            f"}}"
        )
        self._related_active_style = related_active_style
        self._related_inactive_style = related_inactive_style
        
        self._related_btn = QToolButton()
        self._related_btn.setText("Related")
        self._related_btn.setToolTip("Auto-select files imported by your selection")
        self._related_btn.setStyleSheet(related_inactive_style)
        self._related_btn.setCheckable(True)
        self._related_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._related_btn.clicked.connect(self._toggle_related_mode)
        header.addWidget(self._related_btn)
        
        # Level spinbox
        level_label = QLabel("Depth")
        level_label.setStyleSheet(f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 12px; font-weight: 500;")
        header.addWidget(level_label)
        
        self._related_level_spin = QSpinBox()
        self._related_level_spin.setRange(1, 5)
        self._related_level_spin.setValue(1)
        self._related_level_spin.setToolTip("Relationship depth (1=direct imports, 2+=nested)")
        self._related_level_spin.setFixedWidth(45)
        self._related_level_spin.setFixedHeight(28)
        self._related_level_spin.setStyleSheet(
            f"QSpinBox {{ "
            f"  background: {ThemeColors.BG_ELEVATED}; color: {ThemeColors.TEXT_PRIMARY}; "
            f"  border: 1px solid {ThemeColors.BORDER}; border-radius: 4px; "
            f"  padding: 2px; font-size: 12px; "
            f"}} "
            f"QSpinBox::up-button, QSpinBox::down-button {{ width: 12px; }}"
        )
        self._related_level_spin.valueChanged.connect(self._on_related_level_changed)
        header.addWidget(self._related_level_spin)
        
        header.addStretch()
        
        self._token_count_label = QLabel("0 tokens")
        self._token_count_label.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {ThemeColors.PRIMARY};"
        )
        header.addWidget(self._token_count_label)
        layout.addLayout(header)
        
        # File tree widget
        self.file_tree_widget = FileTreeWidget()
        self.file_tree_widget.selection_changed.connect(self._on_selection_changed)
        self.file_tree_widget.file_preview_requested.connect(self._preview_file)
        self.file_tree_widget.token_counting_done.connect(self._update_token_display)
        layout.addWidget(self.file_tree_widget, stretch=1)
        
        return panel
    
    def _build_right_panel(self) -> QFrame:
        """Build right panel với instructions, format selector, action buttons."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # Instructions
        instr_label = QLabel("Instructions")
        instr_label.setStyleSheet(
            f"font-weight: 600; font-size: 14px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(instr_label)
        
        self._instructions_field = QTextEdit()
        self._instructions_field.setPlaceholderText("Enter your task instructions here...")
        self._instructions_field.setMinimumHeight(280)  # Tăng từ 200 lên 280
        self._instructions_field.setStyleSheet(f"""
            QTextEdit {{
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 13px;
                line-height: 1.6;
            }}
        """)
        self._instructions_field.textChanged.connect(self._on_instructions_changed)
        layout.addWidget(self._instructions_field)
        
        # Format selector
        format_layout = QHBoxLayout()
        format_label = QLabel("Output Format:")
        format_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        format_layout.addWidget(format_label)
        
        self._format_combo = QComboBox()
        self._format_combo.setFixedWidth(160)
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
        
        # Action buttons
        actions = self._build_action_buttons()
        layout.addWidget(actions)
        
        # Status toast (nổi bật hơn)
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setMinimumHeight(40)
        self._status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 600;
                color: white;
                background-color: transparent;
                border-radius: 8px;
                padding: 10px 16px;
            }}
        """)
        self._status_label.hide()  # Ẩn mặc định
        layout.addWidget(self._status_label)
        
        # Token stats panel
        self._token_stats = TokenStatsPanelQt()
        self._token_stats.model_changed.connect(self._on_model_changed)
        layout.addWidget(self._token_stats)
        
        layout.addStretch()
        
        return panel
    
    def _build_action_buttons(self) -> QWidget:
        """Build action buttons."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Row 1: Copy Diff Only
        row1 = QHBoxLayout()
        diff_btn = QPushButton("Copy Diff Only")
        diff_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #8B5CF6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #7C3AED;
            }}
            QPushButton:pressed {{
                background-color: #6D28D9;
            }}
            """
        )
        diff_btn.setToolTip("Copy only git diff (Ctrl+Shift+D)")
        diff_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diff_btn.clicked.connect(self._show_diff_only_dialog)
        row1.addWidget(diff_btn)
        layout.addLayout(row1)
        
        # Row 2: Copy Tree Map + Copy Smart
        row2 = QHBoxLayout()
        tree_map_btn = QPushButton("Copy Tree Map")
        tree_map_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 2px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SURFACE};
                border-color: {ThemeColors.BORDER_LIGHT};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.BG_ELEVATED};
            }}
            """
        )
        tree_map_btn.setToolTip("Copy only file structure")
        tree_map_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tree_map_btn.clicked.connect(self._copy_tree_map_only)
        row2.addWidget(tree_map_btn)
        
        smart_btn = QPushButton("Copy Smart")
        smart_btn.setProperty("custom-style", "orange")  # Prevent global override
        smart_btn.setStyleSheet(
            f"""
            QPushButton[custom-style="orange"] {{
                color: {ThemeColors.WARNING};
                border: 2px solid {ThemeColors.WARNING};
                background-color: {ThemeColors.BG_PAGE};
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton[custom-style="orange"]:hover {{
                background-color: {ThemeColors.WARNING};
                color: white;
                border-color: {ThemeColors.WARNING};
            }}
            QPushButton[custom-style="orange"]:pressed {{
                background-color: #D97706;
                border-color: #D97706;
                color: white;
            }}
            """
        )
        smart_btn.setToolTip("Copy code structure only (Smart Context)")
        smart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        smart_btn.clicked.connect(self._copy_smart_context)
        row2.addWidget(smart_btn)
        layout.addLayout(row2)
        
        # Row 3: Copy Context + Copy + OPX
        row3 = QHBoxLayout()
        copy_btn = QPushButton("Copy Context")
        copy_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 2px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SURFACE};
                border-color: {ThemeColors.BORDER_LIGHT};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.BG_ELEVATED};
            }}
            """
        )
        copy_btn.setToolTip("Copy context with basic formatting (Ctrl+C)")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: self._copy_context(include_xml=False))
        row3.addWidget(copy_btn)
        
        opx_btn = QPushButton("Copy + OPX")
        opx_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: #1E40AF;
            }}
            """
        )
        opx_btn.setToolTip("Copy context with OPX instructions (Ctrl+Shift+C)")
        opx_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        opx_btn.clicked.connect(lambda: self._copy_context(include_xml=True))
        row3.addWidget(opx_btn)
        layout.addLayout(row3)
        
        return widget
    
    # ===== Public API =====
    
    def on_workspace_changed(self, workspace_path: Path) -> None:
        """Handle workspace change."""
        from core.logging_config import log_info
        
        log_info(f"[ContextView] Workspace changing to: {workspace_path}")
        
        if self._file_watcher:
            self._file_watcher.stop()
        
        self.file_tree_widget.load_tree(workspace_path)
        self.tree = self.file_tree_widget.get_model()._root_node  # type: ignore
        
        # Start file watcher
        if self._file_watcher:
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
    
    def restore_tree_state(self, selected_files: List[str], expanded_folders: List[str]) -> None:
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
        """Handle instructions text change."""
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
        """Update token count display từ cached values. Không trigger counting."""
        model = self.file_tree_widget.get_model()
        file_count = model.get_selected_file_count()
        
        # Count instruction tokens
        instructions = self._instructions_field.toPlainText()
        instruction_tokens = count_tokens(instructions) if instructions else 0
        
        # Get cached tokens
        total_file_tokens = self.file_tree_widget.get_total_tokens()
        total = total_file_tokens + instruction_tokens
        
        self._token_count_label.setText(f"{total:,} tokens")
        
        # Update stats panel
        self._token_stats.update_stats(
            file_count=file_count,
            file_tokens=total_file_tokens,
            instruction_tokens=instruction_tokens,
        )
    
    @Slot(str)
    def _on_model_changed(self, model_id: str) -> None:
        """
        Handler khi user đổi model.
        
        Clear cache và trigger recount với tokenizer mới.
        """
        # Clear token cache (vì tokenizer đã thay đổi)
        model = self.file_tree_widget.get_model()
        model._token_cache.clear()
        
        # Trigger recount cho selected files
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
    
    def _do_copy_context(
        self, workspace: Path, file_paths: List[Path],
        instructions: str, include_xml: bool,
    ) -> None:
        """Execute copy context."""
        try:
            selected_path_strs = {str(p) for p in file_paths}
            # Use full scan to avoid missing deep branches from lazy tree model.
            tree_item = self._scan_full_tree(workspace)
            file_map = generate_file_map(tree_item, selected_path_strs) if tree_item else ""
            
            if self._selected_output_style == OutputStyle.XML:
                file_contents = generate_file_contents_xml(selected_path_strs)
            elif self._selected_output_style == OutputStyle.JSON:
                file_contents = generate_file_contents_json(selected_path_strs)
            else:
                file_contents = generate_file_contents_plain(selected_path_strs)
            
            prompt = generate_prompt(
                file_map=file_map,
                file_contents=file_contents,
                user_instructions=instructions,
                output_style=self._selected_output_style,
                include_xml_formatting=include_xml,
            )
            copy_to_clipboard(prompt)
            token_count = count_tokens(prompt)
            self._show_status(f"Copied! ({token_count:,} tokens)")
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)
    
    def _copy_smart_context(self) -> None:
        """Copy smart context (code structure only)."""
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
            selected_path_strs = {str(p) for p in file_paths}
            prompt = generate_smart_context(
                selected_paths=selected_path_strs,
                include_relationships=True,
            )
            if instructions:
                prompt = f"{prompt}\n\n<instructions>\n{instructions}\n</instructions>"
            copy_to_clipboard(prompt)
            token_count = count_tokens(prompt)
            self._show_status(f"Smart context copied! ({token_count:,} tokens)")
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)
    
    def _copy_tree_map_only(self) -> None:
        """Copy tree map only."""
        workspace = self.get_workspace()
        if not workspace:
            self._show_status("No workspace selected", is_error=True)
            return
        
        try:
            selected_files = self.file_tree_widget.get_selected_paths()
            selected_strs = set(selected_files) if selected_files else set()
            tree_item = self._scan_full_tree(workspace)
            if not tree_item:
                self._show_status("No file tree loaded", is_error=True)
                return

            # No selection => generate full project tree map from full scan.
            if not selected_strs:
                selected_strs = self._collect_all_tree_paths(tree_item)

            instructions = self._instructions_field.toPlainText() if hasattr(self, '_instructions_field') else ""
            tree_map = generate_tree_map_only(tree_item, selected_strs, instructions)
            copy_to_clipboard(tree_map)
            self._show_status("Tree map copied!")
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)

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
            dialog = DiffOnlyDialogQt(
                parent=self,
                workspace=workspace,
                build_prompt_callback=build_diff_only_prompt,
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
    
    @Slot()
    def _toggle_related_mode(self) -> None:
        """Toggle related files mode on/off."""
        if self._related_mode_active:
            self._deactivate_related_mode()
        else:
            self._activate_related_mode()
    
    def _activate_related_mode(self) -> None:
        """Activate related mode and resolve for current selection."""
        self._related_mode_active = True
        self._related_btn.setChecked(True)
        self._related_btn.setStyleSheet(self._related_active_style)
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
        self._related_btn.setChecked(False)
        self._related_btn.setText("🔗 Related")
        self._related_btn.setStyleSheet(self._related_inactive_style)
    
    @Slot(int)
    def _on_related_level_changed(self, value: int) -> None:
        """Handle level spinbox change — re-resolve if mode active."""
        if self._related_mode_active:
            # Remove old related files first
            if self._last_added_related_files:
                self.file_tree_widget.remove_paths_from_selection(
                    self._last_added_related_files
                )
                self._last_added_related_files.clear()
            self._resolve_related_files()
    
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
            Path(p) for p in user_selected
            if Path(p).is_file() and Path(p).suffix in supported_exts
        ]
        
        if not source_files:
            if self._last_added_related_files:
                self.file_tree_widget.remove_paths_from_selection(
                    self._last_added_related_files
                )
                self._last_added_related_files.clear()
            self._related_btn.setText("🔗 Related")
            return
        
        depth = self._related_level_spin.value()
        
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
                run_on_main_thread(lambda: self._apply_related_results(new_related, user_selected))
            except Exception as e:
                run_on_main_thread(
                    lambda: self._show_status(f"Related files error: {e}", is_error=True)
                )
        
        schedule_background(resolve)
    
    def _apply_related_results(self, new_related: Set[str], user_selected: Set[str]) -> None:
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
            self._related_btn.setText(f"🔗 Related ({count})")
            if count > 0:
                self._show_status(
                    f"Found {count} related files (depth={self._related_level_spin.value()})"
                )
            else:
                self._show_status("No related files found")
        finally:
            self._resolving_related = False
    
    # ===== Helpers =====
    
    def _show_status(self, message: str, is_error: bool = False) -> None:
        """Show status message as subtle notification."""
        # Cancel timer cũ để tránh race condition
        if self._status_timer is not None:
            self._status_timer.stop()
            self._status_timer = None
        
        if is_error:
            bg_color = "#FEE2E2"  # Light red background
            text_color = "#7F1D1D"  # Darker red text (tăng tương phản)
            icon = "⚠"
        else:
            bg_color = "#A7F3D0"  # Darker green background (tăng tương phản)
            text_color = "#064E3B"  # Darker green text
            icon = "✓"
        
        self._status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 600;
                color: {text_color};
                background-color: {bg_color};
                border-radius: 6px;
                padding: 8px 12px;
                border: 1px solid {text_color}66;
            }}
        """)
        self._status_label.setText(f"{icon} {message}")
        self._status_label.show()
        
        # Tạo timer mới
        if message:
            self._status_timer = QTimer()
            self._status_timer.setSingleShot(True)
            self._status_timer.timeout.connect(self._status_label.hide)
            self._status_timer.start(8000)  # 8 giây
