"""
UI Builder Mixin cho ContextViewQt.

Chua tat ca cac methods xay dung UI components.
"""

import os
from typing import Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QTextEdit,
    QPushButton,
    QToolButton,
    QMenu,
    QSplitter,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from presentation.config.theme import ThemeColors
from presentation.components.file_tree.file_tree_widget import FileTreeWidget
from presentation.config.output_format import (
    OUTPUT_FORMATS,
    get_style_by_id,
    DEFAULT_OUTPUT_STYLE,
)
from infrastructure.persistence.settings_manager import load_app_settings
from presentation.components.token_usage_bar import TokenUsageBar

# Compatibility Alias for UI Tests
TokenStatsPanelQt = TokenUsageBar


class UIBuilderMixin:
    """Mixin chua tat ca UI building methods cho ContextViewQt."""

    def _build_ui(self: Any) -> None:
        """Xay dung UI voi top toolbar + 3-panel splitter (30:40:30)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            0, 0, 0, 0
        )  # Xoa bo moi le thua de panel cham sat status bar
        layout.setSpacing(0)

        # Top toolbar: controls + token counter
        toolbar = self.build_toolbar()
        layout.addWidget(toolbar)

        # Main splitter: files | instructions | actions
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(
            f"""
            QSplitter::handle {{
                background-color: {ThemeColors.BORDER};
                margin: 4px 0;
            }}
            QSplitter::handle:hover {{
                background-color: {ThemeColors.PRIMARY};
            }}
        """
        )

        # Left panel - File tree (~30%)
        left_panel = self.build_left_panel()
        splitter.addWidget(left_panel)

        # Center panel - Instructions (~45%)
        center_panel = self.build_instructions_panel()
        splitter.addWidget(center_panel)

        # Right panel - Actions + Token stats (~25%)
        action_panel = self.build_actions_panel()
        splitter.addWidget(action_panel)

        # Ty le 30:40:30 cho 3 panel de Panel phai (Actions) rong hon
        splitter.setStretchFactor(0, 30)
        splitter.setStretchFactor(1, 40)
        splitter.setStretchFactor(2, 30)
        splitter.setSizes([400, 550, 450])

        layout.addWidget(splitter, 1)

    def build_toolbar(self: Any) -> QFrame:
        """Build top toolbar chua controls va token counter."""
        toolbar = QFrame()
        toolbar.setFixedHeight(48)
        toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.setStyleSheet(
            f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
            }}
        """
        )
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 2, 12, 2)
        toolbar_layout.setSpacing(10)
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        import sys

        if hasattr(sys, "_MEIPASS"):
            assets_dir = os.path.join(sys._MEIPASS, "assets")
        else:
            assets_dir = os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                ),
                "assets",
            )

        # Style cho toolbar buttons (Modern & Minimal)
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

        # Refresh button (Labeled)
        refresh_btn = QToolButton()
        refresh_btn.setIcon(QIcon(os.path.join(assets_dir, "refresh.svg")))
        refresh_btn.setIconSize(QSize(14, 14))
        refresh_btn.setText(" Reload")
        refresh_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        refresh_btn.setToolTip("Refresh file tree (F5)")
        refresh_btn.setStyleSheet(modern_btn_style)
        refresh_btn.setFixedHeight(30)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._tree_controller.refresh_tree)
        toolbar_layout.addWidget(refresh_btn)

        # Remote repos (Labeled)
        remote_btn = QToolButton()
        remote_btn.setIcon(QIcon(os.path.join(assets_dir, "cloud.png")))
        remote_btn.setIconSize(QSize(14, 14))
        remote_btn.setText(" Remote")
        remote_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        remote_btn.setToolTip("Git Repositories & Cache")
        remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remote_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        remote_btn.setFixedHeight(30)
        remote_btn.setStyleSheet(f"""
            QToolButton {{
                background: {ThemeColors.BG_ELEVATED}; border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px; padding: 4px 10px; padding-right: 20px;
                color: {ThemeColors.TEXT_PRIMARY}; font-size: 11px; font-weight: 500;
            }}
            QToolButton:hover {{ background: {ThemeColors.BG_HOVER}; }}
            QToolButton::menu-indicator {{
                image: url({os.path.join(assets_dir, "arrow-down.svg")});
                subcontrol-origin: padding; subcontrol-position: center right;
                right: 6px; width: 8px; height: 8px;
            }}
        """)
        remote_menu = QMenu(remote_btn)
        remote_menu.addAction(
            "Clone Repository",
            lambda: (
                self._tree_controller.open_remote_repo_dialog(self)
                if self._tree_controller
                else None
            ),
        )
        remote_menu.addAction(
            "Manage Cache",
            lambda: (
                self._tree_controller.open_cache_management_dialog(self)
                if self._tree_controller
                else None
            ),
        )
        remote_btn.setMenu(remote_menu)
        toolbar_layout.addWidget(remote_btn)

        # Separator dọc
        sep_mid = QFrame()
        sep_mid.setFixedWidth(1)
        sep_mid.setFixedHeight(18)
        sep_mid.setStyleSheet(f"background-color: {ThemeColors.BORDER}40;")
        toolbar_layout.addWidget(sep_mid)

        # Related files dropdown menu with presets
        self._related_menu_btn = QToolButton()
        self._related_menu_btn.setIcon(QIcon(os.path.join(assets_dir, "layers.svg")))
        self._related_menu_btn.setText("Related: Off")
        self._related_menu_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self._related_menu_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._related_menu_btn.setIconSize(QSize(14, 14))
        self._related_menu_btn.setFixedHeight(30)
        self._related_menu_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: {ThemeColors.BG_ELEVATED}; border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px; padding: 4px 10px; padding-right: 20px;
                font-size: 11px; color: {ThemeColors.TEXT_PRIMARY}; font-weight: 500;
            }}
            QToolButton:hover {{ background: {ThemeColors.BG_HOVER}; }}
            QToolButton::menu-indicator {{
                image: url({os.path.join(assets_dir, "arrow-down.svg")});
                subcontrol-origin: padding; subcontrol-position: center right;
                right: 6px; width: 8px; height: 8px;
            }}
        """
        )
        self._related_menu_btn.setToolTip(
            "Auto-select related files with depth presets"
        )
        self._related_menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Create menu with presets
        related_menu = QMenu(self._related_menu_btn)
        related_menu.setStyleSheet(
            f"""
            QMenu {{
                background: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QMenu::item:selected {{
                background: {ThemeColors.BG_HOVER};
            }}
            QMenu::separator {{
                height: 1px;
                background: {ThemeColors.BORDER};
                margin: 4px 8px;
            }}
        """
        )

        # Menu actions without icons
        off_action = related_menu.addAction("Off — manual selection only")
        related_menu.addSeparator()

        direct_action = related_menu.addAction("Direct imports (1 hop)")
        nearby_action = related_menu.addAction("Nearby files (2 hops)")
        deep_action = related_menu.addAction("Extended chain (3 hops)")
        deeper_action = related_menu.addAction("Wide discovery (4 hops)")
        deepest_action = related_menu.addAction("Maximum depth (5 hops)")

        # Connect actions
        off_action.triggered.connect(
            lambda: (
                self._related_controller.set_mode(False, 0)
                if self._related_controller
                else None
            )
        )
        direct_action.triggered.connect(
            lambda: (
                self._related_controller.set_mode(True, 1)
                if self._related_controller
                else None
            )
        )
        nearby_action.triggered.connect(
            lambda: (
                self._related_controller.set_mode(True, 2)
                if self._related_controller
                else None
            )
        )
        deep_action.triggered.connect(
            lambda: (
                self._related_controller.set_mode(True, 3)
                if self._related_controller
                else None
            )
        )
        deeper_action.triggered.connect(
            lambda: (
                self._related_controller.set_mode(True, 4)
                if self._related_controller
                else None
            )
        )
        deepest_action.triggered.connect(
            lambda: (
                self._related_controller.set_mode(True, 5)
                if self._related_controller
                else None
            )
        )

        self._related_menu_btn.setMenu(related_menu)
        toolbar_layout.addWidget(self._related_menu_btn)

        # Separator dọc sau Related Context
        sep_preset = QFrame()
        sep_preset.setFixedWidth(1)
        sep_preset.setFixedHeight(18)
        sep_preset.setStyleSheet(f"background-color: {ThemeColors.BORDER}40;")
        toolbar_layout.addWidget(sep_preset)

        # === MOVE PRESET WIDGET TO TOOLBAR ===
        from presentation.components.preset_widget import PresetWidget

        _preset_controller = getattr(self, "_preset_controller", None)
        if _preset_controller is not None:
            self._preset_widget = PresetWidget(controller=_preset_controller)
            # Remove title label in Presets to keep toolbar slim
            if hasattr(self._preset_widget, "_label"):
                self._preset_widget._label.hide()
            self._preset_widget.setFixedHeight(30)
            toolbar_layout.addWidget(self._preset_widget)

        # --- Phần phải: Output Format + Model Selector + Token Tracker ---
        toolbar_layout.addStretch()

        # Import sớm để dùng cho cả format combo lẫn model selector
        from infrastructure.persistence.settings_manager import (
            load_app_settings as _load_settings,
        )

        # Output Format Selector (QToolButton + QMenu - đồng nhất với Model Selector)
        self._format_menu = QMenu(self)
        self._format_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                color: {ThemeColors.TEXT_SECONDARY};
            }}
            QMenu::item:selected {{
                background-color: {ThemeColors.PRIMARY}20;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)

        # Đổ dữ liệu format options
        descriptions = {
            "xml": "Phân cấp rõ ràng với tag <file>, <instructions>. Tốt nhất cho các mô hình AI thông minh.",
            "json": "Định dạng JSON chuẩn, dễ dàng để các hệ thống khác parse dữ liệu.",
            "markdown": "Thân thiện với con người, dễ đọc trực tiếp trong chatbot.",
            "text": "Chỉ gồm text thuần túy, không có cấu trúc đặc biệt, tiết kiệm token nhất.",
        }

        for cfg in OUTPUT_FORMATS.values():
            tooltip = descriptions.get(cfg.id, f"Sử dụng định dạng {cfg.name}")
            action = self._format_menu.addAction(cfg.name)
            action.setData(cfg.id)
            action.setToolTip(tooltip)
            # Dùng lambda để truyền fid vào signal
            action.triggered.connect(
                lambda checked=False, fid=cfg.id: self._on_format_changed(fid)
            )

        self._format_btn = QToolButton()
        self._format_btn.setMenu(self._format_menu)
        self._format_btn.setFixedHeight(30)
        self._format_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._format_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._format_btn.setToolTip(
            "Output Format: how the context is structured when copied"
        )
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
            QToolButton:hover {{
                background-color: {ThemeColors.BG_HOVER};
                border-color: {ThemeColors.BORDER_LIGHT};
            }}
            QToolButton::menu-indicator {{
                image: url({os.path.join(assets_dir, "arrow-down.svg")});
                subcontrol-origin: padding;
                subcontrol-position: center right;
                right: 8px;
                width: 8px; height: 8px;
            }}
        """)

        saved_format_id = _load_settings().output_format or DEFAULT_OUTPUT_STYLE.value
        try:
            self._selected_output_style = get_style_by_id(saved_format_id)
            if self._selected_output_style:
                self._format_btn.setText(self._selected_output_style.name)
            else:
                self._format_btn.setText("Format")
        except (ValueError, AttributeError):
            self._format_btn.setText("Format")

        toolbar_layout.addWidget(self._format_btn)

        # Separator dọc mỏng
        sep_right = QFrame()
        sep_right.setFixedWidth(1)
        sep_right.setFixedHeight(18)
        sep_right.setStyleSheet(f"background-color: {ThemeColors.BORDER}40;")
        toolbar_layout.addWidget(sep_right)
        toolbar_layout.addSpacing(4)

        # Model Selector (QToolButton + QMenu style - matching Remote/Related)
        from presentation.config.model_config import (
            MODEL_CONFIGS,
            _format_context_length,
        )

        # Menu chooser
        self._model_menu = QMenu(self)
        self._model_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                color: {ThemeColors.TEXT_SECONDARY};
            }}
            QMenu::item:selected {{
                background-color: {ThemeColors.PRIMARY}20;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
        """)

        for m in MODEL_CONFIGS:
            label = f"{m.name} ({_format_context_length(m.context_length)})"
            action = self._model_menu.addAction(label)
            action.setData(m.id)
            # Dung lambda de truyen mid vao signal
            action.triggered.connect(
                lambda checked=False, mid=m.id: self._on_model_changed(mid)
            )

        self._model_btn = QToolButton()
        self._model_btn.setMenu(self._model_menu)
        self._model_btn.setFixedHeight(30)
        self._model_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._model_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._model_btn.setStyleSheet(f"""
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
            QToolButton:hover {{
                background-color: {ThemeColors.BG_HOVER};
                border-color: {ThemeColors.BORDER_LIGHT};
            }}
            QToolButton::menu-indicator {{
                image: url({os.path.join(assets_dir, "arrow-down.svg")});
                subcontrol-origin: padding;
                subcontrol-position: center right;
                right: 8px;
                width: 8px;
                height: 8px;
            }}
        """)
        toolbar_layout.addWidget(self._model_btn)
        toolbar_layout.addSpacing(8)

        # Cập nhật model hiện tại từ settings và đồng bộ view
        from infrastructure.persistence.settings_manager import load_app_settings
        from presentation.config.model_config import get_model_by_id, DEFAULT_MODEL_ID

        app_settings = load_app_settings()
        saved_model_id = app_settings.model_id or DEFAULT_MODEL_ID
        self._selected_model_id = saved_model_id  # Sync quan trọng cho view

        try:
            m_cfg = get_model_by_id(saved_model_id) or get_model_by_id(DEFAULT_MODEL_ID)
            if m_cfg:
                self._model_btn.setText(
                    f"{m_cfg.name} ({_format_context_length(m_cfg.context_length)})"
                )
            else:
                self._model_btn.setText("Select Model")
        except Exception:
            self._model_btn.setText("Select Model")

        # Token Usage Bar — single source of truth cho token stats
        from presentation.components.token_usage_bar import TokenUsageBar

        self._token_usage_bar = TokenUsageBar()
        self._token_usage_bar.setFixedWidth(220)
        toolbar_layout.addWidget(self._token_usage_bar)

        return toolbar

    def build_left_panel(self: Any) -> QFrame:
        """Build left panel chi chua header + preset widget + file tree."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(6)

        # Header: "Files" title
        header = QHBoxLayout()
        header.setSpacing(6)

        files_label = QLabel("Files")
        files_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(files_label)
        header.addStretch()
        layout.addLayout(header)

        # File tree widget (da co san search bar, select/deselect all)
        # Nhan ignore_engine tu ContextViewQt (hoac fallback sang instance moi)
        _ignore_engine = getattr(self, "_ignore_engine", None)
        if _ignore_engine is None:
            from infrastructure.filesystem.ignore_engine import IgnoreEngine as _IE

            _ignore_engine = _IE()

        _tokenization_service = getattr(self, "_tokenization_service", None)
        if _tokenization_service is None:
            from infrastructure.adapters.encoder_registry import (
                get_tokenization_service,
            )

            _tokenization_service = get_tokenization_service()

        self.file_tree_widget = FileTreeWidget(
            ignore_engine=_ignore_engine,
            tokenization_service=_tokenization_service,
        )
        self.file_tree_widget.selection_changed.connect(self._on_selection_changed)
        self.file_tree_widget.file_preview_requested.connect(self._preview_file)
        self.file_tree_widget.token_counting_done.connect(self._update_token_display)
        # Khi user exclude tu context menu, refresh tree ngay lap tuc
        self.file_tree_widget.exclude_patterns_changed.connect(
            self._tree_controller.refresh_tree
        )

        # Connect NEW preset widget to selection changes
        if hasattr(self, "_preset_widget") and self._preset_widget:
            self._preset_widget.connect_selection_changed(
                self.file_tree_widget.selection_changed
            )

        layout.addWidget(self.file_tree_widget, stretch=1)

        return panel

    def build_instructions_panel(self: Any) -> QFrame:
        """Build center panel voi instructions textarea va format selector."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

        # Header row: title + template selector + word count
        header = QHBoxLayout()
        instr_label = QLabel("Instructions")
        instr_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(instr_label)

        # Add Templates button

        self._template_btn = QToolButton()
        self._template_btn.setText("Templates")
        self._template_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._template_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                color: {ThemeColors.PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QToolButton:hover {{
                background: {ThemeColors.BG_HOVER};
            }}
            QToolButton::menu-indicator {{
                width: 0px;
            }}
            """
        )
        self._template_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._template_btn.setToolTip("Insert a task-specific prompt template")

        self._template_menu = QMenu(self._template_btn)
        # Required for QAction tooltips to show while hovering menu items
        self._template_menu.setToolTipsVisible(True)
        self._template_menu.setStyleSheet(
            f"""
            QMenu {{
                background: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QMenu::item:selected {{
                background: {ThemeColors.BG_HOVER};
            }}
            """
        )

        self._template_menu.aboutToShow.connect(self._populate_template_menu)
        self._template_menu.triggered.connect(self._on_template_selected)

        # Cập nhật text mặc định cho button từ settings

        current_tier = getattr(load_app_settings(), "template_tier", "lite")
        tier_label = "Lite" if current_tier == "lite" else "Pro"
        self._template_btn.setText(f"Templates ({tier_label})")

        self._template_btn.setMenu(self._template_menu)
        header.addWidget(self._template_btn)

        # Add History button
        self._history_btn = QToolButton()
        self._history_btn.setText("History")
        self._history_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._history_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QToolButton:hover {{
                background: {ThemeColors.BG_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QToolButton::menu-indicator {{
                width: 0px;
            }}
            """
        )
        self._history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._history_btn.setToolTip("View recent instructions")

        self._history_menu = QMenu(self._history_btn)
        self._history_menu.setStyleSheet(
            f"""
            QMenu {{
                background: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QMenu::item:selected {{
                background: {ThemeColors.BG_HOVER};
            }}
            QMenu::item:disabled {{
                color: {ThemeColors.TEXT_MUTED};
            }}
            """
        )

        self._history_menu.aboutToShow.connect(self._populate_history_menu)
        self._history_menu.triggered.connect(self._on_history_selected)
        self._history_btn.setMenu(self._history_menu)
        header.addWidget(self._history_btn)

        # AI Suggest Select button: doc instruction va tu dong chon files
        self._ai_suggest_btn = QToolButton()
        self._ai_suggest_btn.setText("AI Suggest Select")
        self._ai_suggest_btn.setStyleSheet(
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
        self._ai_suggest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_suggest_btn.setToolTip(
            "AI reads your instruction and auto-selects relevant files"
        )
        self._ai_suggest_btn.clicked.connect(self._run_ai_suggest_from_instructions)
        header.addWidget(self._ai_suggest_btn)

        header.addStretch()

        # Word/char counter
        self._word_count_label = QLabel("0 words")
        self._word_count_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};"
        )
        header.addWidget(self._word_count_label)
        layout.addLayout(header)

        # Textarea - chiem toan bo khong gian con lai
        self._instructions_field = QTextEdit()
        self._instructions_field.setPlaceholderText(
            "Describe your task for the AI...\n\n"
            "Examples:\n"
            "- Refactor the auth module to use JWT tokens\n"
            "- Fix bug: users get 500 error on /api/login\n"
            "- Add rate limiting to all API endpoints\n\n"
            "Tip: Write your task first, then click 'AI Suggest Select'\n"
            "to auto-pick relevant files from the tree."
        )
        self._instructions_field.setStyleSheet(
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
        self._instructions_field.textChanged.connect(self._on_instructions_changed)
        layout.addWidget(self._instructions_field, stretch=1)

        # Bottom row removed (moved to action panel)
        return panel

    def build_actions_panel(self: Any) -> QFrame:
        """Build right panel: Copy buttons (primary), config toggles, tertiary actions.

        Sau khi redesign:
        - Không còn Stats Card (trùng lặp với toolbar TokenUsageBar)
        - Output Format đã chuyển lên toolbar
        - Hierarchy rõ ràng: Primary CTA -> Secondary -> Tertiary
        """
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── Tiêu đề panel ──
        panel_title = QLabel("Copy Context")
        panel_title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(panel_title)

        # ── Warning label (chỉ hiện khi vượt giới hạn token) ──
        self._limit_warning = QLabel("")
        self._limit_warning.setWordWrap(True)
        self._limit_warning.setStyleSheet(
            f"color: {ThemeColors.ERROR}; font-size: 11px; font-weight: 600;"
        )
        self._limit_warning.hide()
        layout.addWidget(self._limit_warning)

        # ── Compatibility alias: _context_info_label trỏ vào toolbar bar ──
        # Không tạo label trùng lặp, chỉ dùng alias để tránh AttributeError
        self._context_info_label = self._limit_warning  # alias cho backward-compat

        # ── Action buttons với hierarchy rõ ràng ──
        actions = self._build_action_buttons()
        layout.addWidget(actions)

        layout.addStretch()

        return panel

    def _build_action_buttons(self: Any) -> QWidget:
        """Build copy buttons với phong cách Soft Modern UI:
        - Loại bỏ khung vuông (boxy look).
        - Sử dụng bo góc lớn (Pill shape) tạo sự thân thiện.
        - Phân tách bằng không gian thay vì đường kẻ cứng.
        """
        from PySide6.QtWidgets import QProgressBar
        from presentation.components.toggle_switch import ToggleSwitch
        from infrastructure.persistence.settings_manager import update_app_setting

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(18)  # Tăng khoảng cách để tạo sự thoáng đãng

        # ── PHẦN 1: PRIMARY CTA ──
        # Nút OPX được bo góc lớn (12px) và gradient mượt mà
        self._opx_btn = QPushButton("Copy + OPX")
        self._opx_btn.setStyleSheet(f"""
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
        self._opx_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._opx_btn.setToolTip(
            "Sao chép context kèm bộ hướng dẫn (Instruction) giúp AI tạo các bản vá code (Patch) theo định dạng OPX."
        )
        self._opx_btn.clicked.connect(
            lambda: self._copy_controller.on_copy_context_requested(include_xml=True)
        )
        layout.addWidget(self._opx_btn)

        # Loading bar mỏng bên dưới nút chính
        self._copy_loading_bar = QProgressBar()
        self._copy_loading_bar.setRange(0, 0)
        self._copy_loading_bar.setFixedHeight(2)
        self._copy_loading_bar.setVisible(False)
        self._copy_loading_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: {ThemeColors.PRIMARY}; }}"
        )
        layout.addWidget(self._copy_loading_bar)

        # ── PHẦN 2: QUICK ACTIONS (Bỏ khung, dùng header nhẹ) ──
        quick_wrap = QVBoxLayout()
        quick_wrap.setSpacing(10)

        quick_header = QLabel("QUICK COPY")
        quick_header.setStyleSheet(f"""
            font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_MUTED};
            letter-spacing: 1.2px; padding-left: 4px;
        """)
        quick_wrap.addWidget(quick_header)

        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(10)

        btn_style_base = f"""
            QPushButton {{
                background-color: {ThemeColors.BG_ELEVATED}40;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER}40;
                border-radius: 20px; /* Pill shape */
                padding: 10px; font-weight: 600; font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_HOVER};
                border-color: {ThemeColors.BORDER};
            }}
        """

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setStyleSheet(btn_style_base)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setToolTip(
            "Sao chép context theo định dạng đang chọn trên toolbar."
        )
        self._copy_btn.clicked.connect(
            lambda: self._copy_controller.on_copy_context_requested(include_xml=False)
        )
        secondary_row.addWidget(self._copy_btn)

        self._smart_btn = QPushButton("Compress")
        self._smart_btn.setStyleSheet(
            btn_style_base.replace(f"{ThemeColors.TEXT_PRIMARY}", "#2DD4BF").replace(
                f"{ThemeColors.BG_ELEVATED}40", "#0D948810"
            )
        )
        self._smart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._smart_btn.setToolTip(
            "Sao chép cấu trúc code rút gọn (Smart Context) giúp tiết kiệm token đáng kể."
        )
        self._smart_btn.clicked.connect(self._copy_controller.on_copy_smart_requested)
        secondary_row.addWidget(self._smart_btn)

        quick_wrap.addLayout(secondary_row)
        layout.addLayout(quick_wrap)

        # ── PHẦN 3: SPECIALIZED ──
        spec_wrap = QVBoxLayout()
        spec_wrap.setSpacing(10)

        spec_header = QLabel("SPECIALIZED")
        spec_header.setStyleSheet(quick_header.styleSheet())
        spec_wrap.addWidget(spec_header)

        tertiary_row = QHBoxLayout()
        tertiary_row.setSpacing(10)

        sub_btn_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER}80;
                border-radius: 18px;
                padding: 8px; font-size: 11px; font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_ELEVATED}40;
                color: {ThemeColors.TEXT_PRIMARY};
                border-color: {ThemeColors.BORDER};
            }}
        """

        self._diff_btn = QPushButton("Git Diff")
        self._diff_btn.setStyleSheet(sub_btn_style)
        self._diff_btn.setToolTip(
            "Sao chép các thay đổi code dựa trên Git (Commits hoặc file chưa commit) của project."
        )
        self._diff_btn.clicked.connect(self._copy_controller._show_diff_only_dialog)
        tertiary_row.addWidget(self._diff_btn)

        self._tree_map_btn = QPushButton("Tree Map")
        self._tree_map_btn.setStyleSheet(sub_btn_style)
        self._tree_map_btn.setToolTip(
            "Sao chép nhanh toàn bộ sơ đồ cấu trúc thư mục của project."
        )
        self._tree_map_btn.clicked.connect(
            self._copy_controller.on_copy_tree_map_requested
        )
        tertiary_row.addWidget(self._tree_map_btn)

        spec_wrap.addLayout(tertiary_row)
        layout.addLayout(spec_wrap)

        # ── PHẦN 4: OPTIONS (Sử dụng padding thay cho đường kẻ) ──
        layout.addSpacing(8)

        opt_wrap = QVBoxLayout()
        opt_wrap.setSpacing(12)

        opt_header = QLabel("OPTIONS")
        opt_header.setStyleSheet(quick_header.styleSheet())
        opt_wrap.addWidget(opt_header)

        def create_toggle_row(label_text: str, tooltip: str = "") -> tuple:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"font-size: 11px; color: {ThemeColors.TEXT_SECONDARY}; padding-left: 4px;"
            )
            if tooltip:
                lbl.setToolTip(tooltip)
            row.addWidget(lbl)
            row.addStretch()
            toggle = ToggleSwitch(checked=False)
            if tooltip:
                toggle.setToolTip(tooltip)
            row.addWidget(toggle)
            return row, toggle

        _file_row, self._copy_as_file_toggle = create_toggle_row(
            "Copy as file",
            "Lưu context vào một file tạm thời thay vì copy vào clipboard (hữu ích cho context cực lớn).",
        )
        opt_wrap.addLayout(_file_row)

        _tree_row, self._full_tree_toggle = create_toggle_row(
            "Include full tree",
            "Đính kèm toàn bộ cấu trúc thư mục project vào prompt để AI nắm bắt được rõ hơn bức tranh tổng thể.",
        )
        saved_full_tree = load_app_settings().include_full_tree
        self._full_tree_toggle.setChecked(saved_full_tree)
        self._full_tree_toggle.toggled.connect(
            lambda checked: (
                update_app_setting(include_full_tree=checked),
                self._copy_controller._prompt_cache.invalidate_all(),
                self._update_token_display(),
            )
        )
        opt_wrap.addLayout(_tree_row)
        layout.addLayout(opt_wrap)

        return container

    def _on_model_action_triggered(self: Any, action: Any) -> None:
        """Handle model selection from dropdown menu."""
        model_id = action.data()
        if model_id:
            self._selected_model_id = model_id
            self._model_btn.setText(action.text())

            # Persist selection vào settings để survive app restart
            from infrastructure.persistence.settings_manager import update_app_setting

            update_app_setting(model_id=model_id)

            # Trigger logic in ContextViewQt
            self._on_model_changed(model_id)

    def _on_model_changed(self: Any, model_id: str) -> None:
        """Fallback for signal connection."""
        pass

    @property
    def _token_count_label(self: Any) -> QLabel:
        """Compatibility property for old tests."""
        return self._token_usage_bar._token_label

    # --- Compatibility Aliases for tests ---
    def build_ui(self: Any) -> None:
        return self._build_ui()

    def build_context_tab_toolbar(self: Any) -> QFrame:
        return self.build_toolbar()
