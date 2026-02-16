"""
History View (PySide6) - Redesigned theo spec mới
Tab hiển thị lịch sử các thao tác đã thực hiện với UI chuyên nghiệp.
"""

from datetime import datetime, timedelta
from typing import Optional, Callable, List, Dict

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QFrame,
    QMessageBox,
    QLineEdit,
    QProgressBar,
)
from PySide6.QtCore import Qt, Slot, QTimer, QSize, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QIcon, QPixmap

from core.theme import ThemeColors, ThemeSpacing, ThemeRadius
from services.history_service import (
    get_history_entries,
    get_entry_by_id,
    delete_entry,
    clear_history,
    get_history_stats,
    HistoryEntry,
)
from services.clipboard_utils import copy_to_clipboard


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS - Icon Generation
# ═══════════════════════════════════════════════════════════════


def create_status_dot_icon(color: str, size: int = 12) -> QIcon:
    """Tạo icon chấm tròn (status dot) với màu cho trước."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.end()
    
    return QIcon(pixmap)


def create_search_icon(size: int = 16) -> QIcon:
    """Tạo icon kính lúp đơn giản."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    pen = QPen(QColor(ThemeColors.TEXT_SECONDARY))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    
    # Circle
    painter.drawEllipse(2, 2, 9, 9)
    # Handle
    painter.drawLine(10, 10, 14, 14)
    painter.end()
    
    return QIcon(pixmap)


# ═══════════════════════════════════════════════════════════════
# DATE GROUPING HELPERS
# ═══════════════════════════════════════════════════════════════


def format_date_group(dt: datetime) -> str:
    """Format date cho group header: 'Hôm nay', 'Hôm qua', hoặc 'MM/DD'."""
    now = datetime.now()
    today = now.date()
    yesterday = (now - timedelta(days=1)).date()
    
    entry_date = dt.date()
    
    if entry_date == today:
        return f"Hôm nay · {dt.strftime('%m/%d')}"
    elif entry_date == yesterday:
        return f"Hôm qua · {dt.strftime('%m/%d')}"
    else:
        return dt.strftime("%m/%d")


def group_entries_by_date(entries: List[HistoryEntry]) -> Dict[str, List[HistoryEntry]]:
    """Nhóm entries theo ngày."""
    groups: Dict[str, List[HistoryEntry]] = {}
    
    for entry in entries:
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            group_key = format_date_group(dt)
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(entry)
        except ValueError:
            # Fallback nếu timestamp không parse được
            if "Unknown" not in groups:
                groups["Unknown"] = []
            groups["Unknown"].append(entry)
    
    return groups


# ═══════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ═══════════════════════════════════════════════════════════════


class DateGroupHeader(QWidget):
    """Header phân cách nhóm ngày với line kẻ ngang."""
    
    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(36)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 8)
        layout.setSpacing(12)
        
        # Text (title case, không UPPERCASE)
        label = QLabel(text)
        label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.3px;
        """)
        layout.addWidget(label)
        
        # Line phải
        right_line = QFrame()
        right_line.setFrameShape(QFrame.Shape.HLine)
        right_line.setStyleSheet(f"background-color: {ThemeColors.BORDER}; max-height: 1px;")
        layout.addWidget(right_line, stretch=1)


class OperationBadge(QLabel):
    """Badge cho operation type (MODIFY, CREATE, DELETE, etc.)."""
    
    COLORS = {
        "MODIFY": ("#60A5FA", "rgba(96, 165, 250, 0.10)"),
        "CREATE": ("#4ADE80", "rgba(74, 222, 128, 0.10)"),
        "DELETE": ("#F87171", "rgba(248, 113, 113, 0.10)"),
        "MOVE": ("#FBBF24", "rgba(251, 191, 36, 0.10)"),
        "RENAME": ("#FBBF24", "rgba(251, 191, 36, 0.10)"),
        "REPLACE": ("#C084FC", "rgba(192, 132, 252, 0.10)"),
        "REWRITE": ("#C084FC", "rgba(192, 132, 252, 0.10)"),
    }
    
    def __init__(self, op_type: str, parent: Optional[QWidget] = None):
        super().__init__(op_type.upper(), parent)
        
        text_color, bg_color = self.COLORS.get(op_type.upper(), (ThemeColors.TEXT_SECONDARY, ThemeColors.BG_ELEVATED))
        
        self.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                background-color: {bg_color};
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 700;
                font-family: 'JetBrains Mono', monospace;
            }}
        """)


class FileChangeRow(QWidget):
    """Row hiển thị một file change với status dot + operation badge + filename + status text."""
    
    def __init__(self, op_type: str, filename: str, success: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(36)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)
        
        # Status dot
        dot_color = ThemeColors.SUCCESS if success else ThemeColors.ERROR
        dot_label = QLabel()
        dot_label.setPixmap(create_status_dot_icon(dot_color, 8).pixmap(8, 8))
        dot_label.setFixedSize(8, 8)
        layout.addWidget(dot_label)
        
        # Operation badge
        badge = OperationBadge(op_type)
        layout.addWidget(badge)
        
        # Filename
        name_label = QLabel(filename)
        name_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
        """)
        layout.addWidget(name_label, stretch=1)
        
        # Status text
        if success:
            status_label = QLabel("✓ done")
            status_label.setStyleSheet(f"""
                color: {ThemeColors.SUCCESS};
                font-size: 11px;
                font-weight: 600;
            """)
        else:
            status_label = QLabel("✗ failed")
            status_label.setStyleSheet(f"""
                color: {ThemeColors.ERROR};
                font-size: 11px;
                font-weight: 600;
            """)
        layout.addWidget(status_label)
        
        # Hover effect - mềm mại, hài hòa với surface
        self.setStyleSheet(f"""
            FileChangeRow {{
                background-color: transparent;
                border-bottom: 1px solid rgba(62, 62, 94, 0.4);
            }}
            FileChangeRow:hover {{
                background-color: rgba(45, 45, 68, 0.6);
            }}
        """)


class ErrorCard(QFrame):
    """Card hiển thị một error message với border-left đỏ và nền gần trong suốt."""
    
    def __init__(self, filename: str, error_msg: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        # Filename (đỏ sáng)
        name_label = QLabel(filename)
        name_label.setStyleSheet(f"""
            color: {ThemeColors.ERROR};
            font-size: 13px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        """)
        layout.addWidget(name_label)
        
        # Error message (wrap, pre-wrap)
        msg_label = QLabel(error_msg)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            white-space: pre-wrap;
        """)
        layout.addWidget(msg_label)
        
        # Style - nền đỏ nhạt đủ nhìn, hài hòa với dark theme
        self.setStyleSheet(f"""
            ErrorCard {{
                background-color: rgba(248, 113, 113, 0.06);
                border-left: 3px solid {ThemeColors.ERROR};
                border-radius: 0 8px 8px 0;
                margin-bottom: 6px;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# MAIN HISTORY VIEW
# ═══════════════════════════════════════════════════════════════


class HistoryViewQt(QWidget):
    """History View - Redesigned với layout 35/65, date grouping, và professional UI."""
    
    def __init__(
        self,
        on_reapply: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.on_reapply = on_reapply
        self.selected_entry_id: Optional[str] = None
        self._all_entries: List[HistoryEntry] = []
        self._filtered_entries: List[HistoryEntry] = []
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build UI với header bar + splitter (list | detail)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ─────────────────────────────────────────────────────────
        # HEADER BAR
        # ─────────────────────────────────────────────────────────
        header_bar = self._build_header_bar()
        layout.addWidget(header_bar)
        
        # ─────────────────────────────────────────────────────────
        # SPLITTER: Left (35%) | Right (65%)
        # ─────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {ThemeColors.BORDER};
            }}
            QSplitter::handle:hover {{
                background-color: {ThemeColors.PRIMARY};
            }}
        """)
        
        # Left panel
        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel
        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)
        
        # Set tỷ lệ 35:65
        splitter.setStretchFactor(0, 35)
        splitter.setStretchFactor(1, 65)
        
        # Set minimum widths
        splitter.setMinimumWidth(680)  # 280 + 400
        left_panel.setMinimumWidth(280)
        right_panel.setMinimumWidth(400)
        
        layout.addWidget(splitter, stretch=1)
        
        # ─────────────────────────────────────────────────────────
        # FOOTER STATUS BAR
        # ─────────────────────────────────────────────────────────
        footer_bar = self._build_footer_bar()
        layout.addWidget(footer_bar)
    
    def _build_header_bar(self) -> QWidget:
        """Build header bar với title + stats + buttons."""
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border-bottom: 1px solid {ThemeColors.BORDER};
            }}
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("History")
        title.setStyleSheet(f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
        """)
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Stats
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
        """)
        layout.addWidget(self._stats_label)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._ghost_button_style())
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)
        
        # Clear All button
        clear_btn = QPushButton("Clear All")
        clear_btn.setStyleSheet(self._ghost_danger_button_style())
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._confirm_clear_all)
        layout.addWidget(clear_btn)
        
        return header
    
    def _build_left_panel(self) -> QWidget:
        """Build left panel: search + entry list."""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.BG_PAGE};
            }}
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Search bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search operations...")
        self._search_input.setFixedHeight(36)
        self._search_input.textChanged.connect(self._on_search_changed)
        
        # Add search icon (simple approach: use placeholder with icon)
        self._search_input.setStyleSheet(f"""
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
        """)
        layout.addWidget(self._search_input)
        
        # Entry list
        self._entry_list = QListWidget()
        self._entry_list.setSpacing(4)  # Add spacing between items
        self._entry_list.setStyleSheet(f"""
            QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                border: none;
                padding: 0;
                margin: 0 0 4px 0;
            }}
        """)
        self._entry_list.itemClicked.connect(self._on_entry_clicked)
        layout.addWidget(self._entry_list)
        
        return panel
    
    def _build_right_panel(self) -> QWidget:
        """Build right panel: detail view."""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.BG_PAGE};
            }}
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)
        
        # Detail scroll area
        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._detail_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
        """)
        
        self._detail_content = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_content)
        self._detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_layout.setSpacing(12)
        
        # Empty state
        self._show_empty_detail_state()
        
        self._detail_scroll.setWidget(self._detail_content)
        layout.addWidget(self._detail_scroll)
        
        return panel
    
    def _build_footer_bar(self) -> QWidget:
        """Build footer status bar."""
        footer = QFrame()
        footer.setFixedHeight(28)
        footer.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border-top: 1px solid {ThemeColors.BORDER};
            }}
        """)
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 0, 16, 0)
        
        self._footer_label = QLabel("")
        self._footer_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 11px;
        """)
        layout.addWidget(self._footer_label)
        
        return footer
    
    # ═══════════════════════════════════════════════════════════════
    # BUTTON STYLES
    # ═══════════════════════════════════════════════════════════════
    
    def _ghost_button_style(self) -> str:
        """Ghost button style (transparent with border)."""
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_HOVER};
                border-color: {ThemeColors.BORDER_LIGHT};
            }}
        """
    
    def _ghost_danger_button_style(self) -> str:
        """Ghost danger button (red text + border)."""
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.ERROR};
                border: 1px solid {ThemeColors.ERROR};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.ERROR};
                color: white;
            }}
        """
    
    def _primary_button_style(self) -> str:
        """Primary button style (accent background)."""
        return f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
        """
    
    # ═══════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════
    
    def on_view_activated(self) -> None:
        """Called khi tab được activate."""
        self._refresh()
    
    # ═══════════════════════════════════════════════════════════════
    # INTERNAL - DATA LOADING
    # ═══════════════════════════════════════════════════════════════
    
    @Slot()
    def _refresh(self) -> None:
        """Refresh danh sách entries."""
        self._all_entries = get_history_entries(limit=100)
        self._filtered_entries = self._all_entries.copy()
        self._render_entry_list()
        self._update_stats()
    
    def _update_stats(self) -> None:
        """Update stats label ở header."""
        stats = get_history_stats()
        self._stats_label.setText(
            f"{stats['total_entries']} entries · "
            f"{stats['total_operations']} ops · "
            f"{stats['success_rate']:.0f}% success"
        )
    
    @Slot(str)
    def _on_search_changed(self, text: str) -> None:
        """Filter entries khi search text thay đổi."""
        query = text.lower().strip()
        
        if not query:
            self._filtered_entries = self._all_entries.copy()
        else:
            self._filtered_entries = [
                entry for entry in self._all_entries
                if query in entry.id.lower()
                or query in entry.timestamp.lower()
                or any(query in action.lower() for action in entry.action_summary)
            ]
        
        self._render_entry_list()
    
    def _render_entry_list(self) -> None:
        """Render entry list với date grouping."""
        self._entry_list.clear()
        
        if not self._filtered_entries:
            # Empty state
            empty_item = QListWidgetItem()
            empty_widget = QLabel("Chưa có operation nào")
            empty_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_widget.setStyleSheet(f"""
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 14px;
                padding: 32px;
            """)
            empty_item.setSizeHint(empty_widget.sizeHint())
            self._entry_list.addItem(empty_item)
            self._entry_list.setItemWidget(empty_item, empty_widget)
            return
        
        # Group by date
        groups = group_entries_by_date(self._filtered_entries)
        
        for group_name, entries in groups.items():
            # Date header
            header_item = QListWidgetItem()
            header_widget = DateGroupHeader(group_name)
            header_item.setSizeHint(header_widget.sizeHint())
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable
            self._entry_list.addItem(header_item)
            self._entry_list.setItemWidget(header_item, header_widget)
            
            # Entries
            for entry in entries:
                entry_item = QListWidgetItem()
                entry_widget = self._create_entry_widget(entry)
                entry_item.setSizeHint(QSize(0, 100))
                entry_item.setData(Qt.ItemDataRole.UserRole, entry.id)
                self._entry_list.addItem(entry_item)
                self._entry_list.setItemWidget(entry_item, entry_widget)
    
    def _create_entry_widget(self, entry: HistoryEntry) -> QWidget:
        """Tạo widget cho một entry item theo spec: 2 dòng đơn giản, không progress bar."""
        widget = QFrame()
        widget.setProperty("entry_id", entry.id)
        
        # Determine status
        if entry.fail_count == 0:
            status_color = ThemeColors.SUCCESS
            status_text = "success"
        elif entry.success_count == 0:
            status_color = ThemeColors.ERROR
            status_text = "failed"
        else:
            status_color = ThemeColors.WARNING
            status_text = "partial"
        
        # Parse timestamp
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            time_str = dt.strftime("%H:%M")
        except ValueError:
            time_str = entry.timestamp[:5]
        
        # Layout
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 12, 14, 12)  # Tăng padding top/bottom
        layout.setSpacing(6)  # Tăng spacing giữa 2 dòng
        
        # DÒNG 1: ● dot + giờ + số files ... status text
        line1 = QHBoxLayout()
        line1.setSpacing(8)
        
        # Status dot 8px
        dot_label = QLabel()
        dot_label.setPixmap(create_status_dot_icon(status_color, 8).pixmap(8, 8))
        dot_label.setFixedSize(8, 8)
        line1.addWidget(dot_label)
        
        # Giờ (font mono 13px bold)
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
        """)
        time_label.setMinimumHeight(18)  # Đảm bảo đủ chiều cao
        line1.addWidget(time_label)
        
        # Số files (font 12px)
        files_label = QLabel(f"{entry.file_count} files")
        files_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 12px;
        """)
        files_label.setMinimumHeight(18)  # Đảm bảo đủ chiều cao
        line1.addWidget(files_label)
        
        line1.addStretch()
        
        # Status text căn phải (font 11px)
        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"""
            color: {status_color};
            font-size: 11px;
            font-weight: 600;
        """)
        status_label.setMinimumHeight(18)  # Đảm bảo đủ chiều cao
        line1.addWidget(status_label)
        
        line1_widget = QWidget()
        line1_widget.setLayout(line1)
        layout.addWidget(line1_widget)
        
        # DÒNG 2: +added / -removed (indent 20px)
        line2 = QHBoxLayout()
        line2.setContentsMargins(20, 0, 0, 0)  # Indent 20px
        line2.setSpacing(4)
        
        # +added (xanh lá)
        added_label = QLabel(f"+{entry.success_count}")
        added_label.setStyleSheet(f"""
            color: {ThemeColors.SUCCESS};
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
        """)
        added_label.setMinimumHeight(16)  # Đảm bảo đủ chiều cao
        line2.addWidget(added_label)
        
        # Separator
        sep_label = QLabel("/")
        sep_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
        """)
        line2.addWidget(sep_label)
        
        # -removed (đỏ)
        removed_label = QLabel(f"-{entry.fail_count}")
        removed_label.setStyleSheet(f"""
            color: {ThemeColors.ERROR};
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
        """)
        removed_label.setMinimumHeight(16)  # Đảm bảo đủ chiều cao
        line2.addWidget(removed_label)
        
        line2.addStretch()
        
        line2_widget = QWidget()
        line2_widget.setLayout(line2)
        layout.addWidget(line2_widget)
        
        # States
        is_selected = (self.selected_entry_id == entry.id)
        
        if is_selected:
            widget.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(124, 111, 255, 0.06);
                    border-left: 2px solid {ThemeColors.PRIMARY};
                    border-bottom: 1px solid {ThemeColors.BORDER};
                }}
            """)
        else:
            widget.setStyleSheet(f"""
                QFrame {{
                    background-color: transparent;
                    border-left: 2px solid transparent;
                    border-bottom: 1px solid {ThemeColors.BORDER};
                }}
                QFrame:hover {{
                    background-color: rgba(45, 45, 68, 0.5);
                }}
            """)
        
        return widget
    
    @Slot(QListWidgetItem)
    def _on_entry_clicked(self, item: QListWidgetItem) -> None:
        """Handle khi user click vào một entry."""
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        if not entry_id:
            return
        
        self.selected_entry_id = entry_id
        self._render_entry_list()  # Re-render để update selected state
        
        entry = get_entry_by_id(entry_id)
        if entry:
            self._show_detail(entry)
    
    # ═══════════════════════════════════════════════════════════════
    # INTERNAL - DETAIL PANEL
    # ═══════════════════════════════════════════════════════════════
    
    def _show_empty_detail_state(self) -> None:
        """Hiển thị empty state cho detail panel."""
        self._clear_detail()
        
        empty = QLabel("Chọn một operation bên trái để xem chi tiết")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 14px;
            padding: 48px;
        """)
        self._detail_layout.addWidget(empty)
    
    def _clear_detail(self) -> None:
        """Clear tất cả widgets trong detail panel."""
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item and (widget := item.widget()):
                widget.deleteLater()
    
    def _show_detail(self, entry: HistoryEntry) -> None:
        """Render detail panel cho một entry."""
        self._clear_detail()
        
        # ─────────────────────────────────────────────────────────
        # DETAIL HEADER
        # ─────────────────────────────────────────────────────────
        header_card = self._create_detail_header(entry)
        self._detail_layout.addWidget(header_card)
        
        # ─────────────────────────────────────────────────────────
        # FILES CHANGED SECTION
        # ─────────────────────────────────────────────────────────
        files_section = self._create_files_section(entry)
        self._detail_layout.addWidget(files_section)
        
        # ─────────────────────────────────────────────────────────
        # ERRORS SECTION (nếu có)
        # ─────────────────────────────────────────────────────────
        if entry.error_messages:
            errors_section = self._create_errors_section(entry)
            self._detail_layout.addWidget(errors_section)
        
        self._detail_layout.addStretch()
    
    def _create_detail_header(self, entry: HistoryEntry) -> QWidget:
        """Tạo detail header card."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 10px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Row 1: Entry ID + Timestamp
        row1 = QHBoxLayout()
        
        entry_label = QLabel(f"Entry #{entry.id}")
        entry_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        """)
        row1.addWidget(entry_label)
        
        row1.addStretch()
        
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            time_str = dt.strftime("%m/%d %H:%M:%S")
        except ValueError:
            time_str = entry.timestamp
        
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
        """)
        row1.addWidget(time_label)
        
        row1_widget = QWidget()
        row1_widget.setLayout(row1)
        layout.addWidget(row1_widget)
        
        # Row 2: Progress bar + stats
        progress_widget = self._create_progress_bar(entry)
        layout.addWidget(progress_widget)
        
        # Row 3: Action buttons
        buttons_widget = self._create_action_buttons(entry)
        layout.addWidget(buttons_widget)
        
        return card
    
    def _create_progress_bar(self, entry: HistoryEntry) -> QWidget:
        """Tạo progress bar mỏng 6px với stats."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Progress bar - 6px height
        progress = QProgressBar()
        progress.setFixedHeight(6)
        progress.setTextVisible(False)
        progress.setMinimum(0)
        progress.setMaximum(entry.file_count)
        progress.setValue(entry.success_count)
        
        # Style progress bar
        progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {ThemeColors.BORDER};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {ThemeColors.SUCCESS};
                border-radius: 3px;
            }}
        """)
        
        layout.addWidget(progress)
        
        # Stats text
        if entry.fail_count == 0:
            stats_text = f"{entry.success_count}/{entry.file_count} all successful"
            stats_color = ThemeColors.SUCCESS
        elif entry.success_count == 0:
            stats_text = f"0/{entry.file_count} all failed"
            stats_color = ThemeColors.ERROR
        else:
            stats_text = f"{entry.success_count}/{entry.file_count} successful"
            stats_color = ThemeColors.TEXT_SECONDARY
        
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet(f"""
            color: {stats_color};
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
        """)
        layout.addWidget(stats_label)
        
        return widget
    
    def _create_action_buttons(self, entry: HistoryEntry) -> QWidget:
        """Tạo row action buttons với height 30px."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Copy OPX (ghost)
        copy_btn = QPushButton("Copy OPX")
        copy_btn.setFixedHeight(30)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_HOVER};
                border-color: {ThemeColors.BORDER_LIGHT};
            }}
        """)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: self._copy_opx(entry))
        layout.addWidget(copy_btn)
        
        # Re-apply (primary)
        reapply_btn = QPushButton("Re-apply")
        reapply_btn.setFixedHeight(30)
        reapply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
        """)
        reapply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reapply_btn.clicked.connect(lambda: self._reapply_opx(entry))
        layout.addWidget(reapply_btn)
        
        layout.addStretch()
        
        # Delete (ghost danger)
        delete_btn = QPushButton("Delete")
        delete_btn.setFixedHeight(30)
        delete_btn.setStyleSheet(f"""
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
        """)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self._confirm_delete_entry(entry.id))
        layout.addWidget(delete_btn)
        
        return widget
    
    def _create_files_section(self, entry: HistoryEntry) -> QWidget:
        """Tạo Files Changed section - hiện tất cả hoặc 15 + Show more."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Section header
        header = QLabel(f"Files Changed ({entry.file_count})")
        header.setStyleSheet(f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 700;
        """)
        layout.addWidget(header)
        
        # Files list container
        files_container = QFrame()
        files_container.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(38, 38, 55, 0.6);
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """)
        
        files_layout = QVBoxLayout(files_container)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(0)
        
        # Hiện 15 files đầu tiên
        display_limit = 15
        for i, action_str in enumerate(entry.action_summary[:display_limit]):
            parts = action_str.split(" ", 1)
            op_type = parts[0] if parts else "UNKNOWN"
            filename = parts[1] if len(parts) > 1 else "unknown"
            
            # Determine success
            success = i < entry.success_count
            
            row = FileChangeRow(op_type, filename, success)
            files_layout.addWidget(row)
        
        # Show more button nếu > 15 files
        if len(entry.action_summary) > display_limit:
            more_btn = QPushButton(f"Show {len(entry.action_summary) - display_limit} more files")
            more_btn.setStyleSheet(f"""
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
                }}
            """)
            more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # TODO: Implement expand functionality
            files_layout.addWidget(more_btn)
        
        layout.addWidget(files_container)
        
        return section
    
    def _create_errors_section(self, entry: HistoryEntry) -> QWidget:
        """Tạo Errors section với divider và badge đúng màu."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 16, 0, 0)  # margin-top 16px
        layout.setSpacing(8)
        
        # Divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"background-color: {ThemeColors.BORDER}; max-height: 1px;")
        layout.addWidget(divider)
        
        # Section header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 8, 0, 0)
        
        header_label = QLabel("Errors")
        header_label.setStyleSheet(f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 600;
        """)
        header_layout.addWidget(header_label)
        
        # Badge pill
        count_badge = QLabel(f"({len(entry.error_messages)})")
        count_badge.setStyleSheet(f"""
            color: {ThemeColors.ERROR};
            background-color: rgba(248, 113, 113, 0.15);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        """)
        header_layout.addWidget(count_badge)
        header_layout.addStretch()
        
        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        layout.addWidget(header_widget)
        
        # Error cards (show first 3)
        for i, error_msg in enumerate(entry.error_messages[:3]):
            # Try to extract filename from error message
            if ":" in error_msg:
                parts = error_msg.split(":", 1)
                filename = parts[0].strip()
                msg = parts[1].strip() if len(parts) > 1 else error_msg
            else:
                filename = "Error"
                msg = error_msg
            
            card = ErrorCard(filename, msg)
            layout.addWidget(card)
        
        # Show more button
        if len(entry.error_messages) > 3:
            more_btn = QPushButton(f"Show {len(entry.error_messages) - 3} more...")
            more_btn.setStyleSheet(f"""
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
                }}
            """)
            more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # TODO: Implement expand functionality
            layout.addWidget(more_btn)
        
        return section
    
    # ═══════════════════════════════════════════════════════════════
    # INTERNAL - ACTIONS
    # ═══════════════════════════════════════════════════════════════
    
    def _copy_opx(self, entry: HistoryEntry) -> None:
        """Copy OPX content to clipboard."""
        success, _ = copy_to_clipboard(entry.opx_content)
        if success:
            self._show_footer_message("OPX copied to clipboard!", False)
        else:
            self._show_footer_message("Failed to copy OPX", True)
    
    def _reapply_opx(self, entry: HistoryEntry) -> None:
        """Re-apply OPX content."""
        if self.on_reapply:
            self.on_reapply(entry.opx_content)
            self._show_footer_message("OPX loaded to Apply tab", False)
    
    @Slot()
    def _confirm_delete_entry(self, entry_id: str) -> None:
        """Confirm và delete một entry."""
        reply = QMessageBox.question(
            self,
            "Delete Entry?",
            "Xóa entry này? Không thể undo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_entry(entry_id):
                self.selected_entry_id = None
                self._refresh()
                self._show_empty_detail_state()
                self._show_footer_message("Entry deleted", False)
            else:
                self._show_footer_message("Failed to delete entry", True)
    
    @Slot()
    def _confirm_clear_all(self) -> None:
        """Confirm và clear toàn bộ history."""
        reply = QMessageBox.question(
            self,
            "Clear All History?",
            "Xóa toàn bộ history? Không thể undo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if clear_history():
                self.selected_entry_id = None
                self._refresh()
                self._show_empty_detail_state()
                self._show_footer_message("History cleared", False)
            else:
                self._show_footer_message("Failed to clear history", True)
    
    def _show_footer_message(self, message: str, is_error: bool = False) -> None:
        """Hiển thị message ở footer bar."""
        color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self._footer_label.setStyleSheet(f"""
            color: {color};
            font-size: 11px;
            font-weight: 600;
        """)
        self._footer_label.setText(message)
        
        # Auto-clear sau 4s
        if not is_error:
            QTimer.singleShot(4000, lambda: self._footer_label.setText(""))
