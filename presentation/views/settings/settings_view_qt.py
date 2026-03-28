"""
Settings View (PySide6) — Redesigned single-column, card-based layout.

Features:
- Single scrollable column, max-width 720px, centered
- Card grouping with accent dot headers
- Toggle switches (not checkboxes) for all on/off settings
- Tag chips for excluded patterns (not textarea)
- Proper button hierarchy with confirm dialogs for destructive actions
"""

import json
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QMessageBox,
    QSizePolicy,
    QComboBox,
    QLineEdit,
    QDialog,
    QPlainTextEdit,
    QMenu,
    QFileDialog,
    QToolButton,
)
from PySide6.QtCore import Qt, Slot, QTimer, Signal

from presentation.config.theme import ThemeColors
from presentation.components.toggle_switch import ToggleSwitch
from presentation.components.tag_chips_widget import TagChipsWidget
from infrastructure.adapters.clipboard_utils import (
    copy_to_clipboard,
    get_clipboard_text,
)
from infrastructure.persistence.session_state import clear_session_state
from infrastructure.persistence.settings_manager import (
    load_settings,
    save_settings,
    DEFAULT_SETTINGS,
)
from infrastructure.persistence.settings_manager import (
    load_app_settings,
    update_app_setting,
)
from presentation.components.toast.toast_qt import toast_success, toast_error


# ============================================================
# Re-exports tu services.workspace_config (backward compatibility)
# Cac functions nay da duoc extract sang services/workspace_config.py
# de tuan thu Dependency Inversion Principle.
# ============================================================
from application.services.workspace_config import (  # noqa: F401
    PRESET_PROFILES,
    get_excluded_patterns,
    get_use_gitignore,
    get_use_relative_paths,
    add_excluded_patterns,
    remove_excluded_patterns,
    _excluded_notifier,
)


# ============================================================
# Helper: Accent Dot Label (section header with colored dot)
# ============================================================


class _AccentDotLabel(QWidget):
    """Card header: small accent dot + title text."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Dot
        dot = QWidget()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {ThemeColors.PRIMARY}; border-radius: 4px;")
        layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Title
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(label)
        layout.addStretch()


# ============================================================
# Helper: Toggle Row (label + description + toggle switch)
# ============================================================


class _ToggleRow(QWidget):
    """A row with label, description, and toggle switch."""

    toggled = Signal(bool)

    def __init__(
        self,
        label: str,
        description: str,
        checked: bool = True,
        tip: str = "",
        parent=None,
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Left: label + description
        left = QVBoxLayout()
        left.setSpacing(3)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {ThemeColors.TEXT_PRIMARY};"
        )
        left.addWidget(lbl)

        desc = QLabel(description)
        desc.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        desc.setWordWrap(True)
        left.addWidget(desc)

        if tip:
            tip_label = QLabel(tip)
            tip_label.setStyleSheet(
                f"font-size: 11px; color: {ThemeColors.WARNING}; font-weight: 500;"
            )
            tip_label.setWordWrap(True)
            left.addWidget(tip_label)

        layout.addLayout(left, stretch=1)

        # Right: toggle
        self._toggle = ToggleSwitch(checked=checked)
        self._toggle.toggled.connect(self.toggled.emit)
        layout.addWidget(self._toggle, alignment=Qt.AlignmentFlag.AlignVCenter)

    def isChecked(self) -> bool:
        return self._toggle.isChecked()

    def setChecked(self, checked: bool) -> None:
        self._toggle.setChecked(checked)


# ============================================================
# Helper: Card Frame
# ============================================================


def _make_card() -> QFrame:
    """Create a styled settings card frame."""
    card = QFrame()
    card.setStyleSheet(
        f"""
        QFrame {{
            background-color: {ThemeColors.BG_SURFACE};
            border: none;
            border-radius: 10px;
        }}
    """
    )
    return card


def _make_separator() -> QFrame:
    """Create a dashed separator line inside a card."""
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(
        f"background: transparent; border-top: 1px dashed {ThemeColors.BORDER};"
    )
    return sep


def _make_ghost_btn(text: str) -> QPushButton:
    """Ghost button style (secondary action)."""
    from presentation.config.theme import ThemeRadius, ThemeSpacing

    btn = QPushButton(text)
    btn.setMinimumHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background: transparent;
            color: {ThemeColors.TEXT_PRIMARY};
            border: 1px solid {ThemeColors.BORDER};
            border-radius: {ThemeRadius.LG}px;
            padding: 0 {ThemeSpacing.LG}px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {ThemeColors.BG_ELEVATED};
            border-color: {ThemeColors.BORDER_LIGHT};
        }}
        QPushButton:pressed {{
            background: {ThemeColors.BG_HOVER};
        }}
    """
    )
    return btn


def _make_danger_btn(text: str) -> QPushButton:
    """Danger button style (destructive action)."""
    from presentation.config.theme import ThemeRadius, ThemeSpacing

    btn = QPushButton(text)
    btn.setMinimumHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background: transparent;
            color: {ThemeColors.ERROR};
            border: 1px solid {ThemeColors.ERROR}50;
            border-radius: {ThemeRadius.LG}px;
            padding: 0 {ThemeSpacing.LG}px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {ThemeColors.ERROR}15;
            border-color: {ThemeColors.ERROR};
        }}
        QPushButton:pressed {{
            background: {ThemeColors.ERROR}25;
        }}
    """
    )
    return btn


# ============================================================
# Settings View
# ============================================================


class SettingsViewQt(QWidget):
    """Settings tab — single column, card-based, centered layout."""

    def __init__(
        self,
        on_settings_changed: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.on_settings_changed = on_settings_changed
        self._has_unsaved = False
        # Luu lai cac status label MCP theo target de co the cap nhat sau khi install
        self._mcp_status_labels: dict[str, QLabel] = {}
        self._fetch_worker = None  # Optional background worker cho fetch models

        # Debounced auto-save timer (800ms)
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(800)
        self._auto_save_timer.timeout.connect(self._save_settings)

        self._build_ui()
        _excluded_notifier.connect(self._reload_excluded_from_settings)

    def _build_ui(self) -> None:
        settings = load_settings()

        # Root layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Header bar ──
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(
            f"""
            QFrame {{
                background: {ThemeColors.BG_PAGE};
                border: none;
            }}
        """
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        title = QLabel("Settings")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {ThemeColors.TEXT_PRIMARY};"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Auto-save indicator
        self._auto_save_indicator = QLabel("")
        self._auto_save_indicator.setFixedWidth(150)
        self._auto_save_indicator.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._auto_save_indicator.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {ThemeColors.TEXT_MUTED};"
        )
        header_layout.addWidget(self._auto_save_indicator)

        root_layout.addWidget(header)

        # ── Scroll area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background: {ThemeColors.BG_PAGE};
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 0;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {ThemeColors.BORDER};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {ThemeColors.PRIMARY};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """
        )

        # Inner content — 3-column grid layout
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background: {ThemeColors.BG_PAGE};")
        outer_layout = QHBoxLayout(scroll_content)
        outer_layout.setContentsMargins(20, 20, 20, 32)
        outer_layout.setSpacing(16)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Column 1
        col1 = QWidget()
        col1.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        col1_layout = QVBoxLayout(col1)
        col1_layout.setContentsMargins(0, 0, 0, 0)
        col1_layout.setSpacing(16)
        col1_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Column 2
        col2 = QWidget()
        col2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        col2_layout = QVBoxLayout(col2)
        col2_layout.setContentsMargins(0, 0, 0, 0)
        col2_layout.setSpacing(16)
        col2_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Column 3
        col3 = QWidget()
        col3.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        col3_layout = QVBoxLayout(col3)
        col3_layout.setContentsMargins(0, 0, 0, 0)
        col3_layout.setSpacing(16)
        col3_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ─────────────────────────────
        # CARD 1: File Tree
        # ─────────────────────────────
        card1 = _make_card()
        card1_layout = QVBoxLayout(card1)
        card1_layout.setContentsMargins(22, 22, 22, 22)
        card1_layout.setSpacing(0)

        card1_layout.addWidget(_AccentDotLabel("File Tree"))
        card1_layout.addSpacing(18)

        self._gitignore_toggle = _ToggleRow(
            label="Respect .gitignore",
            description="Hide files matching .gitignore patterns",
            checked=settings.get("use_gitignore", True),
        )
        self._gitignore_toggle.toggled.connect(self._mark_changed)
        card1_layout.addWidget(self._gitignore_toggle)

        col1_layout.addWidget(card1)

        # ─────────────────────────────
        # CARD 2: Excluded Patterns
        # ─────────────────────────────
        card2 = _make_card()
        card2_layout = QVBoxLayout(card2)
        card2_layout.setContentsMargins(22, 22, 22, 22)
        card2_layout.setSpacing(0)

        card2_layout.addWidget(_AccentDotLabel("Excluded Patterns"))
        card2_layout.addSpacing(8)

        exc_desc = QLabel("Files and folders excluded from tree and AI context")
        exc_desc.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        card2_layout.addWidget(exc_desc)
        card2_layout.addSpacing(14)

        # Tag chips
        initial_patterns = get_excluded_patterns()
        self._tag_chips = TagChipsWidget(patterns=initial_patterns)
        self._tag_chips.patterns_changed.connect(self._on_patterns_changed)
        card2_layout.addWidget(self._tag_chips)

        col1_layout.addWidget(card2)

        # Quick preset dropdown (styled)
        preset_row = QHBoxLayout()
        preset_row.setSpacing(10)

        preset_label = QLabel("Quick Preset")
        preset_label.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {ThemeColors.TEXT_PRIMARY};"
        )
        preset_row.addWidget(preset_label)

        self._preset_combo = QComboBox()
        self._preset_combo.setFixedWidth(180)
        self._preset_combo.setFixedHeight(32)
        self._preset_combo.addItem("Select profile...")
        for name in PRESET_PROFILES:
            self._preset_combo.addItem(name)
        self._preset_combo.setStyleSheet(
            f"""
            QComboBox {{
                background: {ThemeColors.BG_PAGE};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: {ThemeColors.PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background: {ThemeColors.BG_SURFACE};
                color: {ThemeColors.TEXT_PRIMARY};
                selection-background-color: {ThemeColors.PRIMARY};
                selection-color: white;
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 12px;
            }}
        """
        )
        self._preset_combo.currentTextChanged.connect(self._load_preset)
        preset_row.addWidget(self._preset_combo)
        preset_row.addStretch()

        preset_desc = QLabel("Merge preset patterns into current list")
        preset_desc.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.TEXT_SECONDARY};"
        )
        preset_row.addWidget(preset_desc)

        card2_layout.addLayout(preset_row)

        col1_layout.addWidget(card2)
        col1_layout.addStretch()

        # ─────────────────────────────
        # CARD 3: AI Context
        # ─────────────────────────────
        card3 = _make_card()
        card3_layout = QVBoxLayout(card3)
        card3_layout.setContentsMargins(22, 22, 22, 22)
        card3_layout.setSpacing(0)

        card3_layout.addWidget(_AccentDotLabel("AI Context"))
        card3_layout.addSpacing(18)

        self._git_toggle = _ToggleRow(
            label="Include Git Diff/Log",
            description="Include recent git changes in AI context",
            checked=settings.get("include_git_changes", True),
        )
        self._git_toggle.toggled.connect(self._mark_changed)
        card3_layout.addWidget(self._git_toggle)

        card3_layout.addSpacing(16)
        card3_layout.addWidget(_make_separator())
        card3_layout.addSpacing(16)

        self._relative_toggle = _ToggleRow(
            label="Use Relative Paths",
            description="Use paths relative to workspace root in prompts",
            checked=settings.get("use_relative_paths", True),
            tip="Recommended for privacy when sharing prompts",
        )
        self._relative_toggle.toggled.connect(self._mark_changed)
        card3_layout.addWidget(self._relative_toggle)

        col2_layout.addWidget(card3)

        # ─────────────────────────────
        # CARD 3b: AI Context Builder (LLM Provider)
        # ─────────────────────────────
        app_settings = load_app_settings()

        card3b = _make_card()
        card3b_layout = QVBoxLayout(card3b)
        card3b_layout.setContentsMargins(22, 22, 22, 22)
        card3b_layout.setSpacing(0)

        card3b_layout.addWidget(_AccentDotLabel("AI Context Builder"))
        card3b_layout.addSpacing(8)

        ai_desc = QLabel(
            "Configure LLM provider for AI-powered file discovery. "
            "Supports any OpenAI-compatible API."
        )
        ai_desc.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        ai_desc.setWordWrap(True)
        card3b_layout.addWidget(ai_desc)
        card3b_layout.addSpacing(6)

        # Onboarding hint — hiển thị khi chưa có API key
        self._ai_onboarding_hint = QLabel(
            "Quick start: Get a free API key from OpenRouter (openrouter.ai), "
            "Groq (console.groq.com), or use a local LLM with LM Studio (localhost:1234/v1)."
        )
        self._ai_onboarding_hint.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.INFO}; "
            f"background: {ThemeColors.INFO}12; "
            f"border: 1px solid {ThemeColors.INFO}30; "
            f"border-radius: 6px; padding: 8px 10px;"
        )
        self._ai_onboarding_hint.setWordWrap(True)
        self._ai_onboarding_hint.setVisible(not bool(app_settings.ai_api_key.strip()))
        card3b_layout.addWidget(self._ai_onboarding_hint)
        card3b_layout.addSpacing(8)

        # Ẩn hint khi user bắt đầu nhập API key
        self._ai_api_key_input_changed_for_hint = lambda text: (
            self._ai_onboarding_hint.setVisible(not bool(text.strip()))
        )

        # API Key input
        api_key_label = QLabel("API Key")
        api_key_label.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {ThemeColors.TEXT_PRIMARY};"
        )
        card3b_layout.addWidget(api_key_label)
        card3b_layout.addSpacing(4)

        api_key_row = QHBoxLayout()
        api_key_row.setSpacing(0)
        api_key_row.setContentsMargins(0, 0, 0, 0)

        self._ai_api_key_input = QLineEdit()
        self._ai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._ai_api_key_input.setPlaceholderText("sk-...")
        self._ai_api_key_input.setText(app_settings.ai_api_key)
        self._ai_api_key_input.setFixedHeight(34)
        self._ai_api_key_input.setStyleSheet(
            f"""
            QLineEdit {{
                background: {ThemeColors.BG_PAGE};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 6px;
                padding: 4px 36px 4px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ThemeColors.PRIMARY};
            }}
        """
        )
        self._ai_api_key_input.textChanged.connect(self._mark_changed)
        self._ai_api_key_input.textChanged.connect(
            self._ai_api_key_input_changed_for_hint
        )
        api_key_row.addWidget(self._ai_api_key_input, stretch=1)

        # Eye toggle button overlaid on the right side of input
        self._api_key_eye_btn = QToolButton()
        self._api_key_eye_btn.setText("\U0001f441")  # Eye emoji
        self._api_key_eye_btn.setFixedSize(28, 28)
        self._api_key_eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._api_key_eye_btn.setToolTip("Show/Hide API Key")
        self._api_key_eye_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                color: {ThemeColors.TEXT_MUTED};
                font-size: 14px;
                margin-left: -32px;
            }}
            QToolButton:hover {{
                color: {ThemeColors.PRIMARY};
                background: {ThemeColors.BG_ELEVATED};
            }}
        """
        )
        self._api_key_eye_btn.clicked.connect(self._toggle_api_key_visibility)
        api_key_row.addWidget(self._api_key_eye_btn)

        card3b_layout.addLayout(api_key_row)

        card3b_layout.addSpacing(12)

        # Base URL input
        base_url_label = QLabel("Base URL")
        base_url_label.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {ThemeColors.TEXT_PRIMARY};"
        )
        card3b_layout.addWidget(base_url_label)
        card3b_layout.addSpacing(4)

        self._ai_base_url_input = QLineEdit()
        self._ai_base_url_input.setPlaceholderText("https://api.openai.com/v1")
        self._ai_base_url_input.setText(app_settings.ai_base_url)
        self._ai_base_url_input.setFixedHeight(34)
        self._ai_base_url_input.setStyleSheet(
            self._ai_api_key_input.styleSheet()  # Reuse style
        )
        self._ai_base_url_input.textChanged.connect(self._mark_changed)
        card3b_layout.addWidget(self._ai_base_url_input)

        card3b_layout.addSpacing(4)
        url_hint = QLabel(
            "Local LLM: http://localhost:1234/v1 "
            "| OpenRouter: https://openrouter.ai/api/v1"
        )
        url_hint.setStyleSheet(f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};")
        url_hint.setWordWrap(True)
        card3b_layout.addWidget(url_hint)

        card3b_layout.addSpacing(12)

        # Model selector row
        model_label = QLabel("Model")
        model_label.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {ThemeColors.TEXT_PRIMARY};"
        )
        card3b_layout.addWidget(model_label)
        card3b_layout.addSpacing(4)

        model_row = QHBoxLayout()
        model_row.setSpacing(8)

        self._ai_model_combo = QComboBox()
        self._ai_model_combo.setEditable(True)
        self._ai_model_combo.setFixedHeight(34)
        self._ai_model_combo.setStyleSheet(
            self._preset_combo.styleSheet()  # Reuse combo style
        )
        # Them model hien tai neu co
        if app_settings.ai_model_id:
            self._ai_model_combo.addItem(app_settings.ai_model_id)
            self._ai_model_combo.setCurrentText(app_settings.ai_model_id)
        self._ai_model_combo.currentTextChanged.connect(self._mark_changed)
        model_row.addWidget(self._ai_model_combo, stretch=1)

        # Nut Fetch Models tu server
        self._fetch_btn = _make_ghost_btn("Fetch Models")
        self._fetch_btn.setFixedWidth(120)
        self._fetch_btn.clicked.connect(self._fetch_ai_models)
        model_row.addWidget(self._fetch_btn)

        card3b_layout.addLayout(model_row)

        col2_layout.addWidget(card3b)

        # ─────────────────────────────
        # CARD 4: Security
        # ─────────────────────────────
        card4 = _make_card()
        card4_layout = QVBoxLayout(card4)
        card4_layout.setContentsMargins(22, 22, 22, 22)
        card4_layout.setSpacing(0)

        card4_layout.addWidget(_AccentDotLabel("Security"))
        card4_layout.addSpacing(18)

        self._security_toggle = _ToggleRow(
            label="Enable Security Scan",
            description="Scan for API keys, passwords, and secrets before copying",
            checked=settings.get("enable_security_check", True),
        )
        self._security_toggle.toggled.connect(self._mark_changed)
        card4_layout.addWidget(self._security_toggle)

        col2_layout.addWidget(card4)

        # ─────────────────────────────
        # CARD 4b: Output & Templates
        # ─────────────────────────────
        card4b = _make_card()
        card4b_layout = QVBoxLayout(card4b)
        card4b_layout.setContentsMargins(22, 22, 22, 22)
        card4b_layout.setSpacing(0)

        card4b_layout.addWidget(_AccentDotLabel("Output & Templates"))
        card4b_layout.addSpacing(18)

        # Output language selector
        lang_label = QLabel("Report Output Language")
        lang_label.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {ThemeColors.TEXT_PRIMARY};"
        )
        card4b_layout.addWidget(lang_label)
        card4b_layout.addSpacing(2)
        lang_hint = QLabel(
            "Language used in AI analysis reports generated from templates."
        )
        lang_hint.setStyleSheet(f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};")
        lang_hint.setWordWrap(True)
        card4b_layout.addWidget(lang_hint)
        card4b_layout.addSpacing(6)

        self._output_language_combo = QComboBox()
        self._output_language_combo.setEditable(True)
        self._output_language_combo.setFixedHeight(34)
        self._output_language_combo.setStyleSheet(self._preset_combo.styleSheet())
        for lang in [
            "Vietnamese (tiếng Việt có dấu)",
            "English",
            "Japanese (日本語)",
            "Korean (한국어)",
        ]:
            self._output_language_combo.addItem(lang)
        self._output_language_combo.setCurrentText(
            app_settings.output_language or "Vietnamese (tiếng Việt có dấu)"
        )
        self._output_language_combo.currentTextChanged.connect(self._mark_changed)
        card4b_layout.addWidget(self._output_language_combo)

        col2_layout.addWidget(card4b)
        col2_layout.addStretch()

        # ─────────────────────────────
        # CARD 6: MCP Server Integration
        # ─────────────────────────────
        card6 = _make_card()
        card6_layout = QVBoxLayout(card6)
        card6_layout.setContentsMargins(22, 22, 22, 22)
        card6_layout.setSpacing(0)

        card6_layout.addWidget(_AccentDotLabel("MCP Server Integration"))
        card6_layout.addSpacing(8)

        mcp_desc = QLabel(
            "Expose Synapse context directly to AI clients (Cursor, Copilot, etc.) via Model Context Protocol."
        )
        mcp_desc.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};")
        mcp_desc.setWordWrap(True)
        card6_layout.addWidget(mcp_desc)
        card6_layout.addSpacing(14)

        # Buttons cho tung AI client
        from infrastructure.mcp.config_installer import MCP_TARGETS, check_installed

        for target_name in MCP_TARGETS:
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)

            install_btn = _make_ghost_btn(f"Install to {target_name} ▾")
            install_btn.setToolTip(f"Install MCP config and Skills for {target_name}")

            # Giau mui ten dropdown mac dinh xau xi cua PyQt, chi giu icon tren text
            current_style = install_btn.styleSheet()
            install_btn.setStyleSheet(
                current_style
                + "QPushButton::menu-indicator { image: none; width: 0px; }"
            )

            menu = QMenu(install_btn)
            menu.setStyleSheet(
                f"QMenu {{ background-color: {ThemeColors.BG_SURFACE}; border: 1px solid {ThemeColors.BORDER}; border-radius: 6px; padding: 4px; }}"
                f"QMenu::item {{ color: {ThemeColors.TEXT_PRIMARY}; padding: 6px 20px; border-radius: 4px; }}"
                f"QMenu::item:selected {{ background-color: {ThemeColors.BG_HOVER}; }}"
            )

            act_global = menu.addAction("📌 Install Global (Default)")
            act_global.triggered.connect(
                lambda checked=False, t=target_name: self._install_mcp_for(t)
            )

            act_workspace = menu.addAction(
                "📁 Install for specific Project / Workspace..."
            )
            act_workspace.triggered.connect(
                lambda checked=False, t=target_name: self._ask_workspace_and_install(t)
            )

            install_btn.setMenu(menu)

            # Hien thi trang thai da cai hay chua (icon + text cho accessibility)
            if check_installed(target_name):
                status_label = QLabel("\u2713 Installed")
                status_label.setStyleSheet(
                    f"font-size: 11px; font-weight: 600; color: {ThemeColors.SUCCESS};"
                )
            else:
                status_label = QLabel("\u25cb Not installed")
                status_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};"
                )

            # Luu lai de co the cap nhat sau khi user bam Install
            self._mcp_status_labels[target_name] = status_label

            btn_row.addWidget(install_btn)
            btn_row.addWidget(status_label)
            btn_row.addStretch()

            card6_layout.addLayout(btn_row)
            card6_layout.addSpacing(6)

        # Generic IDE Config Snippet cho cac IDE chua duoc ho tro chinh thuc
        card6_layout.addSpacing(6)
        copy_mcp_btn = _make_ghost_btn("Generic IDE Config Snippet")
        copy_mcp_btn.setToolTip(
            "Generate generic MCP configuration for unsupported IDEs (manual copy/paste)"
        )
        copy_mcp_btn.clicked.connect(self._copy_mcp_config)
        card6_layout.addWidget(copy_mcp_btn)

        col3_layout.addWidget(card6)

        # ─────────────────────────────
        # CARD 5: Data & Session
        # ─────────────────────────────
        card5 = _make_card()
        card5_layout = QVBoxLayout(card5)
        card5_layout.setContentsMargins(22, 22, 22, 22)
        card5_layout.setSpacing(0)

        card5_layout.addWidget(_AccentDotLabel("Data & Session"))
        card5_layout.addSpacing(18)

        # Clear Session
        clear_btn = _make_ghost_btn("Clear Saved Session")
        clear_btn.clicked.connect(self._clear_session)
        card5_layout.addWidget(clear_btn)
        card5_layout.addSpacing(6)

        clear_desc = QLabel("Reset workspace and open files state")
        clear_desc.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};"
        )
        card5_layout.addWidget(clear_desc)

        card5_layout.addSpacing(16)
        card5_layout.addWidget(_make_separator())
        card5_layout.addSpacing(16)

        # Export / Import row
        ei_row = QHBoxLayout()
        ei_row.setSpacing(12)

        export_btn = _make_ghost_btn("Export Settings")
        export_btn.clicked.connect(self._export_settings)
        ei_row.addWidget(export_btn)

        import_btn = _make_ghost_btn("Import Settings")
        import_btn.clicked.connect(self._import_settings)
        ei_row.addWidget(import_btn)

        card5_layout.addLayout(ei_row)

        card5_layout.addSpacing(16)
        card5_layout.addWidget(_make_separator())
        card5_layout.addSpacing(16)

        # Reset All — danger style
        reset_btn = _make_danger_btn("Reset All to Defaults")
        reset_btn.clicked.connect(self._reset_settings)
        card5_layout.addWidget(reset_btn)

        col3_layout.addWidget(card5)

        # Add columns to outer layout
        outer_layout.addWidget(col1, stretch=1)
        outer_layout.addWidget(col2, stretch=1)
        outer_layout.addWidget(col3, stretch=1)

        scroll.setWidget(scroll_content)
        root_layout.addWidget(scroll, stretch=1)

    # ===== Slots =====

    @Slot()
    def _reload_excluded_from_settings(self) -> None:
        """Reload tag chips when patterns change externally (e.g. Ignore button)."""
        patterns = get_excluded_patterns()
        self._tag_chips.set_patterns(patterns)

    @Slot(list)
    def _on_patterns_changed(self, patterns: list) -> None:
        """Handle tag chips change."""
        self._mark_changed()

    @Slot()
    def _mark_changed(self) -> None:
        """Trigger debounced auto-save."""
        self._has_unsaved = True
        self._auto_save_indicator.setText("Auto-saving...")
        self._auto_save_indicator.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {ThemeColors.WARNING};"
        )
        self._auto_save_timer.start()

    @Slot()
    def _save_settings(self) -> None:
        """Internal save logic called by debounced timer or manual triggers."""
        # Collect patterns from tag chips
        patterns = self._tag_chips.get_patterns()
        excluded_text = "\n".join(patterns)

        settings_data = {
            "excluded_folders": excluded_text,
            "use_gitignore": self._gitignore_toggle.isChecked(),
            "enable_security_check": self._security_toggle.isChecked(),
            "include_git_changes": self._git_toggle.isChecked(),
            "use_relative_paths": self._relative_toggle.isChecked(),
        }

        # Luu AI settings rieng qua typed API (tranh merge xung dot voi legacy API)
        update_app_setting(
            ai_api_key=self._ai_api_key_input.text().strip(),
            ai_base_url=self._ai_base_url_input.text().strip()
            or "https://api.openai.com/v1",
            ai_model_id=self._ai_model_combo.currentText().strip(),
            output_language=self._output_language_combo.currentText().strip()
            or "Vietnamese (tiếng Việt có dấu)",
        )

        # Immediate visual feedback
        self._auto_save_indicator.setText("Saving...")

        if save_settings(settings_data):
            self._has_unsaved = False

            # Success feedback
            self._auto_save_indicator.setText("✓ Changes saved")
            self._auto_save_indicator.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {ThemeColors.SUCCESS};"
            )

            # Hide indicator after 3s
            QTimer.singleShot(
                3000,
                lambda: (
                    self._auto_save_indicator.setText("")
                    if not self._has_unsaved
                    else None
                ),
            )

            if self.on_settings_changed:
                self.on_settings_changed()
        else:
            self._auto_save_indicator.setText("⚠ Save failed")
            self._auto_save_indicator.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {ThemeColors.ERROR};"
            )
            self._show_status("Error saving settings", is_error=True)

    def _trigger_auto_save(self) -> None:
        """Helper to trigger the timer."""
        self._mark_changed()

    def _reset_save_btn(self) -> None:
        """Deprecated with auto-save but kept for internal compatibility if needed."""
        pass

    @Slot()
    def _reset_settings(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Reset All Settings",
            "Reset all settings to defaults? This cannot be undone.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Apply defaults
        excluded_raw = DEFAULT_SETTINGS.get("excluded_folders", "")
        default_patterns = [
            p.strip()
            for p in str(excluded_raw).splitlines()
            if p.strip() and not p.strip().startswith("#")
        ]
        self._tag_chips.set_patterns(default_patterns)
        self._gitignore_toggle.setChecked(True)
        self._security_toggle.setChecked(True)
        self._git_toggle.setChecked(True)
        self._relative_toggle.setChecked(True)
        self._output_language_combo.setCurrentText("Vietnamese (tiếng Việt có dấu)")

        # Reset AI Context Builder fields
        self._ai_api_key_input.clear()
        self._ai_base_url_input.setText("https://api.openai.com/v1")
        self._ai_model_combo.clear()

        # Save immediately for destructive actions
        self._save_settings()
        self._show_status("Reset to defaults applied.")

    @Slot(str)
    def _load_preset(self, name: str) -> None:
        if name == "Select profile..." or name not in PRESET_PROFILES:
            return

        preset_text = PRESET_PROFILES[name]
        preset_patterns = [p.strip() for p in preset_text.splitlines() if p.strip()]

        # Merge into existing patterns (avoid duplicates)
        current = self._tag_chips.get_patterns()
        for p in preset_patterns:
            if p not in current:
                current.append(p)

        self._tag_chips.set_patterns(current)

        # Save immediately for preset loads
        self._save_settings()

        # Reset combo to placeholder
        self._preset_combo.blockSignals(True)
        self._preset_combo.setCurrentIndex(0)
        self._preset_combo.blockSignals(False)

        self._show_status(f"Merged {name} preset patterns.")

    @Slot()
    def _clear_session(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear Saved Session",
            "Clear saved session? This will reset your workspace state.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if clear_session_state():
            self._show_status("Session cleared. Restart to see effect.")
        else:
            self._show_status("Failed to clear session", is_error=True)

    @Slot()
    def _export_settings(self) -> None:
        from infrastructure.persistence.settings_manager import load_app_settings

        # Save current UI state first
        self._save_settings()

        app_settings = load_app_settings()
        data = app_settings.to_safe_dict()
        data["export_version"] = "1.0"
        data.pop("instruction_history", None)
        success, _ = copy_to_clipboard(json.dumps(data, indent=2, ensure_ascii=False))
        self._show_status(
            "Settings exported to clipboard" if success else "Export failed",
            is_error=not success,
        )

    def _get_mcp_command(self) -> list[str]:
        """Tự động phát hiện lệnh khởi chạy MCP server."""
        from infrastructure.mcp.config_installer import get_mcp_command

        return get_mcp_command()

    @Slot()
    def _copy_mcp_config(self) -> None:
        """
        Sinh config MCP chuan cho cac IDE chua duoc ho tro chinh thuc.

        Output la JSON theo format mcpServers chuan ma hau het IDE deu ho tro:
        {
          "servers": {
            "synapse": {
              "type": "stdio",
              "command": "...",
              "args": ["--run-mcp"]
            }
          }
        }
        User tu copy/paste vao file config cua IDE minh.
        """
        cmd = self._get_mcp_command()
        entry = {
            # MCP server stdio config chuan cho Synapse Desktop
            "type": "stdio",
            "command": cmd[0],
            "args": cmd[1:],
        }
        config_obj = {
            "servers": {
                "synapse": entry,
            }
        }

        # JSON config chuan cho bat ky IDE nao ho tro MCP
        snippet = json.dumps(config_obj, indent=2, ensure_ascii=False)

        # Dialog preview để user dễ nhìn và có thể chỉnh tay nếu cần
        dlg = QDialog(self)
        dlg.setWindowTitle("Generic IDE MCP Configuration")
        dlg.setMinimumSize(720, 440)
        dlg.setStyleSheet(f"QDialog {{ background: {ThemeColors.BG_SURFACE}; }}")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        info_label = QLabel(
            "Generic MCP config — Copy noi dung ben duoi vao file config cua IDE ban dang dung."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            f"font-size: 12px; color: {ThemeColors.TEXT_SECONDARY};"
        )
        layout.addWidget(info_label)

        layout.addSpacing(4)

        editor = QPlainTextEdit()
        editor.setPlainText(snippet)
        editor.setReadOnly(True)
        editor.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background: {ThemeColors.BG_PAGE};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 12px;
                font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
                font-size: 13px;
            }}
        """
        )
        layout.addWidget(editor, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = _make_ghost_btn("Close")
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(cancel_btn)

        copy_btn = QPushButton("Copy snippet")
        copy_btn.setFixedHeight(36)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {ThemeColors.PRIMARY_HOVER};
            }}
        """
        )

        def _do_copy() -> None:
            success, _ = copy_to_clipboard(snippet)
            self._show_status(
                "Generic MCP config snippet copied!" if success else "Failed to copy",
                is_error=not success,
            )
            if success:
                dlg.accept()

        copy_btn.clicked.connect(_do_copy)
        btn_layout.addWidget(copy_btn)

        layout.addLayout(btn_layout)

        dlg.exec()

    @Slot(str)
    def _ask_workspace_and_install(self, target_name: str) -> None:
        """Hoi nguoi dung chon thu muc workspace roi install."""

        dir_path = QFileDialog.getExistingDirectory(
            self,
            f"Select Workspace Directory for {target_name} Integration",
            options=QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks,
        )
        if not dir_path:
            return  # Nguoi dung huy

        self._install_mcp_for(target_name, workspace_path=dir_path)

    def _install_mcp_for(
        self, target_name: str, workspace_path: Optional[str] = None
    ) -> None:
        """Hien thi preview JSON day du va ghi config vao file neu user dong y."""
        from infrastructure.mcp.config_installer import (
            get_config_path,
            preview_json,
            install_config,
            check_installed,
        )

        config_path = get_config_path(target_name, workspace_path)
        preview_text = preview_json(target_name, workspace_path)

        # Tao custom dialog rong rai de hien thi preview JSON cho de doc
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Install MCP to {target_name}")
        dlg.setMinimumSize(720, 440)
        dlg.setStyleSheet(f"QDialog {{ background: {ThemeColors.BG_SURFACE}; }}")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Thong tin file se ghi
        path_label = QLabel("Config will be written to:")
        path_label.setStyleSheet(
            f"font-size: 13px; color: {ThemeColors.TEXT_SECONDARY};"
        )
        layout.addWidget(path_label)

        path_value = QLabel(str(config_path))
        path_value.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {ThemeColors.PRIMARY};"
            f" font-family: monospace;"
        )
        path_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_value)

        layout.addSpacing(4)

        # Preview JSON trong text editor lon
        preview_label = QLabel("Preview JSON:")
        preview_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {ThemeColors.TEXT_PRIMARY};"
        )
        layout.addWidget(preview_label)

        editor = QPlainTextEdit()
        editor.setPlainText(preview_text)
        editor.setReadOnly(True)
        editor.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background: {ThemeColors.BG_PAGE};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 12px;
                font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
                font-size: 13px;
            }}
        """
        )
        layout.addWidget(editor, stretch=1)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = _make_ghost_btn("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(cancel_btn)

        install_btn = QPushButton("Install")
        install_btn.setFixedHeight(36)
        install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        install_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {ThemeColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {ThemeColors.PRIMARY_HOVER};
            }}
        """
        )
        install_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(install_btn)

        layout.addLayout(btn_layout)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        success, msg = install_config(target_name, workspace_path)

        if success:
            # Tu dong cai dat Agent Skills (SKILL.md) vao thu muc skills cua IDE
            try:
                from infrastructure.mcp.skill_installer import install_skills_for_target

                skill_ok, skill_msg = install_skills_for_target(
                    target_name, workspace_path
                )
                if skill_ok and skill_msg:
                    msg = f"{msg}\\n{skill_msg}"
            except Exception:
                # Loi install skills khong chan luong chinh
                pass

            # Cap nhat trang thai label ngay lap tuc, khong can restart app
            try:
                if check_installed(target_name):
                    label = self._mcp_status_labels.get(target_name)
                    if label is not None:
                        label.setText("\u2713 Installed")
                        label.setStyleSheet(
                            f"font-size: 11px; font-weight: 600; color: {ThemeColors.SUCCESS};"
                        )
            except Exception:
                # Neu viec cap nhat trang thai that bai thi chi log toast, khong chan luong chinh
                pass

        self._show_status(
            f"MCP installed to {target_name}!" if success else msg,
            is_error=not success,
        )

    @Slot()
    def _import_settings(self) -> None:
        success, text = get_clipboard_text()
        if not success or not text:
            self._show_status("Clipboard is empty", is_error=True)
            return

        try:
            imported = json.loads(text)
            if "excluded_folders" not in imported:
                self._show_status("Invalid settings format", is_error=True)
                return
        except json.JSONDecodeError:
            self._show_status("Invalid JSON in clipboard", is_error=True)
            return

        reply = QMessageBox.question(
            self,
            "Import Settings",
            "Import settings from clipboard? This will overwrite current settings.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Apply imported settings
        exc_text = imported.get("excluded_folders", "")
        patterns = [
            p.strip()
            for p in str(exc_text).splitlines()
            if p.strip() and not p.strip().startswith("#")
        ]
        self._tag_chips.set_patterns(patterns)

        self._gitignore_toggle.setChecked(imported.get("use_gitignore", True))
        self._git_toggle.setChecked(imported.get("include_git_changes", True))
        self._relative_toggle.setChecked(imported.get("use_relative_paths", True))
        self._security_toggle.setChecked(imported.get("enable_security_check", True))

        # Import AI Context Builder fields (neu co)
        if "ai_base_url" in imported:
            self._ai_base_url_input.setText(imported.get("ai_base_url", ""))
        if "ai_model_id" in imported:
            model_id = imported.get("ai_model_id", "")
            if model_id:
                self._ai_model_combo.setCurrentText(model_id)

        # Save immediately for imports
        self._save_settings()
        self._show_status("Settings imported from clipboard.")

    # ===== Public API =====

    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved

    # ===== Helpers =====

    def _show_status(self, message: str, is_error: bool = False) -> None:
        """Hien thi thong bao qua he thong toast toan cuc."""
        if not message:
            return

        if is_error:
            toast_error(message)
        else:
            toast_success(message)

    def closeEvent(self, event) -> None:
        """
        Clean up background workers khi Settings view bi dong.

        Dam bao khong con signal nao co the chay vao QWidget da bi huy,
        tranh RuntimeError: Internal C++ object already deleted.
        """
        if self._fetch_worker is not None:
            try:
                signals = getattr(self._fetch_worker, "signals", None)
                if signals is not None:
                    try:
                        signals.finished.disconnect(self._on_models_fetched)
                    except (RuntimeError, TypeError):
                        pass
                    try:
                        signals.error.disconnect()
                    except (RuntimeError, TypeError):
                        pass
            except RuntimeError:
                # Worker hoac signals da bi GC / xoa truoc do
                pass
            finally:
                self._fetch_worker = None

        super().closeEvent(event)

    @Slot()
    def _toggle_api_key_visibility(self) -> None:
        """Toggle API key field giữa hiển thị và ẩn."""
        if self._ai_api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._ai_api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._api_key_eye_btn.setToolTip("Hide API Key")
            self._api_key_eye_btn.setStyleSheet(
                self._api_key_eye_btn.styleSheet().replace(
                    f"color: {ThemeColors.TEXT_MUTED}",
                    f"color: {ThemeColors.PRIMARY}",
                )
            )
        else:
            self._ai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._api_key_eye_btn.setToolTip("Show API Key")
            self._api_key_eye_btn.setStyleSheet(
                self._api_key_eye_btn.styleSheet().replace(
                    f"color: {ThemeColors.PRIMARY}",
                    f"color: {ThemeColors.TEXT_MUTED}",
                )
            )

    @Slot()
    def _fetch_ai_models(self) -> None:
        """
        Goi endpoint /v1/models de lay danh sach model tu server.

        Su dung QRunnable background worker de tranh block main UI thread.
        Network request co the mat toi 15 giay neu server cham.
        """
        from infrastructure.ai.openai_provider import OpenAICompatibleProvider
        from PySide6.QtCore import QThreadPool, QRunnable, QObject, Signal
        from PySide6.QtCore import Slot as QSlot

        api_key = self._ai_api_key_input.text().strip()
        base_url = self._ai_base_url_input.text().strip()

        if not api_key:
            self._show_status("Please enter an API Key first.", is_error=True)
            return

        # Disable button de ngan duplicate requests khi dang fetch
        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("Fetching...")
        self._show_status("Fetching models...")

        # Inner classes cho background worker (khong tao file rieng vi chi dung o day)
        class _FetchSignals(QObject):
            """Signals cho fetch models worker."""

            finished = Signal(list)
            error = Signal(str)

        class _FetchWorker(QRunnable):
            """Background worker goi GET /v1/models."""

            def __init__(self, key: str, url: str) -> None:
                super().__init__()
                self.signals = _FetchSignals()
                self.setAutoDelete(True)
                self._key = key
                self._url = url

            @QSlot()
            def run(self) -> None:
                try:
                    provider = OpenAICompatibleProvider()
                    provider.configure(api_key=self._key, base_url=self._url)
                    models = provider.fetch_available_models()
                    self.signals.finished.emit(models)
                except Exception as e:
                    self.signals.error.emit(str(e))

        worker = _FetchWorker(api_key, base_url)
        # Giu reference de tranh GC truoc khi signal duoc deliver
        self._fetch_worker = worker
        worker.signals.finished.connect(self._on_models_fetched)
        worker.signals.error.connect(self._on_models_fetch_error)
        QThreadPool.globalInstance().start(worker)

    def _on_models_fetched(self, models: list) -> None:
        """
        Callback khi fetch models hoan thanh tren background thread.

        Cap nhat model dropdown voi danh sach models moi.
        """
        self._fetch_worker = None  # Giai phong reference

        # Restore button state
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("Fetch Models")

        if not models:
            self._show_status("No models found on this server.", is_error=True)
            return

        # Luu lai model dang chon truoc khi clear
        current_model = self._ai_model_combo.currentText()

        self._ai_model_combo.blockSignals(True)
        self._ai_model_combo.clear()
        self._ai_model_combo.addItems(models)

        # Khoi phuc lai selection cu neu van con trong list moi
        if current_model in models:
            self._ai_model_combo.setCurrentText(current_model)
        self._ai_model_combo.blockSignals(False)

        self._show_status(f"Fetched {len(models)} models.")

    @Slot(str)
    def _on_models_fetch_error(self, msg: str) -> None:
        """
        Xu ly khi fetch models gap loi tren background worker.

        Dam bao giai phong reference worker va hien thi toast loi ro rang.
        """
        self._fetch_worker = None

        # Restore button state
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("Fetch Models")

        if msg:
            self._show_status(msg, is_error=True)
