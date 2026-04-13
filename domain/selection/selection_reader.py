"""
Selection Reader - Helper đọc selection duy nhất cho toàn bộ hệ thống.

Đọc .synapse/selection.json theo chuẩn v2 (SelectionState).

Dùng cho:
- selection_handler.py (manage_selection)
- session_manager.py (build_prompt helper)
- context_handler.py (build_prompt use_selection=True)
"""

import json
import logging
from pathlib import Path

from domain.selection.provenance import SelectionState

logger = logging.getLogger(__name__)


def read_selection_state(session_file: Path) -> SelectionState:
    """Đọc SelectionState v2 từ file.

    Args:
        session_file: Path tới .synapse/selection.json

    Returns:
        SelectionState - trả rỗng nếu file không tồn tại hoặc dữ liệu không hợp lệ.
    """
    if not session_file.exists():
        return SelectionState()

    try:
        raw_text = session_file.read_text(encoding="utf-8")
        if not raw_text.strip():
            return SelectionState()

        data = json.loads(raw_text)
        return _parse_selection_data(data)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to read selection from %s: %s", session_file, e)
        return SelectionState()


def _parse_selection_data(data: object) -> SelectionState:
    """Parse selection data theo v2 format.

    Expected v2 format: {"version": 2, "paths": [...], "provenance": {...}}
    """
    if isinstance(data, dict) and "paths" in data:
        return SelectionState.from_dict(data)

    return SelectionState()


def read_selection_paths(session_file: Path) -> list[str]:
    """Đọc danh sách paths từ selection file.

    Tiện dụng cho build_prompt và các nơi chỉ cần list paths.

    Args:
        session_file: Path tới .synapse/selection.json

    Returns:
        List relative paths đang được chọn.
    """
    state = read_selection_state(session_file)
    return state.paths
