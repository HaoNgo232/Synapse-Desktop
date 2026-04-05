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
from typing import Optional, Set, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from application.interfaces.tokenization_port import ITokenizationService

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
    QMenu,
)
from PySide6.QtCore import (
    Qt,
    Signal,
    Slot,
    QThreadPool,
    QModelIndex,
    QSize,
    QEvent,
    QPoint,
    QTimer,
)
from PySide6.QtGui import QIcon

from presentation.config.theme import ThemeColors
from infrastructure.adapters.qt_utils import DebouncedTimer
from infrastructure.filesystem.ignore_engine import IgnoreEngine
from presentation.components.file_tree.file_tree_model import (
    FileTreeModel,
    TokenCountWorker,
    FileTreeRoles,
)
from presentation.components.file_tree.file_tree_delegate import FileTreeDelegate
from presentation.components.file_tree.file_tree_filter import FileTreeFilterProxy

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
    token_counting_done = Signal()  # Emitted khi batch token counting hoan thanh
    search_results_changed = Signal(int)  # Emitted voi so ket qua search
    exclude_patterns_changed = (
        Signal()
    )  # Emitted khi user exclude file/folder tu context menu

    def __init__(
        self,
        ignore_engine: IgnoreEngine,
        tokenization_service: "ITokenizationService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._tokenization_service = tokenization_service

        # Model & delegate
        self._model = FileTreeModel(ignore_engine=ignore_engine, parent=self)
        self._filter_proxy = FileTreeFilterProxy(self)
        self._filter_proxy.setSourceModel(self._model)
        self._delegate = FileTreeDelegate(self)

        # Token counting
        self._current_token_worker: Optional[TokenCountWorker] = None
        self._token_debounce = DebouncedTimer(300, self._start_token_counting, self)

        # Search debounce
        self._search_debounce = DebouncedTimer(150, self._apply_search, self)

        # Selection sync: đồng bộ selection giữa UI và .synapse/selection.json
        # Poll timer đọc JSON mỗi 2s (agent ghi từ bên ngoài)
        # Write thực hiện synchronous để tránh race condition với poll
        self._last_synced_selection: Set[str] = set()
        self._is_syncing_selection: bool = False
        self._selection_poll_timer = QTimer(self)
        self._selection_poll_timer.setInterval(2000)
        self._selection_poll_timer.timeout.connect(self._poll_agent_selection)

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
            f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 12px; font-weight: 500;"
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

        import sys

        if hasattr(sys, "_MEIPASS"):
            assets_dir = os.path.join(sys._MEIPASS, "assets")
        else:
            assets_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
            )

        # Select All
        self._select_all_btn = QPushButton()
        self._select_all_btn.setIcon(QIcon(os.path.join(assets_dir, "select-all.svg")))
        self._select_all_btn.setIconSize(QSize(20, 20))
        self._select_all_btn.setProperty("class", "flat")
        self._select_all_btn.setFixedSize(30, 30)
        self._select_all_btn.setToolTip("Select All")
        self._select_all_btn.setStyleSheet(
            f"QPushButton {{ color: #CBD5E1; background: transparent; border: 1px solid {ThemeColors.BORDER}; border-radius: 4px; padding: 0; min-width: 30px; min-height: 30px; }} "
            f"QPushButton:hover {{ color: {ThemeColors.TEXT_PRIMARY}; background: {ThemeColors.BG_HOVER}; border-color: {ThemeColors.BORDER_LIGHT}; }}"
        )
        actions_layout.addWidget(self._select_all_btn)

        # Deselect
        self._deselect_all_btn = QPushButton()
        self._deselect_all_btn.setIcon(QIcon(os.path.join(assets_dir, "uncheck.svg")))
        self._deselect_all_btn.setIconSize(QSize(20, 20))
        self._deselect_all_btn.setProperty("class", "flat")
        self._deselect_all_btn.setFixedSize(30, 30)
        self._deselect_all_btn.setToolTip("Deselect All")
        self._deselect_all_btn.setStyleSheet(
            f"QPushButton {{ color: #CBD5E1; background: transparent; border: 1px solid {ThemeColors.BORDER}; border-radius: 4px; padding: 0; min-width: 30px; min-height: 30px; }} "
            f"QPushButton:hover {{ color: {ThemeColors.TEXT_PRIMARY}; background: {ThemeColors.BG_HOVER}; border-color: {ThemeColors.BORDER_LIGHT}; }}"
        )
        actions_layout.addWidget(self._deselect_all_btn)

        # Collapse
        self._collapse_btn = QPushButton()
        self._collapse_btn.setIcon(QIcon(os.path.join(assets_dir, "colapse.svg")))
        self._collapse_btn.setIconSize(QSize(20, 20))
        self._collapse_btn.setProperty("class", "flat")
        self._collapse_btn.setFixedSize(30, 30)
        self._collapse_btn.setToolTip("Collapse All")
        self._collapse_btn.setStyleSheet(
            f"QPushButton {{ color: #CBD5E1; background: transparent; border: 1px solid {ThemeColors.BORDER}; border-radius: 4px; padding: 0; min-width: 30px; min-height: 30px; }} "
            f"QPushButton:hover {{ color: {ThemeColors.TEXT_PRIMARY}; background: {ThemeColors.BG_HOVER}; border-color: {ThemeColors.BORDER_LIGHT}; }}"
        )
        actions_layout.addWidget(self._collapse_btn)

        # Expand
        self._expand_btn = QPushButton()
        self._expand_btn.setIcon(QIcon(os.path.join(assets_dir, "expand.svg")))
        self._expand_btn.setIconSize(QSize(20, 20))
        self._expand_btn.setProperty("class", "flat")
        self._expand_btn.setFixedSize(30, 30)
        self._expand_btn.setToolTip("Expand All")
        self._expand_btn.setStyleSheet(
            f"QPushButton {{ color: #CBD5E1; background: transparent; border: 1px solid {ThemeColors.BORDER}; border-radius: 4px; padding: 0; min-width: 30px; min-height: 30px; }} "
            f"QPushButton:hover {{ color: {ThemeColors.TEXT_PRIMARY}; background: {ThemeColors.BG_HOVER}; border-color: {ThemeColors.BORDER_LIGHT}; }}"
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

        # Event filter de xu ly click theo zone — thay the clicked/doubleClicked
        self._tree_view.viewport().installEventFilter(self)

        # Context menu
        self._tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree_view.customContextMenuRequested.connect(self._on_context_menu)

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

        # Tree interaction: xu ly qua eventFilter (khong dung clicked/doubleClicked)
        # => Moi zone (checkbox, eye, label) co 1 chuc nang duy nhat, khong xung dot

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
        self._filter_proxy.set_search_state("", None)
        self._last_search_results = []
        self._select_results_btn.hide()

        # Start selection poll timer
        self._selection_poll_timer.start()

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
        if not paths:
            return

        self._tree_view.setUpdatesEnabled(False)
        try:
            self._expand_paths_recursive(QModelIndex(), paths)
        finally:
            self._tree_view.setUpdatesEnabled(True)

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
        self._selection_poll_timer.stop()

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

        # Nếu đang gõ "code:" nhưng chưa nhập từ khóa, restore tree về nguyên trạng,
        # không trigger tìm kiếm.
        stripped = query.strip().lower()
        if stripped == "code:" or (
            stripped.startswith("code:") and not stripped[5:].strip()
        ):
            query = ""

        self._delegate.set_search_query(query)

        if query:
            # Use flat index for accurate full-tree search
            self._last_search_results = self._model.search_files(query)
            match_count = len(self._last_search_results)
            self._filter_proxy.set_search_state(query, set(self._last_search_results))

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
            self._filter_proxy.set_search_state("", None)
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

    def eventFilter(self, watched, event) -> bool:
        """Intercept mouse events tren tree viewport de xu ly click theo zone.

        Thay the hoan toan clicked/doubleClicked signals. Moi zone chi co
        1 chuc nang duy nhat, khong xung dot:

        | Zone              | File          | Folder         |
        |-------------------|---------------|----------------|
        | Checkbox + Icon   | Toggle check  | Toggle check   |
        | Eye icon          | Preview       | (khong co)     |
        | Label, badges     | Khong lam gi  | Khong lam gi   |
        | Arrow (Qt native) | (khong co)    | Expand/Collapse|

        Zone duoc xac dinh boi FileTreeDelegate.get_hit_zone() — dung
        CUNG constants voi paint() nen luon chinh xac 100%.
        """
        if watched is not self._tree_view.viewport():
            return super().eventFilter(watched, event)

        # Xu ly ca Press va DblClick de chong moi double-click side effect
        if event.type() not in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
        ):
            return super().eventFilter(watched, event)

        if event.button() != Qt.MouseButton.LeftButton:
            return super().eventFilter(watched, event)

        pos = event.position().toPoint()
        proxy_index = self._tree_view.indexAt(pos)

        if not proxy_index.isValid():
            return False

        item_rect = self._tree_view.visualRect(proxy_index)

        # Click trong vung indentation/arrow → de Qt xu ly expand/collapse
        if pos.x() < item_rect.x():
            return False

        source_index = self._filter_proxy.mapToSource(proxy_index)
        if not source_index.isValid():
            return False

        zone = self._delegate.get_hit_zone(item_rect, pos.x(), source_index)

        if zone == "checkbox":
            # Toggle check/uncheck
            current = self._model.data(source_index, Qt.ItemDataRole.CheckStateRole)
            new_state = (
                Qt.CheckState.Unchecked
                if current == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
            self._model.setData(source_index, new_state, Qt.ItemDataRole.CheckStateRole)
            return True  # Da xu ly, khong truyen tiep

        if zone == "eye":
            # Preview file
            file_path = self._model.data(source_index, FileTreeRoles.FILE_PATH_ROLE)
            if file_path:
                self.file_preview_requested.emit(file_path)
            return True  # Da xu ly, khong truyen tiep

        # Zone "other" (label, badges, khoang trong)
        if zone == "other":
            # Kiem tra modifier keys truoc khi override behavior
            # Neu user giu Ctrl hoac Shift, de Qt xu ly multi-selection
            modifiers = QApplication.keyboardModifiers()
            if modifiers & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
            ):
                return False  # De Qt xu ly multi-selection

            is_dir = self._model.data(source_index, FileTreeRoles.IS_DIR_ROLE)
            if is_dir:
                # Thuc hien ca selection va expand/collapse
                self._tree_view.setCurrentIndex(proxy_index)
                if self._tree_view.isExpanded(proxy_index):
                    self._tree_view.collapse(proxy_index)
                else:
                    self._tree_view.expand(proxy_index)
                return True

        return False

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
        """Forward model selection changes va trigger token counting.

        PIPELINE: User check/uncheck -> setData() -> selection_changed signal
        -> _on_model_selection_changed() -> debounce 300ms -> _start_token_counting()

        Debounce 300ms de:
        - Gop nhieu selection changes lien tiep (vi du: rapid click)
        - Cho setData() hoan thanh targeted emit truoc khi bat dau counting
        - Tranh spam background workers
        """
        self.selection_changed.emit(selected)

        # Sync selection qua selection.json
        self._write_agent_selection(selected)

        # Debounce token counting
        self._token_debounce.start()

    def _start_token_counting(self) -> None:
        """Start background token counting cho selected files.

        FLOW:
        1. Cancel worker cu (neu dang chay)
        2. Snapshot _selection_generation TRUOC KHI goi get_selected_paths()
        3. get_selected_paths() co the BLOCK main thread (scan disk cho unloaded folders)
        4. Kiem tra: neu selection da doi trong luc scan -> bo ket qua (stale)
        5. Luu _last_resolved_files + danh dau _resolved_for_generation
        6. Filter uncached files va start TokenCountWorker

        CANH BAO VE PERFORMANCE:
        - get_selected_paths() chay tren MAIN THREAD va co the block UI
          neu co folders lon chua loaded (can scan disk via os.walk).
        - Day la bottleneck chinh con lai. Xem xet dung _search_index
          de resolve files thay vi scan disk (se tranh hoan toan block).
        """

        # Snapshot selection generation truoc khi resolve files
        sel_gen = self._model._selection_generation

        # get_selected_paths() discovers deep files from disk
        selected_files = self._model.get_selected_paths()

        # Kiem tra: selection co thay doi trong luc resolve khong?
        if self._model._selection_generation != sel_gen:
            # Selection da thay doi — ket qua resolve nay da stale, bo qua
            return

        if not selected_files:
            self._model._selection_mgr.set_resolved_files(set(), -1)
            self.token_counting_done.emit()
            return

        # Track resolved files + danh dau generation cho freshness check
        self._model._selection_mgr.set_resolved_files(set(selected_files), sel_gen)

        # Filter files chua co trong cache
        uncached = [f for f in selected_files if f not in self._model._token_cache]

        if not uncached:
            # All cached — STILL trigger update_token_counts_batch so folder aggregate cache is cleared
            # and ancestors are notified (important when resolving newly discovered files).
            self._model.update_token_counts_batch({})
            self.token_counting_done.emit()
            return

        # Create and start worker with current generation
        current_gen = self._model.generation
        worker = TokenCountWorker(
            uncached,
            tokenization_service=self._tokenization_service,
            generation=current_gen,
        )
        worker.signals.token_counts_batch.connect(self._on_token_counts_batch)
        worker.signals.finished.connect(self._on_token_counting_finished)
        self._current_token_worker = worker

        QThreadPool.globalInstance().start(worker)

    @Slot(dict)
    def _on_token_counts_batch(self, counts: Dict[str, int]) -> None:
        """Handle token count batch results (main thread via signal).

        Discard results neu:
        1. Workspace da thay doi (generation check)
        2. Selection da thay doi sau khi worker bat dau (selection generation check)
        """
        worker = self._current_token_worker
        if worker is not None and hasattr(worker, "generation"):
            # Guard 1: Workspace switch — discard stale workspace results
            if worker.generation != self._model.generation:
                return

        # Guard 2: Selection change — discard results tu selection cu
        # Neu _resolved_for_generation != _selection_generation,
        # nghia la user da check/uncheck SAU khi worker bat dau
        if self._model._resolved_for_generation != self._model._selection_generation:
            return

        self._model.update_token_counts_batch(counts)
        self.token_counting_done.emit()

    @Slot()
    def _on_token_counting_finished(self) -> None:
        """Handle token counting completion."""
        self._current_token_worker = None
        self.token_counting_done.emit()

    @Slot(QPoint)
    def _on_context_menu(self, pos: QPoint) -> None:
        """Hien thi context menu cho file/folder trong tree.

        Hien thi cac hanh dong kha dung:
        - Exclude from Context: Them file/folder vao excluded patterns
        - Manage Exclusions...: Mo dialog quan ly toan bo excluded patterns
        - Mark/Unmark as Project Rule: Danh dau file lam project rule (chi cho file)
        """
        index = self._tree_view.indexAt(pos)
        if not index.isValid():
            return

        source_idx = self._filter_proxy.mapToSource(index)
        file_path = self._model.data(source_idx, FileTreeRoles.FILE_PATH_ROLE)
        is_dir = self._model.data(source_idx, FileTreeRoles.IS_DIR_ROLE)

        if not file_path:
            return

        workspace = self._model.get_workspace_path()
        if not workspace:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
                border-radius: 4px;
                color: #E2E8F0;
                font-size: 12px;
            }
            QMenu::item:selected { background: #2D3F55; }
            QMenu::separator { height: 1px; background: #334155; margin: 4px 8px; }
        """)

        # --- Exclude Section ---
        # Lay ten hien thi (folder hoac file)
        item_name = Path(file_path).name
        exclude_label = (
            f"Exclude Folder '{item_name}'" if is_dir else f"Exclude File '{item_name}'"
        )

        exclude_action = menu.addAction(exclude_label)
        exclude_action.triggered.connect(
            lambda: self._exclude_path(workspace, file_path, is_dir)
        )

        manage_action = menu.addAction("Manage Exclusions...")
        manage_action.triggered.connect(lambda: self._open_exclusions_dialog())

        # --- Project Rule Section (chi hien thi cho file) ---
        if not is_dir:
            menu.addSeparator()

            from application.services.workspace_rules import is_rule_file

            is_rule = is_rule_file(workspace, file_path)

            if is_rule:
                rule_action = menu.addAction("Unmark as Project Rule")
                rule_action.triggered.connect(
                    lambda: self._unmark_rule_file(workspace, file_path)
                )
            else:
                rule_action = menu.addAction("Mark as Project Rule")
                rule_action.triggered.connect(
                    lambda: self._mark_rule_file(workspace, file_path)
                )

        menu.exec(self._tree_view.viewport().mapToGlobal(pos))

    def _exclude_path(self, workspace: Path, file_path: str, is_dir: bool) -> None:
        """Them file/folder vao excluded patterns va refresh tree.

        Tinh toan relative path so voi workspace, sau do luu vao settings.
        Ket qua ngay lap tuc hien thi bang cach refresh tree.
        """
        from application.services.workspace_config import add_excluded_patterns
        from presentation.components.toast.toast_qt import toast_success, toast_error

        try:
            path_obj = Path(file_path)
            rel = path_obj.relative_to(workspace)
            pattern = str(rel)
        except ValueError:
            pattern = Path(file_path).name

        if add_excluded_patterns([pattern]):
            toast_success(f"Excluded: {pattern}")
            # Thong bao cho TreeManagementController refresh tree
            self.exclude_patterns_changed.emit()
        else:
            toast_error("Failed to save exclusion.")

    def _open_exclusions_dialog(self) -> None:
        """Mo dialog quan ly toan bo excluded patterns.

        Hien thi tat ca cac patterns dang active, cho phep user xoa tung cai
        hoac them moi. Thay doi co hieu luc ngay sau khi dong dialog.
        """
        from presentation.components.dialogs.exclusions_dialog import ExclusionsDialog

        dialog = ExclusionsDialog(self)
        if dialog.exec():
            self.exclude_patterns_changed.emit()

    def _mark_rule_file(self, workspace: Path, file_path: str) -> None:
        """Danh dau file la project rule."""
        from application.services.workspace_rules import add_rule_file
        from presentation.components.toast.toast_qt import toast_success

        add_rule_file(workspace, file_path)
        toast_success(f"Marked as project rule: {Path(file_path).name}")
        self._tree_view.viewport().update()

    def _unmark_rule_file(self, workspace: Path, file_path: str) -> None:
        """Bo danh dau file khoi project rule."""
        from application.services.workspace_rules import remove_rule_file
        from presentation.components.toast.toast_qt import toast_success

        remove_rule_file(workspace, file_path)
        toast_success(f"Unmarked project rule: {Path(file_path).name}")
        self._tree_view.viewport().update()

    # ===== Private Helpers =====

    def _collect_expanded(self, parent: QModelIndex, result: List[str]) -> None:
        """Recursively collect expanded folder paths."""
        for row in range(self._filter_proxy.rowCount(parent)):
            index = self._filter_proxy.index(row, 0, parent)
            if index.isValid() and self._tree_view.isExpanded(index):
                source_idx = self._filter_proxy.mapToSource(index)

                path = self._model.data(source_idx, FileTreeRoles.FILE_PATH_ROLE)
                if path:
                    result.append(path)
                self._collect_expanded(index, result)

    def _expand_paths_recursive(self, parent: QModelIndex, paths: Set[str]) -> None:
        """Recursively expand folders matching paths."""
        # FIX: Ho tro lazy loading khi restore state.
        # Neu parent chua fetch children thi rowCount() tra ve 0.
        # Chung ta can fetchMore() truoc khi duyet row.
        if self._filter_proxy.canFetchMore(parent):
            self._filter_proxy.fetchMore(parent)

        for row in range(self._filter_proxy.rowCount(parent)):
            index = self._filter_proxy.index(row, 0, parent)
            if not index.isValid():
                continue

            source_idx = self._filter_proxy.mapToSource(index)

            path = self._model.data(source_idx, FileTreeRoles.FILE_PATH_ROLE)
            is_dir = self._model.data(source_idx, FileTreeRoles.IS_DIR_ROLE)

            if is_dir and path and path in paths:
                self._tree_view.expand(index)
                self._expand_paths_recursive(index, paths)

    # ===== Agent Syncing =====
    #
    # Luồng đồng bộ 2 chiều giữa UI <-> .synapse/selection.json:
    #
    # UI -> JSON (write): Khi user click checkbox, _write_agent_selection()
    #   ghi SYNCHRONOUS vào JSON và update _last_synced_selection ngay lập tức.
    #   Không dùng debounce để tránh race condition với poll timer.
    #
    # JSON -> UI (poll): Timer 2s đọc JSON, so sánh với _last_synced_selection.
    #   Nếu khác (agent đã sửa từ bên ngoài) thì apply vào UI.
    #   Nếu giống (do chính UI vừa ghi) thì skip.
    #
    # Race condition đã fix: Vì write là synchronous, _last_synced_selection
    # luôn khớp với nội dung JSON. Poll timer đọc JSON sẽ thấy data giống
    # _last_synced_selection -> skip. Không bao giờ ghi đè selection mới.

    @Slot()
    def _poll_agent_selection(self) -> None:
        """Poll .synapse/selection.json mỗi 2 giây để đồng bộ từ agent.

        Chỉ apply khi phát hiện agent thay đổi JSON từ bên ngoài.
        Skip nếu data trong JSON trùng với _last_synced_selection (do UI vừa ghi).
        """
        if self._is_syncing_selection:
            return

        workspace = self._model.get_workspace_path()
        if not workspace:
            return

        from infrastructure.mcp.core.workspace_manager import WorkspaceManager
        import json

        session_file = WorkspaceManager.get_session_file(Path(workspace))
        if not session_file.exists():
            return

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                selected_list = data.get("selected_files", [])

            # Convert relative paths (trong JSON) sang absolute (cho UI)
            # Dùng .absolute() thay vì .resolve() để tránh symlink mismatch
            workspace_path = Path(workspace)
            absolute_selected = set()
            for rel_path in selected_list:
                try:
                    fp = (workspace_path / rel_path).absolute()
                    absolute_selected.add(str(fp))
                except Exception:
                    pass

            # CHU Y: Tren Windows, path casing co the khong nhat quan (e: vs E:)
            # Chung ta can filter ra nhung paths thực sự khác biệt để tránh loop refresh
            import platform

            is_windows = platform.system() == "Windows"
            if is_windows:
                # So sánh case-insensitively trên Windows để tránh mismatch (e: vs E:)
                norm_absolute = {p.lower() for p in absolute_selected}
                norm_last = {p.lower() for p in self._last_synced_selection}
                is_changed = norm_absolute != norm_last
            else:
                is_changed = absolute_selected != self._last_synced_selection

            if not is_changed:
                return

            # JSON đã thay đổi (agent sửa từ bên ngoài)
            self._last_synced_selection = absolute_selected

            # Kiểm tra nếu thực sự khác với model state thì mới apply
            model_selected = self._model.get_all_selected_paths()
            
            if is_windows:
                norm_model = {p.lower() for p in model_selected}
                norm_absolute = {p.lower() for p in absolute_selected}
                should_apply = norm_model != norm_absolute
            else:
                should_apply = model_selected != absolute_selected

            if should_apply:
                self._is_syncing_selection = True
                try:
                    self.set_selected_paths(absolute_selected)
                    self._tree_view.viewport().update()
                finally:
                    self._is_syncing_selection = False

        except Exception as e:
            logger.debug(f"Failed to poll selection: {e}")

    def _write_agent_selection(self, selected: Set[str]) -> None:
        """Ghi selection hiện tại vào .synapse/selection.json (synchronous).

        Ghi ĐỒNG BỘ để đảm bảo _last_synced_selection luôn khớp với JSON.
        Nếu dùng debounce, poll timer có thể đọc JSON cũ trong khoảng delay
        và ghi đè selection mới của user -> mất checkbox.
        """
        # Bỏ qua nếu đang sync từ poll (tránh vòng lặp)
        if self._is_syncing_selection:
            return

        workspace = self._model.get_workspace_path()
        if not workspace:
            return

        # Fast path: nếu selection không đổi thì skip IO
        if selected == self._last_synced_selection:
            return

        # Update cache TRƯỚC khi ghi file
        # Đảm bảo poll timer luôn thấy data mới nhất
        self._last_synced_selection = set(selected)

        from infrastructure.mcp.core.workspace_manager import WorkspaceManager
        import json

        workspace_path = Path(workspace)
        session_file = WorkspaceManager.get_session_file(workspace_path)

        # Convert absolute paths (UI) -> relative paths (cho agent)
        relative_selected = []
        for abs_path in selected:
            try:
                rel_path = Path(abs_path).relative_to(workspace_path)
                relative_selected.append(str(rel_path).replace("\\", "/"))
            except ValueError:
                pass

        try:
            session_file.parent.mkdir(parents=True, exist_ok=True)
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump({"selected_files": sorted(relative_selected)}, f, indent=2)
                f.write("\n")
        except Exception as e:
            logger.debug(f"Failed to write selection.json: {e}")
