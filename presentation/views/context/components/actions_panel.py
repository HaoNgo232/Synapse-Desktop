"""
Actions Panel Component.
Chứa các nút Copy (Primary, Secondary, Specialized) và các nút gạt Option.
"""

from typing import Optional

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QProgressBar
)
from PySide6.QtCore import Qt, Signal

from presentation.config.theme import ThemeColors
from presentation.components.toggle_switch import ToggleSwitch


class ActionsPanel(QFrame):
    # Signals
    copy_opx_requested = Signal()
    copy_requested = Signal()
    compress_requested = Signal()
    git_diff_requested = Signal()
    tree_map_requested = Signal()
    
    copy_as_file_toggled = Signal(bool)
    full_tree_toggled = Signal(bool)
    semantic_index_toggled = Signal(bool)

    def __init__(self, parent: Optional[QFrame] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent; border: none;")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Title
        panel_title = QLabel("Copy Context")
        panel_title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(panel_title)

        # Warning
        self.limit_warning = QLabel("")
        self.limit_warning.setWordWrap(True)
        self.limit_warning.setStyleSheet(
            f"color: {ThemeColors.ERROR}; font-size: 11px; font-weight: 600;"
        )
        self.limit_warning.hide()
        layout.addWidget(self.limit_warning)

        # ── Buttons ──
        self.opx_btn = QPushButton("Copy + OPX")
        self.opx_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {ThemeColors.PRIMARY}, stop:1 #9F7AEA);
                color: white; border: none;
                border-radius: 12px; padding: 16px;
                font-weight: 800; font-size: 14px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {ThemeColors.PRIMARY_HOVER}, stop:1 #B794F4);
            }}
            QPushButton:pressed {{ background: {ThemeColors.PRIMARY_PRESSED}; }}
            QPushButton:disabled {{ background: {ThemeColors.BG_ELEVATED}; color: {ThemeColors.TEXT_MUTED}; }}
        """)
        self.opx_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.opx_btn.clicked.connect(self.copy_opx_requested.emit)
        layout.addWidget(self.opx_btn)

        self.copy_loading_bar = QProgressBar()
        self.copy_loading_bar.setRange(0, 0)
        self.copy_loading_bar.setFixedHeight(2)
        self.copy_loading_bar.setVisible(False)
        self.copy_loading_bar.setStyleSheet(f"QProgressBar::chunk {{ background: {ThemeColors.PRIMARY}; }}")
        layout.addWidget(self.copy_loading_bar)

        # Quick Actions
        layout.addWidget(self._create_header("QUICK COPY"))
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.copy_btn = self._create_pill_btn("Copy", self.copy_requested)
        self.compress_btn = self._create_pill_btn("Compress", self.compress_requested, color="#2DD4BF", bg="#0D948810")
        row1.addWidget(self.copy_btn)
        row1.addWidget(self.compress_btn)
        layout.addLayout(row1)

        # Specialized
        layout.addWidget(self._create_header("SPECIALIZED"))
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        self.diff_btn = self._create_sub_btn("Git Diff", self.git_diff_requested)
        self.tree_map_btn = self._create_sub_btn("Tree Map", self.tree_map_requested)
        row2.addWidget(self.diff_btn)
        row2.addWidget(self.tree_map_btn)
        layout.addLayout(row2)

        # Options
        layout.addSpacing(8)
        layout.addWidget(self._create_header("OPTIONS"))
        
        self.copy_as_file_toggle = self._add_toggle_row(layout, "Copy as file", self.copy_as_file_toggled)
        self.full_tree_toggle = self._add_toggle_row(layout, "Include full tree", self.full_tree_toggled)
        self.semantic_index_toggle = self._add_toggle_row(layout, "Semantic index", self.semantic_index_toggled)

        layout.addStretch()

    def _create_header(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_MUTED};
            letter-spacing: 1.2px; padding-left: 4px;
        """)
        return lbl

    def _create_pill_btn(self, text, signal, color=ThemeColors.TEXT_PRIMARY, bg=f"{ThemeColors.BG_ELEVATED}40"):
        btn = QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg}; color: {color};
                border: 1px solid {ThemeColors.BORDER}40;
                border-radius: 20px; padding: 10px; font-weight: 600; font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_HOVER}; border-color: {ThemeColors.BORDER};
            }}
        """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(signal.emit)
        return btn

    def _create_sub_btn(self, text, signal):
        btn = QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER}80;
                border-radius: 18px; padding: 8px; font-size: 11px; font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_ELEVATED}40; border-color: {ThemeColors.BORDER};
            }}
        """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(signal.emit)
        return btn

    def _add_toggle_row(self, vertical_layout, text, signal):
        row = QHBoxLayout()
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 11px; color: {ThemeColors.TEXT_SECONDARY}; padding-left: 4px;")
        row.addWidget(lbl)
        row.addStretch()
        toggle = ToggleSwitch(checked=False)
        toggle.toggled.connect(signal.emit)
        row.addWidget(toggle)
        vertical_layout.addLayout(row)
        return toggle

    def set_buttons_enabled(self, enabled: bool):
        self.copy_loading_bar.setVisible(not enabled)
        self.opx_btn.setText("Copy + OPX" if enabled else "Processing...")
        for btn in (self.copy_btn, self.compress_btn, self.diff_btn, self.tree_map_btn, self.opx_btn):
            btn.setEnabled(enabled)

    def show_limit_warning(self, message: str):
        if message:
            self.limit_warning.setText(message)
            self.limit_warning.show()
        else:
            self.limit_warning.hide()
