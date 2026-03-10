"""
Memory Prompt Adapter - Cầu nối giữa memory store và prompt pipeline.

Load memory từ memory_v2.json (nguồn chuẩn), fallback sang memory.xml
trong giai đoạn migration. Format cho prompt inclusion.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def load_memory_for_prompt(
    workspace_root: Path, max_entries: int = 20
) -> Optional[str]:
    """Load memory và format sẵn sàng cho prompt inclusion.

    Ưu tiên memory_v2.json (structured, 3 layers).
    Fallback sang memory.xml nếu v2 chưa có dữ liệu.

    Args:
        workspace_root: Workspace root path
        max_entries: Số entries tối đa mỗi layer

    Returns:
        Formatted memory string, hoặc None nếu không có memory.
    """
    # Ưu tiên v2
    v2_content = _load_memory_v2(workspace_root, max_entries)
    if v2_content:
        return v2_content

    # Fallback: đọc memory.xml legacy
    return _load_memory_xml_legacy(workspace_root)


def _load_memory_v2(workspace_root: Path, max_entries: int = 20) -> Optional[str]:
    """Load từ memory_v2.json và format bằng MemoryStore.format_for_prompt()."""
    try:
        from domain.memory.memory_service import load_memory_store

        store = load_memory_store(workspace_root)
        if not store.entries:
            return None

        formatted = store.format_for_prompt(max_entries=max_entries)
        return formatted if formatted and formatted.strip() else None
    except Exception as e:
        logger.warning("Failed to load memory_v2 for prompt: %s", e)
        return None


def _load_memory_xml_legacy(workspace_root: Path) -> Optional[str]:
    """Fallback: đọc memory.xml raw content (legacy format)."""
    memory_file = workspace_root / ".synapse" / "memory.xml"
    if not memory_file.exists():
        return None
    try:
        content = memory_file.read_text(encoding="utf-8").strip()
        return content if content else None
    except Exception as e:
        logger.warning("Failed to read legacy memory.xml: %s", e)
        return None
