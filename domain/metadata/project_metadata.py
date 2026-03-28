"""
Domain model cho Project Structural Metadata.

Chua du lieu cau truc thuan tuy tinh tu RelationshipGraph.
Khong co semantic labels (khong can LLM).
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class FileScore:
    """
    Diem quan trong cua mot file trong workspace.

    score = in_edges * 2 + out_edges
    File co diem cao = file trung tam (duoc nhieu file khac su dung).
    """

    path: str  # Relative path tu workspace root
    score: int
    in_edges: int  # So file khac import/call file nay
    out_edges: int  # So file ma file nay import/call


@dataclass(frozen=True)
class ModuleInfo:
    """
    Thong tin ve mot module/nhom file theo directory.

    Module duoc phat hien tu directory structure (khong phai LLM).
    Internal edges cao = cac file trong nhom lien ket chat voi nhau.
    """

    root: str  # Thu muc goc cua module (relative tu workspace)
    file_count: int  # So file trong module
    internal_edges: int  # So edges noi bo (giua cac file cung module)


@dataclass(frozen=True)
class ProjectMetadata:
    """
    Metadata cau truc cua mot project, tinh thuan tuy tu RelationshipGraph.

    Dung de inject vao prompt giup LLM hieu ro hon cau truc project.
    Khong co semantic labels, chi co du lieu cau truc thuan tuy.
    """

    graph_fingerprint: str  # sha256 cua graph de kiem tra staleness
    file_count: int
    edge_count: int
    top_files: List[FileScore]  # Sorted giam dan theo score
    modules: List[ModuleInfo]  # Sorted giam dan theo internal_edges
    sample_flows: List[str]  # Call chains: "a.py -> b.py -> c.py"
