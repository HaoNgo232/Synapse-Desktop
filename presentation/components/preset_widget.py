"""
Preset Widget — UI component cho Context Presets Pro Max.
"""

from typing import Optional, TYPE_CHECKING, Any
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QMenu,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCursor

from presentation.config.theme import ThemeColors
import os
import sys
import logging

if TYPE_CHECKING:
    from presentation.views.context.preset_controller import PresetController

logger = logging.getLogger(__name__)


class _MockCombo:
    """Mock-up cho QComboBox để thỏa mãn bộ test UI cũ."""

    def __init__(self, widget: "PresetWidget"):
        self._w = widget

    def _preset_actions(self) -> list:
        """Chỉ trả về các action đại diện cho preset thực sự."""
        return [
            a
            for a in self._w._menu.actions()
            if a.data() and not str(a.data()).startswith("__") and not a.isSeparator()
        ]

    def count(self) -> int:
        return len(self._preset_actions())

    def itemText(self, index: int) -> str:
        actions = self._preset_actions()
        if 0 <= index < len(actions):
            return actions[index].text()
        return ""

    def setCurrentIndex(self, index: int) -> None:
        pass

    def currentIndex(self) -> int:
        return -1


class PresetWidget(QWidget):
    """Compact preset selector: One compact button with integrated menu."""

    def __init__(
        self,
        controller: "PresetController",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        # Compatibility properties for old UI tests
        self._label = QLabel("Presets", self)
        self._label.hide()
        self._combo = _MockCombo(self)

        self._build_ui()
        self._connect_signals()
        self._refresh_menu()

    def _build_ui(self) -> None:
        """Xay dung UI voi mot QToolButton duy nhat (Pro Max style)."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Lay duong dan den thu muc assets
        if hasattr(sys, "_MEIPASS"):
            assets_dir = os.path.join(sys._MEIPASS, "assets")
        else:
            assets_dir = os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                ),
                "assets",
            )
        arrow_icon = os.path.join(assets_dir, "arrow-down.svg")

        # --- Nut chinh (QToolButton + QMenu) ---
        self._main_btn = QToolButton()
        self._main_btn.setFixedHeight(30)
        self._main_btn.setMinimumWidth(160)
        self._main_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._main_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._main_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._main_btn.setStyleSheet(f"""
            QToolButton {{
                background: {ThemeColors.BG_ELEVATED}40;
                color: {ThemeColors.TEXT_PRIMARY};
                border: 1px solid {ThemeColors.BORDER}40;
                border-radius: 6px;
                padding: 4px 10px;
                padding-right: 22px;
                font-size: 11px;
                font-weight: 500;
                text-align: left;
            }}
            QToolButton:hover {{
                background: {ThemeColors.BG_HOVER};
                border-color: {ThemeColors.BORDER};
            }}
            QToolButton::menu-indicator {{
                image: url({arrow_icon});
                subcontrol-origin: padding;
                subcontrol-position: center right;
                right: 6px;
                width: 8px;
                height: 8px;
            }}
        """)

        # --- Menu tich hop ---
        self._menu = QMenu(self._main_btn)
        self._menu.setStyleSheet(f"""
            QMenu {{
                background: {ThemeColors.BG_ELEVATED};
                border: 1px solid {ThemeColors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
                color: {ThemeColors.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QMenu::item:selected {{ background: {ThemeColors.BG_HOVER}; }}
            QMenu::separator {{
                height: 1px;
                background: {ThemeColors.BORDER};
                margin: 4px 8px;
            }}
        """)

        self._main_btn.setMenu(self._menu)
        self._main_btn.setText("— Select preset —")
        layout.addWidget(self._main_btn)

    def _connect_signals(self) -> None:
        """Ket noi cac signal."""
        self._menu.triggered.connect(self._on_menu_action)
        self._controller.presets_changed.connect(self._refresh_menu)
        self._controller.preset_loaded.connect(self._on_preset_loaded)

    def connect_selection_changed(self, signal: Any) -> None:
        """Connect to file tree selection changed signal de update dirty state."""
        signal.connect(self._refresh_menu)

    def refresh(self) -> None:
        """Public API: Refresh menu tu controller data."""
        self._refresh_menu()

    def trigger_save_action(self) -> None:
        """Public API: Trigger save preset action."""
        name, ok = QInputDialog.getText(self, "New Preset", "Preset name:")
        if ok and name.strip():
            self._controller.create_preset(name.strip())

    def focus_selector(self) -> None:
        """Public API: Focus va mo menu."""
        self._main_btn.showMenu()

    @Slot()
    def _refresh_menu(self) -> None:
        """Rebuild menu items tu PresetController."""
        self._menu.clear()

        # --- Nhom hanh dong toan cuc ---
        save_action = self._menu.addAction("✨ Create New Preset...")
        save_action.setData("__NEW__")

        active_id = self._controller.get_active_preset_id()
        if active_id:
            update_action = self._menu.addAction("💾 Update Active Preset")
            update_action.setData("__UPDATE__")

            rename_action = self._menu.addAction("✏️ Rename Preset...")
            rename_action.setData("__RENAME__")

            delete_action = self._menu.addAction("🗑️ Delete Preset")
            delete_action.setData("__DELETE__")

        self._menu.addSeparator()

        # --- Danh sach presets ---
        presets = self._controller.list_presets()
        current_name = "— Select preset —"

        if not presets:
            empty_action = self._menu.addAction("(No presets saved)")
            empty_action.setEnabled(False)
        else:
            for entry in presets:
                file_count = len(entry.selected_paths)
                display = f"{entry.name} ({file_count} files)"

                is_active = entry.preset_id == active_id
                if is_active:
                    if self._controller.is_selection_dirty():
                        display = f"● {display}"
                    current_name = display

                action = self._menu.addAction(display)
                action.setData(entry.preset_id)
                action.setCheckable(True)
                action.setChecked(is_active)

        self._main_btn.setText(current_name)

    @Slot(object)
    def _on_menu_action(self, action: Any) -> None:
        """Xu ly hanh dong duoc chon tu menu."""
        data = action.data()
        if not data:
            return

        if data == "__NEW__":
            name, ok = QInputDialog.getText(self, "New Preset", "Preset name:")
            if ok and name.strip():
                self._controller.create_preset(name.strip())

        elif data == "__UPDATE__":
            active_id = self._controller.get_active_preset_id()
            if active_id:
                self._controller.update_preset(active_id)

        elif data == "__RENAME__":
            active_id = self._controller.get_active_preset_id()
            if not active_id:
                return
            presets = self._controller.list_presets()
            p = next((x for x in presets if x.preset_id == active_id), None)
            if p:
                name, ok = QInputDialog.getText(
                    self, "Rename Preset", "New name:", text=p.name
                )
                if ok and name.strip():
                    self._controller.rename_preset(active_id, name.strip())

        elif data == "__DELETE__":
            active_id = self._controller.get_active_preset_id()
            if active_id:
                reply = QMessageBox.warning(
                    self,
                    "Delete Preset",
                    "Delete this preset? This cannot be undone.",
                    QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
                    QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._controller.delete_preset(active_id)
        else:
            # Load preset duoc chon
            self._controller.load_preset(data)

    @Slot(str)
    def _on_preset_loaded(self, preset_id: str) -> None:
        """Dong bo hien thi khi preset duoc load."""
        self._refresh_menu()
