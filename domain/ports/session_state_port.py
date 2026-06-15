from typing import Protocol, Dict, Any, runtime_checkable

@runtime_checkable
class ISessionStateService(Protocol):
    def load_session_state(self) -> Dict[str, Any]:
        ...

    def save_session_state(self, state: Dict[str, Any]) -> None:
        ...

    def clear_session_state(self) -> None:
        ...
