from typing import Protocol, List, Optional, runtime_checkable
from dataclasses import dataclass, field


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


@runtime_checkable
class ISessionStateService(Protocol):
    def load_session_state(self) -> Optional[SessionState]: ...

    def save_session_state(self, state: SessionState) -> bool: ...

    def clear_session_state(self) -> bool: ...
