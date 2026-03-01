"""
Threading Utilities — Background thread management for PySide6 app.

Provides:
- Global stop event for graceful app shutdown
- Active view tracking (only update UI if view is still active)
- TaskManager for cancellable background tasks
"""

import threading
from typing import Callable, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# ────────────────────────────────────────────────────────────────
# Global Stop Event — set when app is closing
# ────────────────────────────────────────────────────────────────

_app_stop_event = threading.Event()


def get_app_stop_event() -> threading.Event:
    """Get global stop event. Background threads should check this periodically."""
    return _app_stop_event


def signal_app_shutdown() -> None:
    """Signal all threads to stop. Call when app is closing."""
    _app_stop_event.set()


def is_app_stopping() -> bool:
    """Check whether the app is shutting down."""
    return _app_stop_event.is_set()


def reset_app_state() -> None:
    """Reset state (mainly for testing)."""
    _app_stop_event.clear()


# ────────────────────────────────────────────────────────────────
# Active View Tracking
# ────────────────────────────────────────────────────────────────

_active_view_id: Optional[str] = None
_view_lock = threading.Lock()


def set_active_view(view_id: str) -> None:
    """Set the currently active view ID."""
    global _active_view_id
    with _view_lock:
        _active_view_id = view_id


def get_active_view() -> Optional[str]:
    """Get the currently active view ID."""
    with _view_lock:
        return _active_view_id


def is_view_active(view_id: str) -> bool:
    """Check whether a view is still active. Used to decide if UI should be updated."""
    with _view_lock:
        return _active_view_id == view_id


# ────────────────────────────────────────────────────────────────
# TaskHandle & TaskManager
# ────────────────────────────────────────────────────────────────


@dataclass
class TaskHandle:
    """Handle to track and cancel a background task."""

    task_id: str
    view_id: str
    cancel_event: threading.Event

    def cancel(self) -> None:
        """Cancel this task."""
        self.cancel_event.set()

    def is_cancelled(self) -> bool:
        """Check whether this task has been cancelled or the app is stopping."""
        return self.cancel_event.is_set() or is_app_stopping()


class TaskManager:
    """
    Manage background tasks with view tracking and cancellation.

    Usage:
        manager = TaskManager()

        handle = manager.start_task(
            view_id="context_view",
            task_func=my_long_task,
            on_complete=on_task_done,
        )

        # Cancel when switching view
        manager.cancel_view_tasks("context_view")

        # Shutdown when app closes
        manager.shutdown()
    """

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, TaskHandle] = {}
        self._lock = threading.Lock()
        self._task_counter = 0

    def start_task(
        self,
        view_id: str,
        task_func: Callable[[threading.Event], Any],
        on_complete: Optional[Callable[[Any], None]] = None,
    ) -> TaskHandle:
        """
        Start a background task.

        Args:
            view_id: ID of the view that owns this task
            task_func: Function receiving a cancel_event, returns a result
            on_complete: Callback when task completes (runs on worker thread)

        Returns:
            TaskHandle to track/cancel the task
        """
        with self._lock:
            self._task_counter += 1
            task_id = f"{view_id}_{self._task_counter}"
            cancel_event = threading.Event()
            handle = TaskHandle(task_id, view_id, cancel_event)
            self._tasks[task_id] = handle

        def wrapped_task() -> None:
            try:
                result = task_func(cancel_event)
                if not handle.is_cancelled() and is_view_active(view_id):
                    if on_complete:
                        on_complete(result)
            except Exception:
                pass
            finally:
                with self._lock:
                    self._tasks.pop(task_id, None)

        self._executor.submit(wrapped_task)
        return handle

    def cancel_task(self, task_id: str) -> None:
        """Cancel a single task by ID."""
        with self._lock:
            handle = self._tasks.get(task_id)
            if handle:
                handle.cancel()

    def cancel_view_tasks(self, view_id: str) -> None:
        """Cancel all tasks belonging to a view."""
        with self._lock:
            for handle in list(self._tasks.values()):
                if handle.view_id == view_id:
                    handle.cancel()

    def cancel_all(self) -> None:
        """Cancel all tasks."""
        with self._lock:
            for handle in self._tasks.values():
                handle.cancel()

    def shutdown(self, wait: bool = False) -> None:
        """Shutdown the executor.

        Args:
            wait: Whether to wait for running tasks to complete
        """
        self.cancel_all()
        try:
            self._executor.shutdown(wait=wait, cancel_futures=True)
        except TypeError:
            # Python < 3.9 doesn't have cancel_futures
            self._executor.shutdown(wait=wait)


# ────────────────────────────────────────────────────────────────
# Global TaskManager Singleton
# ────────────────────────────────────────────────────────────────

_global_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get or create the global TaskManager singleton."""
    global _global_task_manager
    if _global_task_manager is None:
        _global_task_manager = TaskManager()
    return _global_task_manager


def shutdown_all() -> None:
    """
    Shutdown all resources when app closes.
    Call from MainWindow.closeEvent().
    """
    signal_app_shutdown()

    global _global_task_manager
    if _global_task_manager:
        _global_task_manager.shutdown(wait=False)
        _global_task_manager = None
