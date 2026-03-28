"""
Edit Patterns Dialog - Cho phép chỉnh sửa danh sách Excluded Patterns dưới dạng text block.

Giải quyết vấn đề khi danh sách quá dài (cục mịch) thì người dùng có thể copy/paste hoặc sửa hàng loạt dễ dàng.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
)
from presentation.config.theme import ThemeColors


class EditPatternsDialog(QDialog):
    """
    Dialog cho phép chỉnh sửa toàn bộ patterns dưới dạng văn bản (mỗi dòng một pattern).
    """

    def __init__(self, patterns: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Excluded Patterns")
        self.setMinimumSize(500, 600)
        self._initial_patterns = patterns
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title & Hint
        title = QLabel("Exclude Patterns (One per line)")
        title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(title)

        hint = QLabel(
            "Enter folder names, file extensions (e.g., *.log), or specific paths to exclude."
        )
        hint.setStyleSheet(f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Text Editor
        self._editor = QPlainTextEdit()
        self._editor.setPlainText("\n".join(self._initial_patterns))
        self._editor.setPlaceholderText("node_modules\n.git\n*.tmp...")
        self._editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {ThemeColors.BG_PAGE};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 10px;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
            }}
            QPlainTextEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """)
        layout.addWidget(self._editor)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(80)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {ThemeColors.TEXT_SECONDARY}; padding: 6px; 
                border: 1px solid {ThemeColors.BORDER}; border-radius: 6px;
            }}
            QPushButton:hover {{ background: {ThemeColors.BG_ELEVATED}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Apply Changes")
        save_btn.setFixedWidth(120)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ThemeColors.PRIMARY}; color: white; padding: 6px; 
                border: none; border-radius: 6px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {ThemeColors.PRIMARY_HOVER}; }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def get_patterns(self) -> list[str]:
        """Lấy danh sách pattern đã chỉnh sửa, loại bỏ các dòng trống."""
        text = self._editor.toPlainText()
        return [p.strip() for p in text.splitlines() if p.strip()]
