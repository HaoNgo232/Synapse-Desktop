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

from typing import cast

from PySide6.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
)
from PySide6.QtCore import Qt, QModelIndex, QPersistentModelIndex, QRect, QSize, QRectF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QFontMetrics,
    QPainterPath,
    QPixmap,
)
import qtawesome as qta

from core.theme import ThemeColors
from components.file_tree_model import FileTreeRoles


# Row dimensions
ROW_HEIGHT = 28
ICON_SIZE = 16
CHECKBOX_SIZE = 16
BADGE_HEIGHT = 18
BADGE_PADDING_H = 6
BADGE_RADIUS = 4
BADGE_Y_OFFSET = 3
BADGE_RIGHT_INSET = 2
SPACING = 6
EYE_ICON_SIZE = 24

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
        _font_normal = QFont("IBM Plex Sans")
        _font_normal.setPointSize(11)
    return _font_normal


def _get_font_bold() -> QFont:
    global _font_bold
    if _font_bold is None:
        _font_bold = QFont("IBM Plex Sans")
        _font_bold.setPointSize(11)
        _font_bold.setWeight(QFont.Weight.Medium)  # Medium thay vì Bold
    return _font_bold


def _get_font_mono() -> QFont:
    global _font_mono
    if _font_mono is None:
        _font_mono = QFont("JetBrains Mono, Fira Code, Consolas, monospace")
        _font_mono.setPointSize(10)
    return _font_mono


def _get_font_small() -> QFont:
    global _font_small
    if _font_small is None:
        _font_small = QFont()
        _font_small.setPointSize(8)
    return _font_small


# File extension -> (mdi_icon_name, color) mapping
# Using Material Design Icons (mdi6) for a professional look
_EXT_ICONS: dict[str, tuple[str, str]] = {
    # Programming Languages
    ".py": ("mdi6.language-python", "#3776AB"),
    ".js": ("mdi6.language-javascript", "#F7DF1E"),
    ".ts": ("mdi6.language-typescript", "#3178C6"),
    ".tsx": ("mdi6.react", "#61DAFB"),  # If fails, will fallback
    ".jsx": ("mdi6.react", "#61DAFB"),
    ".rs": ("mdi6.cog", "#DEA584"),
    ".go": ("mdi6.language-go", "#00ADD8"),
    ".java": ("mdi6.language-java", "#007396"),
    ".c": ("mdi6.language-c", "#A8B9CC"),
    ".cpp": ("mdi6.language-cpp", "#00599C"),
    ".h": ("mdi6.language-cpp", "#00599C"),
    ".cs": ("mdi6.language-csharp", "#239120"),
    ".rb": ("mdi6.language-ruby", "#CC342D"),
    ".php": ("mdi6.language-php", "#777BB4"),
    ".swift": ("mdi6.language-swift", "#F05138"),
    ".kt": ("mdi6.language-kotlin", "#7F52FF"),
    ".sql": ("mdi6.database", "#4479A1"),
    # Web & Config
    ".html": ("mdi6.language-html5", "#E34F26"),
    ".css": ("mdi6.language-css3", "#1572B6"),
    ".json": ("mdi6.code-json", "#CBCB41"),
    ".md": ("mdi6.language-markdown", "#ffffff"),
    ".yml": ("mdi6.cog", "#CB171E"),
    ".yaml": ("mdi6.cog", "#CB171E"),
    ".toml": ("mdi6.cog", "#9C4221"),
    ".xml": ("mdi6.xml", "#ff6600"),
    # Scripts
    ".sh": ("mdi6.bash", "#4EAA25"),
    ".bash": ("mdi6.bash", "#4EAA25"),
    ".zsh": ("mdi6.bash", "#4EAA25"),
    # Media & Docs
    ".txt": ("mdi6.file-document-outline", "#94A3B8"),
    ".log": ("mdi6.file-document-outline", "#94A3B8"),
    ".env": ("mdi6.key-variant", "#FACC15"),
    ".png": ("mdi6.image", "#60A5FA"),
    ".jpg": ("mdi6.image", "#60A5FA"),
    ".svg": ("mdi6.image", "#FB923C"),
    ".gif": ("mdi6.image", "#60A5FA"),
    ".pdf": ("mdi6.file-pdf-box", "#F43F5E"),
    # Lock files
    ".lock": ("mdi6.lock", "#94A3B8"),
    ".gitignore": ("mdi6.git", "#F05032"),
}

# Icon cache to avoid repeated rendering
_icon_cache: dict[str, QPixmap] = {}


def _get_qta_pixmap(name: str, color: QColor, size: int = ICON_SIZE) -> QPixmap:
    cache_key = f"{name}_{color.name()}_{size}"
    if cache_key not in _icon_cache:
        try:
            _icon_cache[cache_key] = qta.icon(name, color=color).pixmap(size, size)
        except Exception:
            # Fallback to a generic file icon if the specific one fails
            try:
                _icon_cache[cache_key] = qta.icon(
                    "mdi6.file-outline", color=color
                ).pixmap(size, size)
            except Exception:
                # Absolute fallback (empty pixmap) to prevent crash
                _icon_cache[cache_key] = QPixmap(size, size)
                _icon_cache[cache_key].fill(Qt.GlobalColor.transparent)

    return _icon_cache[cache_key]


def _draw_file_icon(
    painter: QPainter, x: int, y: int, label: str, is_dir: bool, height: int
):
    """Vẽ icon bằng qtawesome pixmap."""
    if is_dir:
        pixmap = _get_qta_pixmap("mdi6.folder", COLOR_FOLDER)
    else:
        # Check extension for specific icons
        icon_name = "mdi6.file-outline"
        icon_color = COLOR_FILE

        for ext, (name, color) in _EXT_ICONS.items():
            if label.endswith(ext):
                icon_name = name
                icon_color = QColor(color)
                break

        pixmap = _get_qta_pixmap(icon_name, icon_color)

    icon_y = y + (height - ICON_SIZE) // 2
    painter.drawPixmap(x, icon_y, pixmap)


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

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Type narrowing - pyrefly infers option.rect as Ellipsis without this
        rect = cast(QRect, option.rect)
        state = cast(QStyle.StateFlag, option.state)
        is_dir = index.data(FileTreeRoles.IS_DIR_ROLE)
        label = index.data(Qt.ItemDataRole.DisplayRole) or ""
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        token_count = index.data(FileTreeRoles.TOKEN_COUNT_ROLE)
        line_count = index.data(FileTreeRoles.LINE_COUNT_ROLE)

        # Draw selection/hover background
        if state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, COLOR_BG_ELEVATED)
        elif state & QStyle.StateFlag.State_MouseOver:
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

        # 2. Draw icon (Material Design)
        _draw_file_icon(painter, x, y, label, is_dir or False, height)
        x += ICON_SIZE + SPACING

        # 3. Process Badges and Eye Icon widths to determine Label space
        # Badges vung khao sat
        badge_items: list[tuple[str, QColor]] = []
        if token_count is not None and token_count > 0:
            token_text = self._format_count(token_count)
            badge_color = COLOR_PRIMARY if is_dir else COLOR_SUCCESS
            badge_items.append((token_text, badge_color))
        if line_count is not None and line_count > 0:
            badge_items.append((f"{line_count}L", COLOR_PRIMARY))

        badges_total_width = 0
        if badge_items:
            badges_total_width = sum(
                self._badge_width(text) for text, _ in badge_items
            ) + SPACING * (len(badge_items) - 1)

        # Eye icon width (chi cho files)
        eye_reserve = (EYE_ICON_SIZE + SPACING) if not is_dir else 0

        # SPACE CALCULATION
        right_x_limit = rect.right() - BADGE_RIGHT_INSET
        available_for_label_and_eye = (
            right_x_limit - x - (SPACING if badge_items else 0) - badges_total_width
        )

        label_max_width = available_for_label_and_eye - eye_reserve
        label_max_width = max(int(label_max_width), 40)

        # 5. Draw label (with search highlight)
        painter.setFont(_get_font_bold() if is_dir else _get_font_normal())
        painter.setPen(COLOR_TEXT_PRIMARY)

        fm = QFontMetrics(painter.font())
        elided_label = fm.elidedText(
            label, Qt.TextElideMode.ElideRight, label_max_width
        )
        label_width = fm.horizontalAdvance(elided_label)
        label_rect = QRect(x, y, label_width, height)

        if self._search_query and self._search_query in label.lower():
            self._draw_highlighted_text(painter, label_rect, elided_label, height)
        else:
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                elided_label,
            )

        current_x = x + label_width + SPACING

        # 6. Draw Eye icon (chi cho files) - NGAY SAU TEN FILE
        if not is_dir:
            is_hovered = bool(state & QStyle.StateFlag.State_MouseOver)
            eye_color = QColor("#8888AA") if is_hovered else QColor("#444466")
            eye_inner_size = 16  # Nho lai mot chut de hop voi text
            eye_pixmap = _get_qta_pixmap("mdi6.eye-outline", eye_color, eye_inner_size)

            painter.drawPixmap(
                int(current_x + (EYE_ICON_SIZE - eye_inner_size) // 2),
                int(y + (height - eye_inner_size) // 2),
                eye_pixmap,
            )
            current_x += EYE_ICON_SIZE + SPACING

        # 7. Draw badges
        if badge_items:
            # Shift badges neu thieu cho hoac de can doi
            badge_x = current_x
            if badge_x + badges_total_width > right_x_limit:
                badge_x = right_x_limit - badges_total_width

            for text, color in badge_items:
                bw = self._badge_width(text)
                self._draw_badge(painter, badge_x, y, bw, height, text, color)
                badge_x += bw + SPACING

        painter.restore()

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        rect = cast(QRect, option.rect)
        return QSize(rect.width(), ROW_HEIGHT)

    # ===== Hit Testing =====

    def get_hit_zone(self, item_rect: QRect, click_x: int, index: QModelIndex) -> str:
        """Xac dinh vung nao duoc click.

        Phai tinh toan lai y het layout trong paint() vi eye icon hien tai
        nam ngay sau label (dynamic position).
        """
        is_dir = index.data(FileTreeRoles.IS_DIR_ROLE)
        label = index.data(Qt.ItemDataRole.DisplayRole) or ""
        token_count = index.data(FileTreeRoles.TOKEN_COUNT_ROLE)
        line_count = index.data(FileTreeRoles.LINE_COUNT_ROLE)

        x = item_rect.x() + SPACING
        x += CHECKBOX_SIZE + SPACING
        x += ICON_SIZE + SPACING

        # Click vao checkbox/icon zone
        if click_x < x:
            return "checkbox"

        # Tinh toan label_width de biet eye icon bat dau tu dau
        # Logic phai TRUNG KHOP voi paint()
        badge_items_count = 0
        badges_total_width = 0
        if token_count is not None and token_count > 0:
            badges_total_width += self._badge_width(self._format_count(token_count))
            badge_items_count += 1
        if line_count is not None and line_count > 0:
            badges_total_width += self._badge_width(f"{line_count}L")
            badge_items_count += 1
        if badge_items_count > 0:
            badges_total_width += SPACING * (badge_items_count - 1)

        eye_reserve = (EYE_ICON_SIZE + SPACING) if not is_dir else 0
        right_x_limit = item_rect.right() - BADGE_RIGHT_INSET
        available_for_label_and_eye = (
            right_x_limit
            - x
            - (SPACING if badge_items_count > 0 else 0)
            - badges_total_width
        )

        label_max_width = max(int(available_for_label_and_eye - eye_reserve), 40)

        painter_font = _get_font_bold() if is_dir else _get_font_normal()
        fm = QFontMetrics(painter_font)
        elided_label = fm.elidedText(
            label, Qt.TextElideMode.ElideRight, label_max_width
        )
        label_width = fm.horizontalAdvance(elided_label)

        # Eye zone: ngay sau label_width
        if not is_dir:
            eye_start = x + label_width + SPACING
            eye_end = eye_start + EYE_ICON_SIZE
            if eye_start <= click_x < eye_end:
                return "eye"

        return "other"

    # ===== Private Drawing Methods =====

    def _draw_checkbox(
        self, painter: QPainter, x: int, y: int, state: Qt.CheckState
    ) -> None:
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
                int(x + 4),
                int(y + CHECKBOX_SIZE // 2),
                int(x + CHECKBOX_SIZE // 2 - 1),
                int(y + CHECKBOX_SIZE - 5),
            )
            painter.drawLine(
                int(x + CHECKBOX_SIZE // 2 - 1),
                int(y + CHECKBOX_SIZE - 5),
                int(x + CHECKBOX_SIZE - 4),
                int(y + 4),
            )
        elif state == Qt.CheckState.PartiallyChecked:
            # Partial fill
            path = QPainterPath()
            path.addRoundedRect(cb_rect, 3, 3)
            painter.fillPath(path, COLOR_PRIMARY.darker(130))
            # Dash
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawLine(
                int(x + 4),
                int(y + CHECKBOX_SIZE // 2),
                int(x + CHECKBOX_SIZE - 4),
                int(y + CHECKBOX_SIZE // 2),
            )
        else:
            # Empty checkbox — dùng màu sáng hơn để dễ nhìn trên dark bg
            painter.setPen(QPen(QColor("#64748B"), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(cb_rect, 3, 3)

    def _draw_badge(
        self,
        painter: QPainter,
        x: float,
        y: float,
        width: float,
        row_height: float,
        text: str,
        color: QColor,
    ) -> None:
        """Draw badge nhỏ cho token/line count."""
        badge_y = y + (row_height - BADGE_HEIGHT) / 2 + BADGE_Y_OFFSET
        badge_rect = QRectF(x, badge_y, width, BADGE_HEIGHT)

        # Background — tăng alpha để dễ đọc hơn trên dark bg
        bg_color = QColor(color)
        bg_color.setAlpha(90)
        path = QPainterPath()
        path.addRoundedRect(badge_rect, BADGE_RADIUS, BADGE_RADIUS)
        painter.fillPath(path, bg_color)

        # Border — tăng alpha cho rõ hơn
        painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 200), 1))
        painter.drawRoundedRect(badge_rect, BADGE_RADIUS, BADGE_RADIUS)

        # Text
        painter.setFont(_get_font_small())
        text_color = QColor(color).lighter(160)
        painter.setPen(text_color)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _badge_width(self, text: str) -> int:
        """Tính width cho badge."""
        fm = QFontMetrics(_get_font_small())
        return fm.horizontalAdvance(text) + BADGE_PADDING_H * 2

    def _draw_highlighted_text(
        self,
        painter: QPainter,
        rect: QRect,
        text: str,
        row_height: int,
    ) -> None:
        """Draw text với search highlight background."""
        query = self._search_query
        lower_text = text.lower()
        start_idx = lower_text.find(query)

        if start_idx < 0:
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text
            )
            return

        fm = QFontMetrics(painter.font())

        # Before match
        before = text[:start_idx]
        match = text[start_idx : start_idx + len(query)]
        after = text[start_idx + len(query) :]

        x = rect.x()
        y = rect.y()

        # Draw before text
        if before:
            painter.setPen(COLOR_TEXT_PRIMARY)
            painter.drawText(
                x, y, rect.width(), row_height, Qt.AlignmentFlag.AlignVCenter, before
            )
            x += fm.horizontalAdvance(before)

        # Draw highlight background
        match_width = fm.horizontalAdvance(match)
        highlight_rect = QRectF(
            x, y + (row_height - fm.height()) / 2, match_width, fm.height()
        )
        painter.fillRect(highlight_rect, COLOR_SEARCH_HIGHLIGHT)

        # Draw match text
        painter.setPen(QColor(ThemeColors.WARNING))
        painter.drawText(
            int(x),
            y,
            int(match_width),
            row_height,
            Qt.AlignmentFlag.AlignVCenter,
            match,
        )
        x += match_width

        # Draw after text
        if after:
            painter.setPen(COLOR_TEXT_PRIMARY)
            painter.drawText(
                int(x),
                y,
                rect.right() - int(x),
                row_height,
                Qt.AlignmentFlag.AlignVCenter,
                after,
            )

    @staticmethod
    def _format_count(count: int) -> str:
        """Format token count cho display (VD: 1.2k, 45.3k)."""
        if count >= 1000:
            return f"{count / 1000:.1f}k"
        return str(count)
