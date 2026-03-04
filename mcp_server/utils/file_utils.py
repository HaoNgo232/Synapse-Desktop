"""
File Utilities - Cac tien ich xu ly file dung chung.

Bao gom atomic write va cac path helpers.
"""

import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, data: str) -> None:
    """Ghi file du lieu theo kieu atomic de tranh mat du lieu khi ghi dong thoi.

    Quy trinh:
        1. Tao temp file trong cung thu muc.
        2. Ghi data vao temp file.
        3. Dung os.replace() de atomic rename.
        4. Cleanup temp file neu co loi.

    Args:
        path: Duong dan file can ghi.
        data: Noi dung can ghi.

    Raises:
        Exception: Forward exception neu ghi that bai (sau khi cleanup).
    """
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=path.name,
        suffix=".tmp",
    )
    fd_owned = False
    try:
        f = os.fdopen(tmp_fd, "w", encoding="utf-8")
        fd_owned = True  # os.fdopen thanh cong, no se quan ly fd tu gio
        try:
            f.write(data)
        finally:
            f.close()
        os.replace(tmp_path, str(path))
    except Exception:
        if not fd_owned:
            # os.fdopen that bai truoc khi nhan quyen so huu fd
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
