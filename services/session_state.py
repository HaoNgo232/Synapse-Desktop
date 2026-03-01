"""
Session State Service - Lưu trữ và khôi phục trạng thái làm việc

CLEAN SESSION MODE (Auto on app start):
- Workspace path: Restore từ recent folders (workspace gần nhất)
- Instructions text: Restore từ session
- Window size: Restore từ session
- Selected files: CLEAR (fresh start)
- Expanded folders: CLEAR (fresh start)
- Active tab: CLEAR (luôn bắt đầu ở tab 0)

Lưu lại khi đóng app:
- Workspace path đang mở
- Các files đã chọn (nhưng không restore khi mở lại)
- Nội dung instructions
- Tab đang active (nhưng không restore khi mở lại)
- Window size
"""

import json
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime

from core.logging_config import log_error, log_debug, log_info, log_warning
from config.paths import SESSION_FILE


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

    Uses atomic write (temp file + rename) to prevent corruption
    if the app crashes or is killed mid-write.

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
        content = json.dumps(data, indent=2, ensure_ascii=False)

        # Atomic write: write to temp file then rename
        # os.replace() is atomic on POSIX and near-atomic on Windows
        tmp_file = SESSION_FILE.with_suffix(".tmp")
        tmp_file.write_text(content, encoding="utf-8")

        import os

        os.replace(str(tmp_file), str(SESSION_FILE))

        log_debug(f"Session saved: {state.workspace_path}")
        return True

    except (OSError, IOError) as e:
        log_error(f"Failed to save session: {e}")
        # Clean up temp file if it exists
        try:
            tmp_file = SESSION_FILE.with_suffix(".tmp")
            if tmp_file.exists():
                tmp_file.unlink()
        except OSError:
            pass
        return False


def load_session_state() -> Optional[SessionState]:
    """
    Load session state từ file.

    If the main file is corrupted, attempts to recover from the .tmp
    file left by a previous interrupted save.

    Returns:
        SessionState nếu load thành công, None nếu không có hoặc lỗi
    """
    # Try main file first, then fallback to temp file
    for candidate in (SESSION_FILE, SESSION_FILE.with_suffix(".tmp")):
        if not candidate.exists():
            continue
        try:
            content = candidate.read_text(encoding="utf-8")
            data = json.loads(content)
            if candidate != SESSION_FILE:
                log_info(f"Recovered session from {candidate.name}")
                # Promote .tmp to main file
                try:
                    import os

                    os.replace(str(candidate), str(SESSION_FILE))
                except OSError:
                    pass
            break
        except (OSError, json.JSONDecodeError) as e:
            log_warning(f"Failed to parse {candidate.name}: {e}")
            continue
    else:
        # Neither file exists or both are corrupt
        return None

    try:
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
