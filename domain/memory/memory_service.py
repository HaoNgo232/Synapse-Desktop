"""
Memory Service - Quản lý đọc/ghi memory store cho workspace.

Lưu tại .synapse/memory_v2.json, tương thích với memory.xml cũ.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from domain.memory.memory_types import MemoryEntry, MemoryLayer, MemoryStore

logger = logging.getLogger(__name__)

_write_lock = threading.Lock()


def load_memory_store(workspace_root: Path) -> MemoryStore:
    """Load memory store from .synapse/memory_v2.json."""
    memory_file = workspace_root / ".synapse" / "memory_v2.json"
    if not memory_file.exists():
        return MemoryStore()
    try:
        content = memory_file.read_text(encoding="utf-8")
        data = json.loads(content)
        return MemoryStore.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to load memory store: %s", e)
        return MemoryStore()


def save_memory_store(workspace_root: Path, store: MemoryStore) -> None:
    """Save memory store to .synapse/memory_v2.json."""
    synapse_dir = workspace_root / ".synapse"
    memory_file = synapse_dir / "memory_v2.json"

    with _write_lock:
        synapse_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = memory_file.with_suffix(".tmp")
        try:
            tmp_file.write_text(
                json.dumps(store.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(str(tmp_file), str(memory_file))
        except OSError as e:
            logger.error("Failed to save memory store: %s", e)
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)


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
    """Add a memory entry and persist."""
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
        layer_entries = store.get_by_layer(layer_name)
        if len(layer_entries) > max_entries:
            excess = len(layer_entries) - max_entries
            to_remove = layer_entries[:excess]
            store.entries = [e for e in store.entries if e not in to_remove]

    save_memory_store(workspace_root, store)
