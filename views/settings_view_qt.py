"""
Settings View (PySide6) - Tab cấu hình excluded folders, gitignore, security.

PySide6-only implementation.
"""

import json
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QCheckBox,
    QComboBox,
    QFrame,
)
from PySide6.QtCore import Qt, Slot, QTimer, QObject, Signal

from core.theme import ThemeColors
from services.clipboard_utils import copy_to_clipboard, get_clipboard_text
from services.session_state import clear_session_state
from services.settings_manager import load_settings, save_settings


PRESET_PROFILES = {
    "Node.js": "node_modules\ndist\nbuild\n.next\ncoverage\npackage-lock.json\npnpm-lock.yaml\nyarn.lock",
    "Python": "__pycache__\n.pytest_cache\n.venv\nvenv\nbuild\ndist\n*.pyc\n.mypy_cache",
    "Java": "target\nout\n.gradle\n.classpath\n.project\n.settings",
    "Go": "vendor\nbin\ndist\ncoverage.out",
}


def get_excluded_patterns() -> list[str]:
    """Return normalized exclude patterns from settings."""
    raw = load_settings().get("excluded_folders", "")
    patterns: list[str] = []
    for line in raw.splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        patterns.append(value)
    return patterns


def get_use_gitignore() -> bool:
    """Return whether .gitignore should be respected."""
    return bool(load_settings().get("use_gitignore", True))


def get_use_relative_paths() -> bool:
    """Return whether to use workspace-relative paths in prompts (tranh PII)."""
    return bool(load_settings().get("use_relative_paths", True))


class _ExcludedChangedNotifier(QObject):
    """Notifier emit khi excluded patterns thay đổi từ bên ngoài (vd. Ignore button)."""

    excluded_changed = Signal()


_excluded_notifier = _ExcludedChangedNotifier()


def add_excluded_patterns(patterns: list[str]) -> bool:
    """Append new exclude patterns, avoiding duplicates."""
    settings = load_settings()
    existing = get_excluded_patterns()
    merged = existing[:]
    for pattern in patterns:
        normalized = pattern.strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    settings["excluded_folders"] = "\n".join(merged)
    if save_settings(settings):
        _excluded_notifier.excluded_changed.emit()
        return True
    return False


def remove_excluded_patterns(patterns: list[str]) -> bool:
    """Remove exclude patterns from settings."""
    to_remove = {p.strip() for p in patterns if p.strip()}
    settings = load_settings()
    existing = get_excluded_patterns()
    filtered = [p for p in existing if p not in to_remove]
    settings["excluded_folders"] = "\n".join(filtered)
    if save_settings(settings):
        _excluded_notifier.excluded_changed.emit()
        return True
    return False


class SettingsViewQt(QWidget):
    """View cho Settings tab — PySide6 version."""

    def __init__(
        self,
        on_settings_changed: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.on_settings_changed = on_settings_changed
        self._has_unsaved = False
        self._build_ui()
        _excluded_notifier.excluded_changed.connect(self._reload_excluded_from_settings)

    def _build_ui(self) -> None:
        settings = load_settings()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ===== Left Column: Configuration =====
        left = QFrame()
        left.setProperty("class", "surface")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(12)

        # Header
        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("⚙️"))
        conf_title = QLabel("Configuration")
        conf_title.setStyleSheet(
            f"font-weight: 600; font-size: 16px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        left_header.addWidget(conf_title)
        left_header.addStretch()
        left_layout.addLayout(left_header)

        # File Tree Options
        left_layout.addWidget(self._section_header("File Tree Options"))

        self._gitignore_cb = QCheckBox("Respect .gitignore")
        self._gitignore_cb.setChecked(settings.get("use_gitignore", True))
        self._gitignore_cb.stateChanged.connect(self._mark_changed)
        left_layout.addWidget(self._gitignore_cb)
        left_layout.addWidget(
            self._hint_label("Hide files matching .gitignore patterns")
        )

        # AI Context
        left_layout.addWidget(self._section_header("AI Context"))

        self._git_include_cb = QCheckBox("Include Git Diff/Log")
        self._git_include_cb.setChecked(settings.get("include_git_changes", True))
        self._git_include_cb.stateChanged.connect(self._mark_changed)
        left_layout.addWidget(self._git_include_cb)
        left_layout.addWidget(self._hint_label("Include recent git changes in context"))

        self._relative_paths_cb = QCheckBox("Use relative paths in prompts")
        self._relative_paths_cb.setChecked(settings.get("use_relative_paths", True))
        self._relative_paths_cb.stateChanged.connect(self._mark_changed)
        left_layout.addWidget(self._relative_paths_cb)
        left_layout.addWidget(
            self._hint_label("Paths relative to workspace (avoids PII in shared prompts)")
        )

        # Security
        left_layout.addWidget(self._section_header("Security"))

        self._security_cb = QCheckBox("Enable Security Check")
        self._security_cb.setChecked(settings.get("enable_security_check", True))
        self._security_cb.stateChanged.connect(self._mark_changed)
        left_layout.addWidget(self._security_cb)
        left_layout.addWidget(self._hint_label("Scan for secrets before copying"))

        # Presets
        left_layout.addWidget(self._section_header("Quick Presets"))

        self._preset_combo = QComboBox()
        self._preset_combo.addItem("Select a profile...")
        for name in PRESET_PROFILES:
            self._preset_combo.addItem(name)
        self._preset_combo.currentTextChanged.connect(self._load_preset)
        left_layout.addWidget(self._preset_combo)

        # Session
        left_layout.addWidget(self._section_header("Session"))

        clear_session_btn = QPushButton("Clear Saved Session")
        clear_session_btn.setProperty("class", "outlined")
        clear_session_btn.clicked.connect(self._clear_session)
        left_layout.addWidget(clear_session_btn)
        left_layout.addWidget(self._hint_label("Resets workspace and open files state"))

        left_layout.addStretch()

        # Save / Reset buttons
        save_btn = QPushButton("Save Settings")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self._save_settings)
        left_layout.addWidget(save_btn)

        action_row = QHBoxLayout()
        reset_btn = QPushButton("Reset")
        reset_btn.setProperty("class", "outlined")
        reset_btn.clicked.connect(self._reset_settings)
        action_row.addWidget(reset_btn)

        export_btn = QPushButton("Export")
        export_btn.setProperty("class", "outlined")
        export_btn.clicked.connect(self._export_settings)
        action_row.addWidget(export_btn)

        import_btn = QPushButton("Import")
        import_btn.setProperty("class", "outlined")
        import_btn.clicked.connect(self._import_settings)
        action_row.addWidget(import_btn)
        left_layout.addLayout(action_row)

        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size: 12px;")
        left_layout.addWidget(self._status)

        splitter.addWidget(left)

        # ===== Right Column: Excluded Patterns =====
        right = QFrame()
        right.setProperty("class", "surface")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(12)

        right_header = QHBoxLayout()
        right_header.addWidget(QLabel("📁"))
        exc_title = QLabel("Excluded Patterns")
        exc_title.setStyleSheet(
            f"font-weight: 600; font-size: 16px; color: {ThemeColors.TEXT_PRIMARY};"
        )
        right_header.addWidget(exc_title)
        right_header.addStretch()
        right_layout.addLayout(right_header)

        info = QLabel(
            "ℹ️ Exclude files/folders from File Tree & AI Context. One pattern per line."
        )
        info.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_MUTED};")
        info.setWordWrap(True)
        right_layout.addWidget(info)

        self._excluded_field = QPlainTextEdit()
        self._excluded_field.setPlainText(settings.get("excluded_folders", ""))
        self._excluded_field.setPlaceholderText(
            "node_modules\ndist\nbuild\n__pycache__"
        )
        self._excluded_field.textChanged.connect(self._mark_changed)
        right_layout.addWidget(self._excluded_field, stretch=1)

        splitter.addWidget(right)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    # ===== Helpers =====

    def _section_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; "
            f"color: {ThemeColors.TEXT_SECONDARY}; margin-top: 10px;"
        )
        return label

    def _hint_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"font-size: 12px; color: {ThemeColors.TEXT_MUTED};")
        return label

    # ===== Slots =====

    @Slot()
    def _reload_excluded_from_settings(self) -> None:
        """Cập nhật nội dung excluded field từ settings (khi user ignore item từ Context tab)."""
        settings = load_settings()
        new_text = settings.get("excluded_folders", "")
        self._excluded_field.blockSignals(True)
        self._excluded_field.setPlainText(new_text)
        self._excluded_field.blockSignals(False)

    @Slot()
    def _mark_changed(self) -> None:
        self._has_unsaved = True

    @Slot()
    def _save_settings(self) -> None:
        settings_data = {
            "excluded_folders": self._excluded_field.toPlainText(),
            "use_gitignore": self._gitignore_cb.isChecked(),
            "enable_security_check": self._security_cb.isChecked(),
            "include_git_changes": self._git_include_cb.isChecked(),
            "use_relative_paths": self._relative_paths_cb.isChecked(),
        }
        if save_settings(settings_data):
            self._has_unsaved = False
            self._show_status("Settings saved!")
            if self.on_settings_changed:
                self.on_settings_changed()
        else:
            self._show_status("Error saving settings", is_error=True)

    @Slot()
    def _reset_settings(self) -> None:
        default = "node_modules\ndist\nbuild\n.next\n__pycache__\n.pytest_cache\npnpm-lock.yaml\npackage-lock.json\ncoverage"
        self._excluded_field.setPlainText(default)
        self._gitignore_cb.setChecked(True)
        self._security_cb.setChecked(True)
        self._git_include_cb.setChecked(True)
        self._relative_paths_cb.setChecked(True)
        self._show_status("Reset to defaults (not saved yet)")

    @Slot(str)
    def _load_preset(self, name: str) -> None:
        if name == "Select a profile..." or name not in PRESET_PROFILES:
            return
        current = self._excluded_field.toPlainText().rstrip()
        preset = PRESET_PROFILES[name]
        if current:
            self._excluded_field.setPlainText(f"{current}\n# {name} preset\n{preset}")
        else:
            self._excluded_field.setPlainText(f"# {name} preset\n{preset}")
        self._show_status(f"Loaded {name} preset (not saved yet)")

    @Slot()
    def _clear_session(self) -> None:
        if clear_session_state():
            self._show_status("Session cleared. Restart to see effect.")
        else:
            self._show_status("Failed to clear session", is_error=True)

    @Slot()
    def _export_settings(self) -> None:
        data = {
            "excluded_folders": self._excluded_field.toPlainText(),
            "use_gitignore": self._gitignore_cb.isChecked(),
            "include_git_changes": self._git_include_cb.isChecked(),
            "use_relative_paths": self._relative_paths_cb.isChecked(),
            "export_version": "1.0",
        }
        success, _ = copy_to_clipboard(json.dumps(data, indent=2, ensure_ascii=False))
        self._show_status(
            "Exported to clipboard!" if success else "Export failed", not success
        )

    @Slot()
    def _import_settings(self) -> None:
        success, text = get_clipboard_text()
        if not success or not text:
            self._show_status("Clipboard empty", is_error=True)
            return
        try:
            imported = json.loads(text)
            if "excluded_folders" not in imported:
                self._show_status("Invalid settings format", is_error=True)
                return
            self._excluded_field.setPlainText(imported.get("excluded_folders", ""))
            self._gitignore_cb.setChecked(imported.get("use_gitignore", True))
            self._git_include_cb.setChecked(imported.get("include_git_changes", True))
            self._relative_paths_cb.setChecked(
                imported.get("use_relative_paths", True)
            )
            self._show_status("Imported! Click Save to apply.")
        except json.JSONDecodeError:
            self._show_status("Invalid JSON in clipboard", is_error=True)

    # ===== Public =====

    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved

    def _show_status(self, message: str, is_error: bool = False) -> None:
        color = ThemeColors.ERROR if is_error else ThemeColors.SUCCESS
        self._status.setStyleSheet(f"font-size: 12px; color: {color};")
        self._status.setText(message)
        if not is_error:
            QTimer.singleShot(4000, lambda: self._status.setText(""))
