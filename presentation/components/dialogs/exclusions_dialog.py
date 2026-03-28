"""
ExclusionsDialog — Minimalist Context-Menu Edition.
- Removed [X] buttons to reduce visual noise.
- Click a row to show actions (Remove).
- Ultra-clean "Pro Max" UI.
"""

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QWidget,
    QFrame,
    QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCursor

from presentation.config.theme import ThemeColors


class PatternRow(QFrame):
    """Một hàng pattern có khả năng phản hồi khi click chuột."""

    def __init__(self, pattern: str, on_remove_callback, parent=None):
        super().__init__(parent)
        self.pattern = pattern
        self.on_remove_callback = on_remove_callback
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("patternRow")
        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame#patternRow {{
                background-color: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER}; 
                border-radius: 6px;
            }}
            QFrame#patternRow:hover {{
                border-color: {ThemeColors.PRIMARY};
                background-color: {ThemeColors.BG_HOVER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)

        label = QLabel(self.pattern)
        label.setStyleSheet(
            "color: white; font-family: 'Cascadia Code', monospace; font-size: 12px; border: none; background: transparent;"
        )
        layout.addWidget(label, 1)

        # Thêm hint nhỏ ở góc (optional) để user biết là có thể click
        hint = QLabel("•••")
        hint.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        layout.addWidget(hint)

    def mousePressEvent(self, event):
        """Xử lý khi click chuột trái để hiện menu actions."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._show_actions_menu()
        else:
            super().mousePressEvent(event)

    def _show_actions_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: white;
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {ThemeColors.BG_HOVER};
                color: {ThemeColors.ERROR};
            }}
        """)

        remove_action = QAction("Remove pattern", self)
        remove_action.triggered.connect(lambda: self.on_remove_callback(self.pattern))
        menu.addAction(remove_action)

        # Hiển thị menu tại vị trí chuột
        menu.exec(QCursor.pos())


class ExclusionsDialog(QDialog):
    """Dialog quản lý exclusions với phong cách Menu tối giản."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Exclusions")
        self.setMinimumWidth(480)
        self.resize(500, 520)
        self.setModal(True)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER_LIGHT};
                border-radius: 12px;
            }}
        """)
        self._build_ui()
        self._load_patterns()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 20)
        main_layout.setSpacing(12)

        # --- Header ---
        title = QLabel("Excluded Patterns")
        title.setStyleSheet(
            "color: white; font-size: 19px; font-weight: 800; border: none;"
        )
        main_layout.addWidget(title)

        desc = QLabel("Hidden from context. Click any row for actions.")
        desc.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 12px; border: none;"
        )
        main_layout.addWidget(desc)

        main_layout.addSpacing(6)

        # --- Add Pattern Area ---
        add_container = QFrame()
        add_container.setStyleSheet(
            f"background: {ThemeColors.BG_ELEVATED}; border: 1px solid {ThemeColors.BORDER}; border-radius: 8px;"
        )
        add_layout = QHBoxLayout(add_container)
        add_layout.setContentsMargins(8, 2, 2, 2)
        add_layout.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Add pattern (e.g. node_modules, dist/)...")
        self._input.setStyleSheet(
            "border: none; background: transparent; color: white; font-size: 13px; min-height: 32px;"
        )
        self._input.returnPressed.connect(self._on_add)
        add_layout.addWidget(self._input, 1)

        add_btn = QPushButton("Add")
        add_btn.setFixedSize(64, 30)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            f"background-color: {ThemeColors.PRIMARY}; color: white; border-radius: 5px; font-weight: 700;"
        )
        add_btn.clicked.connect(self._on_add)
        add_layout.addWidget(add_btn)
        main_layout.addWidget(add_container)

        # --- List Heading ---
        lbl = QLabel("ACTIVE EXCLUSIONS")
        lbl.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-size: 10px; font-weight: 800; margin-top: 10px;"
        )
        main_layout.addWidget(lbl)

        # --- Scrollable List ---
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {ThemeColors.BG_PAGE}; border: 1px solid {ThemeColors.BORDER}; border-radius: 8px; }}"
        )

        self._list_widget = QWidget()
        self._list_widget.setObjectName("listContainer")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_widget)
        main_layout.addWidget(self._scroll, 1)

        # --- Footer ---
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedSize(100, 36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"background-color: {ThemeColors.BG_ELEVATED}; color: white; border: 1px solid {ThemeColors.BORDER_LIGHT}; border-radius: 6px; font-weight: 600;"
        )
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        main_layout.addLayout(footer)

    def _load_patterns(self) -> None:
        from application.services.workspace_config import get_excluded_patterns

        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        patterns = get_excluded_patterns()
        if not patterns:
            empty = QLabel("No active exclusions")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color: {ThemeColors.TEXT_MUTED}; font-size: 13px; margin: 40px;"
            )
            self._list_layout.insertWidget(0, empty)
        else:
            for i, p in enumerate(patterns):
                row = PatternRow(p, self._on_del)
                self._list_layout.insertWidget(i, row)

    def _on_add(self) -> None:
        from application.services.workspace_config import add_excluded_patterns

        text = self._input.text().strip()
        if text and add_excluded_patterns([text]):
            self._input.clear()
            self._load_patterns()

    def _on_del(self, pattern: str) -> None:
        from application.services.workspace_config import remove_excluded_patterns

        if remove_excluded_patterns([pattern]):
            self._load_patterns()
