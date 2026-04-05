from pathlib import Path
from typing import List

from domain.ports.filesystem import IFileSystem


class LocalFileSystemAdapter(IFileSystem):
    """
    Adapter cho hệ thống tập tin cục bộ, sử dụng pathlib.
    """

    def read_text(self, path: Path) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def list_dir(self, path: Path) -> List[Path]:
        return list(path.iterdir())

    def make_dir(self, path: Path, exist_ok: bool = True) -> None:
        path.mkdir(parents=True, exist_ok=exist_ok)

    def remove(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    def get_mtime(self, path: Path) -> float:
        return path.stat().st_mtime if path.exists() else 0.0
