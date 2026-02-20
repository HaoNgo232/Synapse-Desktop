"""
File Watcher Package - Re-exports cho backward compatibility.

Export cac symbols chinh de consumers khong can thay doi imports:
- FileWatcher (class chinh)
- WatcherCallbacks, FileChangeEvent (data classes)
"""

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
