"""
Preset Widget — UI component cho Context Presets.

Layout compact:
┌─────────────────────────────────────────────┐
│ Presets ▾ [preset_combo    ] [💾] [🗑️] [⋮] │
└─────────────────────────────────────────────┘
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from presentation.views.context.preset_controller import PresetController

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QComboBox,
    QToolButton,
    QLabel,
    QInputDialog,
    QMessageBox,
    QMenu,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCursor

from presentation.config.theme import ThemeColors

import logging

logger = logging.getLogger(__name__)


class PresetWidget(QWidget):
    """Compact preset selector widget."""

    def __init__(
        self,
        controller: "PresetController",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._is_refreshing = False

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("Presets")
        label.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {ThemeColors.TEXT_SECONDARY};"
        )
        layout.addWidget(label)

        self._combo = QComboBox()
        self._combo.setFixedHeight(28)
        self._combo.setMinimumWidth(120)
        self._combo.setStyleSheet(f"""
            QComboBox {{
                background: {ThemeColors.BG_ELEVATED};
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QComboBox:hover {{
                border-color: {ThemeColors.PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 16px;
            }}
            QComboBox QAbstractItemView {{
                background: {ThemeColors.BG_SURFACE};
                color: {ThemeColors.TEXT_PRIMARY};
                selection-background-color: {ThemeColors.PRIMARY};
                selection-color: white;
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 4px;
                padding: 2px;
            }}
        """)
        self._combo.addItem("— Select preset —", "")
        layout.addWidget(self._combo, stretch=1)

        btn_style = (
            f"QToolButton {{ "
            f"  background: transparent; border: 1px solid {ThemeColors.BORDER}; "
            f"  border-radius: 4px; padding: 3px; "
            f"  color: {ThemeColors.TEXT_SECONDARY}; font-size: 13px; "
            f"}} "
            f"QToolButton:hover {{ "
            f"  background: {ThemeColors.BG_HOVER}; "
            f"  color: {ThemeColors.TEXT_PRIMARY}; "
            f"  border-color: {ThemeColors.BORDER_LIGHT}; "
            f"}}"
        )

        self._save_btn = QToolButton()
        self._save_btn.setText("💾")
        self._save_btn.setFixedSize(28, 28)
        self._save_btn.setToolTip("Save current selection as preset")
        self._save_btn.setStyleSheet(btn_style)
        self._save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout.addWidget(self._save_btn)

        self._delete_btn = QToolButton()
        self._delete_btn.setText("🗑️")
        self._delete_btn.setFixedSize(28, 28)
        self._delete_btn.setToolTip("Delete selected preset")
        self._delete_btn.setStyleSheet(btn_style)
        self._delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._delete_btn.setEnabled(False)
        layout.addWidget(self._delete_btn)

        self._menu_btn = QToolButton()
        self._menu_btn.setText("⋮")
        self._menu_btn.setFixedSize(28, 28)
        self._menu_btn.setToolTip("More options")
        self._menu_btn.setStyleSheet(btn_style)
        self._menu_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._menu_btn.setEnabled(False)
        layout.addWidget(self._menu_btn)

    def _connect_signals(self) -> None:
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        self._menu_btn.clicked.connect(self._on_menu_clicked)

        self._controller.presets_changed.connect(self._refresh_combo)
        self._controller.preset_loaded.connect(self._on_preset_loaded)

    def connect_selection_changed(self, signal) -> None:
        """Connect to file tree selection changed signal để update dirty state."""
        signal.connect(self._on_selection_changed_external)

    @Slot()
    def _on_selection_changed_external(self) -> None:
        """Handle external selection change — refresh dirty indicator."""
        if self._controller.get_active_preset_id():
            self._refresh_combo()

    def refresh(self) -> None:
        """Refresh combo box từ controller data."""
        self._refresh_combo()

    def trigger_save_action(self) -> None:
        """Public API để trigger save preset action."""
        self._on_save_clicked()

    def focus_selector(self) -> None:
        """Public API để focus combo box."""
        if hasattr(self, "_combo") and self._combo:
            self._combo.setFocus()
            self._combo.showPopup()

    @Slot()
    def _refresh_combo(self) -> None:
        """Rebuild combo items từ PresetController."""
        self._is_refreshing = True

        current_id = self._combo.currentData()

        self._combo.clear()
        self._combo.addItem("— Select preset —", "")

        presets = self._controller.list_presets()

        if not presets:
            # Empty state message
            self._combo.addItem("(No presets saved yet)", "")
            # type: ignore[missing-attribute]
            self._combo.model().item(1).setEnabled(False)  # type: ignore

        for entry in presets:
            file_count = len(entry.selected_paths)
            display = f"{entry.name} ({file_count} files)"

            # Add dirty indicator
            if entry.preset_id == self._controller.get_active_preset_id():
                if self._controller.is_selection_dirty():
                    display = f"* {display}"

            self._combo.addItem(display, entry.preset_id)

        if current_id:
            idx = self._combo.findData(current_id)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

        self._is_refreshing = False
        self._update_button_states()

    @Slot(int)
    def _on_combo_changed(self, index: int) -> None:
        """Handle combo selection change — auto-load preset."""
        if self._is_refreshing:
            return

        preset_id = self._combo.currentData()
        self._update_button_states()

        if preset_id:
            if not self._controller.load_preset(preset_id):
                # Revert to "Select preset" state if loading fails
                self._is_refreshing = True
                self._combo.setCurrentIndex(0)
                self._is_refreshing = False
                self._update_button_states()

    @Slot(str)
    def _on_preset_loaded(self, preset_id: str) -> None:
        """Sync combo khi preset được load."""
        if self._is_refreshing:
            return

        self._is_refreshing = True
        idx = self._combo.findData(preset_id)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        self._is_refreshing = False
        self._update_button_states()

    @Slot()
    def _on_save_clicked(self) -> None:
        """Save logic: update existing or create new."""
        active_id = self._combo.currentData()

        if active_id:
            reply = QMessageBox.question(
                self,
                "Update Preset",
                "Update preset with current selection?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._controller.update_preset(active_id)
        else:
            name, ok = QInputDialog.getText(
                self,
                "New Preset",
                "Preset name:",
            )
            if ok and name.strip():
                self._controller.create_preset(name.strip())

    @Slot()
    def _on_delete_clicked(self) -> None:
        """Delete preset với confirm dialog."""
        preset_id = self._combo.currentData()
        if not preset_id:
            return

        preset_name = self._combo.currentText()
        reply = QMessageBox.warning(
            self,
            "Delete Preset",
            f"Delete preset '{preset_name}'? This cannot be undone.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._controller.delete_preset(preset_id)
            self._combo.setCurrentIndex(0)

    @Slot()
    def _on_menu_clicked(self) -> None:
        """Show context menu với more options."""
        preset_id = self._combo.currentData()
        if not preset_id:
            return

        menu = QMenu(self)
        rename_action = menu.addAction("Rename...")
        duplicate_action = menu.addAction("Duplicate")

        action = menu.exec(QCursor.pos())

        if action == rename_action:
            self._rename_preset(preset_id)
        elif action == duplicate_action:
            self._controller.duplicate_preset(preset_id)

    def _rename_preset(self, preset_id: str) -> None:
        """Rename preset dialog."""
        current_name = self._combo.currentText().split(" (")[0].lstrip("* ")

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Preset",
            "New name:",
            text=current_name,
        )
        if ok and new_name.strip():
            self._controller.rename_preset(preset_id, new_name.strip())

    def _update_button_states(self) -> None:
        """Enable/disable buttons dựa trên combo state."""
        has_selection = bool(self._combo.currentData())
        self._delete_btn.setEnabled(has_selection)
        self._menu_btn.setEnabled(has_selection)

        if has_selection:
            self._save_btn.setToolTip("Update this preset with current selection")
        else:
            self._save_btn.setToolTip("Save current selection as new preset")
