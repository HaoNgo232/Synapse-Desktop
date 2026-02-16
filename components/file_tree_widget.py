"""
File Tree Widget - QWidget wrapper cho QTreeView + Model + Delegate + Filter.

Composite widget bao gồm:
- Search field (QLineEdit)
- Action buttons (Select All, Deselect All, Collapse)
- QTreeView với custom model/delegate
- Token count integration (async background)
"""

import os
import logging
from pathlib import Path
from typing import Optional, Set, List, Dict

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTreeView,
    QPushButton,
    QLabel,
    QAbstractItemView,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, Slot, QThreadPool, QModelIndex, QSize
from PySide6.QtGui import QIcon

from core.theme import ThemeColors
from core.utils.qt_utils import DebouncedTimer
from components.file_tree_model import FileTreeModel, TokenCountWorker
from components.file_tree_delegate import (
    FileTreeDelegate,
    EYE_ICON_SIZE,
    SPACING as DELEGATE_SPACING,
)
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
    search_results_changed = Signal(int)  # Emitted với số kết quả search

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
        self._last_search_results: List[str] = []  # Full paths from flat index search

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

        # "Select All" button — visible only when search has results
        self._select_results_btn = QPushButton("Select All")
        self._select_results_btn.setFixedHeight(24)
        self._select_results_btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background-color: {ThemeColors.PRIMARY}; color: white; "
            f"  border: none; border-radius: 4px; padding: 2px 10px; "
            f"  font-size: 11px; font-weight: 600; "
            f"}} "
            f"QPushButton:hover {{ background-color: {ThemeColors.PRIMARY_HOVER}; }}"
        )
        self._select_results_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_results_btn.setToolTip("Select all search results")
        self._select_results_btn.clicked.connect(self._on_select_search_results)
        self._select_results_btn.hide()  # Hidden by default
        search_layout.addWidget(self._select_results_btn)

        layout.addLayout(search_layout)

        # Action buttons với Lucide SVG icons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(4)

        # Get assets directory
        assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
        )

        # Select All
        self._select_all_btn = QPushButton()
        self._select_all_btn.setIcon(QIcon(os.path.join(assets_dir, "select-all.svg")))
        self._select_all_btn.setIconSize(QSize(20, 20))
        self._select_all_btn.setProperty("class", "flat")
        self._select_all_btn.setFixedSize(36, 28)
        self._select_all_btn.setToolTip("Select All")
        self._select_all_btn.setStyleSheet(
            "QPushButton { color: #94A3B8; } QPushButton:hover { color: #E2E8F0; }"
        )
        actions_layout.addWidget(self._select_all_btn)

        # Deselect
        self._deselect_all_btn = QPushButton()
        self._deselect_all_btn.setIcon(QIcon(os.path.join(assets_dir, "uncheck.svg")))
        self._deselect_all_btn.setIconSize(QSize(20, 20))
        self._deselect_all_btn.setProperty("class", "flat")
        self._deselect_all_btn.setFixedSize(36, 28)
        self._deselect_all_btn.setToolTip("Deselect All")
        self._deselect_all_btn.setStyleSheet(
            "QPushButton { color: #94A3B8; } QPushButton:hover { color: #E2E8F0; }"
        )
        actions_layout.addWidget(self._deselect_all_btn)

        # Collapse
        self._collapse_btn = QPushButton()
        self._collapse_btn.setIcon(QIcon(os.path.join(assets_dir, "colapse.svg")))
        self._collapse_btn.setIconSize(QSize(20, 20))
        self._collapse_btn.setProperty("class", "flat")
        self._collapse_btn.setFixedSize(36, 28)
        self._collapse_btn.setToolTip("Collapse All")
        self._collapse_btn.setStyleSheet(
            "QPushButton { color: #94A3B8; } QPushButton:hover { color: #E2E8F0; }"
        )
        actions_layout.addWidget(self._collapse_btn)

        # Expand
        self._expand_btn = QPushButton()
        self._expand_btn.setIcon(QIcon(os.path.join(assets_dir, "expand.svg")))
        self._expand_btn.setIconSize(QSize(20, 20))
        self._expand_btn.setProperty("class", "flat")
        self._expand_btn.setFixedSize(36, 28)
        self._expand_btn.setToolTip("Expand All")
        self._expand_btn.setStyleSheet(
            "QPushButton { color: #94A3B8; } QPushButton:hover { color: #E2E8F0; }"
        )
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
        self._tree_view.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self._tree_view.setMouseTracking(True)  # Enable hover for eye icon

        layout.addWidget(self._tree_view, stretch=1)

    def _connect_signals(self) -> None:
        """Connect all signals."""
        # Search
        self._search_field.textChanged.connect(self._on_search_changed)
        self._search_field.returnPressed.connect(self._on_search_return_pressed)

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

        # Stop debounce timers to prevent stale callbacks
        self._token_debounce.stop()
        self._search_debounce.stop()

        self._search_field.clear()
        self._match_count_label.setText("")
        self._delegate.set_search_query("")
        self._filter_proxy.set_search_query("")
        self._last_search_results = []
        self._select_results_btn.hide()

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

    def add_paths_to_selection(self, paths: Set[str]) -> int:
        """Add paths to selection. Returns count added."""
        return self._model.add_paths_to_selection(paths)

    def remove_paths_from_selection(self, paths: Set[str]) -> int:
        """Remove paths from selection. Returns count removed."""
        return self._model.remove_paths_from_selection(paths)

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

    def get_search_results(self) -> List[str]:
        """Get current search result paths (from flat index)."""
        return self._last_search_results

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

    @Slot()
    def _on_search_return_pressed(self) -> None:
        """Handle Enter trong search field: expand all trước rồi apply search ngay.

        Kết quả tìm kiếm (filter proxy) phụ thuộc vào nodes đã load trong model.
        Lazy loading chỉ load children khi expand, nên expandAll() trước để đảm bảo
        filter có đủ tree để match. Chỉ expand khi có query để tránh load toàn bộ
        tree khi user nhấn Enter với ô search trống.
        """
        self._search_debounce.stop()
        query = (self._pending_search or "").strip()
        expanded = False
        if query:
            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                QApplication.processEvents()
                self._tree_view.expandAll()
                expanded = True
            except Exception as e:
                logger.warning(f"Expand all before search: {e}")
            finally:
                QApplication.restoreOverrideCursor()
        self._apply_search(skip_expand=expanded)

    def _apply_search(self, skip_expand: bool = False) -> None:
        """Apply search filter (debounced).

        Uses flat search index for accurate results independent of lazy loading,
        then applies filter proxy for visual filtering of loaded tree nodes.

        Args:
            skip_expand: True nếu expandAll đã được gọi trước đó (vd. từ returnPressed).
        """
        query = self._pending_search
        self._filter_proxy.set_search_query(query)
        self._delegate.set_search_query(query)

        if query:
            # Use flat index for accurate full-tree search
            self._last_search_results = self._model.search_files(query)
            match_count = len(self._last_search_results)

            # Expand visible tree để filter có đủ nodes để match. Hiển thị wait cursor
            # khi expandAll chạy lâu trên project lớn. Skip nếu đã expand (returnPressed).
            if not skip_expand:
                try:
                    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    QApplication.processEvents()
                    self._tree_view.expandAll()
                finally:
                    QApplication.restoreOverrideCursor()

            # Show match count from flat index (accurate)
            if match_count > 0:
                self._match_count_label.setText(f"{match_count} files found")
                self._select_results_btn.setText(f"Select All Results ({match_count})")
                self._select_results_btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"  background-color: {ThemeColors.PRIMARY}; color: white; "
                    f"  border: none; border-radius: 4px; padding: 2px 10px; "
                    f"  font-size: 11px; font-weight: 600; "
                    f"}} "
                    f"QPushButton:hover {{ background-color: {ThemeColors.PRIMARY_HOVER}; }}"
                )
                self._select_results_btn.show()
            else:
                # Fallback to filter proxy count (for loaded nodes)
                proxy_count = self._filter_proxy.get_match_count()
                self._match_count_label.setText(
                    f"{proxy_count} matches" if proxy_count > 0 else "No matches"
                )
                self._last_search_results = []
                self._select_results_btn.hide()

            self.search_results_changed.emit(match_count)
        else:
            self._last_search_results = []
            self._match_count_label.setText("")
            self._select_results_btn.hide()
            self.search_results_changed.emit(0)

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
        try:
            self._tree_view.expandAll()
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Error during expand all: {e}")

    @Slot(QModelIndex)
    def _on_item_clicked(self, proxy_index: QModelIndex) -> None:
        """Handle item click — toggle checkbox or preview if eye icon clicked."""
        source_index = self._filter_proxy.mapToSource(proxy_index)
        if not source_index.isValid():
            return

        from components.file_tree_model import FileTreeRoles

        is_dir = self._model.data(source_index, FileTreeRoles.IS_DIR_ROLE)

        # Check if click was on the eye icon area (now on the left, next to file icon)
        if not is_dir:
            cursor_pos = self._tree_view.viewport().mapFromGlobal(
                self._tree_view.cursor().pos()
            )
            item_rect = self._tree_view.visualRect(proxy_index)

            # Toạ độ X của con mắt (bên trái, sau icon file)
            # Checkbox (16) + Icon (16) + 3 * SPACING (6)
            eye_x_start = item_rect.left() + 16 + 16 + (3 * DELEGATE_SPACING)
            eye_x_end = eye_x_start + EYE_ICON_SIZE + 4

            if eye_x_start <= cursor_pos.x() <= eye_x_end:
                file_path = self._model.data(source_index, FileTreeRoles.FILE_PATH_ROLE)
                if file_path:
                    self.file_preview_requested.emit(file_path)
                return

        # Toggle check state
        current_state = self._model.data(source_index, Qt.ItemDataRole.CheckStateRole)
        new_state = (
            Qt.CheckState.Unchecked
            if current_state == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
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

    @Slot()
    def _on_select_search_results(self) -> None:
        """Select all files from search results."""
        if not self._last_search_results:
            return

        paths_to_add = set(self._last_search_results)
        added = self._model.add_paths_to_selection(paths_to_add)

        if added > 0:
            # Update button text to indicate selection was made
            self._select_results_btn.setText(f"Selected ({added})")
            self._select_results_btn.setStyleSheet(
                f"QPushButton {{ "
                f"  background-color: {ThemeColors.SUCCESS}; color: white; "
                f"  border: none; border-radius: 4px; padding: 2px 10px; "
                f"  font-size: 11px; font-weight: 600; "
                f"}} "
                f"QPushButton:hover {{ background-color: #059669; }}"
            )

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
            self._current_token_worker = None

        # get_selected_paths() now discovers deep files from disk
        selected_files = self._model.get_selected_paths()
        if not selected_files:
            self._model._last_resolved_files.clear()
            self.token_counting_done.emit()
            return

        # Track resolved files for accurate total counting
        self._model._last_resolved_files = set(selected_files)

        # Filter files chưa có trong cache
        uncached = [f for f in selected_files if f not in self._model._token_cache]

        if not uncached:
            # All cached — just emit done to refresh display
            self.token_counting_done.emit()
            return

        # Create and start worker with current generation
        current_gen = self._model.generation
        worker = TokenCountWorker(uncached, generation=current_gen)
        worker.signals.token_counts_batch.connect(self._on_token_counts_batch)
        worker.signals.finished.connect(self._on_token_counting_finished)
        self._current_token_worker = worker

        QThreadPool.globalInstance().start(worker)

    @Slot(dict)
    def _on_token_counts_batch(self, counts: Dict[str, int]) -> None:
        """Handle token count batch results (main thread via signal).

        Discard results if generation has changed (workspace switched).
        """
        # Check if this worker's results are still relevant
        worker = self._current_token_worker
        if worker is not None and hasattr(worker, "generation"):
            if worker.generation != self._model.generation:
                # Stale results from old workspace — discard
                return

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
