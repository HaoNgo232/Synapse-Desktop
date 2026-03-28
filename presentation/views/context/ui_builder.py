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
    QComboBox,
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
        toolbar.setFixedHeight(44)
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
        toolbar_layout.setContentsMargins(12, 0, 12, 0)
        toolbar_layout.setSpacing(10)

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
            toolbar_layout.addWidget(self._preset_widget)

        # --- Model Selector & Token Tracker (Right aligned) ---
        toolbar_layout.addStretch()

        # Model Selector (QToolButton + QMenu style - matching Remote/Related)
        from presentation.config.model_config import MODEL_CONFIGS, DEFAULT_MODEL_ID
        from infrastructure.persistence.settings_manager import load_app_settings

        self._model_btn = QToolButton()
        self._model_btn.setFixedHeight(30)
        self._model_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._model_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._model_btn.setStyleSheet(f"""
            QToolButton {{
                background: {ThemeColors.BG_ELEVATED}40; color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER}40; border-radius: 6px;
                padding: 4px 10px; padding-right: 20px;
                font-size: 11px; font-weight: 500;
            }}
            QToolButton:hover {{ background: {ThemeColors.BG_HOVER}; border-color: {ThemeColors.BORDER}; }}
            QToolButton::menu-indicator {{
                image: url({os.path.join(assets_dir, "arrow-down.svg")});
                subcontrol-origin: padding; subcontrol-position: center right;
                right: 6px; width: 8px; height: 8px;
            }}
        """)

        model_menu = QMenu(self._model_btn)
        model_menu.setStyleSheet(
            f"QMenu {{ background: {ThemeColors.BG_ELEVATED}; border: 1px solid {ThemeColors.BORDER}; }}"
        )

        saved_model_id = load_app_settings().model_id or DEFAULT_MODEL_ID
        self._selected_model_id = saved_model_id  # Sync voi view
        current_label = "Select Model"

        for m in MODEL_CONFIGS:
            label = f"{m.name} ({m.context_length // 1000}k)"
            action = model_menu.addAction(label)
            action.setData(m.id)
            if m.id == saved_model_id:
                current_label = label

        self._model_btn.setText(current_label)
        self._model_btn.setMenu(model_menu)
        model_menu.triggered.connect(self._on_model_action_triggered)
        toolbar_layout.addWidget(self._model_btn)

        toolbar_layout.addSpacing(8)

        # Token Usage Bar

        self._token_usage_bar = TokenUsageBar()
        self._token_usage_bar.setFixedWidth(220)
        toolbar_layout.addWidget(self._token_usage_bar)

        return toolbar

    def build_left_panel(self: Any) -> QFrame:
        """Build left panel chi chua header + preset widget + file tree."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 2)
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
        layout.setContentsMargins(12, 8, 12, 2)
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
        self._history_btn.setText("History 🕒")
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

        # Bottom row: format selector
        format_layout = QHBoxLayout()
        format_layout.setSpacing(6)

        format_label = QLabel("Format:")
        format_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {ThemeColors.TEXT_SECONDARY};"
        )
        format_layout.addWidget(format_label)

        self._format_combo = QComboBox()
        self._format_combo.setFixedWidth(140)
        for cfg in OUTPUT_FORMATS.values():
            self._format_combo.addItem(cfg.name, cfg.id)

        # Restore saved format
        saved_format_id = (
            load_app_settings().output_format or DEFAULT_OUTPUT_STYLE.value
        )
        try:
            self._selected_output_style = get_style_by_id(saved_format_id)
            idx = self._format_combo.findData(saved_format_id)
            if idx >= 0:
                self._format_combo.setCurrentIndex(idx)
        except ValueError:
            pass

        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addWidget(self._format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)

        return panel

    def build_actions_panel(self: Any) -> QFrame:
        """Build right panel: Token stats (top) -> Copy buttons -> Status (bottom)."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 2)  # Margins cuc ky thap o bottom
        layout.setSpacing(10)

        # Compact Context Label (Small info area)
        self._context_info_label = QLabel("0 files · 0 tokens")
        self._context_info_label.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY}; font-weight: 500;"
        )
        layout.addWidget(self._context_info_label)

        # Warning Label (Fixed height, no layout jump)
        self._limit_warning = QLabel("")
        self._limit_warning.setWordWrap(True)
        self._limit_warning.setStyleSheet(
            f"color: {ThemeColors.ERROR}; font-size: 11px; font-weight: 600;"
        )
        self._limit_warning.setFixedHeight(30)  # Fixed height to prevent expanding
        self._limit_warning.hide()
        layout.addWidget(self._limit_warning)

        # Action buttons voi visual hierarchy ro rang
        actions = self._build_action_buttons()
        layout.addWidget(actions, 1)  # Cho phep actions widget tu gian theo ti le

        # Footer space: Giu panel phang nhung khong qua trong trai
        layout.addSpacing(10)

        return panel

    def _build_action_buttons(self: Any) -> QWidget:
        """Build copy buttons voi visual hierarchy: CTA -> Secondary -> Tertiary."""
        from PySide6.QtWidgets import QProgressBar

        widget = QWidget()
        widget.setStyleSheet("background-color: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Copy as File toggle (persistent preference) ──
        from presentation.components.toggle_switch import ToggleSwitch

        _file_row = QHBoxLayout()
        _file_row.setSpacing(8)
        _file_row.setContentsMargins(0, 0, 0, 0)

        _file_label = QLabel("Copy as file attachment")
        _file_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {ThemeColors.TEXT_SECONDARY};"
            f" background: transparent; border: none;"
        )
        _file_row.addWidget(_file_label)
        _file_row.addStretch()

        self._copy_as_file_toggle = ToggleSwitch(checked=False)
        self._copy_as_file_toggle.setToolTip(
            "When ON, copies as a file attachment instead of plain text.\n"
            "Web chats (ChatGPT, Claude) receive it as file upload\n"
            "— avoids lag when pasting large context."
        )
        _file_row.addWidget(self._copy_as_file_toggle)
        layout.addLayout(_file_row)

        _file_hint = QLabel("Paste as file upload in web chats to avoid lag")
        _file_hint.setStyleSheet(
            f"font-size: 10px; color: {ThemeColors.TEXT_MUTED};"
            f" background: transparent; border: none;"
        )
        layout.addWidget(_file_hint)

        _toggle_sep = QFrame()
        _toggle_sep.setFixedHeight(1)
        _toggle_sep.setStyleSheet(
            f"background-color: {ThemeColors.BORDER}; border: none;"
        )
        layout.addWidget(_toggle_sep)
        layout.addSpacing(4)

        # Style chung cho secondary buttons (ghost style)
        secondary_style = (
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {ThemeColors.TEXT_PRIMARY};"
            f"  border: 1px solid {ThemeColors.BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 8px 12px;"
            f"  font-weight: 600;"
            f"  font-size: 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {ThemeColors.BG_HOVER};"
            f"  border-color: {ThemeColors.BORDER_LIGHT};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {ThemeColors.BG_ELEVATED};"
            f"}}"
            f"QPushButton:disabled {{"
            f"  color: {ThemeColors.TEXT_MUTED};"
            f"  border-color: {ThemeColors.BG_ELEVATED};"
            f"}}"
        )

        # === PRIMARY CTA: Copy + OPX (Ion nhat, noi bat nhat) ===
        self._opx_btn = QPushButton("Copy + OPX")
        self._opx_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ThemeColors.PRIMARY}; color: white; "
            f"border: none; border-radius: 10px; padding: 14px; font-weight: 700; font-size: 14px; }}"
            f"QPushButton:hover {{ background-color: {ThemeColors.PRIMARY_HOVER}; }}"
            f"QPushButton:pressed {{ background-color: {ThemeColors.PRIMARY_PRESSED}; }}"
        )
        self._opx_btn.setToolTip(
            "Copy full context + OPX patch instructions for AI auto-apply."
        )
        self._opx_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._opx_btn.clicked.connect(
            lambda: self._copy_controller.on_copy_context_requested(include_xml=True)
        )
        layout.addWidget(self._opx_btn)

        # Loading indicator
        self._copy_loading_bar = QProgressBar()
        self._copy_loading_bar.setRange(0, 0)
        self._copy_loading_bar.setFixedHeight(3)
        self._copy_loading_bar.setVisible(False)
        self._copy_loading_bar.setStyleSheet(
            f"QProgressBar {{ border: none; background: transparent; }} QProgressBar::chunk {{ background: {ThemeColors.PRIMARY}; }}"
        )
        layout.addWidget(self._copy_loading_bar)

        layout.addSpacing(8)

        # === SECONDARY GROUP: Context & Smart ===
        sec_row = QHBoxLayout()
        sec_row.setSpacing(8)

        self._copy_btn = QPushButton("Normal Copy")
        self._copy_btn.setStyleSheet(secondary_style)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(
            lambda: self._copy_controller.on_copy_context_requested(include_xml=False)
        )
        sec_row.addWidget(self._copy_btn)

        self._smart_btn = QPushButton("Smart Copy")
        self._smart_btn.setStyleSheet(
            "QPushButton { background-color: #0D948820; color: #2DD4BF; "
            "border: 1px solid #14B8A650; border-radius: 6px; padding: 8px; font-weight: 600; }"
            "QPushButton:hover { background-color: #0D9488; color: white; }"
        )
        self._smart_btn.setToolTip(
            "Copy only code structure (classes, methods) — saves ~80% tokens."
        )
        self._smart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._smart_btn.clicked.connect(self._copy_controller.on_copy_smart_requested)
        sec_row.addWidget(self._smart_btn)

        layout.addLayout(sec_row)
        layout.addSpacing(4)

        # === TERTIARY GROUP: Utils (Compact) ===
        utils_layout = QHBoxLayout()
        utils_layout.setSpacing(8)

        utils_btn_style = (
            f"QPushButton {{ background-color: transparent; color: {ThemeColors.TEXT_SECONDARY}; "
            f"border: 1px solid {ThemeColors.BORDER}; border-radius: 6px; padding: 6px; font-size: 11px; }}"
            f"QPushButton:hover {{ background-color: {ThemeColors.BG_HOVER}; color: {ThemeColors.TEXT_PRIMARY}; }}"
        )

        self._diff_btn = QPushButton("Copy Diff")
        self._diff_btn.setStyleSheet(utils_btn_style)
        self._diff_btn.clicked.connect(self._copy_controller._show_diff_only_dialog)
        utils_layout.addWidget(self._diff_btn)

        self._tree_map_btn = QPushButton("Tree Map")
        self._tree_map_btn.setStyleSheet(utils_btn_style)
        self._tree_map_btn.clicked.connect(
            self._copy_controller.on_copy_tree_map_requested
        )
        utils_layout.addWidget(self._tree_map_btn)

        layout.addLayout(utils_layout)

        layout.addStretch()  # Day toan bo control len tren de giu su nhat quan

        return widget

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
