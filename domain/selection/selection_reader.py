"""
Selection Reader - Helper đọc selection duy nhất cho toàn bộ hệ thống.

Đọc .synapse/selection.json, hỗ trợ cả v2 (SelectionState) và v1
({"selected_files": [...]}). Nếu gặp v1, tự migrate sang v2 (migrate-on-read).

Dùng cho:
- selection_handler.py (manage_selection)
- session_manager.py (build_prompt helper)
- context_handler.py (build_prompt use_selection=True)
"""

import json
import logging
from pathlib import Path
from typing import Optional

from domain.selection.provenance import SelectionState

logger = logging.getLogger(__name__)


def read_selection_state(session_file: Path) -> SelectionState:
    """Đọc SelectionState từ file, tự nhận diện v1/v2 và migrate nếu cần.

    Args:
        session_file: Path tới .synapse/selection.json

    Returns:
        SelectionState (v2 format) - trả rỗng nếu file không tồn tại hoặc lỗi.
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
    """Parse selection data, hỗ trợ cả v1 và v2 format.

    v1 format: {"selected_files": ["a.py", "b.py"]}
    v2 format: {"version": 2, "paths": [...], "provenance": {...}}
    Legacy: plain list ["a.py", "b.py"]
    """
    if isinstance(data, list):
        # Legacy format: bare list
        return SelectionState.from_dict(data)

    if isinstance(data, dict):
        # v1 format: {"selected_files": [...]} without "version"
        if "selected_files" in data and "version" not in data:
            return SelectionState.from_dict(data["selected_files"])
        # v2 format hoặc dict có version
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


def migrate_v1_to_v2(session_file: Path) -> Optional[SelectionState]:
    """Đọc file selection, nếu đang v1 thì rewrite thành v2.

    Args:
        session_file: Path tới .synapse/selection.json

    Returns:
        SelectionState đã migrate, hoặc None nếu file không tồn tại.
    """
    if not session_file.exists():
        return None

    try:
        raw_text = session_file.read_text(encoding="utf-8")
        if not raw_text.strip():
            return None

        data = json.loads(raw_text)

        # Kiểm tra xem có phải v1 format không
        is_v1 = (
            isinstance(data, dict)
            and "selected_files" in data
            and "version" not in data
        ) or isinstance(data, list)

        state = _parse_selection_data(data)

        # Nếu là v1, rewrite thành v2
        if is_v1 and state.paths:
            session_file.parent.mkdir(parents=True, exist_ok=True)
            session_file.write_text(
                json.dumps(state.to_dict(), indent=2) + "\n",
                encoding="utf-8",
            )
            logger.info(
                "Migrated selection.json from v1 to v2 (%d paths)", len(state.paths)
            )

        return state
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to migrate selection: %s", e)
        return None
