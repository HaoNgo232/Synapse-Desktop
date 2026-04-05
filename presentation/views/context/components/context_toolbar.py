"""
Context Toolbar Component.
Chứa các bộ lọc, selector model/format và thông số token.
"""

import os
import sys
from typing import Optional, List

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QToolButton, QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon

from presentation.config.theme import ThemeColors
from presentation.components.token_usage_bar import TokenUsageBar
from presentation.config.output_format import (
    OUTPUT_FORMATS, OutputStyle, DEFAULT_OUTPUT_STYLE, get_format_config, get_style_by_id
)
from presentation.config.model_config import (
    MODEL_CONFIGS, _format_context_length, get_model_by_id, DEFAULT_MODEL_ID
)
from infrastructure.persistence.settings_manager import load_app_settings


class ContextToolbar(QFrame):
    # Signals
    refresh_requested = Signal()
    clone_repo_requested = Signal()
    manage_cache_requested = Signal()
    related_mode_changed = Signal(bool, int)  # active, depth
    format_changed = Signal(str)
    model_changed = Signal(str)

    def __init__(self, parent: Optional[QFrame] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
            """
        )
        self._build_ui()

    def _get_assets_dir(self) -> str:
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, "assets")
        
        # presentation/views/context/components/context_toolbar.py -> assets/
        return os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "assets"
        ))

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 2)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        assets_dir = self._get_assets_dir()

        modern_btn_style = (
            f"QToolButton {{ "
            f"  background: {ThemeColors.BG_ELEVATED}; border: 1px solid {ThemeColors.BORDER}; "
            f"  border-radius: 6px; padding: 4px 10px; "
            f"  color: {ThemeColors.TEXT_PRIMARY}; font-size: 11px; font-weight: 500; "
            f"}} "
            f"QToolButton:hover {{ "
            f"  background: {ThemeColors.BG_HOVER}; "
            f"}}"
        )

        # ── Refresh Button ──
        refresh_btn = QToolButton()
        refresh_path = os.path.join(assets_dir, "refresh.svg")
        if os.path.exists(refresh_path):
            refresh_btn.setIcon(QIcon(refresh_path))
        refresh_btn.setIconSize(QSize(14, 14))
        refresh_btn.setText(" Reload")
        refresh_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        refresh_btn.setToolTip("Refresh file tree (F5)")
        refresh_btn.setStyleSheet(modern_btn_style)
        refresh_btn.setFixedHeight(30)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(refresh_btn)

        # ── Remote Repos ──
        remote_btn = QToolButton()
        cloud_path = os.path.join(assets_dir, "cloud.png")
        if os.path.exists(cloud_path):
            remote_btn.setIcon(QIcon(cloud_path))
        remote_btn.setIconSize(QSize(14, 14))
        remote_btn.setText(" Remote")
        remote_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        remote_btn.setToolTip("Git Repositories & Cache")
        remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remote_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        remote_btn.setFixedHeight(30)
        arrow_path = os.path.join(assets_dir, "arrow-down.svg").replace("\\", "/")
        remote_btn.setStyleSheet(f"""
            QToolButton {{
                background: {ThemeColors.BG_ELEVATED}; border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px; padding: 4px 10px; padding-right: 20px;
                color: {ThemeColors.TEXT_PRIMARY}; font-size: 11px; font-weight: 500;
            }}
            QToolButton:hover {{ background: {ThemeColors.BG_HOVER}; }}
            QToolButton::menu-indicator {{
                image: url({arrow_path});
                subcontrol-origin: padding; subcontrol-position: center right;
                right: 6px; width: 8px; height: 8px;
            }}
        """)
        remote_menu = QMenu(remote_btn)
        remote_menu.addAction("Clone Repository", self.clone_repo_requested.emit)
        remote_menu.addAction("Manage Cache", self.manage_cache_requested.emit)
        remote_btn.setMenu(remote_menu)
        layout.addWidget(remote_btn)

        # ── Separator ──
        sep_mid = QFrame()
        sep_mid.setFixedWidth(1)
        sep_mid.setFixedHeight(18)
        sep_mid.setStyleSheet(f"background-color: {ThemeColors.BORDER}40;")
        layout.addWidget(sep_mid)

        # ── Related Files Dropdown ──
        self._related_btn = QToolButton()
        layers_path = os.path.join(assets_dir, "layers.svg")
        if os.path.exists(layers_path):
            self._related_btn.setIcon(QIcon(layers_path))
        self._related_btn.setText("Related: Off")
        self._related_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._related_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._related_btn.setIconSize(QSize(14, 14))
        self._related_btn.setFixedHeight(30)
        self._related_btn.setStyleSheet(f"""
            QToolButton {{
                background: {ThemeColors.BG_ELEVATED}; border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px; padding: 4px 10px; padding-right: 20px;
                font-size: 11px; color: {ThemeColors.TEXT_PRIMARY}; font-weight: 500;
            }}
            QToolButton:hover {{ background: {ThemeColors.BG_HOVER}; }}
            QToolButton::menu-indicator {{
                image: url({arrow_path});
                subcontrol-origin: padding; subcontrol-position: center right;
                right: 6px; width: 8px; height: 8px;
            }}
        """)
        self._related_btn.setToolTip("Auto-select related files with depth presets")
        self._related_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        related_menu = QMenu(self._related_btn)
        related_menu.addAction("Off", lambda: self.related_mode_changed.emit(False, 0))
        related_menu.addSeparator()
        related_menu.addAction("Direct imports (1 hop)", lambda: self.related_mode_changed.emit(True, 1))
        related_menu.addAction("Nearby files (2 hops)", lambda: self.related_mode_changed.emit(True, 2))
        related_menu.addAction("Extended chain (3 hops)", lambda: self.related_mode_changed.emit(True, 3))
        related_menu.addAction("Wide discovery (4 hops)", lambda: self.related_mode_changed.emit(True, 4))
        related_menu.addAction("Maximum depth (5 hops)", lambda: self.related_mode_changed.emit(True, 5))
        self._related_btn.setMenu(related_menu)
        layout.addWidget(self._related_btn)

        # ── Separator ──
        sep_preset = QFrame()
        sep_preset.setFixedWidth(1)
        sep_preset.setFixedHeight(18)
        sep_preset.setStyleSheet(f"background-color: {ThemeColors.BORDER}40;")
        layout.addWidget(sep_preset)

        # ── Preset Widget placeholder (will be set from main view) ──
        # Since PresetWidget requires a controller, we'll let ContextView add it to our layout
        self.layout_for_presets = layout

        # ── Right Side stretch ──
        layout.addStretch()

        # ── Output Format ──
        self._format_btn = QToolButton()
        self._format_btn.setFixedHeight(30)
        self._format_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._format_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._format_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                padding-right: 22px;
                font-size: 11px;
                font-weight: 500;
            }}
            QToolButton::menu-indicator {{
                image: url({arrow_path});
                subcontrol-origin: padding; subcontrol-position: center right;
                right: 8px; width: 8px; height: 8px;
            }}
        """)
        
        format_menu = QMenu(self._format_btn)
        for cfg in OUTPUT_FORMATS.values():
            action = format_menu.addAction(cfg.name)
            action.triggered.connect(lambda checked=False, fid=cfg.id: self.format_changed.emit(fid))
        self._format_btn.setMenu(format_menu)
        layout.addWidget(self._format_btn)

        # ── Model Selector ──
        self._model_btn = QToolButton()
        self._model_btn.setFixedHeight(30)
        self._model_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._model_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._model_btn.setStyleSheet(self._format_btn.styleSheet())
        
        model_menu = QMenu(self._model_btn)
        for m in MODEL_CONFIGS:
            label = f"{m.name} ({_format_context_length(m.context_length)})"
            action = model_menu.addAction(label)
            action.triggered.connect(lambda checked=False, mid=m.id: self.model_changed.emit(mid))
        self._model_btn.setMenu(model_menu)
        layout.addWidget(self._model_btn)

        # ── Token Usage Bar ──
        self.token_usage_bar = TokenUsageBar()
        self.token_usage_bar.setFixedWidth(220)
        layout.addWidget(self.token_usage_bar)

        # Initialize labels
        self.update_format_display(load_app_settings().output_format or DEFAULT_OUTPUT_STYLE.value)
        self.update_model_display(load_app_settings().model_id or DEFAULT_MODEL_ID)

    def update_format_display(self, format_id: str) -> None:
        style = get_style_by_id(format_id)
        if style:
            self._format_btn.setText(style.name)

    def update_model_display(self, model_id: str) -> None:
        m_cfg = get_model_by_id(model_id) or get_model_by_id(DEFAULT_MODEL_ID)
        if m_cfg:
            self._model_btn.setText(f"{m_cfg.name} ({_format_context_length(m_cfg.context_length)})")

    def update_related_button_text(self, active: bool, depth: int, count: int) -> None:
        if not active:
            self._related_btn.setText("Related: Off")
            return
        depth_names = {1: "Direct", 2: "Nearby", 3: "Deep", 4: "Deeper", 5: "Deepest"}
        depth_name = depth_names.get(depth, f"{depth} hops")
        text = f"Related: {depth_name}"
        if count > 0:
            text += f" ({count})"
        self._related_btn.setText(text)
