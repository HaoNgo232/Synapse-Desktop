"""
Token Stats Component - Hiển thị thống kê tokens với model context warning

Updated UI: Modern Dashboard Metrics Style
"""

import flet as ft
from dataclasses import dataclass
from typing import List, Optional, Callable

from core.theme import ThemeColors
from config.model_config import (
    MODEL_CONFIGS,
    DEFAULT_MODEL_ID,
    get_model_by_id,
    ModelConfig,
)
from services.settings_manager import get_setting, set_setting


@dataclass
class TokenStats:
    """Thống kê tokens chi tiết"""

    file_count: int = 0
    file_tokens: int = 0
    instruction_tokens: int = 0
    total_tokens: int = 0
    total_with_xml_tokens: int = 0


# Constant cho số token ước tính của OPX XML instructions
OPX_XML_OVERHEAD_TOKENS = 150


@dataclass
class SkippedFile:
    """File bị skip khi tính tokens"""

    path: str
    reason: str  # 'binary', 'too-large', 'error'
    message: Optional[str] = None


def _get_warning_level(percentage: float) -> str:
    """Xác định warning level dựa trên percentage usage."""
    if percentage > 1.0:
        return "critical"
    elif percentage >= 0.90:
        return "high"
    elif percentage >= 0.75:
        return "medium"
    return "normal"


def _get_warning_color(level: str) -> str:
    """Lấy màu tương ứng với warning level"""
    colors = {
        "normal": ThemeColors.PRIMARY,
        "medium": ThemeColors.WARNING,
        "high": "#FF8C00",  # Dark Orange
        "critical": ThemeColors.ERROR,
    }
    return colors.get(level, ThemeColors.PRIMARY)


class TokenStatsPanel:
    """
    Component hiển thị thống kê tokens với giao diện Modern Dashboard Metrics.

    Feature:
    - Card Layout với Padding & Shadow
    - Header: Context Usage & Model Selector
    - Progress Bar: Thicker, Rounded
    - Stats Grid: Metrics (Big) & Details (Small)
    - Warning Banner: Hiển thị khi Critical
    - Preserves selected model in settings
    - PERFORMANCE: Throttled UI updates để tránh spam với project lớn
    """

    def __init__(self, on_model_changed: Optional[Callable[[str], None]] = None):
        self.stats = TokenStats()
        self.skipped_files: List[SkippedFile] = []
        self.is_loading: bool = False
        self.on_model_changed = on_model_changed
        
        # PERFORMANCE: Throttle UI updates - tăng lên cho project lớn
        self._last_ui_update_time: float = 0.0
        self._min_update_interval: float = 0.25  # 250ms minimum between UI updates (tăng từ 100ms)

        # Load saved model or default
        saved_model_id = get_setting("model_id", DEFAULT_MODEL_ID)
        self._selected_model_id = saved_model_id

        # Verify if model exists, if not fallback
        model = get_model_by_id(saved_model_id)
        if not model:
            self._selected_model_id = DEFAULT_MODEL_ID
            self._selected_model = get_model_by_id(DEFAULT_MODEL_ID)
        else:
            self._selected_model = model

        # UI Elements
        self.container: Optional[ft.Container] = None
        self.model_dropdown: Optional[ft.Dropdown] = None

        # Stats Texts
        self.usage_text: Optional[ft.Text] = None
        self.percentage_text: Optional[ft.Text] = None
        self.details_text: Optional[ft.Text] = None

        # Visuals
        self.progress_bar: Optional[ft.ProgressBar] = None
        self.warning_banner: Optional[ft.Container] = None
        self.loading_indicator: Optional[ft.ProgressRing] = None
        self.skipped_column: Optional[ft.Column] = None

    def build(self) -> ft.Container:
        """Build UI component"""

        # 1. Header Row
        self.model_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(
                    key=m.id,
                    text=f"{m.name} ({self._format_context(m.context_length)})",
                )
                for m in MODEL_CONFIGS
            ],
            value=self._selected_model_id,
            on_select=self._on_model_dropdown_changed,
            width=220,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=0),
            border_color="#525252",  # Clearer border for visibility
            focused_border_color=ThemeColors.PRIMARY,
            bgcolor=ThemeColors.BG_SURFACE,
        )

        header_row = ft.Row(
            [
                ft.Text(
                    "CONTEXT USAGE",
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color=ThemeColors.TEXT_SECONDARY,
                ),
                self.model_dropdown,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 2. Main Stats Row (Usage & Percentage)
        self.usage_text = ft.Text(
            "0 / 200,000",
            size=20,
            weight=ft.FontWeight.BOLD,
            color=ThemeColors.TEXT_PRIMARY,
        )

        self.percentage_text = ft.Text(
            "0%",
            size=12,
            weight=ft.FontWeight.W_500,
            color=ThemeColors.TEXT_SECONDARY,
        )

        self.loading_indicator = ft.ProgressRing(
            width=16,
            height=16,
            stroke_width=2,
            color=ThemeColors.PRIMARY,
            visible=False,
        )

        stats_row = ft.Row(
            [
                ft.Row(
                    [self.usage_text, self.loading_indicator],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.percentage_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

        # 3. Progress Bar
        self.progress_bar = ft.ProgressBar(
            value=0,
            bgcolor=ThemeColors.BG_SURFACE,
            color=ThemeColors.PRIMARY,
            height=10,
            border_radius=5,
        )

        # 4. Details Text
        self.details_text = ft.Text(
            "Files: 0 • Instr: 0 • OPX: 150",
            size=11,
            color=ThemeColors.TEXT_SECONDARY,
        )

        # 5. Warning Banner (Hidden by default)
        self.warning_banner = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_ROUNDED, color=ThemeColors.ERROR, size=16),
                    ft.Text(
                        "Context Limit Exceeded!",
                        color=ThemeColors.ERROR,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=5,
            ),
            # Use a safe color way for opacity - direct hex with alpha
            bgcolor="#33" + ThemeColors.ERROR.lstrip("#"),
            padding=5,
            border_radius=4,
            visible=False,
        )

        # 6. Skipped Files Section
        self.skipped_column = ft.Column(visible=False, spacing=2)

        # Main Container
        self.container = ft.Container(
            content=ft.Column(
                [
                    header_row,
                    ft.Container(height=5),  # Spacer
                    stats_row,
                    self.progress_bar,
                    self.details_text,
                    self.warning_banner,
                    self.skipped_column,
                ],
                spacing=8,
            ),
            padding=16,
            bgcolor=ThemeColors.BG_ELEVATED,
            border=ft.border.all(1, ThemeColors.BORDER),
            border_radius=8,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=10,
                color="#1A000000",  # Black with 10% opacity
                offset=ft.Offset(0, 2),
            ),
        )

        return self.container

    def _on_model_dropdown_changed(self, e):
        """Handle model change"""
        if e.control.value:
            self._selected_model_id = e.control.value
            self._selected_model = get_model_by_id(self._selected_model_id)

            # Save to settings
            set_setting("model_id", self._selected_model_id)

            self._refresh_ui()
            if self.on_model_changed:
                self.on_model_changed(self._selected_model_id)

    def _format_context(self, length: int) -> str:
        if length >= 1000000:
            return f"{length // 1000000}M"
        elif length >= 1000:
            return f"{length // 1000}k"
        return str(length)

    def update_stats(
        self,
        file_count: int,
        file_tokens: int,
        instruction_tokens: int,
        xml_overhead: int = OPX_XML_OVERHEAD_TOKENS,
    ):
        """Update statistics"""
        self.stats = TokenStats(
            file_count=file_count,
            file_tokens=file_tokens,
            instruction_tokens=instruction_tokens,
            total_tokens=file_tokens + instruction_tokens,
            total_with_xml_tokens=file_tokens + instruction_tokens + xml_overhead,
        )
        self._refresh_ui()

    def set_skipped_files(self, skipped: List[SkippedFile]):
        self.skipped_files = skipped
        self._refresh_skipped_ui()

    def _refresh_ui(self):
        """Refresh visuals based on data - với throttling để tránh spam"""
        import time
        
        if not self._selected_model:
            return
        
        # PERFORMANCE: Throttle UI updates
        current_time = time.time()
        if current_time - self._last_ui_update_time < self._min_update_interval:
            return  # Skip update nếu chưa đủ thời gian
        self._last_ui_update_time = current_time

        context_limit = self._selected_model.context_length
        total_tokens = self.stats.total_tokens

        # Calculate Logic
        percentage = total_tokens / context_limit if context_limit > 0 else 0
        warning_level = _get_warning_level(percentage)
        warning_color = _get_warning_color(warning_level)

        # Update Value Texts
        if self.usage_text:
            self.usage_text.value = (
                f"{total_tokens:,} / {self._format_context(context_limit)}"
            )
            self.usage_text.color = (
                warning_color if warning_level != "normal" else ThemeColors.TEXT_PRIMARY
            )

        if self.percentage_text:
            self.percentage_text.value = f"{percentage:.1%}"
            self.percentage_text.color = (
                warning_color
                if warning_level != "normal"
                else ThemeColors.TEXT_SECONDARY
            )

        # Update Progress Bar
        if self.progress_bar:
            self.progress_bar.value = min(percentage, 1.0)
            self.progress_bar.color = warning_color

        # Update Details
        if self.details_text:
            self.details_text.value = f"Files: {self.stats.file_count} ({self.stats.file_tokens:,}) • Instr: {self.stats.instruction_tokens:,} • OPX: {self.stats.total_with_xml_tokens - self.stats.total_tokens}"

        # Update Warning Banner
        if self.warning_banner and self.container:
            if warning_level == "critical":
                self.warning_banner.visible = True
                self.container.border = ft.border.all(1, ThemeColors.ERROR)
            else:
                self.warning_banner.visible = False
                self.container.border = ft.border.all(1, ThemeColors.BORDER)

        if self.container and self.container.page:
            self.container.update()

    def set_loading(self, is_loading: bool):
        self.is_loading = is_loading
        if self.loading_indicator:
            self.loading_indicator.visible = is_loading

    def reset(self):
        self.stats = TokenStats()
        self.skipped_files = []
        self._refresh_ui()
        self._refresh_skipped_ui()

    def get_stats(self) -> TokenStats:
        return self.stats

    def get_selected_model(self) -> Optional[ModelConfig]:
        return self._selected_model

    def _refresh_skipped_ui(self):
        """Update skipped files list"""
        if not self.skipped_column:
            return

        self.skipped_column.controls.clear()

        if self.skipped_files:
            self.skipped_column.visible = True

            # Header
            self.skipped_column.controls.append(
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.WARNING_AMBER_ROUNDED,
                            size=12,
                            color=ThemeColors.WARNING,
                        ),
                        ft.Text(
                            f"Skipped {len(self.skipped_files)} files",
                            size=11,
                            color=ThemeColors.WARNING,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    spacing=4,
                )
            )

            # List
            for f in self.skipped_files[:3]:
                self.skipped_column.controls.append(
                    ft.Text(
                        f"• {f.path.split('/')[-1]}: {f.reason}",
                        size=10,
                        color=ThemeColors.TEXT_MUTED,
                    )
                )

            if len(self.skipped_files) > 3:
                self.skipped_column.controls.append(
                    ft.Text(
                        f"...and {len(self.skipped_files)-3} more",
                        size=10,
                        color=ThemeColors.TEXT_MUTED,
                        italic=True,
                    )
                )
        else:
            self.skipped_column.visible = False
