from abc import ABC, abstractmethod
from typing import Optional, List
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PresetEntry:
    """Một preset chứa snapshot selection state."""

    preset_id: str
    name: str
    selected_paths: List[str]
    instructions: str = ""
    output_format: str = ""
    created_at: str = ""
    updated_at: str = ""


class IPresetStore(ABC):
    """
    Interface cho PresetStore quản lý context presets.
    """

    @abstractmethod
    def list_presets(self) -> List[PresetEntry]:
        """Trả về tất cả presets."""
        pass

    @abstractmethod
    def get_preset(self, preset_id: str) -> Optional[PresetEntry]:
        """Lấy preset theo ID."""
        pass

    @abstractmethod
    def create_preset(
        self,
        name: str,
        selected_paths: List[str],
        instructions: str = "",
        output_format: str = "",
    ) -> PresetEntry:
        """Tạo preset mới."""
        pass

    @abstractmethod
    def update_preset(
        self,
        preset_id: str,
        name: Optional[str] = None,
        selected_paths: Optional[List[str]] = None,
        instructions: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> Optional[PresetEntry]:
        """Cập nhật preset."""
        pass

    @abstractmethod
    def delete_preset(self, preset_id: str) -> bool:
        """Xóa preset."""
        pass

    @abstractmethod
    def rename_preset(self, preset_id: str, new_name: str) -> Optional[PresetEntry]:
        """Đổi tên preset."""
        pass

    @abstractmethod
    def to_absolute_paths(self, relative_paths: List[str]) -> List[str]:
        """Chuyển đổi các đường dẫn tương đối thành tuyệt đối."""
        pass


class IPresetStoreFactory(ABC):
    """
    Factory để tạo PresetStore theo workspace root.
    """

    @abstractmethod
    def create_preset_store(self, workspace_root: Path) -> IPresetStore:
        """Tạo PresetStore instance."""
        pass
