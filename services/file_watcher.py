"""
File Watcher Service - Theo dõi thay đổi file trong workspace

Sử dụng thư viện watchdog để phát hiện khi file được thêm, sửa, xóa
và trigger callback để cập nhật file tree.

Port logic từ: pastemax/electron/watcher.js
"""

from pathlib import Path
from threading import Timer
from typing import Any, Callable, Optional, Set
from dataclasses import dataclass

from watchdog.observers import Observer
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

from core.logging_config import log_info, log_error, log_debug


@dataclass
class FileChangeEvent:
    """
    Đại diện cho một sự kiện thay đổi file.

    Attributes:
        event_type: Loại sự kiện ('created', 'deleted', 'modified', 'moved')
        path: Đường dẫn tuyệt đối của file/folder bị thay đổi
        is_directory: True nếu là thư mục
    """

    event_type: str
    path: str
    is_directory: bool


@dataclass
class WatcherCallbacks:
    """
    Callbacks cho file watcher - cho phép xử lý incremental.

    Nếu on_file_modified/created/deleted được set,
    sẽ gọi chúng thay vì on_batch_change.

    Attributes:
        on_file_modified: Callback khi file bị sửa (invalidate cache)
        on_file_created: Callback khi file mới được tạo
        on_file_deleted: Callback khi file bị xóa
        on_batch_change: Fallback callback khi có nhiều thay đổi
    """

    on_file_modified: Optional[Callable[[str], None]] = None
    on_file_created: Optional[Callable[[str], None]] = None
    on_file_deleted: Optional[Callable[[str], None]] = None
    on_batch_change: Optional[Callable[[], None]] = None


class _DebouncedEventHandler(FileSystemEventHandler):
    """
    Event handler với debounce để gom nhiều events liên tiếp.

    Khi có nhiều thay đổi liên tục (VD: IDE tự save), ta không muốn
    refresh tree liên tục. Handler này sẽ đợi 500ms sau event cuối
    cùng trước khi trigger callback.
    """

    # Danh sách patterns cần ignore (hardcoded để đơn giản)
    IGNORED_PATTERNS: Set[str] = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
        ".idea",
        ".vscode",
        "dist",
        "build",
        ".mypy_cache",
    }

    def __init__(
        self,
        callbacks: WatcherCallbacks,
        debounce_seconds: float = 0.5,
    ):
        """
        Khởi tạo handler.

        Args:
            callbacks: WatcherCallbacks với các callback functions
            debounce_seconds: Thời gian chờ trước khi trigger callback
        """
        super().__init__()
        self._callbacks = callbacks
        self._debounce_seconds = debounce_seconds
        self._timer: Optional[Timer] = None
        self._pending_events: list[FileChangeEvent] = []

    def _should_ignore(self, path: str) -> bool:
        """
        Kiểm tra xem path có nên bị ignore không.

        Args:
            path: Đường dẫn cần kiểm tra

        Returns:
            True nếu path nằm trong thư mục cần ignore
        """
        path_parts = Path(path).parts
        for pattern in self.IGNORED_PATTERNS:
            if pattern in path_parts:
                return True
        return False

    def _schedule_callback(self):
        """Schedule callback với debounce."""
        # Cancel timer cũ nếu có
        if self._timer is not None:
            self._timer.cancel()

        # Schedule timer mới
        self._timer = Timer(self._debounce_seconds, self._trigger_callback)
        self._timer.daemon = True
        self._timer.start()

    def _trigger_callback(self):
        """Thực thi callback sau debounce - hỗ trợ incremental."""
        if not self._pending_events:
            return

        log_debug(
            f"[FileWatcher] Triggering callback with {len(self._pending_events)} events"
        )

        # Copy và clear pending events
        events = self._pending_events.copy()
        self._pending_events.clear()

        try:
            # Nếu có incremental callbacks, xử lý từng event
            has_incremental = (
                self._callbacks.on_file_modified
                or self._callbacks.on_file_created
                or self._callbacks.on_file_deleted
            )

            if has_incremental:
                # Process từng event riêng
                for event in events:
                    if event.is_directory:
                        continue  # Skip directories, only handle files

                    if (
                        event.event_type == "modified"
                        and self._callbacks.on_file_modified
                    ):
                        self._callbacks.on_file_modified(event.path)
                    elif (
                        event.event_type == "created"
                        and self._callbacks.on_file_created
                    ):
                        self._callbacks.on_file_created(event.path)
                    elif (
                        event.event_type == "deleted"
                        and self._callbacks.on_file_deleted
                    ):
                        self._callbacks.on_file_deleted(event.path)

            # Luôn gọi batch callback nếu có (để refresh tree)
            if self._callbacks.on_batch_change:
                self._callbacks.on_batch_change()

        except Exception as e:
            log_error(f"[FileWatcher] Error in callback: {e}")

    def _handle_event(self, event, event_type: str):
        """Xử lý event chung cho tất cả loại sự kiện."""
        # Ignore các thư mục đặc biệt
        if self._should_ignore(event.src_path):
            return

        # Thêm event vào pending list
        self._pending_events.append(
            FileChangeEvent(
                event_type=event_type,
                path=event.src_path,
                is_directory=event.is_directory,
            )
        )

        log_debug(f"[FileWatcher] Event: {event_type} - {event.src_path}")

        # Schedule callback
        self._schedule_callback()

    # Override event handlers
    def on_created(self, event):
        """Xử lý khi file/folder được tạo."""
        if isinstance(event, (FileCreatedEvent, DirCreatedEvent)):
            self._handle_event(event, "created")

    def on_deleted(self, event):
        """Xử lý khi file/folder bị xóa."""
        if isinstance(event, (FileDeletedEvent, DirDeletedEvent)):
            self._handle_event(event, "deleted")

    def on_modified(self, event):
        """Xử lý khi file bị sửa."""
        # Chỉ xử lý file, không xử lý folder (folder modified quá nhiều noise)
        if isinstance(event, FileModifiedEvent):
            self._handle_event(event, "modified")

    def on_moved(self, event):
        """Xử lý khi file/folder bị di chuyển/đổi tên."""
        if isinstance(event, (FileMovedEvent, DirMovedEvent)):
            self._handle_event(event, "moved")

    def cleanup(self):
        """Dọn dẹp timer khi shutdown."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._pending_events.clear()


class FileWatcher:
    """
    Service theo dõi thay đổi file trong workspace.

    Features:
    - Theo dõi file created/deleted/modified/moved
    - Debounce events để tránh spam
    - Auto-ignore các thư mục như .git, node_modules
    - Chạy trong background thread

    Usage:
        watcher = FileWatcher()
        watcher.start(Path("/path/to/workspace"), callback=lambda: refresh_tree())
        # ... later
        watcher.stop()
    """

    def __init__(self):
        """Khởi tạo FileWatcher."""
        # Sử dụng Any để tránh Pyrefly false positive với Observer type
        self._observer: Optional[Any] = None
        self._handler: Optional[_DebouncedEventHandler] = None
        self._current_path: Optional[Path] = None

    def start(
        self,
        path: Path,
        on_change: Optional[Callable[[], None]] = None,
        callbacks: Optional[WatcherCallbacks] = None,
        debounce_seconds: float = 0.5,
    ):
        """
        Bắt đầu theo dõi một thư mục.

        Nếu đang theo dõi thư mục khác, sẽ tự động stop trước.

        Có thể dùng on_change (backward compatible) hoặc callbacks (incremental).

        Args:
            path: Đường dẫn thư mục cần theo dõi
            on_change: Callback legacy khi có thay đổi (backward compatible)
            callbacks: WatcherCallbacks cho incremental updates
            debounce_seconds: Thời gian debounce (mặc định 0.5s)
        """
        # Stop watcher cũ nếu có
        self.stop()

        if not path.exists() or not path.is_dir():
            log_error(f"[FileWatcher] Invalid path: {path}")
            return

        # Build callbacks - support both old and new API
        if callbacks is None:
            callbacks = WatcherCallbacks(on_batch_change=on_change)

        try:
            self._handler = _DebouncedEventHandler(
                callbacks=callbacks,
                debounce_seconds=debounce_seconds,
            )

            self._observer = Observer()
            self._observer.schedule(
                self._handler,
                str(path),
                recursive=True,
            )
            self._observer.start()

            self._current_path = path
            log_info(f"[FileWatcher] Started watching: {path}")

        except Exception as e:
            log_error(f"[FileWatcher] Failed to start: {e}")
            self.stop()

    def stop(self):
        """Dừng theo dõi."""
        if self._handler is not None:
            self._handler.cleanup()
            self._handler = None

        observer = self._observer
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=2.0)
                log_info(f"[FileWatcher] Stopped watching: {self._current_path}")
            except Exception as e:
                log_error(f"[FileWatcher] Error stopping: {e}")
            finally:
                self._observer = None

        self._current_path = None

    def is_running(self) -> bool:
        """Kiểm tra watcher có đang chạy không."""
        observer = self._observer
        return observer is not None and observer.is_alive()

    @property
    def current_path(self) -> Optional[Path]:
        """Lấy đường dẫn đang được theo dõi."""
        return self._current_path
