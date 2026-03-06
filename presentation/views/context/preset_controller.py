"""
PresetController — Controller quản lý Context Presets.

Theo composition pattern giống TreeManagementController:
- Nhận ViewProtocol qua constructor
- QObject để sử dụng Slot decorator
- Quản lý PresetStore lifecycle
"""

from pathlib import Path
from typing import Optional, List, Protocol, runtime_checkable

from PySide6.QtCore import QObject, Signal

from services.preset_store import PresetStore, PresetEntry

import logging

logger = logging.getLogger(__name__)


@runtime_checkable
class PresetViewProtocol(Protocol):
    """Protocol định nghĩa những gì PresetController cần từ View."""

    def get_workspace(self) -> "Path | None":
        """Trả về workspace path hiện tại."""
        ...

    def get_selected_paths(self) -> "set[str]":
        """Trả về danh sách selected file paths (absolute)."""
        ...

    def get_instructions_text(self) -> str:
        """Trả về nội dung instructions field."""
        ...

    def get_output_style(self) -> object:
        """Trả về output style hiện tại."""
        ...

    def set_selected_paths_from_preset(self, paths: "set[str]") -> None:
        """Apply selection từ preset (replace toàn bộ selection hiện tại)."""
        ...

    def set_instructions_text(self, text: str) -> None:
        """Set nội dung instructions field."""
        ...

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Hiển thị status message."""
        ...


class PresetController(QObject):
    """
    Controller quản lý Context Presets.

    Signals:
        presets_changed: Emitted khi danh sách presets thay đổi.
        preset_loaded(str): Emitted với preset_id khi preset được load.
    """

    presets_changed = Signal()
    preset_loaded = Signal(str)

    def __init__(
        self,
        view: PresetViewProtocol,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._store: Optional[PresetStore] = None
        self._active_preset_id: Optional[str] = None

    def on_workspace_changed(self, workspace_path: Path) -> None:
        """Khởi tạo/reset PresetStore khi workspace thay đổi."""
        self._store = PresetStore(workspace_path)
        self._active_preset_id = None
        self.presets_changed.emit()

    def cleanup(self) -> None:
        """Cleanup resources."""
        self._store = None
        self._active_preset_id = None

    def list_presets(self) -> List[PresetEntry]:
        """Trả về danh sách presets cho UI hiển thị."""
        if self._store is None:
            return []
        return self._store.list_presets()

    def get_active_preset_id(self) -> Optional[str]:
        """Trả về ID của preset đang active."""
        return self._active_preset_id

    def is_selection_dirty(self) -> bool:
        """Check xem selection hiện tại có khác với active preset không."""
        if not self._active_preset_id or not self._store:
            return False

        entry = self._store.get_preset(self._active_preset_id)
        if not entry:
            return False

        current_paths = set(self._view.get_selected_paths())
        preset_paths = set(self._store.to_absolute_paths(entry.selected_paths))

        return current_paths != preset_paths

    def create_preset(self, name: str) -> Optional[PresetEntry]:
        """Tạo preset mới từ selection hiện tại."""
        if self._store is None:
            self._view.show_status("No workspace open", is_error=True)
            return None

        name = name.strip()
        if not name:
            self._view.show_status("Preset name cannot be empty", is_error=True)
            return None

        selected = list(self._view.get_selected_paths())
        if not selected:
            self._view.show_status(
                "No files selected. Select files before saving a preset.",
                is_error=True,
            )
            return None

        instructions = self._view.get_instructions_text()
        output_style = self._view.get_output_style()
        format_id = getattr(output_style, "value", "")

        entry = self._store.create_preset(
            name=name,
            selected_paths=selected,
            instructions=instructions,
            output_format=format_id,
        )

        self._active_preset_id = entry.preset_id
        self._view.show_status(f"Preset '{name}' saved ({len(selected)} files)")
        self.presets_changed.emit()
        self.preset_loaded.emit(entry.preset_id)

        return entry

    def load_preset(self, preset_id: str) -> bool:
        """Load preset — apply selection + instructions vào view."""
        if self._store is None:
            return False

        entry = self._store.get_preset(preset_id)
        if entry is None:
            self._view.show_status("Preset not found", is_error=True)
            return False

        absolute_paths = self._store.to_absolute_paths(entry.selected_paths)
        missing_count = len(entry.selected_paths) - len(absolute_paths)

        if not absolute_paths:
            self._view.show_status(
                f"All {len(entry.selected_paths)} files in preset no longer exist",
                is_error=True,
            )
            return False

        self._view.set_selected_paths_from_preset(set(absolute_paths))

        if entry.instructions:
            self._view.set_instructions_text(entry.instructions)

        self._active_preset_id = preset_id

        status = f"Loaded '{entry.name}' ({len(absolute_paths)} files)"
        if missing_count > 0:
            status += f" — {missing_count} files no longer exist"

        self._view.show_status(status)
        self.preset_loaded.emit(preset_id)

        return True

    def update_preset(self, preset_id: str) -> bool:
        """Cập nhật preset với selection hiện tại."""
        if self._store is None:
            return False

        selected = list(self._view.get_selected_paths())
        if not selected:
            self._view.show_status("No files selected", is_error=True)
            return False

        instructions = self._view.get_instructions_text()
        output_style = self._view.get_output_style()
        format_id = getattr(output_style, "value", "")

        entry = self._store.update_preset(
            preset_id=preset_id,
            selected_paths=selected,
            instructions=instructions,
            output_format=format_id,
        )

        if entry is None:
            self._view.show_status("Preset not found", is_error=True)
            return False

        self._view.show_status(f"Preset '{entry.name}' updated ({len(selected)} files)")
        self.presets_changed.emit()
        return True

    def delete_preset(self, preset_id: str) -> bool:
        """Xóa preset."""
        if self._store is None:
            return False

        entry = self._store.get_preset(preset_id)
        name = entry.name if entry else "Unknown"

        if self._store.delete_preset(preset_id):
            if self._active_preset_id == preset_id:
                self._active_preset_id = None
            self._view.show_status(f"Preset '{name}' deleted")
            self.presets_changed.emit()
            return True

        self._view.show_status("Failed to delete preset", is_error=True)
        return False

    def rename_preset(self, preset_id: str, new_name: str) -> bool:
        """Đổi tên preset."""
        if self._store is None:
            return False

        new_name = new_name.strip()
        if not new_name:
            self._view.show_status("Name cannot be empty", is_error=True)
            return False

        entry = self._store.rename_preset(preset_id, new_name)
        if entry is None:
            self._view.show_status("Preset not found", is_error=True)
            return False

        self._view.show_status(f"Preset renamed to '{new_name}'")
        self.presets_changed.emit()
        return True

    def duplicate_preset(self, preset_id: str) -> Optional[PresetEntry]:
        """Duplicate preset với tên mới."""
        if self._store is None:
            return None

        entry = self._store.get_preset(preset_id)
        if entry is None:
            return None

        new_name = f"{entry.name} (Copy)"
        new_entry = self._store.create_preset(
            name=new_name,
            selected_paths=self._store.to_absolute_paths(entry.selected_paths),
            instructions=entry.instructions,
            output_format=entry.output_format,
        )

        self._view.show_status(f"Preset duplicated as '{new_name}'")
        self.presets_changed.emit()
        return new_entry
