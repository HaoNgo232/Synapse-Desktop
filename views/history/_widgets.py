"""
views/history/_widgets.py

Cac widget nho tai su dung va ham helper cho HistoryViewQt.

Bao gom:
- Helper functions: create_status_dot_icon, create_search_icon
- Date helpers: format_date_group, group_entries_by_date
- Custom widgets: DateGroupHeader, OperationBadge, FileChangeRow, ErrorCard
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QIcon, QPixmap

from core.theme import ThemeColors
from services.history_service import HistoryEntry


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS - Icon Generation
# ═══════════════════════════════════════════════════════════════


def create_status_dot_icon(color: str, size: int = 12) -> QIcon:
    """Tao icon cham tron (status dot) voi mau cho truoc."""
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
    """Tao icon kinh lup don gian."""
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
    """Format date cho group header: 'Today', 'Yesterday', hoac 'MM/DD'."""
    now = datetime.now()
    today = now.date()
    yesterday = (now - timedelta(days=1)).date()

    entry_date = dt.date()

    if entry_date == today:
        return f"Today · {dt.strftime('%m/%d')}"
    elif entry_date == yesterday:
        return f"Yesterday · {dt.strftime('%m/%d')}"
    else:
        return dt.strftime("%m/%d")


def group_entries_by_date(entries: List[HistoryEntry]) -> Dict[str, List[HistoryEntry]]:
    """Nhom entries theo ngay."""
    groups: Dict[str, List[HistoryEntry]] = {}

    for entry in entries:
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            group_key = format_date_group(dt)

            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(entry)
        except ValueError:
            # Fallback neu timestamp khong parse duoc
            if "Unknown" not in groups:
                groups["Unknown"] = []
            groups["Unknown"].append(entry)

    return groups


# ═══════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ═══════════════════════════════════════════════════════════════


class DateGroupHeader(QWidget):
    """Header phan cach nhom ngay voi line ke ngang."""

    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 8)
        layout.setSpacing(12)

        # Text label
        label = QLabel(text)
        label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.3px;
        """
        )
        layout.addWidget(label)

        # Line phai
        right_line = QFrame()
        right_line.setFrameShape(QFrame.Shape.HLine)
        right_line.setStyleSheet(
            f"background-color: {ThemeColors.BORDER}; max-height: 1px;"
        )
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

        text_color, bg_color = self.COLORS.get(
            op_type.upper(), (ThemeColors.TEXT_SECONDARY, ThemeColors.BG_ELEVATED)
        )

        self.setStyleSheet(
            f"""
            QLabel {{
                color: {text_color};
                background-color: {bg_color};
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 700;
                font-family: 'Cascadia Code', 'Fira Code', monospace;
            }}
        """
        )


class FileChangeRow(QWidget):
    """Row hien thi mot file change voi status dot + operation badge + filename + status."""

    def __init__(
        self,
        op_type: str,
        filename: str,
        success: bool = True,
        parent: Optional[QWidget] = None,
    ):
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
        name_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_PRIMARY};
            font-size: 13px;
            font-family: 'Cascadia Code', 'Fira Code', monospace;
        """
        )
        layout.addWidget(name_label, stretch=1)

        # Status text
        if success:
            status_label = QLabel("done")
            status_label.setStyleSheet(
                f"""
                color: {ThemeColors.SUCCESS};
                font-size: 11px;
                font-weight: 600;
            """
            )
        else:
            status_label = QLabel("failed")
            status_label.setStyleSheet(
                f"""
                color: {ThemeColors.ERROR};
                font-size: 11px;
                font-weight: 600;
            """
            )
        layout.addWidget(status_label)

        self.setStyleSheet(
            """
            FileChangeRow {
                background-color: transparent;
                border-bottom: 1px solid rgba(62, 62, 94, 0.4);
            }
            FileChangeRow:hover {
                background-color: rgba(45, 45, 68, 0.6);
            }
        """
        )


class ErrorCard(QFrame):
    """Card hien thi mot error message voi border-left do."""

    def __init__(self, filename: str, error_msg: str, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Filename (do sang)
        name_label = QLabel(filename)
        name_label.setStyleSheet(
            f"""
            color: {ThemeColors.ERROR};
            font-size: 13px;
            font-weight: 700;
            font-family: 'Cascadia Code', 'Fira Code', monospace;
        """
        )
        layout.addWidget(name_label)

        # Error message (wrap)
        msg_label = QLabel(error_msg)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(
            f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-size: 12px;
            font-family: 'Cascadia Code', 'Fira Code', monospace;
            white-space: pre-wrap;
        """
        )
        layout.addWidget(msg_label)

        self.setStyleSheet(
            f"""
            ErrorCard {{
                background-color: rgba(248, 113, 113, 0.06);
                border-left: 3px solid {ThemeColors.ERROR};
                border-radius: 0 8px 8px 0;
                margin-bottom: 6px;
            }}
        """
        )


def _ghost_button_style() -> str:
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


def _ghost_danger_button_style() -> str:
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


def _primary_button_style() -> str:
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


def make_ghost_btn(text: str, parent: Optional[QWidget] = None) -> QPushButton:
    """Tao QPushButton voi ghost style san."""
    btn = QPushButton(text, parent)
    btn.setStyleSheet(_ghost_button_style())
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def make_danger_btn(text: str, parent: Optional[QWidget] = None) -> QPushButton:
    """Tao QPushButton voi ghost danger style san."""
    btn = QPushButton(text, parent)
    btn.setStyleSheet(_ghost_danger_button_style())
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def make_primary_btn(
    text: str, height: int = 30, parent: Optional[QWidget] = None
) -> QPushButton:
    """Tao QPushButton voi primary style san."""
    btn = QPushButton(text, parent)
    btn.setFixedHeight(height)
    btn.setStyleSheet(_primary_button_style())
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn
