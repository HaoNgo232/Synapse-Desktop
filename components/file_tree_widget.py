"""
File Tree Widget - QWidget wrapper cho QTreeView + Model + Delegate + Filter.

Composite widget bao gồm:
- Search field (QLineEdit)
- Action buttons (Select All, Deselect All, Collapse)
- QTreeView với custom model/delegate
- Token count integration (async background)

Thay thế components/file_tree.py và components/virtual_file_tree.py từ Flet.
"""

import logging
from pathlib import Path
from typing import Optional, Set, List, Callable, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTreeView,
    QPushButton, QToolButton, QLabel, QFrame, QSizePolicy,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, Slot, QThreadPool, QModelIndex, QTimer

from core.theme import ThemeColors
from core.utils.qt_utils import DebouncedTimer, run_on_main_thread
from components.file_tree_model import FileTreeModel, TokenCountWorker
from components.file_tree_delegate import FileTreeDelegate
from components.file_tree_filter import FileTreeFilterProxy

logger = logging.getLogger(__name__)


class FileTreeWidget(QWidget):
    """
    Complete file tree widget với search, selection, token counting.
    
    Signals:
        selection_changed(Set[str]): Emitted khi selection thay đổi
        file_preview_requested(str): Emitted khi user double-click file
    """
    
    # Signals
    selection_changed = Signal(set)
    file_preview_requested = Signal(str)
    token_counting_done = Signal()  # Emitted khi batch token counting hoàn thành
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Model & delegate
        self._model = FileTreeModel(self)
        self._filter_proxy = FileTreeFilterProxy(self)
        self._filter_proxy.setSourceModel(self._model)
        self._delegate = FileTreeDelegate(self)
        
        # Token counting
        self._current_token_worker: Optional[TokenCountWorker] = None
        self._token_debounce = DebouncedTimer(300, self._start_token_counting, self)
        
        # Search debounce
        self._search_debounce = DebouncedTimer(150, self._apply_search, self)
        
        # State
        self._pending_search: str = ""
        
        # Build UI
        self._build_ui()
        self._connect_signals()
    
    def _build_ui(self) -> None:
        """Build widget layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)
        
        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText("Search files...")
        self._search_field.setClearButtonEnabled(True)
        search_layout.addWidget(self._search_field, stretch=1)
        
        self._match_count_label = QLabel("")
        self._match_count_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-size: 11px;"
        )
        search_layout.addWidget(self._match_count_label)
        
        layout.addLayout(search_layout)
        
        # Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(4)
        
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setProperty("class", "flat")
        self._select_all_btn.setFixedHeight(26)
        actions_layout.addWidget(self._select_all_btn)
        
        self._deselect_all_btn = QPushButton("Deselect")
        self._deselect_all_btn.setProperty("class", "flat")
        self._deselect_all_btn.setFixedHeight(26)
        actions_layout.addWidget(self._deselect_all_btn)
        
        self._collapse_btn = QPushButton("Collapse")
        self._collapse_btn.setProperty("class", "flat")
        self._collapse_btn.setFixedHeight(26)
        actions_layout.addWidget(self._collapse_btn)
        
        self._expand_btn = QPushButton("Expand")
        self._expand_btn.setProperty("class", "flat")
        self._expand_btn.setFixedHeight(26)
        actions_layout.addWidget(self._expand_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        # Tree view
        self._tree_view = QTreeView()
        self._tree_view.setModel(self._filter_proxy)
        self._tree_view.setItemDelegate(self._delegate)
        self._tree_view.setHeaderHidden(True)
        self._tree_view.setAnimated(True)
        self._tree_view.setIndentation(20)
        self._tree_view.setExpandsOnDoubleClick(False)  # Handle manually
        self._tree_view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._tree_view.setUniformRowHeights(True)  # Performance optimization
        self._tree_view.setAlternatingRowColors(False)
        self._tree_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        layout.addWidget(self._tree_view, stretch=1)
    
    def _connect_signals(self) -> None:
        """Connect all signals."""
        # Search
        self._search_field.textChanged.connect(self._on_search_changed)
        
        # Actions
        self._select_all_btn.clicked.connect(self._on_select_all)
        self._deselect_all_btn.clicked.connect(self._on_deselect_all)
        self._collapse_btn.clicked.connect(self._on_collapse_all)
        self._expand_btn.clicked.connect(self._on_expand_all)
        
        # Tree interaction
        self._tree_view.clicked.connect(self._on_item_clicked)
        self._tree_view.doubleClicked.connect(self._on_item_double_clicked)
        
        # Model selection changes
        self._model.selection_changed.connect(self._on_model_selection_changed)
    
    # ===== Public API =====
    
    def load_tree(self, workspace_path: Path) -> None:
        """Load file tree cho workspace."""
        # Cancel pending token counting
        if self._current_token_worker:
            self._current_token_worker.cancel()
            self._current_token_worker = None
        
        self._search_field.clear()
        self._model.load_tree(workspace_path)
        
        # Expand root node
        root_idx = self._filter_proxy.index(0, 0)
        if root_idx.isValid():
            self._tree_view.expand(root_idx)
    
    def get_selected_paths(self) -> List[str]:
        """Get danh sách selected file paths."""
        return self._model.get_selected_paths()
    
    def get_root_tree_item(self):
        """Get root TreeItem (for tree map generation)."""
        return self._model.get_root_tree_item()
    
    def get_all_selected_paths(self) -> Set[str]:
        """Get tất cả selected paths."""
        return self._model.get_all_selected_paths()
    
    def get_expanded_paths(self) -> List[str]:
        """Get danh sách expanded folder paths."""
        expanded = []
        self._collect_expanded(QModelIndex(), expanded)
        return expanded
    
    def set_selected_paths(self, paths: Set[str]) -> None:
        """Set selected paths (session restore)."""
        self._model.set_selected_paths(paths)
    
    def set_expanded_paths(self, paths: Set[str]) -> None:
        """Expand folders theo paths (session restore)."""
        self._expand_paths_recursive(QModelIndex(), paths)
    
    def clear_token_cache(self) -> None:
        """Clear token cache."""
        self._model.clear_token_cache()
    
    def get_total_tokens(self) -> int:
        """Get tổng tokens cho selection."""
        return self._model.get_total_tokens()
    
    def get_model(self) -> FileTreeModel:
        """Get underlying model."""
        return self._model
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        if self._current_token_worker:
            self._current_token_worker.cancel()
        self._token_debounce.stop()
        self._search_debounce.stop()
    
    # ===== Slots =====
    
    @Slot(str)
    def _on_search_changed(self, text: str) -> None:
        """Handle search text change với debounce."""
        self._pending_search = text
        self._search_debounce.start()
    
    def _apply_search(self) -> None:
        """Apply search filter (debounced)."""
        query = self._pending_search
        self._filter_proxy.set_search_query(query)
        self._delegate.set_search_query(query)
        
        if query:
            # Expand all để show matches
            self._tree_view.expandAll()
            match_count = self._filter_proxy.get_match_count()
            self._match_count_label.setText(f"{match_count} matches")
        else:
            self._match_count_label.setText("")
        
        # Trigger repaint
        self._tree_view.viewport().update()
    
    @Slot()
    def _on_select_all(self) -> None:
        self._model.select_all()
    
    @Slot()
    def _on_deselect_all(self) -> None:
        self._model.deselect_all()
    
    @Slot()
    def _on_collapse_all(self) -> None:
        self._tree_view.collapseAll()
        # Expand root
        root_idx = self._filter_proxy.index(0, 0)
        if root_idx.isValid():
            self._tree_view.expand(root_idx)
    
    @Slot()
    def _on_expand_all(self) -> None:
        self._tree_view.expandAll()
    
    @Slot(QModelIndex)
    def _on_item_clicked(self, proxy_index: QModelIndex) -> None:
        """Handle item click — toggle checkbox."""
        source_index = self._filter_proxy.mapToSource(proxy_index)
        if not source_index.isValid():
            return
        
        # Toggle check state
        current_state = self._model.data(source_index, Qt.ItemDataRole.CheckStateRole)
        new_state = Qt.CheckState.Unchecked if current_state == Qt.CheckState.Checked else Qt.CheckState.Checked
        self._model.setData(source_index, new_state, Qt.ItemDataRole.CheckStateRole)
    
    @Slot(QModelIndex)
    def _on_item_double_clicked(self, proxy_index: QModelIndex) -> None:
        """Handle double click — preview file or toggle expand."""
        source_index = self._filter_proxy.mapToSource(proxy_index)
        if not source_index.isValid():
            return
        
        from components.file_tree_model import FileTreeRoles
        is_dir = self._model.data(source_index, FileTreeRoles.IS_DIR_ROLE)
        
        if is_dir:
            # Toggle expand
            if self._tree_view.isExpanded(proxy_index):
                self._tree_view.collapse(proxy_index)
            else:
                self._tree_view.expand(proxy_index)
        else:
            # Preview file
            file_path = self._model.data(source_index, FileTreeRoles.FILE_PATH_ROLE)
            if file_path:
                self.file_preview_requested.emit(file_path)
    
    @Slot(set)
    def _on_model_selection_changed(self, selected: set) -> None:
        """Forward model selection changes và trigger token counting."""
        self.selection_changed.emit(selected)
        
        # Debounce token counting
        self._token_debounce.start()
    
    def _start_token_counting(self) -> None:
        """Start background token counting cho selected files."""
        # Cancel previous worker
        if self._current_token_worker:
            self._current_token_worker.cancel()
        
        # get_selected_paths() now discovers deep files from disk
        selected_files = self._model.get_selected_paths()
        if not selected_files:
            self._model._last_resolved_files.clear()
            self.token_counting_done.emit()
            return
        
        # Track resolved files for accurate total counting
        self._model._last_resolved_files = set(selected_files)
        
        # Filter files chưa có trong cache
        uncached = [
            f for f in selected_files 
            if f not in self._model._token_cache
        ]
        
        if not uncached:
            # All cached — just emit done to refresh display
            self.token_counting_done.emit()
            return
        
        # Create and start worker
        worker = TokenCountWorker(uncached)
        worker.signals.token_counts_batch.connect(self._on_token_counts_batch)
        worker.signals.finished.connect(self._on_token_counting_finished)
        self._current_token_worker = worker
        
        QThreadPool.globalInstance().start(worker)
    
    @Slot(dict)
    def _on_token_counts_batch(self, counts: Dict[str, int]) -> None:
        """Handle token count batch results (main thread via signal)."""
        self._model.update_token_counts_batch(counts)
        self.token_counting_done.emit()
    
    @Slot()
    def _on_token_counting_finished(self) -> None:
        """Handle token counting completion."""
        self._current_token_worker = None
        self.token_counting_done.emit()
    
    # ===== Private Helpers =====
    
    def _collect_expanded(self, parent: QModelIndex, result: List[str]) -> None:
        """Recursively collect expanded folder paths."""
        for row in range(self._filter_proxy.rowCount(parent)):
            index = self._filter_proxy.index(row, 0, parent)
            if index.isValid() and self._tree_view.isExpanded(index):
                source_idx = self._filter_proxy.mapToSource(index)
                from components.file_tree_model import FileTreeRoles
                path = self._model.data(source_idx, FileTreeRoles.FILE_PATH_ROLE)
                if path:
                    result.append(path)
                self._collect_expanded(index, result)
    
    def _expand_paths_recursive(self, parent: QModelIndex, paths: Set[str]) -> None:
        """Recursively expand folders matching paths."""
        for row in range(self._filter_proxy.rowCount(parent)):
            index = self._filter_proxy.index(row, 0, parent)
            if not index.isValid():
                continue
            
            source_idx = self._filter_proxy.mapToSource(index)
            from components.file_tree_model import FileTreeRoles
            path = self._model.data(source_idx, FileTreeRoles.FILE_PATH_ROLE)
            is_dir = self._model.data(source_idx, FileTreeRoles.IS_DIR_ROLE)
            
            if is_dir and path and path in paths:
                self._tree_view.expand(index)
                self._expand_paths_recursive(index, paths)
