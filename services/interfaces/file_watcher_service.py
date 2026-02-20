"""
Interfaces cho File Watcher Service.

Dinh nghia contracts cho:
- IFileWatcherService: Start/stop theo doi file system
- IIgnoreStrategy: Xac dinh path nao can bo qua
- IEventDebouncer: Gom nhom events va dispatch sau debounce
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Optional

from dataclasses import dataclass


@dataclass
class FileChangeEvent:
    """
    Dai dien cho mot su kien thay doi file.

    Attributes:
        event_type: Loai su kien ('created', 'deleted', 'modified', 'moved')
        path: Duong dan tuyet doi cua file/folder bi thay doi
        is_directory: True neu la thu muc
    """

    event_type: str
    path: str
    is_directory: bool


@dataclass
class WatcherCallbacks:
    """
    Callbacks cho file watcher - cho phep xu ly incremental.

    Neu on_file_modified/created/deleted duoc set,
    se goi chung thay vi on_batch_change.

    Attributes:
        on_file_modified: Callback khi file bi sua (invalidate cache)
        on_file_created: Callback khi file moi duoc tao
        on_file_deleted: Callback khi file bi xoa
        on_batch_change: Fallback callback khi co nhieu thay doi
    """

    on_file_modified: Optional[Callable[[str], None]] = None
    on_file_created: Optional[Callable[[str], None]] = None
    on_file_deleted: Optional[Callable[[str], None]] = None
    on_batch_change: Optional[Callable[[], None]] = None


class IIgnoreStrategy(ABC):
    """
    Interface xac dinh logic bo qua path.

    Implementation co the dua tren hardcoded patterns,
    .gitignore, hoac bat ky logic nao khac.
    """

    @abstractmethod
    def should_ignore(self, path: str) -> bool:
        """
        Kiem tra xem path co nen bi bo qua khong.

        Args:
            path: Duong dan tuyet doi can kiem tra

        Returns:
            True neu path can bi bo qua
        """
        ...


class IEventDebouncer(ABC):
    """
    Interface gom nhom events va dispatch sau debounce.

    Nhan events lien tuc, chi trigger callback sau khi
    khong co event moi trong khoang thoi gian debounce.
    """

    @abstractmethod
    def add_event(self, event: FileChangeEvent) -> None:
        """
        Them mot event vao hang doi va reset debounce timer.

        Args:
            event: Su kien file change can xu ly
        """
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Don dep timer va pending events khi shutdown."""
        ...


class IFileWatcherService(ABC):
    """
    Interface cho dich vu theo doi file trong workspace.

    Moi implementation phai dam bao:
    - Thread-safe start/stop
    - Auto-stop khi switch sang path moi
    - Background thread cho event listening
    """

    @abstractmethod
    def start(
        self,
        path: Path,
        on_change: Optional[Callable[[], None]] = None,
        callbacks: Optional[WatcherCallbacks] = None,
        debounce_seconds: float = 0.5,
    ) -> None:
        """
        Bat dau theo doi mot thu muc.

        Neu dang theo doi thu muc khac, se tu dong stop truoc.

        Args:
            path: Duong dan thu muc can theo doi
            on_change: Callback legacy khi co thay doi (backward compatible)
            callbacks: WatcherCallbacks cho incremental updates
            debounce_seconds: Thoi gian debounce (mac dinh 0.5s)
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Dung theo doi."""
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Kiem tra watcher co dang chay khong."""
        ...

    @property
    @abstractmethod
    def current_path(self) -> Optional[Path]:
        """Lay duong dan dang duoc theo doi."""
        ...
