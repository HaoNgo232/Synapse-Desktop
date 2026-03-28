"""
Code Unit Scorer - Chấm điểm ưu tiên các semantic units (Symbol) trong một file
dựa trên tầm quan trọng trong Graph (callers, callees) và relevance hints.

Được dùng bởi smart_truncate() trong file_slicer.py để quyết định
giữ lại Code Unit nào khi tổng token vượt quá budget.
"""

from dataclasses import dataclass, field
from typing import Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from domain.codemap.graph_builder import CodeMapBuilder


# --- Hằng số chấm điểm ---
SCORE_WEIGHTS = {
    "RELEVANCE_HINT": 100,  # Match với relevance_hints của user
    "RELEVANCE_MAIN": 10,  # Ưu tiên hàm main/entry point
    "RELEVANCE_DOCS": 2,  # Ưu tiên code có documentation
    "IN_DEGREE": 3,  # Được gọi nhiều -> quan trọng
    "OUT_DEGREE": 1,  # Gọi nhiều -> quan trọng
}

# Điểm cơ sở cho mọi symbol (function/class đều quan trọng hơn empty)
SCORE_BASE = 5
# Phạt theo kích thước để tránh một unit lớn nuốt hết budget
PENALTY_PER_THOUSAND_CHARS = 1.0


@dataclass
class CodeUnit:
    """
    Đơn vị code có ý nghĩa (function, class, method) sau khi bóc tách từ Symbol.

    Attributes:
        name: Tên symbol (function/class name)
        kind: Loại symbol ('function', 'class', 'method', v.v.)
        content: Toàn bộ nội dung source code của unit này
        line_start: Dòng bắt đầu trong file gốc (1-indexed)
        line_end: Dòng kết thúc trong file gốc (1-indexed)
        score: Điểm ưu tiên (cao hơn = được giữ lại trước)
        estimated_tokens: Ước tính số tokens (4 chars/token)
    """

    name: str
    kind: str
    content: str
    line_start: int
    line_end: int
    score: float = field(default=0.0)
    estimated_tokens: int = field(default=0)

    def __post_init__(self) -> None:
        """Ước tính token ngay sau khi khởi tạo, dùng heuristic 4 chars/token."""
        if self.estimated_tokens == 0:
            # Heuristic: 1 token ~ 4 ký tự Unicode (tiêu chuẩn GPT tokenizer)
            self.estimated_tokens = max(1, len(self.content) // 4)


def score_code_unit(
    unit: "CodeUnit",
    codemap_builder: Optional["CodeMapBuilder"],
    relevance_hints: Optional[Set[str]] = None,
) -> float:
    """
    Tính điểm ưu tiên cho một CodeUnit dựa trên các yếu tố:
    1. relevance_hints: Symbol được caller xác định là quan trọng (+100)
    2. inbound callers: Số function/class khác gọi đến symbol này (+3 mỗi caller)
    3. outbound callees: Số function symbol này gọi đến (+1 mỗi callee)
    4. base score: Điểm sàn cho mọi symbol (+5)
    5. size penalty: Phạt nhẹ theo số ký tự để tránh nuốt budget (-1 mỗi 1000 ký tự)

    Args:
        unit: CodeUnit cần chấm điểm
        codemap_builder: Graph builder đã build index (None = fallback sang hints-only)
        relevance_hints: Set tên symbols được workflow đánh dấu là quan trọng

    Returns:
        Điểm ưu tiên (float, cao hơn = ưu tiên hơn)
    """
    score: float = SCORE_BASE

    # 1. Relevance hints (Injected by workflows)
    if relevance_hints and unit.name in relevance_hints:
        score += SCORE_WEIGHTS["RELEVANCE_HINT"]

    # 2. Graph-aware scoring (Dependency Importance)
    if codemap_builder:
        callers = codemap_builder.get_callers(unit.name)
        score += len(callers) * SCORE_WEIGHTS["IN_DEGREE"]
        callees = codemap_builder.get_callees(unit.name)
        score += len(callees) * SCORE_WEIGHTS["OUT_DEGREE"]

    # 3. Semantic & Structural boost
    # 3.1. Main / Entry point boost
    if unit.name == "main":
        score += SCORE_WEIGHTS["RELEVANCE_MAIN"]

    # 3.2. Documentation boost (nhận diện qua docstrings)
    if (
        '"""' in unit.content
        or "'''" in unit.content
        or "///" in unit.content
        or "/**" in unit.content
    ):
        score += SCORE_WEIGHTS["RELEVANCE_DOCS"]

    # Phạt theo kích thước để ưu tiên nhiều unit nhỏ hơn một unit khổng lồ
    score -= len(unit.content) / 1000 * PENALTY_PER_THOUSAND_CHARS

    return score
