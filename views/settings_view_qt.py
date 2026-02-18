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
)
from PySide6.QtCore import Qt, Slot, QTimer, Signal

from core.theme import ThemeColors
from components.toggle_switch import ToggleSwitch
from components.tag_chips_widget import TagChipsWidget
from services.clipboard_utils import copy_to_clipboard, get_clipboard_text
from services.session_state import clear_session_state
from services.settings_manager import load_settings, save_settings, DEFAULT_SETTINGS
from components.toast_qt import toast_success, toast_error


# ============================================================
# Re-exports tu services.workspace_config (backward compatibility)
# Cac functions nay da duoc extract sang services/workspace_config.py
# de tuan thu Dependency Inversion Principle.
# ============================================================
from services.workspace_config import (  # noqa: F401
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
    btn = QPushButton(text)
    btn.setFixedHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background: transparent;
            color: {ThemeColors.TEXT_PRIMARY};
            border: 1px solid {ThemeColors.BORDER};
            border-radius: 8px;
            padding: 0 16px;
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
    btn = QPushButton(text)
    btn.setFixedHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background: transparent;
            color: {ThemeColors.ERROR};
            border: 1px solid {ThemeColors.ERROR}50;
            border-radius: 8px;
            padding: 0 16px;
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

        # Debounced auto-save timer (800ms)
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(800)
        self._auto_save_timer.timeout.connect(self._save_settings)

        self._build_ui()
        _excluded_notifier.excluded_changed.connect(self._reload_excluded_from_settings)

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

        card2_layout.addSpacing(16)
        card2_layout.addWidget(_make_separator())
        card2_layout.addSpacing(16)

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
        col2_layout.addStretch()

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
        patterns = self._tag_chips.get_patterns()
        data = {
            "excluded_folders": "\n".join(patterns),
            "use_gitignore": self._gitignore_toggle.isChecked(),
            "include_git_changes": self._git_toggle.isChecked(),
            "use_relative_paths": self._relative_toggle.isChecked(),
            "enable_security_check": self._security_toggle.isChecked(),
            "export_version": "1.0",
        }
        success, _ = copy_to_clipboard(json.dumps(data, indent=2, ensure_ascii=False))
        self._show_status(
            "Settings exported to clipboard" if success else "Export failed",
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
