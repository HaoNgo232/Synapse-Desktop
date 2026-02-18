"""
Base Formatter Protocol - Interface chung cho tat ca formatters.
"""

from typing import Protocol, runtime_checkable

from core.prompting.types import FileEntry


@runtime_checkable
class Formatter(Protocol):
    """
    Protocol cho cac file content formatters.

    Moi formatter implement phuong thuc format_files()
    de render List[FileEntry] thanh string output.
    """

    def format_files(self, entries: list[FileEntry]) -> str:
        """Render danh sach FileEntry thanh string theo format cu the."""
        ...
