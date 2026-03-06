"""
Prompt Types - Cac kieu du lieu dung chung cho pipeline tao prompt.

Cung cap:
- FileEntry: Dataclass dai dien cho 1 file da doc (path, content, error, language)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True, slots=True)
class FileEntry:
    """
    Dai dien cho 1 file da doc tu disk.

    Moi formatter nhan List[FileEntry] va render theo format rieng.
    Immutable (frozen) de dam bao thread-safe khi parallel processing.

    Attributes:
        path: Path goc cua file
        display_path: Path hien thi (co the la relative path)
        content: Noi dung file (None neu bi skip)
        error: Ly do skip (None neu doc thanh cong)
        language: Ngon ngu lap trinh (tu file extension, dung cho syntax highlighting)
    """

    path: Path
    display_path: str
    content: Optional[str]
    error: Optional[str]
    language: str
