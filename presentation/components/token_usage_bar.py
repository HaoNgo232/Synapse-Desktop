"""
Token Usage Bar - Một component cao cấp hiển thị dung lượng prompt đã dùng.

Thay vì chỉ hiển thị text đơn điệu, component này cung cấp:
- Thanh progress bar trực quan với gradient.
- Thông tin file selection và token count được gom nhóm.
- Cảnh báo khi sắp vượt quá giới hạn.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from presentation.config.theme import ThemeColors


class TokenUsageBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tokens = 0
        self._limit = 200000  # Mặc định cho Claude/GPT-4o
        self._selected_files = 0
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Top row: Stats labels
        stats_layout = QHBoxLayout()

        self._files_label = QLabel("0 selected")
        self._files_label.setStyleSheet(
            f"font-size: 10px; color: {ThemeColors.TEXT_MUTED}; font-weight: 600;"
        )

        self._token_label = QLabel("0 tokens / 200k")
        self._token_label.setStyleSheet(
            f"font-size: 10px; color: {ThemeColors.TEXT_SECONDARY}; font-weight: 700;"
        )

        stats_layout.addWidget(self._files_label)
        stats_layout.addStretch()
        stats_layout.addWidget(self._token_label)

        layout.addLayout(stats_layout)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, self._limit)
        self._progress.setValue(0)
        self._progress.setStyleSheet(self._get_progress_style(ThemeColors.PRIMARY))
        layout.addWidget(self._progress)

    def _get_progress_style(self, chunk_color: str) -> str:
        """Tạo stylesheet cho QProgressBar với màu chunk tùy biến."""
        return f"""
            QProgressBar {{
                background-color: {ThemeColors.BG_PAGE};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                            stop:0 {chunk_color}, 
                                            stop:1 #A78BFA);
                border-radius: 2px;
            }}
        """

    def update_stats(self, tokens: int, limit: int, files: int):
        self._tokens = tokens
        self._limit = max(1, limit)
        self._selected_files = files

        self._files_label.setText(
            f"{files} {'file' if files == 1 else 'files'} selected"
        )
        self._token_label.setText(f"{tokens:,} / {limit // 1000}k tokens")

        self._progress.setRange(0, self._limit)
        self._progress.setValue(min(tokens, self._limit))

        # Đổi màu chunk nếu vượt limit hoặc sắp hết
        usage_pct = (tokens / self._limit) * 100
        chunk_color = ThemeColors.PRIMARY
        if usage_pct > 90:
            chunk_color = ThemeColors.ERROR
        elif usage_pct > 70:
            chunk_color = ThemeColors.WARNING

        # Luôn rebuild stylesheet từ template → đảm bảo đúng màu ở mọi trạng thái
        self._progress.setStyleSheet(self._get_progress_style(chunk_color))
