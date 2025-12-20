"""
Session State Service - Lưu trữ và khôi phục trạng thái làm việc

Lưu lại:
- Workspace path đang mở
- Các files đã chọn
- Nội dung instructions
- Tab đang active
"""

import json
from pathlib import Path
from typing import List, Optional, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime

from core.logging_config import log_error, log_debug, log_info


# Session file path
SESSION_FILE = Path.home() / ".synapse-desktop" / "session.json"


@dataclass
class SessionState:
    """Trạng thái session của app"""

    workspace_path: Optional[str] = None
    selected_files: List[str] = field(default_factory=list)
    expanded_folders: List[str] = field(default_factory=list)
    instructions_text: str = ""
    active_tab_index: int = 0
    window_width: Optional[int] = None
    window_height: Optional[int] = None
    saved_at: Optional[str] = None


def save_session_state(state: SessionState) -> bool:
    """
    Lưu session state ra file.

    Args:
        state: SessionState object

    Returns:
        True nếu lưu thành công
    """
    try:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp
        state.saved_at = datetime.now().isoformat()

        data = asdict(state)

        SESSION_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        log_debug(f"Session saved: {state.workspace_path}")
        return True

    except (OSError, IOError) as e:
        log_error(f"Failed to save session: {e}")
        return False


def load_session_state() -> Optional[SessionState]:
    """
    Load session state từ file.

    Returns:
        SessionState nếu load thành công, None nếu không có hoặc lỗi
    """
    try:
        if not SESSION_FILE.exists():
            return None

        content = SESSION_FILE.read_text(encoding="utf-8")
        data = json.loads(content)

        # Validate workspace still exists
        workspace = data.get("workspace_path")
        if workspace and not Path(workspace).exists():
            log_debug(f"Previous workspace no longer exists: {workspace}")
            data["workspace_path"] = None
            data["selected_files"] = []
            data["expanded_folders"] = []

        # Filter selected files that still exist
        if data.get("selected_files"):
            valid_files = [f for f in data["selected_files"] if Path(f).exists()]
            data["selected_files"] = valid_files

        state = SessionState(
            workspace_path=data.get("workspace_path"),
            selected_files=data.get("selected_files", []),
            expanded_folders=data.get("expanded_folders", []),
            instructions_text=data.get("instructions_text", ""),
            active_tab_index=data.get("active_tab_index", 0),
            window_width=data.get("window_width"),
            window_height=data.get("window_height"),
            saved_at=data.get("saved_at"),
        )

        log_info(f"Session restored: {state.workspace_path}")
        return state

    except (OSError, json.JSONDecodeError) as e:
        log_debug(f"Could not load session: {e}")
        return None


def clear_session_state() -> bool:
    """
    Xóa session state file.

    Returns:
        True nếu xóa thành công
    """
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
        return True
    except OSError as e:
        log_error(f"Failed to clear session: {e}")
        return False


def get_session_age_hours() -> Optional[float]:
    """
    Lấy tuổi của session (tính bằng giờ).

    Returns:
        Số giờ từ lần save cuối, None nếu không có session
    """
    state = load_session_state()
    if not state or not state.saved_at:
        return None

    try:
        saved_time = datetime.fromisoformat(state.saved_at)
        age = datetime.now() - saved_time
        return age.total_seconds() / 3600
    except (ValueError, TypeError):
        return None
