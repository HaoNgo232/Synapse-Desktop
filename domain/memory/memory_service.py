"""
Memory Service - Quản lý đọc/ghi memory store cho workspace.

Lưu tại .synapse/memory_v2.json — nguồn dữ liệu duy nhất cho memory.
Legacy memory.xml đã được hợp nhất vào đây.
"""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

from domain.memory.memory_types import MemoryEntry, MemoryLayer, MemoryStore

logger = logging.getLogger(__name__)

# Intra-process lock for thread safety
_memory_lock = threading.RLock()


def load_memory_store(workspace_root: Path) -> MemoryStore:
    """Load memory store from .synapse/memory_v2.json."""
    memory_file = workspace_root / ".synapse" / "memory_v2.json"
    if not memory_file.exists():
        return MemoryStore()
    try:
        with _memory_lock:
            content = memory_file.read_text(encoding="utf-8")
            data = json.loads(content)
            return MemoryStore.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to load memory store: %s", e)
        return MemoryStore()


def _atomic_json_write(file_path: Path, data: dict) -> None:
    """Cross-platform atomic JSON write."""
    dir_path = file_path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(file_path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def save_memory_store(workspace_root: Path, store: MemoryStore) -> None:
    """Save memory store to .synapse/memory_v2.json using atomic write."""
    memory_file = workspace_root / ".synapse" / "memory_v2.json"
    with _memory_lock:
        _atomic_json_write(memory_file, store.to_dict())


def add_memory(
    workspace_root: Path,
    layer: MemoryLayer,
    content: str,
    linked_files: Optional[list] = None,
    linked_symbols: Optional[list] = None,
    workflow: str = "",
    tags: Optional[list] = None,
    max_entries: int = 100,
) -> None:
    """Add a memory entry and persist securely with locking and atomic write."""
    memory_file = workspace_root / ".synapse" / "memory_v2.json"

    with _memory_lock:
        store = load_memory_store(workspace_root)

        entry = MemoryEntry(
            layer=layer,
            content=content,
            linked_files=linked_files or [],
            linked_symbols=linked_symbols or [],
            workflow=workflow,
            tags=tags or [],
        )
        store.add(entry)

        # Trim old entries per layer
        for layer_name in ("action", "decision", "constraint"):
            layer_entries = store.get_by_layer(layer_name)  # type: ignore
            if len(layer_entries) > max_entries:
                excess = len(layer_entries) - max_entries
                to_remove = layer_entries[:excess]
                store.entries = [e for e in store.entries if e not in to_remove]

        _atomic_json_write(memory_file, store.to_dict())
