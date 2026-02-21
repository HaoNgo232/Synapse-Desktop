"""
Token Stats Panel (PySide6) - Hiển thị thống kê tokens với model context warning.

Modern Dashboard Metrics Style.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QProgressBar,
    QFrame,
)
from PySide6.QtCore import Signal, Slot

from core.theme import ThemeColors
from config.model_config import (
    MODEL_CONFIGS,
    DEFAULT_MODEL_ID,
    get_model_by_id,
    ModelConfig,
)
from services.settings_manager import load_app_settings, update_app_setting


class TokenStatsPanelQt(QWidget):
    """
    Token stats panel với progress bar và model selector.

    Features:
    - Card layout
    - Model dropdown
    - Progress bar (color changes by usage level)
    - Stats: usage / total, percentage
    - Warning banner at critical levels
    """

    model_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # State
        self._file_count = 0
        self._file_tokens = 0
        self._instruction_tokens = 0
        self._is_loading = False

        # Load saved model
        saved_model_id = load_app_settings().model_id or DEFAULT_MODEL_ID
        model = get_model_by_id(saved_model_id)
        if not model:
            saved_model_id = DEFAULT_MODEL_ID
            model = get_model_by_id(DEFAULT_MODEL_ID)
        self._selected_model_id = saved_model_id
        self._selected_model: ModelConfig | None = model

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header: "CONTEXT USAGE" + model dropdown
        header = QHBoxLayout()
        title = QLabel("CONTEXT USAGE")
        title.setStyleSheet(
            f"font-size: 11px; font-weight: bold; color: {ThemeColors.TEXT_SECONDARY};"
        )
        header.addWidget(title)
        header.addStretch()

        self._model_combo = QComboBox()
        self._model_combo.setFixedWidth(220)
        self._model_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {ThemeColors.BG_SURFACE};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QComboBox:hover {{
                border-color: {ThemeColors.PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {ThemeColors.BG_SURFACE};
                color: {ThemeColors.TEXT_PRIMARY};
                selection-background-color: {ThemeColors.PRIMARY};
                selection-color: white;
                border: 1px solid {ThemeColors.BORDER};
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 12px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {ThemeColors.PRIMARY}33;
            }}
        """)
        for m in MODEL_CONFIGS:
            label = f"{m.name} ({self._format_context(m.context_length)})"
            self._model_combo.addItem(label, m.id)

        idx = self._model_combo.findData(self._selected_model_id)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        header.addWidget(self._model_combo)
        layout.addLayout(header)

        # Stats row: usage text + percentage
        stats_row = QHBoxLayout()
        self._usage_label = QLabel("0 / 200,000")
        self._usage_label.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {ThemeColors.TEXT_PRIMARY};"
        )
        stats_row.addWidget(self._usage_label)
        stats_row.addStretch()

        self._percentage_label = QLabel("0%")
        self._percentage_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {ThemeColors.TEXT_SECONDARY};"
        )
        stats_row.addWidget(self._percentage_label)
        layout.addLayout(stats_row)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximum(1000)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(10)
        layout.addWidget(self._progress_bar)

        # Details
        self._details_label = QLabel("")
        self._details_label.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};"
        )
        layout.addWidget(self._details_label)

        # Warning banner (hidden by default)
        self._warning_banner = QFrame()
        self._warning_banner.setStyleSheet(
            f"background-color: #450A0A; border: 1px solid {ThemeColors.ERROR}; "
            f"border-radius: 6px; padding: 8px;"
        )
        self._warning_label = QLabel("")
        self._warning_label.setStyleSheet(
            f"color: {ThemeColors.ERROR}; font-size: 12px;"
        )
        warning_layout = QVBoxLayout(self._warning_banner)
        warning_layout.addWidget(self._warning_label)
        self._warning_banner.hide()
        layout.addWidget(self._warning_banner)

        # Style container
        self.setStyleSheet(
            f"TokenStatsPanelQt {{ "
            f"background-color: {ThemeColors.BG_SURFACE}; "
            f"border: 1px solid {ThemeColors.BORDER}; "
            f"border-radius: 8px; }}"
        )

    def update_stats(
        self,
        file_count: int = 0,
        file_tokens: int = 0,
        instruction_tokens: int = 0,
    ) -> None:
        """Update stats display."""
        self._file_count = file_count
        self._file_tokens = file_tokens
        self._instruction_tokens = instruction_tokens

        total = file_tokens + instruction_tokens
        context_length = (
            self._selected_model.context_length if self._selected_model else 200000
        )

        # Update labels
        self._usage_label.setText(f"{total:,} / {context_length:,}")

        percentage = total / context_length if context_length > 0 else 0
        self._percentage_label.setText(f"{percentage:.1%}")

        # Update progress bar (0-1000 range)
        bar_value = min(int(percentage * 1000), 1000)
        self._progress_bar.setValue(bar_value)

        # Color by level
        level = self._get_warning_level(percentage)
        color = self._get_warning_color(level)
        self._progress_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 5px; }}"
            f"QProgressBar {{ background-color: {ThemeColors.BG_SURFACE}; border: none; border-radius: 5px; }}"
        )
        self._percentage_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {color};"
        )

        # Details
        details = f"{file_count} files · {file_tokens:,} file tokens · {instruction_tokens:,} instruction tokens"
        self._details_label.setText(details)

        # Warning banner
        if level == "critical":
            self._warning_banner.show()
            over = total - context_length
            self._warning_label.setText(
                f"⚠ Context exceeds limit by {over:,} tokens! Some content may be truncated."
            )
        elif level == "high":
            self._warning_banner.show()
            remaining = context_length - total
            self._warning_label.setText(
                f"⚠ Approaching context limit. {remaining:,} tokens remaining."
            )
            self._warning_banner.setStyleSheet(
                f"background-color: #422006; border: 1px solid {ThemeColors.WARNING}; "
                f"border-radius: 6px; padding: 8px;"
            )
            self._warning_label.setStyleSheet(
                f"color: {ThemeColors.WARNING}; font-size: 12px;"
            )
        else:
            self._warning_banner.hide()

    def set_loading(self, loading: bool) -> None:
        """Set loading state."""
        self._is_loading = loading

    @Slot(int)
    def _on_model_changed(self, index: int) -> None:
        model_id = self._model_combo.currentData()
        if model_id:
            model = get_model_by_id(model_id)
            if model:
                self._selected_model_id = model_id
                self._selected_model = model
                update_app_setting(model_id=model_id)

                # Reset tokenizer de reload voi model moi qua TokenizationService
                from services.encoder_registry import get_tokenization_service

                get_tokenization_service().reset_encoder()

                # Re-render
                self.update_stats(
                    self._file_count, self._file_tokens, self._instruction_tokens
                )
                self.model_changed.emit(model_id)

    @staticmethod
    def _format_context(length: int) -> str:
        if length >= 1000000:
            return f"{length / 1000000:.0f}M"
        return f"{length / 1000:.0f}k"

    @staticmethod
    def _get_warning_level(percentage: float) -> str:
        if percentage > 1.0:
            return "critical"
        elif percentage >= 0.90:
            return "high"
        elif percentage >= 0.75:
            return "medium"
        return "normal"

    @staticmethod
    def _get_warning_color(level: str) -> str:
        colors = {
            "normal": ThemeColors.PRIMARY,
            "medium": ThemeColors.WARNING,
            "high": "#FF8C00",
            "critical": ThemeColors.ERROR,
        }
        return colors.get(level, ThemeColors.PRIMARY)
