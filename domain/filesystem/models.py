from dataclasses import dataclass, field
from typing import List


@dataclass
class TreeItem:
    """
    Một item trong file tree (file hoặc folder).
    Tương đương VscodeTreeItem trong TypeScript.

    is_loaded: True nếu children đã được scan (cho lazy loading).
               False = folder chưa được scan, children = []
    """

    label: str  # Tên hiển thị (filename/dirname)
    path: str  # Đường dẫn tuyệt đối
    is_dir: bool = False
    children: List["TreeItem"] = field(default_factory=list)
    is_loaded: bool = True  # True = đã scan, False = chưa scan (lazy)
