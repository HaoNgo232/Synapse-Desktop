"""
File Utilities - Cac tien ich xu ly file dung chung.

Bao gom atomic write va cac path helpers.
"""

import os
import tempfile
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore


def atomic_write(path: Path, data: str) -> None:
    """Ghi file du lieu theo kieu atomic de tranh mat du lieu khi ghi dong thoi.

    Sua loi: Khoa (lock) thuc su tren lock file chu khong phai temp file
    de bao ve viec ghi tu nhieu process cung luc.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_fd = None
    try:
        if fcntl:
            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)

        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=path.name,
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    finally:
        if lock_fd is not None:
            if fcntl:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
