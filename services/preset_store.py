"""
Preset Store — Quản lý lưu trữ context presets tại workspace root.

File format: .synapse_presets.json
{
  "version": 1,
  "presets": {
    "preset-uuid-1": {
      "name": "Backend API files",
      "created_at": "2025-01-15T10:30:00",
      "updated_at": "2025-01-15T10:30:00",
      "selected_paths": ["src/api/routes.py", "src/api/models.py"],
      "instructions": "Refactor auth flow",
      "output_format": "synapse_xml"
    }
  }
}

Paths stored as RELATIVE to workspace root for portability.
Thread-safe with threading.Lock for all I/O operations.
"""

import json
import uuid
import threading
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, List

import logging

logger = logging.getLogger(__name__)

PRESET_FILENAME = ".synapse_presets.json"
CURRENT_VERSION = 1


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

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "selected_paths": self.selected_paths,
            "instructions": self.instructions,
            "output_format": self.output_format,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(preset_id: str, data: dict) -> "PresetEntry":
        return PresetEntry(
            preset_id=preset_id,
            name=data.get("name", "Untitled"),
            selected_paths=data.get("selected_paths", []),
            instructions=data.get("instructions", ""),
            output_format=data.get("output_format", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class PresetStore:
    """
    Quản lý CRUD cho presets, lưu tại workspace_root/.synapse_presets.json.
    Thread-safe với _lock cho mọi read/write operation.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root
        self._file_path = workspace_root / PRESET_FILENAME
        self._lock = threading.Lock()
        self._cache: Optional[Dict[str, PresetEntry]] = None

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def set_workspace(self, workspace_root: Path) -> None:
        """Đổi workspace — invalidate cache."""
        with self._lock:
            self._workspace_root = workspace_root
            self._file_path = workspace_root / PRESET_FILENAME
            self._cache = None

    def list_presets(self) -> List[PresetEntry]:
        """Trả về tất cả presets, sắp xếp theo updated_at mới nhất."""
        with self._lock:
            presets = self._load_unlocked()
            result = list(presets.values())
            result.sort(key=lambda p: p.updated_at or "", reverse=True)
            return result

    def get_preset(self, preset_id: str) -> Optional[PresetEntry]:
        """Lấy preset theo ID."""
        with self._lock:
            presets = self._load_unlocked()
            return presets.get(preset_id)

    def create_preset(
        self,
        name: str,
        selected_paths: List[str],
        instructions: str = "",
        output_format: str = "",
    ) -> PresetEntry:
        """Tạo preset mới. selected_paths là absolute paths, sẽ convert sang relative."""
        now = datetime.now().isoformat()
        preset_id = str(uuid.uuid4())[:8]

        relative_paths = self._to_relative_paths(selected_paths)

        entry = PresetEntry(
            preset_id=preset_id,
            name=name,
            selected_paths=relative_paths,
            instructions=instructions,
            output_format=output_format,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            presets = self._load_unlocked()
            presets[preset_id] = entry
            self._save_unlocked(presets)

        return entry

    def update_preset(
        self,
        preset_id: str,
        name: Optional[str] = None,
        selected_paths: Optional[List[str]] = None,
        instructions: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> Optional[PresetEntry]:
        """Cập nhật preset. Chỉ update fields non-None."""
        with self._lock:
            presets = self._load_unlocked()
            entry = presets.get(preset_id)
            if entry is None:
                return None

            if name is not None:
                entry.name = name
            if selected_paths is not None:
                entry.selected_paths = self._to_relative_paths(selected_paths)
            if instructions is not None:
                entry.instructions = instructions
            if output_format is not None:
                entry.output_format = output_format

            entry.updated_at = datetime.now().isoformat()
            self._save_unlocked(presets)

        return entry

    def delete_preset(self, preset_id: str) -> bool:
        """Xóa preset. Returns True nếu xóa thành công."""
        with self._lock:
            presets = self._load_unlocked()
            if preset_id not in presets:
                return False
            del presets[preset_id]
            self._save_unlocked(presets)
        return True

    def rename_preset(self, preset_id: str, new_name: str) -> Optional[PresetEntry]:
        """Đổi tên preset."""
        return self.update_preset(preset_id, name=new_name)

    def _to_relative_paths(self, absolute_paths: List[str]) -> List[str]:
        """Convert absolute paths sang relative paths."""
        result = []
        for p in absolute_paths:
            try:
                rel = str(Path(p).relative_to(self._workspace_root))
                result.append(rel)
            except ValueError:
                result.append(p)
        return result

    def to_absolute_paths(self, relative_paths: List[str]) -> List[str]:
        """Convert relative paths to absolute paths with security validation."""
        result = []
        try:
            workspace_resolved = self._workspace_root.resolve()
        except OSError:
            logger.error("Cannot resolve workspace root path")
            return result

        for p in relative_paths:
            try:
                # Resolve the full path to handle .. and . components
                candidate_path = (self._workspace_root / p).resolve()

                # Security check: ensure path is within workspace boundary
                try:
                    candidate_path.relative_to(workspace_resolved)
                except ValueError:
                    logger.warning(f"Security: Blocked path traversal attempt: {p}")
                    continue

                # Check existence only after security validation
                if candidate_path.exists():
                    result.append(str(candidate_path))
                else:
                    logger.debug(f"Preset path no longer exists: {p}")

            except (OSError, ValueError) as e:
                logger.warning(f"Invalid path in preset: {p} - {e}")
                continue

        return result

    def _load_unlocked(self) -> Dict[str, PresetEntry]:
        """Load presets từ file. PHẢI gọi trong _lock context."""
        if self._cache is not None:
            return self._cache

        presets: Dict[str, PresetEntry] = {}

        if not self._file_path.exists():
            self._cache = presets
            return presets

        try:
            content = self._file_path.read_text(encoding="utf-8")
            data = json.loads(content)

            raw_presets = data.get("presets", {})

            for pid, pdata in raw_presets.items():
                try:
                    if self._validate_preset_data(pdata):
                        presets[pid] = PresetEntry.from_dict(pid, pdata)
                except Exception as e:
                    logger.warning(f"Skipping invalid preset {pid}: {e}")

        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load presets from {self._file_path}: {e}")
            self._backup_corrupt_file()

        self._cache = presets
        return presets

    def _save_unlocked(self, presets: Dict[str, PresetEntry]) -> bool:
        """Save presets ra file. PHẢI gọi trong _lock context. Atomic write."""
        try:
            data = {
                "version": CURRENT_VERSION,
                "presets": {pid: entry.to_dict() for pid, entry in presets.items()},
            }
            content = json.dumps(data, indent=2, ensure_ascii=False)

            tmp_file = self._file_path.with_suffix(".tmp")
            tmp_file.write_text(content, encoding="utf-8")

            os.replace(str(tmp_file), str(self._file_path))

            self._cache = presets
            return True

        except (OSError, IOError) as e:
            logger.error(f"Failed to save presets: {e}")
            try:
                tmp = self._file_path.with_suffix(".tmp")
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            return False

    def _validate_preset_data(self, data: dict) -> bool:
        """Validate preset data structure."""
        required = {"name", "selected_paths"}
        return all(k in data for k in required) and isinstance(
            data["selected_paths"], list
        )

    def _backup_corrupt_file(self) -> None:
        """Backup corrupt preset file."""
        try:
            if self._file_path.exists():
                backup = self._file_path.with_suffix(".json.bak")
                self._file_path.rename(backup)
                logger.info(f"Backed up corrupt preset file to {backup}")
        except OSError as e:
            logger.error(f"Failed to backup corrupt file: {e}")
