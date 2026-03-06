"""
views/history/_list_panel.py

HistoryListPanel - Left panel cua HistoryViewQt.

Quan ly:
- Search bar (QLineEdit)
- Entry list (QListWidget) voi date grouping
- Render entry widgets voi selection state
"""

from datetime import datetime
from typing import Optional, Callable, List, Dict

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QHBoxLayout,
)
from PySide6.QtCore import Qt, Slot, QSize

from presentation.config.theme import ThemeColors
from services.history_service import HistoryEntry
from presentation.views.history.widgets import (
    DateGroupHeader,
    create_status_dot_icon,
    group_entries_by_date,
)


class HistoryListPanel(QWidget):
    """
    Left panel cua HistoryViewQt - danh sach cac entries.

    Nhan callback de bao cao entry nao duoc chon:
    - on_entry_selected(entry_id): Goi khi user click vao entry
    """

    def __init__(
        self,
        on_entry_selected: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        # Callback bao cao ra ngoai khi user chon entry
        self._on_entry_selected = on_entry_selected

        self._all_entries: List[HistoryEntry] = []
        self._filtered_entries: List[HistoryEntry] = []
        self._selected_entry_id: Optional[str] = None

        self._build_ui()

    # ─────────────────────────────────────────────────────────
    # BUILD UI
    # ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Tao layout: search bar + entry list."""
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {ThemeColors.BG_PAGE};
            }}
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Search bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search operations...")
        self._search_input.setFixedHeight(36)
        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding-left: 36px;
                padding-right: 12px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """
        )
        layout.addWidget(self._search_input)

        # Entry list
        self._entry_list = QListWidget()
        self._entry_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._entry_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._entry_list.setSpacing(4)
        self._entry_list.setStyleSheet(
            """
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item,
            QListWidget::item:selected,
            QListWidget::item:focus,
            QListWidget::item:hover {
                background: transparent;
                border: none;
                outline: none;
                padding: 0;
                margin: 0;
            }
        """
        )
        self._entry_list.itemClicked.connect(self._on_entry_clicked)
        layout.addWidget(self._entry_list)

    # ─────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────

    def load_entries(self, entries: List[HistoryEntry]) -> None:
        """Load danh sach entries moi, reset filter."""
        self._all_entries = entries
        self._filtered_entries = entries.copy()
        self._render()

    def get_selected_id(self) -> Optional[str]:
        """Tra ve ID cua entry dang duoc chon."""
        return self._selected_entry_id

    def clear_selection(self) -> None:
        """Xoa selection hien tai."""
        old_id = self._selected_entry_id
        self._selected_entry_id = None
        self._update_entry_style(old_id, selected=False)

    # ─────────────────────────────────────────────────────────
    # PRIVATE - RENDER
    # ─────────────────────────────────────────────────────────

    def _render(self) -> None:
        """Render entry list voi date grouping."""
        self._entry_list.clear()

        if not self._filtered_entries:
            empty_item = QListWidgetItem()
            empty_widget = QLabel("No operations yet")
            empty_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_widget.setStyleSheet(
                f"""
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 14px;
                padding: 32px;
            """
            )
            empty_item.setSizeHint(empty_widget.sizeHint())
            self._entry_list.addItem(empty_item)
            self._entry_list.setItemWidget(empty_item, empty_widget)
            return

        groups = group_entries_by_date(self._filtered_entries)

        for group_name, entries in groups.items():
            # Date header
            header_item = QListWidgetItem()
            header_widget = DateGroupHeader(group_name)
            header_item.setSizeHint(header_widget.sizeHint())
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._entry_list.addItem(header_item)
            self._entry_list.setItemWidget(header_item, header_widget)

            # Entry items
            for entry in entries:
                entry_item = QListWidgetItem()
                entry_widget = self._create_entry_widget(entry)
                entry_item.setSizeHint(QSize(0, 88))
                entry_item.setData(Qt.ItemDataRole.UserRole, entry.id)
                self._entry_list.addItem(entry_item)
                self._entry_list.setItemWidget(entry_item, entry_widget)

    def _create_entry_widget(self, entry: HistoryEntry) -> QWidget:
        """Tao widget cho mot entry item trong list (3 dong)."""
        widget = QFrame()
        widget.setProperty("entry_id", entry.id)

        # Xac dinh status
        if entry.fail_count == 0:
            status_color = ThemeColors.SUCCESS
            status_text = "done"
            status_bg = "rgba(74, 222, 128, 0.12)"
        elif entry.success_count == 0:
            status_color = ThemeColors.ERROR
            status_text = "failed"
            status_bg = "rgba(248, 113, 113, 0.12)"
        else:
            status_color = ThemeColors.WARNING
            status_text = "partial"
            status_bg = "rgba(251, 191, 36, 0.12)"

        # Parse timestamp
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            time_str = dt.strftime("%H:%M")
        except ValueError:
            time_str = entry.timestamp[:5]

        # Tom tat operation types
        op_counts: Dict[str, int] = {}
        for action in entry.action_summary:
            op = action.split(" ", 1)[0] if action else "UNKNOWN"
            op_counts[op] = op_counts.get(op, 0) + 1
        op_parts = [
            f"{count} {op}"
            for op, count in sorted(op_counts.items(), key=lambda x: -x[1])[:3]
        ]
        op_summary = " / ".join(op_parts) if op_parts else ""

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 8, 12, 8)
        layout.setSpacing(3)

        # DONG 1: [dot] time  file_count  [status badge]
        line1 = QHBoxLayout()
        line1.setSpacing(6)
        line1.setContentsMargins(0, 0, 0, 0)

        dot_label = QLabel()
        dot_label.setPixmap(create_status_dot_icon(status_color, 6).pixmap(6, 6))
        dot_label.setFixedSize(6, 6)
        line1.addWidget(dot_label)

        time_label = QLabel(time_str)
        time_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
        """
        )
        line1.addWidget(time_label)

        files_label = QLabel(f"{entry.file_count} files")
        files_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 11px;
        """
        )
        line1.addWidget(files_label)

        line1.addStretch()

        status_badge = QLabel(status_text)
        status_badge.setStyleSheet(
            f"""
            color: {status_color};
            background-color: {status_bg};
            padding: 1px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        """
        )
        line1.addWidget(status_badge)

        line1_widget = QWidget()
        line1_widget.setLayout(line1)
        layout.addWidget(line1_widget)

        # DONG 2: op summary
        if op_summary:
            line2 = QHBoxLayout()
            line2.setContentsMargins(14, 0, 0, 0)
            line2.setSpacing(0)
            ops_label = QLabel(op_summary)
            ops_label.setStyleSheet(
                f"""
                color: {ThemeColors.TEXT_MUTED};
                font-size: 11px;
                font-family: 'JetBrains Mono', monospace;
            """
            )
            line2.addWidget(ops_label)
            line2.addStretch()
            line2_widget = QWidget()
            line2_widget.setLayout(line2)
            layout.addWidget(line2_widget)

        # DONG 3: done X / fail Y
        line3 = QHBoxLayout()
        line3.setContentsMargins(14, 0, 0, 0)
        line3.setSpacing(4)

        done_label = QLabel(f"done {entry.success_count}")
        done_label.setStyleSheet(
            f"""
            color: {ThemeColors.SUCCESS};
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
        """
        )
        line3.addWidget(done_label)

        sep_label = QLabel("/")
        sep_label.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 11px;")
        line3.addWidget(sep_label)

        fail_color = (
            ThemeColors.ERROR if entry.fail_count > 0 else ThemeColors.TEXT_MUTED
        )
        fail_label = QLabel(f"fail {entry.fail_count}")
        fail_label.setStyleSheet(
            f"""
            color: {fail_color};
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
        """
        )
        line3.addWidget(fail_label)
        line3.addStretch()

        line3_widget = QWidget()
        line3_widget.setLayout(line3)
        layout.addWidget(line3_widget)

        # STYLING - selected hay khong
        is_selected = self._selected_entry_id == entry.id
        self._apply_entry_style(widget, selected=is_selected)

        return widget

    def _apply_entry_style(self, widget: QWidget, selected: bool) -> None:
        """Ap dung style cho entry widget (selected va not selected)."""
        if selected:
            widget.setStyleSheet(
                f"""
                QFrame {{
                    background-color: rgba(124, 111, 255, 0.1);
                    border-left: 4px solid {ThemeColors.PRIMARY};
                    border-radius: 8px;
                }}
            """
            )
        else:
            widget.setStyleSheet(
                """
                QFrame {
                    background-color: transparent;
                    border-left: 4px solid transparent;
                    border-radius: 8px;
                }
                QFrame:hover {
                    background-color: rgba(45, 45, 68, 0.4);
                }
            """
            )

    def _update_entry_style(self, entry_id: Optional[str], selected: bool) -> None:
        """Update style cua entry widget by ID (in-place, khong re-render)."""
        if not entry_id:
            return

        for i in range(self._entry_list.count()):
            list_item = self._entry_list.item(i)
            if not list_item:
                continue
            if list_item.data(Qt.ItemDataRole.UserRole) != entry_id:
                continue
            widget = self._entry_list.itemWidget(list_item)
            if widget:
                self._apply_entry_style(widget, selected=selected)
            break

    # ─────────────────────────────────────────────────────────
    # PRIVATE - EVENTS
    # ─────────────────────────────────────────────────────────

    @Slot(str)
    def _on_search_changed(self, text: str) -> None:
        """Filter entries khi search text thay doi."""
        query = text.lower().strip()

        if not query:
            self._filtered_entries = self._all_entries.copy()
        else:
            self._filtered_entries = [
                entry
                for entry in self._all_entries
                if query in entry.id.lower()
                or query in entry.timestamp.lower()
                or any(query in action.lower() for action in entry.action_summary)
            ]

        self._render()

    @Slot(QListWidgetItem)
    def _on_entry_clicked(self, item: QListWidgetItem) -> None:
        """Handle khi user click vao mot entry."""
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        if not entry_id:
            return

        old_selected_id = self._selected_entry_id
        self._selected_entry_id = entry_id

        # Update style in-place
        self._update_entry_style(old_selected_id, selected=False)
        self._update_entry_style(entry_id, selected=True)

        # Thong bao ra ngoai
        if self._on_entry_selected:
            self._on_entry_selected(entry_id)
