"""
File Watcher Service - Backward-compatible re-exports.

Module nay giu nguyen import path cu:
    from services.file_watcher import FileWatcher, WatcherCallbacks

Tat ca logic da duoc chuyen sang package:
    services.file_watcher_pkg.service (FileWatcher)
    services.file_watcher_pkg.debouncer (TimerEventDebouncer)
    services.file_watcher_pkg.handler (WorkspaceEventHandler)
    services.file_watcher_pkg.ignore_strategies (DefaultIgnoreStrategy)
    services.interfaces.file_watcher_service (Interfaces + Data classes)
"""

# Re-export de consumers khong can thay doi imports
from services.file_watcher_pkg.service import FileWatcher
from services.interfaces.file_watcher_service import (
    FileChangeEvent,
    WatcherCallbacks,
)

__all__ = [
    "FileWatcher",
    "FileChangeEvent",
    "WatcherCallbacks",
]
