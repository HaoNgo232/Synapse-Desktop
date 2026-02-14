"""
History View (PySide6) - Tab hiển thị lịch sử các thao tác đã thực hiện.
"""

from datetime import datetime
from typing import Optional, Callable, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QScrollArea,
    QFrame, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from core.theme import ThemeColors
from services.history_service import (
    get_history_entries, get_entry_by_id, delete_entry,
    clear_history, get_history_stats, HistoryEntry,
)
from services.clipboard_utils import copy_to_clipboard


# Action type → color
_ACTION_COLORS = {
    "CREATE": ThemeColors.SUCCESS,
    "MODIFY": ThemeColors.PRIMARY,
    "REWRITE": ThemeColors.WARNING,
    "DELETE": ThemeColors.ERROR,
    "RENAME": "#A855F7",
}


class HistoryViewQt(QWidget):
    """View cho History tab — PySide6."""

    def __init__(
        self,
        on_reapply: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.on_reapply = on_reapply
        self.selected_entry_id: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("📋 History")
        title.setStyleSheet(
            f"font-weight: 600; font-size: 20px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(title)
        header.addStretch()

        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};"
        )
        header.addWidget(self._stats_label)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("class", "outlined")
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(refresh_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.setProperty("class", "danger")
        clear_btn.clicked.connect(self._confirm_clear_all)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        # Splitter: entry list | detail
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: entry list
        left_frame = QFrame()
        left_frame.setProperty("class", "surface")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(12, 12, 12, 12)

        left_title = QLabel("Recent Operations")
        left_title.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        left_layout.addWidget(left_title)

        self._entry_list = QListWidget()
        self._entry_list.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none; }}"
            f"QListWidget::item {{ padding: 8px; border-bottom: 1px solid {ThemeColors.BORDER}; }}"
            f"QListWidget::item:selected {{ background-color: {ThemeColors.BG_ELEVATED}; }}"
        )
        self._entry_list.currentRowChanged.connect(self._on_entry_selected)
        left_layout.addWidget(self._entry_list)
        splitter.addWidget(left_frame)

        # Right: detail
        right_frame = QFrame()
        right_frame.setProperty("class", "surface")
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(12, 12, 12, 12)

        right_title = QLabel("Details")
        right_title.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        right_layout.addWidget(right_title)

        self._detail_area = QScrollArea()
        self._detail_area.setWidgetResizable(True)
        self._detail_area.setFrameShape(QFrame.Shape.NoFrame)

        self._detail_content = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_content)
        self._detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._detail_area.setWidget(self._detail_content)

        # Empty state
        empty = QLabel("Select an entry to view details")
        empty.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-style: italic; padding: 30px;"
        )
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_layout.addWidget(empty)

        right_layout.addWidget(self._detail_area)
        splitter.addWidget(right_frame)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)  # stretch=1 để chiếm hết chiều cao

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size: 12px;")
        layout.addWidget(self._status)

    # ===== Public =====

    def on_view_activated(self) -> None:
        """Called khi tab selected."""
        self._refresh()

    # ===== Internal =====

    @Slot()
    def _refresh(self) -> None:
        self._entry_list.clear()
        entries = get_history_entries(limit=50)
        self._entries = entries

        if not entries:
            item = QListWidgetItem("No history yet")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._entry_list.addItem(item)
        else:
            for entry in entries:
                try:
                    dt = datetime.fromisoformat(entry.timestamp)
                    time_str = dt.strftime("%m/%d %H:%M")
                except ValueError:
                    time_str = entry.timestamp[:16]

                if entry.fail_count == 0:
                    icon = "✅"
                elif entry.success_count == 0:
                    icon = "❌"
                else:
                    icon = "⚠️"

                text = f"{icon} {entry.file_count} files  {time_str}  +{entry.success_count}/-{entry.fail_count}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, entry.id)
                self._entry_list.addItem(item)

        # Stats
        stats = get_history_stats()
        self._stats_label.setText(
            f"{stats['total_entries']} entries | "
            f"{stats['total_operations']} ops | "
            f"{stats['success_rate']:.0f}% success"
        )

    @Slot(int)
    def _on_entry_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self._entry_list.item(row)
        if not item:
            return
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        if not entry_id:
            return
        self.selected_entry_id = entry_id
        entry = get_entry_by_id(entry_id)
        if entry:
            self._show_detail(entry)

    def _show_detail(self, entry: HistoryEntry) -> None:
        """Render detail panel."""
        # Clear existing
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item and (widget := item.widget()):
                widget.deleteLater()

        try:
            dt = datetime.fromisoformat(entry.timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            time_str = entry.timestamp

        # Header
        h = QHBoxLayout()
        h.addWidget(QLabel(f"Entry #{entry.id}"))
        h.addStretch()
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 11px;")
        h.addWidget(time_label)
        header_widget = QWidget()
        header_widget.setLayout(h)
        self._detail_layout.addWidget(header_widget)

        # Stats badges
        stats_row = QHBoxLayout()
        s_label = QLabel(f"✅ {entry.success_count} success")
        s_label.setStyleSheet(
            f"color: {ThemeColors.SUCCESS}; background: {ThemeColors.BG_ELEVATED}; "
            f"padding: 4px 8px; border-radius: 4px; font-size: 11px;"
        )
        stats_row.addWidget(s_label)

        f_color = ThemeColors.ERROR if entry.fail_count > 0 else ThemeColors.TEXT_MUTED
        f_label = QLabel(f"❌ {entry.fail_count} failed")
        f_label.setStyleSheet(
            f"color: {f_color}; background: {ThemeColors.BG_ELEVATED}; "
            f"padding: 4px 8px; border-radius: 4px; font-size: 11px;"
        )
        stats_row.addWidget(f_label)
        stats_row.addStretch()
        stats_widget = QWidget()
        stats_widget.setLayout(stats_row)
        self._detail_layout.addWidget(stats_widget)

        # Actions
        actions_label = QLabel("Actions:")
        actions_label.setStyleSheet(
            f"font-weight: 600; font-size: 12px; color: {ThemeColors.TEXT_PRIMARY}; margin-top: 8px;"
        )
        self._detail_layout.addWidget(actions_label)

        for action_str in entry.action_summary[:10]:
            parts = action_str.split(" ", 1)
            action_type = parts[0] if parts else "?"
            file_name = parts[1] if len(parts) > 1 else ""
            color = _ACTION_COLORS.get(action_type, ThemeColors.TEXT_SECONDARY)

            action_label = QLabel(f"<span style='background-color:{color};color:#FFF;padding:2px 6px;border-radius:3px;font-size:9px;font-weight:bold;'>{action_type}</span> {file_name}")
            action_label.setTextFormat(Qt.TextFormat.RichText)
            action_label.setStyleSheet(f"font-size: 11px; color: {ThemeColors.TEXT_SECONDARY};")
            self._detail_layout.addWidget(action_label)

        if len(entry.action_summary) > 10:
            more = QLabel(f"... and {len(entry.action_summary) - 10} more")
            more.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-style: italic; font-size: 10px;")
            self._detail_layout.addWidget(more)

        # Error messages
        if entry.error_messages:
            err_title = QLabel("Errors:")
            err_title.setStyleSheet(
                f"font-weight: 600; font-size: 12px; color: {ThemeColors.ERROR}; margin-top: 8px;"
            )
            self._detail_layout.addWidget(err_title)
            for msg in entry.error_messages[:5]:
                display = msg[:100] + "..." if len(msg) > 100 else msg
                err_label = QLabel(display)
                err_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.TEXT_SECONDARY}; "
                    f"background: {ThemeColors.BG_ELEVATED}; padding: 4px; border-radius: 4px;"
                )
                err_label.setWordWrap(True)
                self._detail_layout.addWidget(err_label)

        self._detail_layout.addStretch()

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 10, 0, 0)
        copy_btn = QPushButton("Copy OPX")
        copy_btn.setProperty("class", "outlined")
        copy_btn.setMinimumHeight(34)
        copy_btn.clicked.connect(lambda: self._copy_opx(entry))
        btn_row.addWidget(copy_btn)

        reapply_btn = QPushButton("Re-apply")
        reapply_btn.setProperty("class", "primary")
        reapply_btn.setMinimumHeight(34)
        reapply_btn.clicked.connect(lambda: self._reapply_opx(entry))
        btn_row.addWidget(reapply_btn)

        btn_row.addStretch()

        del_btn = QPushButton("🗑 Delete")
        del_btn.setToolTip("Delete this entry")
        del_btn.setMinimumHeight(34)
        del_btn.setStyleSheet(
            f"QPushButton {{ "
            f"  font-size: 13px; border-radius: 6px; padding: 6px 14px; "
            f"  border: 1px solid {ThemeColors.ERROR}; "
            f"  background-color: transparent; color: {ThemeColors.ERROR}; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background-color: {ThemeColors.ERROR}; color: #FFFFFF; "
            f"}}"
        )
        del_btn.clicked.connect(lambda: self._delete_entry(entry.id))
        btn_row.addWidget(del_btn)

        btn_widget = QWidget()
        btn_widget.setLayout(btn_row)
        self._detail_layout.addWidget(btn_widget)

    def _copy_opx(self, entry: HistoryEntry) -> None:
        success, _ = copy_to_clipboard(entry.opx_content)
        self._show_status("OPX copied!" if success else "Copy failed", not success)

    def _reapply_opx(self, entry: HistoryEntry) -> None:
        if self.on_reapply:
            self.on_reapply(entry.opx_content)
            self._show_status("OPX loaded to Apply tab")

    def _delete_entry(self, entry_id: str) -> None:
        if delete_entry(entry_id):
            self.selected_entry_id = None
            self._refresh()
            self._show_status("Entry deleted")
        else:
            self._show_status("Failed to delete", is_error=True)

    @Slot()
    def _confirm_clear_all(self) -> None:
        reply = QMessageBox.question(
            self, "Clear All History?",
            "This will permanently delete all history entries. Cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if clear_history():
                self._refresh()
                self._show_status("History cleared")
            else:
                self._show_status("Failed to clear", is_error=True)

    def _show_status(self, message: str, is_error: bool = False) -> None:
        color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self._status.setStyleSheet(f"font-size: 12px; color: {color};")
        self._status.setText(message)
        if not is_error:
            QTimer.singleShot(4000, lambda: self._status.setText(""))
