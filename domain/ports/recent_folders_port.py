from typing import Protocol, List, runtime_checkable

@runtime_checkable
class IRecentFoldersService(Protocol):
    def load_recent_folders(self) -> List[str]:
        ...

    def save_recent_folders(self, folders: List[str]) -> None:
        ...

    def clear_recent_folders(self) -> None:
        ...
