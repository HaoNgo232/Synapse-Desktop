"""
Tag Chips Widget — Visual tag-based editor for excluded patterns.

Features:
- Chips with delete (x) button
- Input field + Add button
- Enter to add
- Duplicate/empty validation
- Wrap layout (FlowLayout)
"""

from typing import List, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QLayout,
    QSizePolicy,
    QLayoutItem,
)
from PySide6.QtCore import Qt, Signal, QRect, QSize, QPoint, QTimer
from PySide6.QtGui import QFont, QIcon

from core.theme import ThemeColors


# Icon paths
ASSETS_DIR = Path(__file__).parent.parent / "assets"
ICON_ADD = str(ASSETS_DIR / "add.svg")
ICON_REMOVE = str(ASSETS_DIR / "remove.svg")


def create_colored_icon(svg_path: str, color: str) -> QIcon:
    """Create a colored icon from SVG by replacing fill/stroke colors."""
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QPixmap, QPainter
    
    # Read SVG content
    with open(svg_path, 'r') as f:
        svg_content = f.read()
    
    # Replace colors (simple approach - replace common attributes)
    svg_content = svg_content.replace('fill="black"', f'fill="{color}"')
    svg_content = svg_content.replace('stroke="black"', f'stroke="{color}"')
    svg_content = svg_content.replace('fill="#000000"', f'fill="{color}"')
    svg_content = svg_content.replace('stroke="#000000"', f'stroke="{color}"')
    
    # If no explicit color, add fill to path elements
    if 'fill=' not in svg_content and '<path' in svg_content:
        svg_content = svg_content.replace('<path', f'<path fill="{color}"')
    
    # Render to pixmap
    renderer = QSvgRenderer(svg_content.encode())
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    
    return QIcon(pixmap)


class FlowLayout(QLayout):
    """Layout that wraps items like flex-wrap."""

    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = spacing

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            wid = item.widget()
            if wid is None:
                continue
            space_x = self._spacing
            space_y = self._spacing
            item_size = item.sizeHint()

            next_x = x + item_size.width() + space_x
            if next_x - space_x > effective.right() + 1 and line_height > 0:
                x = effective.x()
                y = y + line_height + space_y
                next_x = x + item_size.width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y() + m.bottom()


class ChipWidget(QWidget):
    """Single chip with label and delete button."""

    removed = Signal(str)

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 6, 5)
        layout.setSpacing(6)

        label = QLabel(text)
        label.setFont(QFont("Cascadia Code, Fira Code, Consolas", 11))
        label.setStyleSheet(f"color: {ThemeColors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(label)

        close_btn = QPushButton()
        close_btn.setIcon(create_colored_icon(ICON_REMOVE, "white"))
        close_btn.setIconSize(QSize(12, 12))
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 107, 107, 0.2);
                border: none;
                border-radius: 11px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: #FF4757;
            }}
        """)
        close_btn.clicked.connect(lambda: self.removed.emit(self._text))
        layout.addWidget(close_btn)

        self.setFixedHeight(32)
        self._update_style()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._update_style()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._update_style()

    def _update_style(self) -> None:
        if self._hovered:
            self.setStyleSheet(
                f"ChipWidget {{ background: #4A4A6E; border-radius: 8px; border: 1px solid {ThemeColors.PRIMARY}; }}"
            )
        else:
            self.setStyleSheet(
                "ChipWidget { background: #3E3E5E; border-radius: 8px; border: 1px solid #55557A; }"
            )

    @property
    def text(self) -> str:
        return self._text


class TagChipsWidget(QWidget):
    """
    Tag chips editor for excluded patterns.

    Signals:
        patterns_changed(list): Emitted when patterns list changes.
    """

    patterns_changed = Signal(list)

    def __init__(self, patterns: Optional[List[str]] = None, parent=None):
        super().__init__(parent)
        self._patterns: List[str] = list(patterns) if patterns else []
        self._build_ui()
        self._render_chips()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Chips container with flow layout
        self._chips_container = QWidget()
        self._flow_layout = FlowLayout(self._chips_container, spacing=8)
        self._chips_container.setLayout(self._flow_layout)
        layout.addWidget(self._chips_container)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Add pattern...")
        self._input.setFixedHeight(36)
        self._input.setFont(QFont("Cascadia Code, Fira Code, Consolas", 11))
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {ThemeColors.BG_PAGE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 0 12px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        self._input.returnPressed.connect(self._add_from_input)
        input_row.addWidget(self._input, stretch=1)

        add_btn = QPushButton()
        add_btn.setIcon(create_colored_icon(ICON_ADD, "white"))
        add_btn.setIconSize(QSize(18, 18))
        add_btn.setFixedSize(36, 36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ThemeColors.PRIMARY};
                border: none;
                border-radius: 8px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background: {ThemeColors.PRIMARY_PRESSED};
            }}
        """)
        add_btn.clicked.connect(self._add_from_input)
        input_row.addWidget(add_btn)

        layout.addLayout(input_row)

    def _render_chips(self) -> None:
        """Clear and re-render all chips."""
        # Remove old chips
        while self._flow_layout.count():
            item = self._flow_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for pattern in self._patterns:
            chip = ChipWidget(pattern)
            chip.removed.connect(self._remove_pattern)
            self._flow_layout.addWidget(chip)

        # Force layout recalculation
        self._chips_container.updateGeometry()
        self.updateGeometry()

    def _add_from_input(self) -> None:
        text = self._input.text().strip()
        if not text:
            return

        if text in self._patterns:
            # Flash red border for duplicate
            self._input.setStyleSheet(f"""
                QLineEdit {{
                    background: {ThemeColors.BG_PAGE};
                    border: 1px solid {ThemeColors.ERROR};
                    border-radius: 6px;
                    padding: 0 10px;
                    color: {ThemeColors.TEXT_PRIMARY};
                    font-size: 12px;
                }}
            """)
            self._input.setToolTip("Pattern already exists")
            QTimer.singleShot(1500, self._reset_input_style)
            return

        self._patterns.append(text)
        self._input.clear()
        self._render_chips()
        self.patterns_changed.emit(self._patterns.copy())

    def _reset_input_style(self) -> None:
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {ThemeColors.BG_PAGE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 0 10px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        self._input.setToolTip("")

    def _remove_pattern(self, pattern: str) -> None:
        if pattern in self._patterns:
            self._patterns.remove(pattern)
            self._render_chips()
            self.patterns_changed.emit(self._patterns.copy())

    # --- Public API ---

    def get_patterns(self) -> List[str]:
        return self._patterns.copy()

    def set_patterns(self, patterns: List[str]) -> None:
        self._patterns = list(patterns)
        self._render_chips()

    def add_pattern(self, pattern: str) -> bool:
        """Add a pattern. Returns False if duplicate."""
        pattern = pattern.strip()
        if not pattern or pattern in self._patterns:
            return False
        self._patterns.append(pattern)
        self._render_chips()
        self.patterns_changed.emit(self._patterns.copy())
        return True

    def remove_pattern(self, pattern: str) -> bool:
        """Remove a pattern. Returns False if not found."""
        if pattern not in self._patterns:
            return False
        self._patterns.remove(pattern)
        self._render_chips()
        self.patterns_changed.emit(self._patterns.copy())
        return True