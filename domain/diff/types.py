"""
Diff Types - Kiểu dữ liệu cho diff domain model.

DiffLine và DiffLineType là pure domain types,
không phụ thuộc vào bất kỳ UI framework nào.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DiffLineType(Enum):
    """
    Loai dong trong diff output.
    - ADDED: Dong duoc them vao (bat dau bang +)
    - REMOVED: Dong bi xoa (bat dau bang -)
    - CONTEXT: Dong khong thay doi (context)
    - HEADER: Header line (@@...@@)
    """

    ADDED = "added"
    REMOVED = "removed"
    CONTEXT = "context"
    HEADER = "header"


@dataclass
class DiffLine:
    """
    Mot dong trong diff output.

    Attributes:
        content: Noi dung dong (bao gom prefix +/-/space)
        line_type: Loai dong (ADDED, REMOVED, CONTEXT, HEADER)
        old_line_no: So dong trong file cu (None neu la dong moi)
        new_line_no: So dong trong file moi (None neu la dong bi xoa)
    """

    content: str
    line_type: DiffLineType
    old_line_no: Optional[int] = None
    new_line_no: Optional[int] = None


# Maximum lines to process for diff (performance guard)
MAX_DIFF_LINES = 10000
MAX_DIFF_OUTPUT_LINES = 2000
