from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

"""
Các kiểu dữ liệu cơ bản cho RelationshipGraph ở mức file.

Khác với `domain.codemap.types` (làm việc ở mức symbol), module này chỉ
tập trung vào mối quan hệ giữa các file trong workspace.

Ví dụ:
- Edge: file A IMPORTS file B
- Edge: file A CALLS symbols được định nghĩa trong file B
"""


class EdgeKind(Enum):
    """
    Loại quan hệ giữa các file.

    Lưu ý: Đây là abstraction ở mức file, không phải symbol-level.
    """

    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"


@dataclass(frozen=True)
class Edge:
    """
    Đại diện cho một cạnh trong RelationshipGraph giữa hai file.

    Attributes:
        source_file: Đường dẫn tuyệt đối của file nguồn
        target_file: Đường dẫn tuyệt đối của file đích
        kind: Loại quan hệ giữa hai file
        metadata: Thông tin phụ trợ (tên symbol, dòng code, v.v.)
    """

    source_file: str
    target_file: str
    kind: EdgeKind
    metadata: Optional[dict[str, Any]] = field(
        default_factory=dict, compare=False, hash=False
    )


@dataclass
class FileNode:
    """
    Node biểu diễn một file trong graph.

    Attributes:
        file_path: Đường dẫn tuyệt đối của file
        edges_out: Danh sách các cạnh đi ra từ file này
        edges_in: Danh sách các cạnh đi vào file này
    """

    file_path: str
    edges_out: list[Edge] = field(default_factory=list)
    edges_in: list[Edge] = field(default_factory=list)
