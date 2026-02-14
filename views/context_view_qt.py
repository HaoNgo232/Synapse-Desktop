"""
Context View (PySide6) - Tab để chọn files và copy context.

Refactored từ Flet version, sử dụng FileTreeWidget + signals/slots.
"""

import os
import threading
from pathlib import Path
from typing import Optional, Set, List, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QToolButton, QTextEdit,
    QComboBox, QFrame, QMenu, QProgressBar, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThreadPool

from core.theme import ThemeColors
from core.utils.qt_utils import (
    DebouncedTimer, run_on_main_thread, schedule_background,
)
from core.utils.file_utils import scan_directory_shallow, TreeItem
from core.token_counter import count_tokens_batch_parallel, count_tokens
from core.prompt_generator import (
    generate_prompt, generate_file_map, generate_file_contents,
    generate_file_contents_xml, generate_file_contents_json,
    generate_file_contents_plain, generate_smart_context,
)
from core.utils.git_utils import get_git_diffs, get_git_logs, DiffOnlyResult
from core.tree_map_generator import generate_tree_map_only
from core.security_check import scan_for_secrets, scan_secrets_in_files_cached
from components.file_tree_widget import FileTreeWidget
from components.token_stats_qt import TokenStatsPanelQt
from services.clipboard_utils import copy_to_clipboard
from services.file_watcher import FileWatcher, WatcherCallbacks
from services.settings_manager import get_setting, set_setting
from views.settings_view_qt import get_excluded_patterns, get_use_gitignore
from config.output_format import (
    OutputStyle, OUTPUT_FORMATS, get_format_tooltip,
    get_style_by_id, DEFAULT_OUTPUT_STYLE,
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
        self._loading_lock = threading.Lock()
        self._is_loading = False
        self._pending_refresh = False
        self._token_generation = 0
        
        # Services
        self._file_watcher: Optional[FileWatcher] = FileWatcher()
        
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
        
        # Header: "Files" + token count
        header = QHBoxLayout()
        files_label = QLabel("Files")
        files_label.setStyleSheet(
            f"font-weight: 600; font-size: 14px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(files_label)
        header.addStretch()
        
        self._token_count_label = QLabel("0 tokens")
        self._token_count_label.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {ThemeColors.PRIMARY};"
        )
        header.addWidget(self._token_count_label)
        layout.addLayout(header)
        
        # Toolbar
        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)
        
        # File tree widget
        self.file_tree_widget = FileTreeWidget()
        self.file_tree_widget.selection_changed.connect(self._on_selection_changed)
        self.file_tree_widget.file_preview_requested.connect(self._preview_file)
        layout.addWidget(self.file_tree_widget, stretch=1)
        
        return panel
    
    def _build_toolbar(self) -> QWidget:
        """Build toolbar với action buttons."""
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)
        
        layout.addStretch()
        
        # Refresh
        refresh_btn = QToolButton()
        refresh_btn.setText("🔄")
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self._refresh_tree)
        layout.addWidget(refresh_btn)
        
        # Remote repos menu
        remote_btn = QPushButton("Remote Repos")
        remote_btn.setProperty("class", "outlined")
        remote_btn.setFixedHeight(28)
        remote_menu = QMenu(remote_btn)
        remote_menu.addAction("Clone Repository", self._open_remote_repo_dialog)
        remote_menu.addAction("Manage Cache", self._open_cache_management_dialog)
        remote_btn.setMenu(remote_menu)
        layout.addWidget(remote_btn)
        
        # Ignore buttons
        ignore_btn = QToolButton()
        ignore_btn.setText("🚫")
        ignore_btn.setToolTip("Add selected to ignore list")
        ignore_btn.clicked.connect(self._add_to_ignore)
        layout.addWidget(ignore_btn)
        
        undo_btn = QToolButton()
        undo_btn.setText("↩")
        undo_btn.setToolTip("Undo last ignore")
        undo_btn.clicked.connect(self._undo_ignore)
        layout.addWidget(undo_btn)
        
        return toolbar
    
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
        self._instructions_field.setMaximumHeight(120)
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
        
        # Status text
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.SUCCESS};")
        layout.addWidget(self._status_label)
        
        # Token stats panel
        self._token_stats = TokenStatsPanelQt()
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
            f"background-color: #8B5CF6; color: #FFFFFF; border: none; "
            f"border-radius: 6px; padding: 8px 16px; font-weight: 500;"
        )
        diff_btn.setToolTip("Copy only git diff")
        diff_btn.clicked.connect(self._show_diff_only_dialog)
        row1.addWidget(diff_btn)
        layout.addLayout(row1)
        
        # Row 2: Copy Tree Map + Copy Smart
        row2 = QHBoxLayout()
        tree_map_btn = QPushButton("Copy Tree Map")
        tree_map_btn.setProperty("class", "outlined")
        tree_map_btn.setToolTip("Copy only file structure")
        tree_map_btn.clicked.connect(self._copy_tree_map_only)
        row2.addWidget(tree_map_btn)
        
        smart_btn = QPushButton("Copy Smart")
        smart_btn.setStyleSheet(
            f"color: {ThemeColors.WARNING}; border: 1px solid {ThemeColors.WARNING}; "
            f"background: transparent; border-radius: 6px; padding: 8px 16px; font-weight: 500;"
        )
        smart_btn.setToolTip("Copy code structure only")
        smart_btn.clicked.connect(self._copy_smart_context)
        row2.addWidget(smart_btn)
        layout.addLayout(row2)
        
        # Row 3: Copy Context + Copy + OPX
        row3 = QHBoxLayout()
        copy_btn = QPushButton("Copy Context")
        copy_btn.setProperty("class", "outlined")
        copy_btn.setToolTip("Copy context with basic formatting")
        copy_btn.clicked.connect(lambda: self._copy_context(include_xml=False))
        row3.addWidget(copy_btn)
        
        opx_btn = QPushButton("Copy + OPX")
        opx_btn.setProperty("class", "primary")
        opx_btn.setToolTip("Copy context with OPX instructions")
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
        self._update_token_count()
    
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
        """Handle selection change với adaptive debouncing."""
        self._token_generation += 1
        self._update_token_count()
    
    @Slot()
    def _on_instructions_changed(self) -> None:
        """Handle instructions text change."""
        QTimer.singleShot(150, self._update_token_count)
    
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
    
    def _update_token_count(self) -> None:
        """Update token count display."""
        selected_files = self.file_tree_widget.get_selected_paths()
        file_count = len(selected_files)
        
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
            tree_item = self.file_tree_widget.get_root_tree_item()
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
            tree_item = self.file_tree_widget.get_root_tree_item()
            if not tree_item:
                self._show_status("No file tree loaded", is_error=True)
                return
            instructions = self._instructions_field.toPlainText() if hasattr(self, '_instructions_field') else ""
            tree_map = generate_tree_map_only(tree_item, selected_strs, instructions)
            copy_to_clipboard(tree_map)
            self._show_status("Tree map copied!")
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)
    
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
                patterns.append(rel.name)
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
        """Open remote repo dialog — not yet integrated with PySide6 version."""
        self._show_status("Remote repos not yet integrated", is_error=True)
    
    def _open_cache_management_dialog(self) -> None:
        """Open cache management dialog — not yet integrated with PySide6 version."""
        self._show_status("Cache management not yet integrated", is_error=True)
    
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
    
    # ===== Helpers =====
    
    def _show_status(self, message: str, is_error: bool = False) -> None:
        """Show status message."""
        color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self._status_label.setStyleSheet(f"font-size: 12px; color: {color};")
        self._status_label.setText(message)
        
        if message and not is_error:
            QTimer.singleShot(5000, lambda: self._status_label.setText(""))
