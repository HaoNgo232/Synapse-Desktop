"""
Event Debouncer cho File Watcher.

Gom nhom cac file system events va dispatch callback sau debounce.
Tranh spam callback khi co nhieu thay doi lien tuc (vd: IDE auto-save).
"""

from threading import Timer
from typing import Optional

from core.logging_config import log_debug, log_error
from services.interfaces.file_watcher_service import (
    FileChangeEvent,
    IEventDebouncer,
    WatcherCallbacks,
)


class TimerEventDebouncer(IEventDebouncer):
    """
    Debouncer su dung threading.Timer.

    Doi mot khoang thoi gian (debounce_seconds) sau event cuoi cung
    truoc khi trigger callback. Neu co event moi trong khoang thoi gian do,
    timer duoc reset.

    Ho tro 2 che do:
    - Incremental: Goi on_file_modified/created/deleted cho tung event
    - Batch: Goi on_batch_change khi co thay doi bat ky

    Attributes:
        _callbacks: Tap hop callbacks se duoc goi
        _debounce_seconds: Thoi gian cho truoc khi dispatch
        _timer: Timer hien tai (None neu khong co pending)
        _pending_events: Danh sach events dang cho xu ly
    """

    def __init__(
        self,
        callbacks: WatcherCallbacks,
        debounce_seconds: float = 0.5,
    ):
        """
        Khoi tao debouncer.

        Args:
            callbacks: WatcherCallbacks voi cac callback functions
            debounce_seconds: Thoi gian cho truoc khi trigger callback
        """
        self._callbacks = callbacks
        self._debounce_seconds = debounce_seconds
        self._timer: Optional[Timer] = None
        self._pending_events: list[FileChangeEvent] = []

    def add_event(self, event: FileChangeEvent) -> None:
        """
        Them event vao hang doi va reset debounce timer.

        Moi khi co event moi, timer cu bi huy va timer moi duoc tao.
        Chi khi khong co event moi trong debounce_seconds thi callback moi duoc goi.

        Args:
            event: Su kien file change can xu ly
        """
        self._pending_events.append(event)

        # Cancel timer cu neu co
        if self._timer is not None:
            self._timer.cancel()

        # Schedule timer moi
        self._timer = Timer(self._debounce_seconds, self._trigger_callback)
        self._timer.daemon = True
        self._timer.start()

    def cleanup(self) -> None:
        """Don dep timer va pending events khi shutdown."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._pending_events.clear()

    def _trigger_callback(self) -> None:
        """
        Thuc thi callback sau debounce - ho tro incremental.

        Process flow:
        1. Copy va clear pending events
        2. Neu co incremental callbacks, xu ly tung event rieng
        3. Luon goi batch callback (de refresh tree)
        """
        if not self._pending_events:
            return

        log_debug(
            f"[FileWatcher] Triggering callback with {len(self._pending_events)} events"
        )

        # Copy va clear pending events
        events = self._pending_events.copy()
        self._pending_events.clear()

        try:
            # Neu co incremental callbacks, xu ly tung event
            has_incremental = (
                self._callbacks.on_file_modified
                or self._callbacks.on_file_created
                or self._callbacks.on_file_deleted
            )

            if has_incremental:
                # Process tung event rieng
                for event in events:
                    if event.is_directory:
                        continue  # Skip directories, chi handle files

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

            # Luon goi batch callback neu co (de refresh tree)
            if self._callbacks.on_batch_change:
                self._callbacks.on_batch_change()

        except Exception as e:
            log_error(f"[FileWatcher] Error in callback: {e}")
