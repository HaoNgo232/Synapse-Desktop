from dataclasses import dataclass
from enum import Enum


class DiffLineType(Enum):
    """Loại dòng trong diff."""

    UNCHANGED = " "
    ADDED = "+"
    REMOVED = "-"


@dataclass(frozen=True)
class DiffLine:
    """Dữ liệu một dòng trong diff view."""

    type: DiffLineType
    content: str
    old_line_no: int | None = None
    new_line_no: int | None = None
