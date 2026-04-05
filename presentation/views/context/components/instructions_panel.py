"""
Instructions Panel Component.
Chứa vùng nhập liệu hướng dẫn và toolbar con (Templates, History, AI Suggest).
"""

from typing import Optional, List

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QMenu, QTextEdit
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from presentation.config.theme import ThemeColors


class InstructionsPanel(QFrame):
    # Signals
    text_changed = Signal(str)
    ai_suggest_requested = Signal()
    template_menu_about_to_show = Signal(QMenu)
    history_menu_about_to_show = Signal(QMenu)
    template_selected = Signal(object)
    history_selected = Signal(object)

    def __init__(self, parent: Optional[QFrame] = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "surface")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

        # Header row
        header = QHBoxLayout()
        instr_label = QLabel("Instructions")
        instr_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(instr_label)

        # Templates Button
        self.template_btn = QToolButton()
        self.template_btn.setText("Templates")
        self.template_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._setup_btn_style(self.template_btn, ThemeColors.PRIMARY)
        self.template_btn.setToolTip("Insert a task-specific prompt template")
        
        self._template_menu = QMenu(self.template_btn)
        self._template_menu.setToolTipsVisible(True)
        self._setup_menu_style(self._template_menu)
        self._template_menu.aboutToShow.connect(lambda: self.template_menu_about_to_show.emit(self._template_menu))
        self._template_menu.triggered.connect(self.template_selected.emit)
        self.template_btn.setMenu(self._template_menu)
        header.addWidget(self.template_btn)

        # History Button
        self.history_btn = QToolButton()
        self.history_btn.setText("History")
        self.history_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._setup_btn_style(self.history_btn, ThemeColors.TEXT_SECONDARY)
        self.history_btn.setToolTip("View recent instructions")
        
        self._history_menu = QMenu(self.history_btn)
        self._setup_menu_style(self._history_menu)
        self._history_menu.aboutToShow.connect(lambda: self.history_menu_about_to_show.emit(self._history_menu))
        self._history_menu.triggered.connect(self.history_selected.emit)
        self.history_btn.setMenu(self._history_menu)
        header.addWidget(self.history_btn)

        # AI Suggest Button
        self.ai_suggest_btn = QToolButton()
        self.ai_suggest_btn.setText("AI Suggest Select")
        self.ai_suggest_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.PRIMARY};
                border: 1px solid {ThemeColors.PRIMARY}50;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QToolButton:hover {{
                background: {ThemeColors.PRIMARY}20;
                border-color: {ThemeColors.PRIMARY};
            }}
            QToolButton:disabled {{
                background: {ThemeColors.BG_SURFACE};
                color: {ThemeColors.TEXT_MUTED};
                border-color: {ThemeColors.BORDER};
            }}
            """
        )
        self.ai_suggest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_suggest_btn.setToolTip("AI reads your instruction and auto-selects relevant files")
        self.ai_suggest_btn.clicked.connect(self.ai_suggest_requested.emit)
        header.addWidget(self.ai_suggest_btn)

        header.addStretch()

        # Word counter
        self._word_count_label = QLabel("0 words")
        self._word_count_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};"
        )
        header.addWidget(self._word_count_label)
        layout.addLayout(header)

        # Textarea
        self.instructions_field = QTextEdit()
        self.instructions_field.setPlaceholderText(
            "Describe your task for the AI...\n\n"
            "Examples:\n"
            "- Refactor the auth module to use JWT tokens\n"
            "- Fix bug: users get 500 error on /api/login\n"
            "- Add rate limiting to all API endpoints"
        )
        self.instructions_field.setStyleSheet(
            f"""
            QTextEdit {{
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 13px;
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
            QTextEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """
        )
        self.instructions_field.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.instructions_field, stretch=1)

    def _setup_btn_style(self, btn, color):
        btn.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent; color: {color};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px; padding: 2px 8px;
                font-size: 11px;
            }}
            QToolButton:hover {{ background: {ThemeColors.BG_HOVER}; }}
            QToolButton::menu-indicator {{ width: 0px; }}
            """
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_menu_style(self, menu):
        menu.setStyleSheet(
            f"""
            QMenu {{
                background: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px; padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 16px; border-radius: 4px;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QMenu::item:selected {{ background: {ThemeColors.BG_HOVER}; }}
            """
        )

    def _on_text_changed(self):
        text = self.instructions_field.toPlainText()
        word_count = len(text.split()) if text.strip() else 0
        self._word_count_label.setText(f"{word_count} words")
        self.text_changed.emit(text)

    def set_text(self, text: str):
        self.instructions_field.setPlainText(text)

    def get_text(self) -> str:
        return self.instructions_field.toPlainText()

    def set_ai_suggest_busy(self, busy: bool):
        if busy:
            self.ai_suggest_btn.setEnabled(False)
            self.ai_suggest_btn.setText("AI Suggesting...")
        else:
            self.ai_suggest_btn.setEnabled(True)
            self.ai_suggest_btn.setText("AI Suggest Select")
