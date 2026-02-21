"""
UI Builder Mixin cho ContextViewQt.

Chua tat ca cac methods xay dung UI components.
"""

import os
from typing import TYPE_CHECKING

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

from core.theme import ThemeColors
from components.file_tree_widget import FileTreeWidget
from components.token_stats_qt import TokenStatsPanelQt
from config.output_format import (
    OUTPUT_FORMATS,
    get_style_by_id,
    DEFAULT_OUTPUT_STYLE,
)
from services.settings_manager import load_app_settings

if TYPE_CHECKING:
    from views.context_view_qt import ContextViewQt


class UIBuilderMixin:
    """Mixin chua tat ca UI building methods cho ContextViewQt."""

    def _build_ui(self: "ContextViewQt") -> None:
        """Xay dung UI voi top toolbar + 3-panel splitter (30:45:25)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Top toolbar: controls + token counter
        toolbar = self._build_toolbar()
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
        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)

        # Center panel - Instructions (~45%)
        center_panel = self._build_instructions_panel()
        splitter.addWidget(center_panel)

        # Right panel - Actions + Token stats (~25%)
        action_panel = self._build_actions_panel()
        splitter.addWidget(action_panel)

        # Ty le 30:45:25 cho 3 panel
        splitter.setStretchFactor(0, 30)
        splitter.setStretchFactor(1, 45)
        splitter.setStretchFactor(2, 25)
        splitter.setSizes([420, 630, 350])

        layout.addWidget(splitter)

    def _build_toolbar(self: "ContextViewQt") -> QFrame:
        """Build top toolbar chua controls va token counter."""
        toolbar = QFrame()
        toolbar.setFixedHeight(40)
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
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        assets_dir = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            "assets",
        )

        # Style cho toolbar icon buttons
        icon_btn_style = (
            f"QToolButton {{ "
            f"  background: transparent; border: none; "
            f"  border-radius: 6px; padding: 5px; "
            f"  color: {ThemeColors.TEXT_SECONDARY}; "
            f"}} "
            f"QToolButton:hover {{ "
            f"  background: {ThemeColors.BG_HOVER}; "
            f"  color: {ThemeColors.TEXT_PRIMARY}; "
            f"}}"
        )

        # Refresh button
        refresh_btn = QToolButton()
        refresh_btn.setIcon(QIcon(os.path.join(assets_dir, "refresh.svg")))
        refresh_btn.setIconSize(QSize(16, 16))
        refresh_btn.setToolTip("Refresh file tree (F5)")
        refresh_btn.setStyleSheet(icon_btn_style)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_tree)
        layout.addWidget(refresh_btn)

        # Separator nho
        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setFixedHeight(20)
        sep1.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        layout.addWidget(sep1)

        # Ignore button
        ignore_btn = QToolButton()
        ignore_btn.setIcon(QIcon(os.path.join(assets_dir, "ban.svg")))
        ignore_btn.setIconSize(QSize(16, 16))
        ignore_btn.setToolTip("Ignore selected files")
        ignore_btn.setStyleSheet(icon_btn_style)
        ignore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ignore_btn.clicked.connect(self._add_to_ignore)
        layout.addWidget(ignore_btn)

        # Undo ignore button
        undo_btn = QToolButton()
        undo_btn.setIcon(QIcon(os.path.join(assets_dir, "undo.svg")))
        undo_btn.setIconSize(QSize(16, 16))
        undo_btn.setToolTip("Undo last ignore")
        undo_btn.setStyleSheet(icon_btn_style)
        undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        undo_btn.clicked.connect(self._undo_ignore)
        layout.addWidget(undo_btn)

        # Separator
        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(20)
        sep2.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        layout.addWidget(sep2)

        # Remote repos dropdown
        remote_btn = QToolButton()
        remote_btn.setIcon(QIcon(os.path.join(assets_dir, "cloud.png")))
        remote_btn.setIconSize(QSize(16, 16))
        remote_btn.setToolTip("Remote Repositories")
        remote_btn.setStyleSheet(icon_btn_style)
        remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remote_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        remote_menu = QMenu(remote_btn)
        remote_menu.addAction("Clone Repository", self._open_remote_repo_dialog)
        remote_menu.addAction("Manage Cache", self._open_cache_management_dialog)
        remote_btn.setMenu(remote_menu)
        layout.addWidget(remote_btn)

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
                background: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-weight: 500;
            }}
            QToolButton:hover {{
                background: {ThemeColors.BG_HOVER};
            }}
            QToolButton::menu-indicator {{
                width: 0px;
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
        off_action = related_menu.addAction("Off")
        related_menu.addSeparator()

        direct_action = related_menu.addAction("Direct (depth 1)")
        nearby_action = related_menu.addAction("Nearby (depth 2)")
        deep_action = related_menu.addAction("Deep (depth 3)")
        deeper_action = related_menu.addAction("Deeper (depth 4)")
        deepest_action = related_menu.addAction("Deepest (depth 5)")

        # Connect actions
        off_action.triggered.connect(lambda: self._set_related_mode(False, 0))
        direct_action.triggered.connect(lambda: self._set_related_mode(True, 1))
        nearby_action.triggered.connect(lambda: self._set_related_mode(True, 2))
        deep_action.triggered.connect(lambda: self._set_related_mode(True, 3))
        deeper_action.triggered.connect(lambda: self._set_related_mode(True, 4))
        deepest_action.triggered.connect(lambda: self._set_related_mode(True, 5))

        self._related_menu_btn.setMenu(related_menu)
        layout.addWidget(self._related_menu_btn)

        # Track current depth for internal use
        self._related_depth = 1

        # Stretch de day token counter sang ben phai
        layout.addStretch()

        # Selection meta label
        self._selection_meta_label = QLabel("0 selected")
        self._selection_meta_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_MUTED}; font-weight: 500;"
        )
        layout.addWidget(self._selection_meta_label)

        # Separator truoc token counter
        sep3 = QFrame()
        sep3.setFixedWidth(1)
        sep3.setFixedHeight(20)
        sep3.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        layout.addWidget(sep3)

        # Token counter noi bat
        self._token_count_label = QLabel("0 tokens")
        self._token_count_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.PRIMARY};"
        )
        layout.addWidget(self._token_count_label)

        return toolbar

    def _build_left_panel(self: "ContextViewQt") -> QFrame:
        """Build left panel chi chua header + file tree (controls da len toolbar)."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
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
        self.file_tree_widget = FileTreeWidget()
        self.file_tree_widget.selection_changed.connect(self._on_selection_changed)
        self.file_tree_widget.file_preview_requested.connect(self._preview_file)
        self.file_tree_widget.token_counting_done.connect(self._update_token_display)
        layout.addWidget(self.file_tree_widget, stretch=1)

        return panel

    def _build_instructions_panel(self: "ContextViewQt") -> QFrame:
        """Build center panel voi instructions textarea va format selector."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Header row: title + template selector + word count
        header = QHBoxLayout()
        instr_label = QLabel("Instructions")
        instr_label.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header.addWidget(instr_label)

        # Add Templates button
        from core.prompting.template_manager import list_templates

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

        template_menu = QMenu(self._template_btn)
        template_menu.setStyleSheet(
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

        for tmpl in list_templates():
            action = template_menu.addAction(tmpl.display_name)
            action.setToolTip(tmpl.description)
            # Store template ID in action's data for retrieval later
            action.setData(tmpl.template_id)

        # Connect the menu's triggered signal to a handler in ContextViewQt
        template_menu.triggered.connect(self._on_template_selected)

        self._template_btn.setMenu(template_menu)
        header.addWidget(self._template_btn)

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
            "Describe your request here...\n\n"
            "Examples:\n"
            "- Refactor module X to Y\n"
            "- Fix bug: [error description]\n"
            "- Add feature: [functionality description]\n\n"
            "Optional: include output format, constraints, or edge cases."
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

    def _build_actions_panel(self: "ContextViewQt") -> QFrame:
        """Build right panel: Token stats (top) -> Copy buttons -> Status (bottom)."""
        panel = QFrame()
        panel.setProperty("class", "surface")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Token stats panel (model selector + budget bar) o tren cung
        self._token_stats = TokenStatsPanelQt()
        self._token_stats.model_changed.connect(self._on_model_changed)
        layout.addWidget(self._token_stats)

        # Separator giua stats va buttons
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {ThemeColors.BORDER};")
        layout.addWidget(sep)

        # Action buttons voi visual hierarchy ro rang
        actions = self._build_action_buttons()
        layout.addWidget(actions)

        layout.addStretch()

        return panel

    def _build_action_buttons(self: "ContextViewQt") -> QWidget:
        """Build copy buttons voi visual hierarchy: CTA -> Secondary -> Tertiary."""
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

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

        # === PRIMARY CTA: Copy + OPX (lon nhat, noi bat nhat) ===
        self._opx_btn = QPushButton("Copy + OPX")
        self._opx_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ThemeColors.PRIMARY_PRESSED};
            }}
            QPushButton:disabled {{
                background-color: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_MUTED};
            }}
        """
        )
        self._opx_btn.setToolTip("Copy context with OPX instructions (Ctrl+Shift+C)")
        self._opx_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._opx_btn.clicked.connect(lambda: self._copy_context(include_xml=True))
        layout.addWidget(self._opx_btn)

        # === SECONDARY: Copy Context ===
        self._copy_btn = QPushButton("Copy Context")
        self._copy_btn.setStyleSheet(secondary_style)
        self._copy_btn.setToolTip("Copy context with basic formatting (Ctrl+C)")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(lambda: self._copy_context(include_xml=False))
        layout.addWidget(self._copy_btn)

        # === SECONDARY: Copy Smart ===
        self._smart_btn = QPushButton("Copy Smart")
        self._smart_btn.setProperty("custom-style", "orange")
        self._smart_btn.setStyleSheet(
            f"""
            QPushButton[custom-style="orange"] {{
                background-color: transparent;
                color: {ThemeColors.WARNING};
                border: 1px solid {ThemeColors.WARNING};
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton[custom-style="orange"]:hover {{
                background-color: {ThemeColors.WARNING};
                color: white;
            }}
            QPushButton[custom-style="orange"]:pressed {{
                background-color: #D97706;
                color: white;
            }}
            QPushButton[custom-style="orange"]:disabled {{
                color: {ThemeColors.TEXT_MUTED};
                border-color: {ThemeColors.BG_ELEVATED};
            }}
        """
        )
        self._smart_btn.setToolTip("Copy code structure only (Smart Context)")
        self._smart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._smart_btn.clicked.connect(self._copy_smart_context)
        layout.addWidget(self._smart_btn)

        # === SECONDARY: Copy Diff Only ===
        self._diff_btn = QPushButton("Copy Diff Only")
        self._diff_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: #A78BFA;
                border: 1px solid #8B5CF6;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #8B5CF6;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: #7C3AED;
                color: white;
            }}
            QPushButton:disabled {{
                color: {ThemeColors.TEXT_MUTED};
                border-color: {ThemeColors.BG_ELEVATED};
            }}
        """
        )
        self._diff_btn.setToolTip("Copy only git diff (Ctrl+Shift+D)")
        self._diff_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._diff_btn.clicked.connect(self._show_diff_only_dialog)
        layout.addWidget(self._diff_btn)

        # === TERTIARY: Copy Tree Map ===
        self._tree_map_btn = QPushButton("Copy Tree Map")
        self._tree_map_btn.setStyleSheet(secondary_style)
        self._tree_map_btn.setToolTip("Copy only file structure")
        self._tree_map_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tree_map_btn.clicked.connect(self._copy_tree_map_only)
        layout.addWidget(self._tree_map_btn)

        return widget
