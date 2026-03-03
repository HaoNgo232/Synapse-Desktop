"""
Prompt Types - Cac kieu du lieu cho ket qua build prompt.

Cung cap:
- FileTokenInfo: Thong tin token cua tung file trong prompt
- BuildResult: Ket qua toan dien cua qua trinh build prompt,
  bao gom prompt text, token breakdown, per-file metadata, va trim notes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class FileTokenInfo:
    """
    Thong tin token cua mot file trong prompt.

    Luu tru path, so token, va cac co trang thai (is_dependency, was_trimmed)
    de ho tro multi-agent decision making.

    Attributes:
        path: Duong dan tuong doi cua file
        tokens: So luong token cua file content
        is_dependency: True neu file duoc them tu dependency expansion (Feature 3)
        was_trimmed: True neu file bi cat giam boi ContextTrimmer (Feature 2)
    """

    path: str
    tokens: int
    is_dependency: bool = False
    was_trimmed: bool = False


@dataclass(slots=True)
class BuildResult:
    """
    Ket qua day du cua qua trinh build prompt.

    Chua tat ca metadata can thiet cho AI planner agent de ra quyet dinh
    (vi du: tong token vuot budget -> can split; file nao chiem nhieu token nhat).

    Method cu `build_prompt()` van tra ve tuple 3 phan tu de backward-compat.
    Method moi `build_prompt_full()` tra ve BuildResult truc tiep.

    Attributes:
        prompt_text: Noi dung prompt da assemble
        total_tokens: Tong so token cua prompt
        file_count: So luong file trong prompt
        format: Output format da su dung (xml, json, plain, smart)
        profile: Ten profile da ap dung (None neu khong dung profile)
        trimmed: True neu ContextTrimmer da cat giam context (Feature 2)
        trimmed_notes: Danh sach ghi chu ve nhung phan bi cat
        breakdown: Token breakdown theo tung section (instruction, tree, rule, ...)
        files: Danh sach thong tin token per-file
        dependency_graph: Do thi phu thuoc giua cac file (Feature 3)
    """

    prompt_text: str
    total_tokens: int
    file_count: int
    format: str
    profile: Optional[str] = None
    trimmed: bool = False
    trimmed_notes: List[str] = field(default_factory=list)
    breakdown: Dict[str, int] = field(default_factory=dict)
    files: List[FileTokenInfo] = field(default_factory=list)
    dependency_graph: Optional[Dict[str, List[str]]] = None

    def to_legacy_tuple(self) -> tuple[str, int, Dict[str, int]]:
        """
        Chuyen doi BuildResult ve tuple 3 phan tu (prompt, tokens, breakdown)
        de backward-compatible voi API cu cua build_prompt().

        Returns:
            Tuple (prompt_text, total_tokens, breakdown)
        """
        return self.prompt_text, self.total_tokens, self.breakdown

    def to_metadata_dict(self) -> Dict[str, Any]:
        """
        Serialize metadata thanh dict de tra ve JSON cho multi-agent workflow.

        Khong bao gom prompt_text de giam kich thuoc response.
        prompt_text da duoc ghi ra output_file.

        Returns:
            Dict chua metadata co cau truc cho AI planner
        """
        return {
            "status": "ok",
            "total_tokens": self.total_tokens,
            "file_count": self.file_count,
            "format": self.format,
            "profile": self.profile,
            "trimmed": self.trimmed,
            "trimmed_notes": self.trimmed_notes,
            "breakdown": self.breakdown,
            "files": [
                {
                    "path": f.path,
                    "tokens": f.tokens,
                    "is_dependency": f.is_dependency,
                    "was_trimmed": f.was_trimmed,
                }
                for f in self.files
            ],
            "dependency_graph": self.dependency_graph,
        }
