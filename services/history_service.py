"""
History Service - Lưu trữ và quản lý lịch sử các thao tác

Lưu lại:
- OPX đã apply
- Thời gian thực hiện
- Kết quả (success/fail)
- Cho phép xem lại và copy lại
"""

import json
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime

from core.logging_config import log_error, log_debug, log_info


# History file path
HISTORY_FILE = Path.home() / ".synapse-desktop" / "history.json"

# Số lượng tối đa entries lưu trữ
MAX_HISTORY_ENTRIES = 100


@dataclass
class HistoryEntry:
    """Một entry trong lịch sử"""

    id: str  # UUID
    timestamp: str  # ISO format
    workspace_path: str
    opx_content: str
    file_count: int
    success_count: int
    fail_count: int
    action_summary: List[str] = field(
        default_factory=list
    )  # ["CREATE file1.py", "MODIFY file2.py"]
    error_messages: List[str] = field(default_factory=list)


@dataclass
class HistoryData:
    """Dữ liệu lịch sử"""

    entries: List[HistoryEntry] = field(default_factory=list)
    version: str = "1.0"


def _generate_id() -> str:
    """Tạo unique ID cho entry"""
    import uuid

    return str(uuid.uuid4())[:8]


def load_history() -> HistoryData:
    """Load lịch sử từ file"""
    try:
        if HISTORY_FILE.exists():
            content = HISTORY_FILE.read_text(encoding="utf-8")
            data = json.loads(content)

            entries = []
            for entry_dict in data.get("entries", []):
                entries.append(
                    HistoryEntry(
                        id=entry_dict.get("id", _generate_id()),
                        timestamp=entry_dict.get("timestamp", ""),
                        workspace_path=entry_dict.get("workspace_path", ""),
                        opx_content=entry_dict.get("opx_content", ""),
                        file_count=entry_dict.get("file_count", 0),
                        success_count=entry_dict.get("success_count", 0),
                        fail_count=entry_dict.get("fail_count", 0),
                        action_summary=entry_dict.get("action_summary", []),
                        error_messages=entry_dict.get("error_messages", []),
                    )
                )

            return HistoryData(entries=entries, version=data.get("version", "1.0"))
    except (OSError, json.JSONDecodeError) as e:
        log_debug(f"Could not load history: {e}")

    return HistoryData()


def save_history(history: HistoryData) -> bool:
    """Lưu lịch sử ra file"""
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": history.version,
            "entries": [asdict(entry) for entry in history.entries],
        }

        HISTORY_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True

    except (OSError, IOError) as e:
        log_error(f"Failed to save history: {e}")
        return False


def add_history_entry(
    workspace_path: str,
    opx_content: str,
    action_results: List[
        dict
    ],  # [{"action": "CREATE", "path": "...", "success": True, "message": "..."}]
) -> Optional[HistoryEntry]:
    """
    Thêm entry mới vào lịch sử.

    Args:
        workspace_path: Đường dẫn workspace
        opx_content: Nội dung OPX đã apply
        action_results: Kết quả các actions

    Returns:
        HistoryEntry nếu thành công
    """
    try:
        history = load_history()

        # Tính toán thống kê
        success_count = sum(1 for r in action_results if r.get("success", False))
        fail_count = len(action_results) - success_count

        action_summary = [
            f"{r.get('action', 'UNKNOWN').upper()} {Path(r.get('path', '')).name}"
            for r in action_results
        ]

        error_messages = [
            r.get("message", "")
            for r in action_results
            if not r.get("success", False) and r.get("message")
        ]

        entry = HistoryEntry(
            id=_generate_id(),
            timestamp=datetime.now().isoformat(),
            workspace_path=workspace_path,
            opx_content=opx_content,
            file_count=len(action_results),
            success_count=success_count,
            fail_count=fail_count,
            action_summary=action_summary,
            error_messages=error_messages,
        )

        # Thêm vào đầu list (mới nhất trước)
        history.entries.insert(0, entry)

        # Giới hạn số lượng
        history.entries = history.entries[:MAX_HISTORY_ENTRIES]

        if save_history(history):
            log_info(f"Added history entry: {entry.id}")
            return entry

    except Exception as e:
        log_error(f"Failed to add history entry: {e}")

    return None


def get_history_entries(limit: int = 50) -> List[HistoryEntry]:
    """Lấy danh sách entries (mới nhất trước)"""
    history = load_history()
    return history.entries[:limit]


def get_entry_by_id(entry_id: str) -> Optional[HistoryEntry]:
    """Tìm entry theo ID"""
    history = load_history()
    for entry in history.entries:
        if entry.id == entry_id:
            return entry
    return None


def delete_entry(entry_id: str) -> bool:
    """Xóa một entry"""
    history = load_history()
    original_count = len(history.entries)
    history.entries = [e for e in history.entries if e.id != entry_id]

    if len(history.entries) < original_count:
        return save_history(history)
    return False


def clear_history() -> bool:
    """Xóa toàn bộ lịch sử"""
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        return True
    except OSError as e:
        log_error(f"Failed to clear history: {e}")
        return False


def get_history_stats() -> dict:
    """Lấy thống kê lịch sử"""
    history = load_history()

    total_operations = sum(e.file_count for e in history.entries)
    total_success = sum(e.success_count for e in history.entries)
    total_fail = sum(e.fail_count for e in history.entries)

    return {
        "total_entries": len(history.entries),
        "total_operations": total_operations,
        "total_success": total_success,
        "total_fail": total_fail,
        "success_rate": (
            (total_success / total_operations * 100) if total_operations > 0 else 0
        ),
    }
