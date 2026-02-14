"""
DiffViewer Widget (PySide6) - Hiển thị visual diff cho file changes.

Sử dụng QTextEdit với colored blocks thay vì tạo widget mỗi dòng.
Reuse logic từ components/diff_viewer.py.
"""

from typing import List, Optional

from PySide6.QtWidgets import QTextEdit, QWidget, QVBoxLayout
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
from PySide6.QtCore import Qt

from components.diff_viewer import DiffLine, DiffLineType, DiffColors


class DiffViewerWidget(QWidget):
    """
    Widget hiển thị diff content với colored lines.
    
    Sử dụng QTextEdit với formatted blocks —
    hiệu quả hơn tạo widget per-line.
    """
    
    def __init__(
        self,
        diff_lines: Optional[List[DiffLine]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._diff_lines = diff_lines or []
        self._build_ui()
        if self._diff_lines:
            self.set_diff_lines(self._diff_lines)
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont("JetBrains Mono, Fira Code, Consolas", 11))
        self._text_edit.setStyleSheet(
            f"QTextEdit {{ "
            f"background-color: {DiffColors.CONTEXT_BG}; "
            f"border: 1px solid #334155; "
            f"border-radius: 6px; "
            f"padding: 4px; }}"
        )
        layout.addWidget(self._text_edit)
    
    def set_diff_lines(self, diff_lines: List[DiffLine]) -> None:
        """Set diff content."""
        self._diff_lines = diff_lines
        self._render()
    
    def _render(self) -> None:
        """Render diff lines vào QTextEdit."""
        self._text_edit.clear()
        cursor = self._text_edit.textCursor()
        
        for i, line in enumerate(self._diff_lines):
            if i > 0:
                cursor.insertText("\n")
            
            fmt = QTextCharFormat()
            
            # Set background và text color theo line type
            if line.line_type == DiffLineType.ADDED:
                fmt.setBackground(QColor(DiffColors.ADDED_BG))
                fmt.setForeground(QColor(DiffColors.ADDED_TEXT))
            elif line.line_type == DiffLineType.REMOVED:
                fmt.setBackground(QColor(DiffColors.REMOVED_BG))
                fmt.setForeground(QColor(DiffColors.REMOVED_TEXT))
            elif line.line_type == DiffLineType.HEADER:
                fmt.setBackground(QColor(DiffColors.HEADER_BG))
                fmt.setForeground(QColor(DiffColors.HEADER_TEXT))
            else:
                fmt.setForeground(QColor("#94A3B8"))  # Muted text for context
            
            # Line number prefix
            prefix = ""
            if line.line_type == DiffLineType.ADDED and line.new_line_no:
                prefix = f"{line.new_line_no:>4} "
            elif line.line_type == DiffLineType.REMOVED and line.old_line_no:
                prefix = f"{line.old_line_no:>4} "
            elif line.old_line_no and line.new_line_no:
                prefix = f"{line.old_line_no:>4} "
            elif line.line_type == DiffLineType.HEADER:
                prefix = "     "
            else:
                prefix = "     "
            
            # Line number format (dimmer)
            line_no_fmt = QTextCharFormat(fmt)
            line_no_fmt.setForeground(QColor("#64748B"))
            cursor.insertText(prefix, line_no_fmt)
            
            # Content
            cursor.insertText(line.content, fmt)
        
        # Scroll to top
        self._text_edit.moveCursor(QTextCursor.MoveOperation.Start)
