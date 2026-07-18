"""
AI Pick Files Dialog - Giao diện hiển thị tiến trình Step-by-Step cho AI Pick Files.
"""

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QWidget,
    QPushButton,
)
from PySide6.QtCore import Qt, QTimer
from presentation.config.theme import ThemeColors, ThemeFonts


class StepRow(QWidget):
    """
    Một hàng đại diện cho một bước trong checklist tiến trình.
    """

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._init_ui(text)

    def _init_ui(self, text: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self.icon_label = QLabel("○")
        self.icon_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-size: 14px; font-weight: bold;"
        )
        self.icon_label.setFixedWidth(20)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text_label = QLabel(text)
        self.text_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED}; font-family: {ThemeFonts.FAMILY_BODY}; font-size: 12px;"
        )
        self.text_label.setWordWrap(True)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1)

    def set_status(self, status: str, detail_text: str = "") -> None:
        if status == "pending":
            self.icon_label.setText("○")
            self.icon_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_MUTED}; font-size: 14px; font-weight: bold;"
            )
            self.text_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_MUTED}; font-family: {ThemeFonts.FAMILY_BODY}; font-size: 12px;"
            )
        elif status == "active":
            self.icon_label.setText("●")
            self.icon_label.setStyleSheet(
                f"color: {ThemeColors.PRIMARY}; font-size: 14px; font-weight: bold;"
            )
            self.text_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_PRIMARY}; font-family: {ThemeFonts.FAMILY_BODY}; font-size: 12px; font-weight: 600;"
            )
            if detail_text:
                self.text_label.setText(detail_text)
        elif status == "success":
            self.icon_label.setText("✓")
            self.icon_label.setStyleSheet(
                f"color: {ThemeColors.SUCCESS}; font-size: 14px; font-weight: bold;"
            )
            self.text_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_SECONDARY}; font-family: {ThemeFonts.FAMILY_BODY}; font-size: 12px;"
            )
            if detail_text:
                self.text_label.setText(detail_text)
        elif status == "error":
            self.icon_label.setText("✗")
            self.icon_label.setStyleSheet(
                f"color: {ThemeColors.ERROR}; font-size: 14px; font-weight: bold;"
            )
            self.text_label.setStyleSheet(
                f"color: {ThemeColors.ERROR}; font-family: {ThemeFonts.FAMILY_BODY}; font-size: 12px; font-weight: 600;"
            )
            if detail_text:
                self.text_label.setText(detail_text)


class AIPickFilesDialog(QDialog):
    """
    Hộp thoại hiển thị tiến trình chọn file của AI.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI File Suggestions")
        self.setFixedSize(380, 270)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER_LIGHT};
                border-radius: 12px;
            }}
        """)

        self.elapsed_seconds = 0
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_time)

        self._build_ui()
        self.timer.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title_label = QLabel("AI File Selection Progress")
        title_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(title_label)

        self.step_container = QVBoxLayout()
        self.step_container.setSpacing(6)

        self.steps = [
            StepRow("Initialize Codex Agent"),
            StepRow("Connect to LLM Provider"),
            StepRow("Explore workspace & find relevant files"),
            StepRow("Synchronize files to UI"),
        ]

        for step in self.steps:
            self.step_container.addWidget(step)

        layout.addLayout(self.step_container)

        # Thin loading bar at the bottom
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Infinite spinner
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {ThemeColors.BORDER}40;
                border: none;
                border-radius: 1px;
            }}
            QProgressBar::chunk {{
                background: {ThemeColors.PRIMARY};
                border-radius: 1px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Footer layout containing timer and cancel button
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)

        self.time_label = QLabel("Elapsed: 0s")
        self.time_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED}; font-family: {ThemeFonts.FAMILY_BODY};"
        )
        footer_layout.addWidget(self.time_label)

        footer_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(72, 28)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER_LIGHT};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.ERROR}20;
                color: {ThemeColors.ERROR};
                border-color: {ThemeColors.ERROR};
            }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        layout.addLayout(footer_layout)

        # Set initial status
        self.current_step_index = 0
        self.update_step(0, "active")
        for i in range(1, len(self.steps)):
            self.update_step(i, "pending")

    def _update_time(self) -> None:
        self.elapsed_seconds += 1
        self.time_label.setText(f"Elapsed: {self.elapsed_seconds}s")

    def update_step(self, index: int, status: str, detail_text: str = "") -> None:
        """Cập nhật trạng thái cho từng bước."""
        if 0 <= index < len(self.steps):
            self.steps[index].set_status(status, detail_text)
            if status == "active":
                self.current_step_index = index

    def show_error(self, error_msg: str) -> None:
        """Hiển thị lỗi tại step đang chạy hiện tại và chuyển progress bar sang màu đỏ."""
        self.timer.stop()
        self.cancel_btn.setEnabled(False)
        
        idx = getattr(self, "current_step_index", 0)
        self.update_step(idx, "error", f"Error: {error_msg}")
        
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background: {ThemeColors.ERROR};
            }}
        """)

    def finish_with_success(self) -> None:
        """Đánh dấu tất cả các bước thành công và đóng Dialog sau 600ms để hiển thị mượt mà."""
        self.timer.stop()
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background: {ThemeColors.SUCCESS};
            }}
        """)
        # Đợi một chút để người dùng thấy hoàn thành
        QTimer.singleShot(600, self, self.accept)

    def reject(self) -> None:
        self.timer.stop()
        super().reject()
