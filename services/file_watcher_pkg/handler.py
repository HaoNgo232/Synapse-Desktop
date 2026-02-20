"""
Workspace Event Handler cho File Watcher.

Nhan events tu watchdog, ap dung ignore strategy,
va delegate events hop le sang debouncer.

Class nay chi lam 1 viec: chuyen doi watchdog events
thanh FileChangeEvent va chuyen tiep cho debouncer.
"""

from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
)

from core.logging_config import log_debug
from services.interfaces.file_watcher_service import (
    FileChangeEvent,
    IEventDebouncer,
    IIgnoreStrategy,
)


class WorkspaceEventHandler(FileSystemEventHandler):
    """
    Event handler nhan events tu watchdog va delegate cho debouncer.

    Trach nhiem duy nhat:
    - Nhan watchdog events (on_created, on_deleted, on_modified, on_moved)
    - Kiem tra ignore strategy
    - Chuyen doi sang FileChangeEvent va gui cho debouncer

    Khong chua logic debounce hay business logic nao khac.

    Attributes:
        _ignore_strategy: Strategy xac dinh path nao can bo qua
        _debouncer: Debouncer gom nhom events truoc khi dispatch
    """

    def __init__(
        self,
        ignore_strategy: IIgnoreStrategy,
        debouncer: IEventDebouncer,
    ):
        """
        Khoi tao handler voi dependencies duoc inject.

        Args:
            ignore_strategy: Strategy xac dinh path nao can ignore
            debouncer: Debouncer de gom nhom events
        """
        super().__init__()
        self._ignore_strategy = ignore_strategy
        self._debouncer = debouncer

    def _handle_event(self, event: object, event_type: str) -> None:
        """
        Xu ly event chung cho tat ca loai su kien.

        Flow:
        1. Kiem tra ignore strategy
        2. Tao FileChangeEvent
        3. Gui cho debouncer

        Args:
            event: Watchdog event (FileCreatedEvent, etc.)
            event_type: Loai su kien ('created', 'deleted', 'modified', 'moved')
        """
        src_path: str = getattr(event, "src_path", "")
        is_directory: bool = getattr(event, "is_directory", False)

        # Kiem tra ignore strategy
        if self._ignore_strategy.should_ignore(src_path):
            return

        # Tao FileChangeEvent va gui cho debouncer
        change_event = FileChangeEvent(
            event_type=event_type,
            path=src_path,
            is_directory=is_directory,
        )

        log_debug(f"[FileWatcher] Event: {event_type} - {src_path}")
        self._debouncer.add_event(change_event)

    # Override watchdog event handlers
    def on_created(self, event: object) -> None:
        """Xu ly khi file/folder duoc tao."""
        if isinstance(event, (FileCreatedEvent, DirCreatedEvent)):
            self._handle_event(event, "created")

    def on_deleted(self, event: object) -> None:
        """Xu ly khi file/folder bi xoa."""
        if isinstance(event, (FileDeletedEvent, DirDeletedEvent)):
            self._handle_event(event, "deleted")

    def on_modified(self, event: object) -> None:
        """Xu ly khi file bi sua."""
        # Chi xu ly file, khong xu ly folder (folder modified qua nhieu noise)
        if isinstance(event, FileModifiedEvent):
            self._handle_event(event, "modified")

    def on_moved(self, event: object) -> None:
        """Xu ly khi file/folder bi di chuyen/doi ten."""
        if isinstance(event, (FileMovedEvent, DirMovedEvent)):
            self._handle_event(event, "moved")
