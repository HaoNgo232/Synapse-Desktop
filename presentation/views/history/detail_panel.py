"""
views/history/_detail_panel.py

HistoryDetailPanel - Right panel cua HistoryViewQt.

Quan ly:
- Detail header card (entry ID, timestamp, stats)
- Progress bar (dual-segment success/fail)
- Action buttons (Copy OPX, Re-apply, Delete)
- Files Changed section (expand/collapse)
- Errors section (expand/collapse)
"""

from datetime import datetime
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QMessageBox,
)
from PySide6.QtCore import Qt

from presentation.config.theme import ThemeColors
from infrastructure.persistence.history_service import HistoryEntry, delete_entry
from infrastructure.adapters.clipboard_utils import copy_to_clipboard
from presentation.views.history.widgets import (
    FileChangeRow,
    ErrorCard,
    make_ghost_btn,
    make_primary_btn,
)


class HistoryDetailPanel(QWidget):
    """
    Right panel cua HistoryViewQt - hien thi chi tiet cho entry duoc chon.

    Nhan callbacks tu ngoai de xu ly:
    - on_reapply: goi khi user click Re-apply
    - on_entry_deleted: goi khi entry bi xoa (de refresh list)
    - on_footer_message: hien thi thong bao tren footer
    """

    def __init__(
        self,
        on_reapply: Optional[Callable[[str], None]] = None,
        on_entry_deleted: Optional[Callable[[], None]] = None,
        on_footer_message: Optional[Callable[[str, bool], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        # Callbacks duoc inject tu ngoai
        self._on_reapply = on_reapply
        self._on_entry_deleted = on_entry_deleted
        self._on_footer_message = on_footer_message

        self._build_ui()

    # ─────────────────────────────────────────────────────────
    # BUILD UI
    # ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Tao layout chinh: scroll area cho detail content."""
        panel = self
        panel.setStyleSheet(
            f"""
            QWidget {{
                background-color: {ThemeColors.BG_PAGE};
            }}
        """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        # Detail scroll area
        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._detail_scroll.setStyleSheet(
            """
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """
        )

        self._detail_content = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_content)
        self._detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_layout.setSpacing(12)

        # Empty state mac dinh
        self.show_empty()

        self._detail_scroll.setWidget(self._detail_content)
        layout.addWidget(self._detail_scroll)

    # ─────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────

    def show_empty(self) -> None:
        """Hien thi empty state (chua chon entry nao)."""
        self._clear()

        empty = QLabel("Select an operation from the list to view details")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 14px;
            padding: 48px;
        """
        )
        self._detail_layout.addWidget(empty)

    def show_entry(self, entry: HistoryEntry) -> None:
        """Render chi tiet cho mot entry."""
        self._clear()

        # Header card
        self._detail_layout.addWidget(self._create_detail_header(entry))
        # Files Changed section
        self._detail_layout.addWidget(self._create_files_section(entry))
        # Errors section (neu co)
        if entry.error_messages:
            self._detail_layout.addWidget(self._create_errors_section(entry))

        self._detail_layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # PRIVATE - CLEAR
    # ─────────────────────────────────────────────────────────

    def _clear(self) -> None:
        """Xoa tat ca widgets trong detail layout."""
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item and (widget := item.widget()):
                widget.deleteLater()

    # ─────────────────────────────────────────────────────────
    # PRIVATE - BUILD SECTIONS
    # ─────────────────────────────────────────────────────────

    def _create_detail_header(self, entry: HistoryEntry) -> QWidget:
        """Tao detail header card."""
        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 10px;
            }}
        """
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Row 1: Entry ID + Timestamp
        row1 = QHBoxLayout()

        entry_label = QLabel(f"Entry #{entry.id}")
        entry_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        """
        )
        row1.addWidget(entry_label)
        row1.addStretch()

        try:
            dt = datetime.fromisoformat(entry.timestamp)
            time_str = dt.strftime("%m/%d %H:%M:%S")
        except ValueError:
            time_str = entry.timestamp

        time_label = QLabel(time_str)
        time_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
        """
        )
        row1.addWidget(time_label)

        row1_widget = QWidget()
        row1_widget.setLayout(row1)
        layout.addWidget(row1_widget)

        # Row 2: Progress bar + stats
        layout.addWidget(self._create_progress_bar(entry))

        # Row 3: Action buttons
        layout.addWidget(self._create_action_buttons(entry))

        return card

    def _create_progress_bar(self, entry: HistoryEntry) -> QWidget:
        """Tao dual-segment progress bar: xanh (success) + do (fail)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Dual-segment bar
        bar_container = QFrame()
        bar_container.setFixedHeight(14)
        bar_container.setStyleSheet(
            f"""
            QFrame {{
                background-color: {ThemeColors.BORDER};
                border-radius: 7px;
            }}
        """
        )

        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        # Segment xanh (success)
        if entry.success_count > 0:
            success_seg = QFrame()
            radius = "7px" if entry.fail_count == 0 else "7px 0 0 7px"
            success_seg.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {ThemeColors.SUCCESS};
                    border-radius: {radius};
                }}
            """
            )
            bar_layout.addWidget(success_seg, stretch=entry.success_count)

        # Segment do (fail)
        if entry.fail_count > 0:
            fail_seg = QFrame()
            radius = "7px" if entry.success_count == 0 else "0 7px 7px 0"
            fail_seg.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {ThemeColors.ERROR};
                    border-radius: {radius};
                }}
            """
            )
            bar_layout.addWidget(fail_seg, stretch=entry.fail_count)

        layout.addWidget(bar_container)

        # Stats text
        if entry.fail_count == 0:
            stats_text = f"{entry.success_count}/{entry.file_count} all successful"
            stats_color = ThemeColors.SUCCESS
        elif entry.success_count == 0:
            stats_text = f"0/{entry.file_count} all failed"
            stats_color = ThemeColors.ERROR
        else:
            stats_text = f"{entry.success_count} done / {entry.fail_count} failed"
            stats_color = ThemeColors.TEXT_SECONDARY

        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet(
            f"""
            color: {stats_color};
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
        """
        )
        layout.addWidget(stats_label)

        return widget

    def _create_action_buttons(self, entry: HistoryEntry) -> QWidget:
        """Tao row action buttons."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Copy OPX (ghost)
        copy_btn = make_ghost_btn("Copy OPX")
        copy_btn.setFixedHeight(30)
        copy_btn.clicked.connect(lambda: self._copy_opx(entry))
        layout.addWidget(copy_btn)

        # Re-apply (primary)
        reapply_btn = make_primary_btn("Re-apply", height=30)
        reapply_btn.clicked.connect(lambda: self._reapply_opx(entry))
        layout.addWidget(reapply_btn)

        layout.addStretch()

        # Delete (ghost danger)
        delete_btn = QPushButton("Delete")
        delete_btn.setFixedHeight(30)
        delete_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.ERROR};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: rgba(248, 113, 113, 0.12);
                border-color: {ThemeColors.ERROR};
            }}
        """
        )
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self._confirm_delete_entry(entry.id))
        layout.addWidget(delete_btn)

        return widget

    def _create_files_section(self, entry: HistoryEntry) -> QWidget:
        """Tao Files Changed section voi expand/collapse khi > 15 files."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Section header
        header = QLabel(f"Files Changed ({entry.file_count})")
        header.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 700;
        """
        )
        layout.addWidget(header)

        # Files list container
        files_container = QFrame()
        files_container.setStyleSheet(
            f"""
            QFrame {{
                background-color: rgba(38, 38, 55, 0.6);
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """
        )

        files_layout = QVBoxLayout(files_container)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(0)

        display_limit = 15
        total_actions = len(entry.action_summary)

        # Hien 15 files dau tien
        for i, action_str in enumerate(entry.action_summary[:display_limit]):
            parts = action_str.split(" ", 1)
            op_type = parts[0] if parts else "UNKNOWN"
            filename = parts[1] if len(parts) > 1 else "unknown"
            success = i < entry.success_count
            files_layout.addWidget(FileChangeRow(op_type, filename, success))

        # Container an cho files con lai
        hidden_container = QWidget()
        hidden_layout = QVBoxLayout(hidden_container)
        hidden_layout.setContentsMargins(0, 0, 0, 0)
        hidden_layout.setSpacing(0)
        hidden_container.setVisible(False)

        for i, action_str in enumerate(
            entry.action_summary[display_limit:], start=display_limit
        ):
            parts = action_str.split(" ", 1)
            op_type = parts[0] if parts else "UNKNOWN"
            filename = parts[1] if len(parts) > 1 else "unknown"
            success = i < entry.success_count
            hidden_layout.addWidget(FileChangeRow(op_type, filename, success))

        files_layout.addWidget(hidden_container)

        # Show more / collapse button
        if total_actions > display_limit:
            remaining = total_actions - display_limit
            more_btn = QPushButton(f"Show {remaining} more files")
            more_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    color: {ThemeColors.PRIMARY};
                    border: none;
                    text-align: left;
                    padding: 8px 12px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    color: {ThemeColors.PRIMARY_HOVER};
                    background-color: rgba(124, 111, 255, 0.06);
                }}
            """
            )
            more_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def _toggle_files(btn=more_btn, container=hidden_container, rem=remaining):
                """Toggle hien/an cac files con lai."""
                is_visible = container.isVisible()
                container.setVisible(not is_visible)
                btn.setText(f"Show {rem} more files" if is_visible else "Collapse")

            more_btn.clicked.connect(lambda: _toggle_files())
            files_layout.addWidget(more_btn)

        layout.addWidget(files_container)
        return section

    def _create_errors_section(self, entry: HistoryEntry) -> QWidget:
        """Tao Errors section voi expand/collapse khi > 3 errors."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(8)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(
            f"background-color: {ThemeColors.BORDER}; max-height: 1px;"
        )
        layout.addWidget(divider)

        # Section header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 8, 0, 0)

        header_label = QLabel("Errors")
        header_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 600;
        """
        )
        header_layout.addWidget(header_label)

        count_badge = QLabel(f"{len(entry.error_messages)}")
        count_badge.setStyleSheet(
            f"""
            color: {ThemeColors.ERROR};
            background-color: rgba(248, 113, 113, 0.15);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        """
        )
        header_layout.addWidget(count_badge)
        header_layout.addStretch()

        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        layout.addWidget(header_widget)

        display_limit = 3
        total_errors = len(entry.error_messages)

        for error_msg in entry.error_messages[:display_limit]:
            if ":" in error_msg:
                parts = error_msg.split(":", 1)
                filename = parts[0].strip()
                msg = parts[1].strip() if len(parts) > 1 else error_msg
            else:
                filename = "Error"
                msg = error_msg
            layout.addWidget(ErrorCard(filename, msg))

        if total_errors > display_limit:
            hidden_container = QWidget()
            hidden_layout = QVBoxLayout(hidden_container)
            hidden_layout.setContentsMargins(0, 0, 0, 0)
            hidden_layout.setSpacing(0)
            hidden_container.setVisible(False)

            for error_msg in entry.error_messages[display_limit:]:
                if ":" in error_msg:
                    parts = error_msg.split(":", 1)
                    filename = parts[0].strip()
                    msg = parts[1].strip() if len(parts) > 1 else error_msg
                else:
                    filename = "Error"
                    msg = error_msg
                hidden_layout.addWidget(ErrorCard(filename, msg))

            layout.addWidget(hidden_container)

            remaining = total_errors - display_limit
            more_btn = QPushButton(f"Show {remaining} more errors...")
            more_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    color: {ThemeColors.PRIMARY};
                    border: none;
                    text-align: left;
                    padding: 4px 8px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    color: {ThemeColors.PRIMARY_HOVER};
                    background-color: rgba(124, 111, 255, 0.06);
                }}
            """
            )
            more_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def _toggle_errors(btn=more_btn, container=hidden_container, rem=remaining):
                """Toggle hien/an cac errors con lai."""
                is_visible = container.isVisible()
                container.setVisible(not is_visible)
                btn.setText(
                    f"Show {rem} more errors..." if is_visible else "Collapse errors"
                )

            more_btn.clicked.connect(lambda: _toggle_errors())
            layout.addWidget(more_btn)

        return section

    # ─────────────────────────────────────────────────────────
    # PRIVATE - ACTIONS
    # ─────────────────────────────────────────────────────────

    def _copy_opx(self, entry: HistoryEntry) -> None:
        """Copy OPX content vao clipboard."""
        success, _ = copy_to_clipboard(entry.opx_content)
        if self._on_footer_message:
            if success:
                self._on_footer_message("OPX copied to clipboard!", False)
            else:
                self._on_footer_message("Failed to copy OPX", True)

    def _reapply_opx(self, entry: HistoryEntry) -> None:
        """Re-apply OPX content."""
        if self._on_reapply:
            self._on_reapply(entry.opx_content)
            if self._on_footer_message:
                self._on_footer_message("OPX loaded to Apply tab", False)

    def _confirm_delete_entry(self, entry_id: str) -> None:
        """Confirm va delete mot entry."""
        reply = QMessageBox.question(
            self,
            "Delete Entry?",
            "Delete this entry? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if delete_entry(entry_id):
                if self._on_entry_deleted:
                    self._on_entry_deleted()
                if self._on_footer_message:
                    self._on_footer_message("Entry deleted", False)
            else:
                if self._on_footer_message:
                    self._on_footer_message("Failed to delete entry", True)
