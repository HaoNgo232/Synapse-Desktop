from dataclasses import dataclass, field


@dataclass
class TreeItem:
    """
    Mot item trong file tree (file hoac folder).
    Tuong duong VscodeTreeItem trong TypeScript.

    is_loaded: True nếu children đã được scan (cho lazy loading).
               False = folder chưa được scan, children = []
    """

    label: str  # Ten hien thi (filename/dirname)
    path: str  # Duong dan tuyet doi
    is_dir: bool = False
    children: list["TreeItem"] = field(default_factory=list)
    is_loaded: bool = True  # True = đã scan, False = chưa scan (lazy)
