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
    QStackedWidget,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from presentation.config.theme import ThemeColors, ThemeFonts
from presentation.components.file_tree.file_tree_widget import FileTreeWidget
from presentation.components.qt_utils import create_colored_icon
from domain.config.output_format import (
    OUTPUT_FORMATS,
    get_style_by_id,
    DEFAULT_OUTPUT_STYLE,
)
from domain.ports.registry import DomainRegistry
from presentation.components.token_usage_bar import TokenUsageBar
import logging

logger = logging.getLogger("synapse-desktop")


# Compatibility Alias for UI Tests
TokenStatsPanelQt = TokenUsageBar


def load_app_settings() -> Any:
    return DomainRegistry.settings()


def update_app_setting(**kwargs: Any) -> bool:
    svc = DomainRegistry.settings_service()
    for k, v in kwargs.items():
        svc.update_setting(k, v)
    return True


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

        from shared.utils.path_utils import get_assets_dir

        assets_dir = str(get_assets_dir())
        arrow_down_url = os.path.join(assets_dir, "arrow-down.svg").replace("\\", "/")

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
        refresh_btn.setIcon(
            create_colored_icon(
                os.path.join(assets_dir, "refresh.svg"), ThemeColors.TEXT_PRIMARY
            )
        )
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
                image: url({arrow_down_url});
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
        self._related_menu_btn.setIcon(
            create_colored_icon(
                os.path.join(assets_dir, "layers.svg"), ThemeColors.TEXT_PRIMARY
            )
        )
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
                image: url({arrow_down_url});
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

        # Dung DomainRegistry thay vi load_app_settings
        _load_settings = DomainRegistry.settings

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
            "xml": "Clear hierarchy with <file> and <instructions> tags. Best for smart AI models.",
            "json": "Standard JSON format, easy for other systems to parse data.",
            "markdown": "Human-friendly, easy to read directly in a chatbot.",
            "text": "Plain text only, no special structure, most token-efficient.",
        }

        for cfg in OUTPUT_FORMATS.values():
            tooltip = descriptions.get(cfg.id, f"Use format {cfg.name}")
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
                image: url({arrow_down_url});
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
            pass  # intentionally silent — format not found or settings not initialized
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
        from domain.config.model_config import (
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
            # Connect to handler that updates UI and triggers recount
            action.triggered.connect(
                lambda checked=False, a=action: self._on_model_action_triggered(a)
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
                image: url({arrow_down_url});
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
        from domain.config.model_config import get_model_by_id, DEFAULT_MODEL_ID

        app_settings = DomainRegistry.settings()
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
            logger.error("ui_builder: UI construction failed", exc_info=True)
            self._model_btn.setText("Select Model")

        # Token Usage Bar — single source of truth cho token stats
        from presentation.components.token_usage_bar import TokenUsageBar

        self._token_usage_bar = TokenUsageBar()
        self._token_usage_bar.setMinimumWidth(380)
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
            _ignore_engine = DomainRegistry.ignore_engine()

        _tokenization_service = getattr(self, "_tokenization_service", None)
        if _tokenization_service is None:
            _tokenization_service = DomainRegistry.tokenization_service()

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

        # ── Stacked widget for switching between file tree and empty state ──
        self._left_stacked_widget = QStackedWidget()
        self._left_stacked_widget.addWidget(self.file_tree_widget)

        # Build beautiful empty state widget
        empty_state = QFrame()
        empty_state.setStyleSheet("background: transparent;")
        empty_layout = QVBoxLayout(empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(16)
        empty_layout.setContentsMargins(20, 40, 20, 40)

        # Folder Icon with styling
        icon_label = QLabel()
        from shared.utils.path_utils import get_assets_dir

        assets_dir = str(get_assets_dir())
        icon_folder = create_colored_icon(
            os.path.join(assets_dir, "folder.svg"), ThemeColors.TEXT_MUTED
        )
        icon_label.setPixmap(icon_folder.pixmap(QSize(48, 48)))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon_label)

        # Title
        title_label = QLabel("No Folder Opened")
        title_label.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {ThemeColors.TEXT_SECONDARY};"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "Open a workspace folder to scan and select files for AI context."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.TEXT_MUTED}; line-height: 1.4;"
        )
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(desc_label)

        # Spacer
        empty_layout.addSpacing(4)

        # Open Folder Button
        self._empty_open_btn = QPushButton(" Open Folder")
        self._empty_open_btn.setIcon(
            create_colored_icon(os.path.join(assets_dir, "folder.svg"), "#FFFFFF")
        )
        self._empty_open_btn.setIconSize(QSize(14, 14))
        self._empty_open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._empty_open_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
        """)
        self._empty_open_btn.clicked.connect(self._on_empty_open_clicked)
        empty_layout.addWidget(self._empty_open_btn)

        self._left_stacked_widget.addWidget(empty_state)

        # Set default active widget based on workspace
        workspace = self.get_workspace()
        if workspace is None:
            self._left_stacked_widget.setCurrentIndex(1)  # Show empty state
        else:
            self._left_stacked_widget.setCurrentIndex(0)  # Show file tree

        layout.addWidget(self._left_stacked_widget, stretch=1)

        return panel

    def _on_empty_open_clicked(self: Any) -> None:
        """Slot to handle 'Open Folder' button click when in empty state."""
        win = self.window()
        if win and hasattr(win, "_open_folder_dialog"):
            win._open_folder_dialog()

    def build_instructions_panel(self: Any) -> QFrame:
        """Build center panel voi instructions textarea va format selector."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

        # Header row: title + template selector + word count
        header = QHBoxLayout()
        header.setSpacing(8)
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
        self._template_btn.setText("Templates")

        self._template_btn.setMenu(self._template_menu)
        header.addWidget(self._template_btn)

        # Find assets directory
        from shared.utils.path_utils import get_assets_dir

        assets_dir = str(get_assets_dir())

        # Add Save Template button (one-click)
        self._save_template_btn = QToolButton()
        self._save_template_btn.setIcon(
            create_colored_icon(os.path.join(assets_dir, "add.svg"), "white")
        )
        self._save_template_btn.setIconSize(QSize(13, 13))
        self._save_template_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                color: {ThemeColors.TEXT_MUTED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 1px;
            }}
            QToolButton:hover {{
                background: {ThemeColors.BG_HOVER};
                color: {ThemeColors.PRIMARY};
                border-color: {ThemeColors.PRIMARY};
            }}
            """
        )
        self._save_template_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_template_btn.setToolTip("Save current instruction as a template")
        self._save_template_btn.clicked.connect(self._on_save_instruction_as_template)
        header.addWidget(self._save_template_btn)

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

        # Improve Instructions button: doc instruction va goi AI toi uu hoa
        self._improve_instructions_btn = QToolButton()
        self._improve_instructions_btn.setText("Improve Instructions")
        self._improve_instructions_btn.setStyleSheet(
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
        self._improve_instructions_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._improve_instructions_btn.setToolTip(
            "Improve your instruction using AI for clearer results"
        )
        self._improve_instructions_btn.clicked.connect(self._run_improve_instructions)
        header.addWidget(self._improve_instructions_btn)

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
        )
        self._instructions_field.setStyleSheet(
            f"""
            QTextEdit {{
                font-family: {ThemeFonts.FAMILY_BODY};
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
        - Sử dụng QButtonGroup exclusive cho 3 chế độ (Full, Smart, Apply).
        - 2 checkboxes cho Git Diff và Tree Map only.
        - 1 nút Copy Context chính (Primary CTA).
        """
        from PySide6.QtWidgets import QProgressBar, QCheckBox, QButtonGroup
        from presentation.components.toggle_switch import ToggleSwitch

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(16)

        # ── PHẦN 1: MODE SELECTOR (3 buttons exclusive) ──
        mode_section_label = QLabel("COPY MODE")
        quick_header_style = f"""
            font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_MUTED};
            letter-spacing: 1.2px; padding-left: 4px;
        """
        mode_section_label.setStyleSheet(quick_header_style)
        layout.addWidget(mode_section_label)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(6)

        self._mode_full_btn = QPushButton("Full")
        self._mode_smart_btn = QPushButton("Smart")
        self._mode_apply_btn = QPushButton("Apply")

        tab_style = f"""
            QPushButton {{
                background-color: {ThemeColors.BG_ELEVATED}40;
                color: {ThemeColors.TEXT_SECONDARY};
                border: 1px solid {ThemeColors.BORDER}40;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_HOVER};
                color: {ThemeColors.TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: {ThemeColors.PRIMARY};
                color: #FFFFFF;
                border-color: {ThemeColors.PRIMARY};
            }}
            QPushButton:disabled {{
                background-color: {ThemeColors.BG_ELEVATED}10;
                color: {ThemeColors.TEXT_MUTED};
                border-color: {ThemeColors.BORDER}20;
            }}
        """

        self._mode_full_btn.setToolTip("Copy entire content of selected files")
        self._mode_smart_btn.setToolTip(
            "Copy code structure only (AST signatures & docstrings)"
        )
        self._mode_apply_btn.setToolTip(
            "Copy with Search/Replace instructions (Aider-style)"
        )

        self._mode_group = QButtonGroup(container)
        self._mode_group.setExclusive(True)

        for i, btn in enumerate(
            (self._mode_full_btn, self._mode_smart_btn, self._mode_apply_btn)
        ):
            btn.setCheckable(True)
            btn.setStyleSheet(tab_style)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            mode_layout.addWidget(btn)
            self._mode_group.addButton(btn, i)

        layout.addLayout(mode_layout)

        # Load saved mode
        saved_settings = load_app_settings()
        saved_mode = saved_settings.copy_mode
        if saved_mode == "smart":
            self._mode_smart_btn.setChecked(True)
        elif saved_mode == "apply":
            self._mode_apply_btn.setChecked(True)
        else:
            self._mode_full_btn.setChecked(True)

        def on_mode_changed(button):
            mode_str = "full"
            if button == self._mode_smart_btn:
                mode_str = "smart"
            elif button == self._mode_apply_btn:
                mode_str = "apply"
            update_app_setting(copy_mode=mode_str)
            if self._copy_controller:
                self._copy_controller._prompt_cache.invalidate_all()
            self._update_token_display()

        self._mode_group.buttonClicked.connect(on_mode_changed)

        # ── PHẦN 2: SUB-OPTIONS (Checkboxes) ──
        options_header = QLabel("SUB-OPTIONS")
        options_header.setStyleSheet(quick_header_style)
        layout.addWidget(options_header)

        cb_layout = QVBoxLayout()
        cb_layout.setSpacing(10)

        cb_style = f"""
            QCheckBox {{
                color: {ThemeColors.TEXT_SECONDARY};
                font-size: 12px;
                padding-left: 4px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QCheckBox:disabled {{
                color: {ThemeColors.TEXT_MUTED};
            }}
        """

        # Row chứa checkbox "Include Git Diff", Commit SpinBox, và nút Advanced ⚙️
        git_diff_row = QHBoxLayout()
        git_diff_row.setSpacing(8)
        git_diff_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._git_diff_cb = QCheckBox("Include Git Diff")
        self._git_diff_cb.setStyleSheet(cb_style)
        self._git_diff_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._git_diff_cb.setChecked(saved_settings.include_git_changes)
        self._git_diff_cb.setToolTip(
            "Include git diff changes of recent commits into the context"
        )
        git_diff_row.addWidget(self._git_diff_cb)

        git_diff_row.addSpacing(2)

        commit_depth_label = QLabel("Commits:")
        commit_depth_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};"
        )
        commit_depth_label.setToolTip(
            "Number of recent commits to analyze for git diff"
        )
        git_diff_row.addWidget(commit_depth_label)

        from PySide6.QtWidgets import QSpinBox

        self._commit_depth_spin = QSpinBox()
        self._commit_depth_spin.setRange(0, 100)
        self._commit_depth_spin.setValue(saved_settings.git_commit_depth)
        self._commit_depth_spin.setFixedWidth(50)
        self._commit_depth_spin.setToolTip(
            "Select number of recent commits (0 means working tree diff only)"
        )
        self._commit_depth_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 2px 4px;
                font-size: 11px;
            }}
            QSpinBox:hover {{
                border-color: {ThemeColors.PRIMARY}80;
            }}
            QSpinBox:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 14px;
                border-left: 1px solid {ThemeColors.BORDER}40;
                background: {ThemeColors.BG_ELEVATED};
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: {ThemeColors.BG_HOVER};
            }}
        """)
        self._commit_depth_spin.setEnabled(saved_settings.include_git_changes)
        git_diff_row.addWidget(self._commit_depth_spin)

        git_diff_row.addStretch()

        self._mode_diff_config_btn = QToolButton()
        self._mode_diff_config_btn.setText("⚙️")
        self._mode_diff_config_btn.setToolTip("Advanced configuration & copy diff only")
        self._mode_diff_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mode_diff_config_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: none;
                font-size: 14px;
                color: {ThemeColors.TEXT_SECONDARY};
                padding: 2px 6px;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                color: {ThemeColors.PRIMARY};
                background: {ThemeColors.BG_HOVER};
            }}
        """)
        self._mode_diff_config_btn.clicked.connect(self._on_configure_diff_clicked)
        git_diff_row.addWidget(self._mode_diff_config_btn)
        cb_layout.addLayout(git_diff_row)

        def on_git_diff_toggled(checked):
            update_app_setting(include_git_changes=checked)
            self._commit_depth_spin.setEnabled(checked)
            if self._copy_controller:
                self._copy_controller._prompt_cache.invalidate_all()
            self._update_token_display()

        self._git_diff_cb.toggled.connect(on_git_diff_toggled)

        def on_commit_depth_changed(val):
            update_app_setting(git_commit_depth=val)
            if self._copy_controller:
                self._copy_controller._prompt_cache.invalidate_all()
            self._update_token_display()

        self._commit_depth_spin.valueChanged.connect(on_commit_depth_changed)

        self._tree_map_only_cb = QCheckBox("Tree Map only")
        self._tree_map_only_cb.setStyleSheet(cb_style)
        self._tree_map_only_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tree_map_only_cb.setChecked(saved_settings.tree_map_only)

        def apply_tree_map_only_state(checked):
            self._mode_full_btn.setEnabled(not checked)
            self._mode_smart_btn.setEnabled(not checked)
            self._mode_apply_btn.setEnabled(not checked)

        apply_tree_map_only_state(saved_settings.tree_map_only)

        def on_tree_map_only_toggled(checked):
            update_app_setting(tree_map_only=checked)
            apply_tree_map_only_state(checked)
            if self._copy_controller:
                self._copy_controller._prompt_cache.invalidate_all()
            self._update_token_display()

        self._tree_map_only_cb.toggled.connect(on_tree_map_only_toggled)
        cb_layout.addWidget(self._tree_map_only_cb)

        layout.addLayout(cb_layout)

        # ── PHẦN 3: PRIMARY COPY ACTION ──
        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setStyleSheet(f"""
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
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setToolTip("Copy context according to current configuration.")
        self._copy_btn.clicked.connect(self._on_copy_clicked)
        layout.addWidget(self._copy_btn)

        # Loading bar mỏng
        self._copy_loading_bar = QProgressBar()
        self._copy_loading_bar.setRange(0, 0)
        self._copy_loading_bar.setFixedHeight(2)
        self._copy_loading_bar.setVisible(False)
        self._copy_loading_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: {ThemeColors.PRIMARY}; }}"
        )
        layout.addWidget(self._copy_loading_bar)

        # ── PHẦN 4: SETTINGS OPTIONS (Copy as file, full tree) ──
        layout.addSpacing(8)
        opt_wrap = QVBoxLayout()
        opt_wrap.setSpacing(12)

        opt_header = QLabel("SYSTEM OPTIONS")
        opt_header.setStyleSheet(quick_header_style)
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
            "Save context to a temporary file instead of copying to clipboard (useful for extremely large contexts).",
        )
        opt_wrap.addLayout(_file_row)

        _tree_row, self._full_tree_toggle = create_toggle_row(
            "Include full tree",
            "Attach the entire project directory structure to the prompt for the AI to better understand the overall structure.",
        )
        self._full_tree_toggle.setChecked(saved_settings.include_full_tree)
        self._full_tree_toggle.toggled.connect(
            lambda checked: (
                update_app_setting(include_full_tree=checked),
                self._copy_controller._prompt_cache.invalidate_all(),
                self._update_token_display(),
            )
        )
        opt_wrap.addLayout(_tree_row)
        layout.addLayout(opt_wrap)

        # ── PHẦN 5: ALIASES ẨN CHO TESTS CŨ ──
        self._smart_btn = QPushButton()
        self._smart_btn.setVisible(False)
        self._smart_btn.clicked.connect(self._copy_controller.on_copy_smart_requested)

        self._opx_btn = QPushButton()
        self._opx_btn.setVisible(False)
        self._opx_btn.clicked.connect(
            lambda: self._copy_controller.on_copy_context_requested(include_xml=True)
        )

        self._diff_btn = QPushButton()
        self._diff_btn.setVisible(False)
        self._diff_btn.clicked.connect(self._copy_controller._show_diff_only_dialog)

        self._tree_map_btn = QPushButton()
        self._tree_map_btn.setVisible(False)
        self._tree_map_btn.clicked.connect(
            self._copy_controller.on_copy_tree_map_requested
        )

        return container

    def _on_model_action_triggered(self: Any, action: Any) -> None:
        """Handle model selection from dropdown menu."""
        model_id = action.data()
        if model_id:
            self._selected_model_id = model_id
            self._model_btn.setText(action.text())

            # Persist selection vào settings để survive app restart
            update_app_setting(model_id=model_id)

            # Trigger logic in ContextViewQt
            self._on_model_changed(model_id)

    def _on_model_changed(self: Any, model_id: str) -> None:
        """Override point for model change handling - implemented in ContextViewQt."""
        # This method is overridden in ContextViewQt with actual implementation
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
