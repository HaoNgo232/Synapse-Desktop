"""Utilities for cross-platform advisory file locking.

Uses ``fcntl`` on Unix and ``msvcrt`` on Windows.
"""

from typing import Protocol

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]


class LockableFile(Protocol):
    """Minimal protocol for file objects that can be locked."""

    def fileno(self) -> int: ...

    def seek(self, offset: int, whence: int = 0) -> int: ...


def lock_file(file_obj: LockableFile) -> None:
    """Acquire an exclusive lock on a file object.

    Locking is advisory. If neither backend is available, this is a no-op.
    """
    if fcntl is not None:
        fcntl.flock(file_obj, fcntl.LOCK_EX)
        return

    if msvcrt is not None:
        file_obj.seek(0)
        msvcrt.locking(file_obj.fileno(), msvcrt.LK_LOCK, 1)


def unlock_file(file_obj: LockableFile) -> None:
    """Release a previously acquired lock on a file object."""
    if fcntl is not None:
        fcntl.flock(file_obj, fcntl.LOCK_UN)
        return

    if msvcrt is not None:
        file_obj.seek(0)
        msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
