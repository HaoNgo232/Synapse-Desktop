"""
views/history/_view.py

HistoryViewQt - Composition root cho History View.

Chi chiu trach nhiem:
- Build layout tong the (header + splitter + footer)
- Wire panels (HistoryListPanel, HistoryDetailPanel)
- Load data va dieu phoi tuong tac giua 2 panels
"""

from typing import Optional, Callable

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QFrame,
    QMessageBox,
)
from PySide6.QtCore import Qt, Slot, QTimer

from core.theme import ThemeColors
from services.history_service import (
    get_history_entries,
    get_entry_by_id,
    clear_history,
    get_history_stats,
)
from views.history._list_panel import HistoryListPanel
from views.history._detail_panel import HistoryDetailPanel
from views.history._widgets import make_ghost_btn, make_danger_btn


class HistoryViewQt(QWidget):
    """
    History View - Composition root.

    Compose HistoryListPanel (left 35%) va HistoryDetailPanel (right 65%).
    Wire tat ca callbacks va quan ly data loading.
    """

    def __init__(
        self,
        on_reapply: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.on_reapply = on_reapply

        self._build_ui()

    # ─────────────────────────────────────────────────────────
    # BUILD UI
    # ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build layout tong the: header + splitter + footer."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        layout.addWidget(self._build_header_bar())

        # Splitter: List (35%) | Detail (65%)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(
            f"""
            QSplitter::handle {{
                background-color: {ThemeColors.BORDER};
            }}
            QSplitter::handle:hover {{
                background-color: {ThemeColors.PRIMARY};
            }}
        """
        )

        # List panel (left)
        self._list_panel = HistoryListPanel(
            on_entry_selected=self._on_entry_selected,
        )
        splitter.addWidget(self._list_panel)

        # Detail panel (right)
        self._detail_panel = HistoryDetailPanel(
            on_reapply=self.on_reapply,
            on_entry_deleted=self._on_entry_deleted,
            on_footer_message=self._show_footer_message,
        )
        splitter.addWidget(self._detail_panel)

        # Ty le 35:65
        splitter.setStretchFactor(0, 35)
        splitter.setStretchFactor(1, 65)
        splitter.setMinimumWidth(680)
        self._list_panel.setMinimumWidth(280)
        self._detail_panel.setMinimumWidth(400)

        layout.addWidget(splitter, stretch=1)

        # Footer status bar
        layout.addWidget(self._build_footer_bar())

    def _build_header_bar(self) -> QWidget:
        """Build header bar voi title + stats + buttons."""
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(
            f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border-bottom: 1px solid {ThemeColors.BORDER};
            }}
        """
        )

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        title = QLabel("History")
        title.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
        """
        )
        layout.addWidget(title)
        layout.addStretch()

        # Stats label
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 12px;
            font-family: 'Cascadia Code', 'Fira Code', monospace;
        """
        )
        layout.addWidget(self._stats_label)

        # Refresh button
        refresh_btn = make_ghost_btn("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)

        # Clear All button
        clear_btn = make_danger_btn("Clear All")
        clear_btn.clicked.connect(self._confirm_clear_all)
        layout.addWidget(clear_btn)

        return header

    def _build_footer_bar(self) -> QWidget:
        """Build footer status bar."""
        footer = QFrame()
        footer.setFixedHeight(28)
        footer.setStyleSheet(
            f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border-top: 1px solid {ThemeColors.BORDER};
            }}
        """
        )

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 0, 16, 0)

        self._footer_label = QLabel("")
        self._footer_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 11px;
        """
        )
        layout.addWidget(self._footer_label)

        return footer

    # ─────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────

    def on_view_activated(self) -> None:
        """Called khi tab duoc activate."""
        self._refresh()

    # ─────────────────────────────────────────────────────────
    # PRIVATE - DATA LOADING
    # ─────────────────────────────────────────────────────────

    @Slot()
    def _refresh(self) -> None:
        """Refresh danh sach entries."""
        entries = get_history_entries(limit=100)
        self._list_panel.load_entries(entries)
        self._update_stats()

    def _update_stats(self) -> None:
        """Update stats label o header."""
        stats = get_history_stats()
        self._stats_label.setText(
            f"{stats['total_entries']} entries · "
            f"{stats['total_operations']} ops · "
            f"{stats['success_rate']:.0f}% success"
        )

    # ─────────────────────────────────────────────────────────
    # PRIVATE - CALLBACKS (wire giua panels)
    # ─────────────────────────────────────────────────────────

    def _on_entry_selected(self, entry_id: str) -> None:
        """Goi boi HistoryListPanel khi user chon mot entry."""
        entry = get_entry_by_id(entry_id)
        if entry:
            self._detail_panel.show_entry(entry)
        else:
            self._detail_panel.show_empty()

    def _on_entry_deleted(self) -> None:
        """Goi boi HistoryDetailPanel khi entry bi xoa thanh cong."""
        self._list_panel.clear_selection()
        self._refresh()
        self._detail_panel.show_empty()

    # ─────────────────────────────────────────────────────────
    # PRIVATE - ACTIONS
    # ─────────────────────────────────────────────────────────

    @Slot()
    def _confirm_clear_all(self) -> None:
        """Confirm va clear toan bo history."""
        reply = QMessageBox.question(
            self,
            "Clear All History?",
            "Clear all history? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if clear_history():
                self._list_panel.clear_selection()
                self._refresh()
                self._detail_panel.show_empty()
                self._show_footer_message("History cleared", False)
            else:
                self._show_footer_message("Failed to clear history", True)

    def _show_footer_message(self, message: str, is_error: bool = False) -> None:
        """Hien thi message o footer bar, tu xoa sau 4s."""
        color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self._footer_label.setStyleSheet(
            f"""
            color: {color};
            font-size: 11px;
            font-weight: 600;
        """
        )
        self._footer_label.setText(message)

        # Auto-clear sau 4s
        QTimer.singleShot(4000, self._clear_footer_message)

    @Slot()
    def _clear_footer_message(self) -> None:
        """Xoa message tren footer."""
        self._footer_label.setText("")
        self._footer_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 11px;
        """
        )
