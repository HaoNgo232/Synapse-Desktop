"""
File Tree Delegate - Custom painting cho tree rows.

Renders:
- Checkbox (tri-state)
- File/folder icon (colored)
- File name (with search highlight)
- Token count badge (green)
- Line count badge (blue)

MUCH faster than creating widgets per row —
Qt chỉ gọi paint() cho visible rows.
"""

from PySide6.QtWidgets import (
    QStyledItemDelegate, QStyleOptionViewItem, QStyle, QApplication,
)
from PySide6.QtCore import Qt, QModelIndex, QPersistentModelIndex, QRect, QSize, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QFontMetrics, QIcon, QPainterPath,
)

from core.theme import ThemeColors
from components.file_tree_model import FileTreeRoles


# Row dimensions
ROW_HEIGHT = 28
ICON_SIZE = 16
CHECKBOX_SIZE = 16
BADGE_HEIGHT = 18
BADGE_PADDING_H = 6
BADGE_RADIUS = 4
SPACING = 6

# Colors
COLOR_FOLDER = QColor(ThemeColors.ICON_FOLDER)
COLOR_FILE = QColor(ThemeColors.ICON_FILE)
COLOR_TEXT_PRIMARY = QColor(ThemeColors.TEXT_PRIMARY)
COLOR_TEXT_SECONDARY = QColor(ThemeColors.TEXT_SECONDARY)
COLOR_TEXT_MUTED = QColor(ThemeColors.TEXT_MUTED)
COLOR_PRIMARY = QColor(ThemeColors.PRIMARY)
COLOR_SUCCESS = QColor(ThemeColors.SUCCESS)
COLOR_BORDER = QColor(ThemeColors.BORDER)
COLOR_BG_ELEVATED = QColor(ThemeColors.BG_ELEVATED)
COLOR_CHECKBOX_BG = QColor(ThemeColors.BG_SURFACE)
COLOR_SEARCH_HIGHLIGHT = QColor(ThemeColors.SEARCH_HIGHLIGHT)

# Fonts (lazy initialized)
_font_normal: QFont | None = None
_font_bold: QFont | None = None
_font_mono: QFont | None = None
_font_small: QFont | None = None


def _get_font_normal() -> QFont:
    global _font_normal
    if _font_normal is None:
        _font_normal = QFont()
        _font_normal.setPointSize(10)
    return _font_normal


def _get_font_bold() -> QFont:
    global _font_bold
    if _font_bold is None:
        _font_bold = QFont()
        _font_bold.setPointSize(10)
        _font_bold.setBold(True)
    return _font_bold


def _get_font_mono() -> QFont:
    global _font_mono
    if _font_mono is None:
        _font_mono = QFont("JetBrains Mono, Fira Code, Consolas, monospace")
        _font_mono.setPointSize(9)
    return _font_mono


def _get_font_small() -> QFont:
    global _font_small
    if _font_small is None:
        _font_small = QFont()
        _font_small.setPointSize(8)
    return _font_small


# File extension → icon symbol mapping
_EXT_ICONS: dict[str, str] = {
    '.py': '🐍', '.js': '📜', '.ts': '📘', '.tsx': '⚛',
    '.jsx': '⚛', '.html': '🌐', '.css': '🎨', '.json': '📋',
    '.md': '📝', '.yml': '⚙', '.yaml': '⚙', '.toml': '⚙',
    '.rs': '🦀', '.go': '🐹', '.java': '☕', '.c': '🔧',
    '.cpp': '🔧', '.h': '🔧', '.cs': '💠', '.rb': '💎',
    '.php': '🐘', '.swift': '🐦', '.kt': '🟠', '.sql': '🗄',
    '.sh': '🖥', '.bash': '🖥', '.zsh': '🖥',
    '.txt': '📄', '.log': '📋', '.env': '🔒',
    '.png': '🖼', '.jpg': '🖼', '.svg': '🖼', '.gif': '🖼',
    '.lock': '🔒', '.gitignore': '🚫',
}


def _get_file_icon(label: str, is_dir: bool) -> str:
    """Get icon symbol cho file/folder."""
    if is_dir:
        return "📁"
    
    # Check extension
    for ext, icon in _EXT_ICONS.items():
        if label.endswith(ext):
            return icon
    
    return "📄"  # Default file icon


class FileTreeDelegate(QStyledItemDelegate):
    """
    Custom delegate cho file tree rendering.
    
    Paints mỗi row với: checkbox | icon | label | badges (tokens/lines)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_query: str = ""
    
    def set_search_query(self, query: str) -> None:
        """Set search query để highlight matches."""
        self._search_query = query.lower()
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        rect = option.rect
        is_dir = index.data(FileTreeRoles.IS_DIR_ROLE)
        label = index.data(Qt.ItemDataRole.DisplayRole) or ""
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        token_count = index.data(FileTreeRoles.TOKEN_COUNT_ROLE)
        line_count = index.data(FileTreeRoles.LINE_COUNT_ROLE)
        
        # Draw selection/hover background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, COLOR_BG_ELEVATED)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            hover_color = QColor(COLOR_BG_ELEVATED)
            hover_color.setAlpha(128)
            painter.fillRect(rect, hover_color)
        
        x = rect.x() + SPACING
        y = rect.y()
        height = rect.height()
        center_y = y + (height - CHECKBOX_SIZE) // 2
        
        # 1. Draw checkbox
        self._draw_checkbox(painter, x, center_y, check_state)
        x += CHECKBOX_SIZE + SPACING
        
        # 2. Draw icon
        icon_str = _get_file_icon(label, is_dir or False)
        painter.setFont(_get_font_normal())
        painter.setPen(COLOR_FOLDER if is_dir else COLOR_FILE)
        icon_rect = QRect(x, y, ICON_SIZE + 4, height)
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, icon_str)
        x += ICON_SIZE + SPACING + 2
        
        # 3. Calculate available space for label (excluding badges)
        right_x = rect.right() - SPACING
        badges_width = 0
        
        if token_count is not None and token_count > 0:
            badges_width += self._badge_width(self._format_count(token_count)) + SPACING
        if line_count is not None and line_count > 0:
            badges_width += self._badge_width(f"{line_count}L") + SPACING
        
        label_max_width = right_x - x - badges_width - SPACING
        
        # 4. Draw label (with search highlight)
        painter.setFont(_get_font_bold() if is_dir else _get_font_normal())
        painter.setPen(COLOR_TEXT_PRIMARY)
        
        fm = QFontMetrics(painter.font())
        elided_label = fm.elidedText(label, Qt.TextElideMode.ElideRight, max(label_max_width, 50))
        label_rect = QRect(x, y, int(label_max_width), height)
        
        if self._search_query and self._search_query in label.lower():
            self._draw_highlighted_text(painter, label_rect, elided_label, height)
        else:
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_label)
        
        # 5. Draw badges (right-aligned)
        badge_x = right_x
        
        if line_count is not None and line_count > 0:
            line_text = f"{line_count}L"
            bw = self._badge_width(line_text)
            badge_x -= bw
            self._draw_badge(painter, badge_x, y, bw, height, line_text, COLOR_PRIMARY)
            badge_x -= SPACING
        
        if token_count is not None and token_count > 0:
            token_text = self._format_count(token_count)
            bw = self._badge_width(token_text)
            badge_x -= bw
            self._draw_badge(painter, badge_x, y, bw, height, token_text, COLOR_SUCCESS)
        
        painter.restore()
    
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> QSize:
        return QSize(option.rect.width(), ROW_HEIGHT)
    
    # ===== Private Drawing Methods =====
    
    def _draw_checkbox(self, painter: QPainter, x: int, y: int, state: Qt.CheckState) -> None:
        """Draw checkbox với tri-state support."""
        cb_rect = QRectF(x, y, CHECKBOX_SIZE, CHECKBOX_SIZE)
        
        if state == Qt.CheckState.Checked:
            # Filled checkbox
            path = QPainterPath()
            path.addRoundedRect(cb_rect, 3, 3)
            painter.fillPath(path, COLOR_PRIMARY)
            # Checkmark
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawLine(
                int(x + 4), int(y + CHECKBOX_SIZE // 2),
                int(x + CHECKBOX_SIZE // 2 - 1), int(y + CHECKBOX_SIZE - 5),
            )
            painter.drawLine(
                int(x + CHECKBOX_SIZE // 2 - 1), int(y + CHECKBOX_SIZE - 5),
                int(x + CHECKBOX_SIZE - 4), int(y + 4),
            )
        elif state == Qt.CheckState.PartiallyChecked:
            # Partial fill
            path = QPainterPath()
            path.addRoundedRect(cb_rect, 3, 3)
            painter.fillPath(path, COLOR_PRIMARY.darker(130))
            # Dash
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawLine(
                int(x + 4), int(y + CHECKBOX_SIZE // 2),
                int(x + CHECKBOX_SIZE - 4), int(y + CHECKBOX_SIZE // 2),
            )
        else:
            # Empty checkbox
            painter.setPen(QPen(COLOR_BORDER, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(cb_rect, 3, 3)
    
    def _draw_badge(
        self, painter: QPainter, x: float, y: float,
        width: float, row_height: float,
        text: str, color: QColor,
    ) -> None:
        """Draw badge nhỏ cho token/line count."""
        badge_y = y + (row_height - BADGE_HEIGHT) / 2
        badge_rect = QRectF(x, badge_y, width, BADGE_HEIGHT)
        
        # Background
        bg_color = QColor(color)
        bg_color.setAlpha(30)
        path = QPainterPath()
        path.addRoundedRect(badge_rect, BADGE_RADIUS, BADGE_RADIUS)
        painter.fillPath(path, bg_color)
        
        # Border
        painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 80), 1))
        painter.drawRoundedRect(badge_rect, BADGE_RADIUS, BADGE_RADIUS)
        
        # Text
        painter.setFont(_get_font_small())
        painter.setPen(color)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
    
    def _badge_width(self, text: str) -> int:
        """Tính width cho badge."""
        fm = QFontMetrics(_get_font_small())
        return fm.horizontalAdvance(text) + BADGE_PADDING_H * 2
    
    def _draw_highlighted_text(
        self, painter: QPainter, rect: QRect,
        text: str, row_height: int,
    ) -> None:
        """Draw text với search highlight background."""
        query = self._search_query
        lower_text = text.lower()
        start_idx = lower_text.find(query)
        
        if start_idx < 0:
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            return
        
        fm = QFontMetrics(painter.font())
        
        # Before match
        before = text[:start_idx]
        match = text[start_idx:start_idx + len(query)]
        after = text[start_idx + len(query):]
        
        x = rect.x()
        y = rect.y()
        
        # Draw before text
        if before:
            painter.setPen(COLOR_TEXT_PRIMARY)
            painter.drawText(x, y, rect.width(), row_height, Qt.AlignmentFlag.AlignVCenter, before)
            x += fm.horizontalAdvance(before)
        
        # Draw highlight background
        match_width = fm.horizontalAdvance(match)
        highlight_rect = QRectF(x, y + (row_height - fm.height()) / 2, match_width, fm.height())
        painter.fillRect(highlight_rect, COLOR_SEARCH_HIGHLIGHT)
        
        # Draw match text
        painter.setPen(QColor(ThemeColors.WARNING))
        painter.drawText(int(x), y, int(match_width), row_height, Qt.AlignmentFlag.AlignVCenter, match)
        x += match_width
        
        # Draw after text
        if after:
            painter.setPen(COLOR_TEXT_PRIMARY)
            painter.drawText(int(x), y, rect.right() - int(x), row_height, Qt.AlignmentFlag.AlignVCenter, after)
    
    @staticmethod
    def _format_count(count: int) -> str:
        """Format token count cho display (VD: 1.2k, 45.3k)."""
        if count >= 1000:
            return f"{count / 1000:.1f}k"
        return str(count)
