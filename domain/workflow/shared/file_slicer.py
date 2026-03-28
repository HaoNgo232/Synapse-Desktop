"""
File Slicer - Cắt file thông minh theo symbol, line range, hoặc smart (graph-aware).

Thay vì gửi toàn bộ file lớn (2000+ dòng) cho LLM, chỉ gửi
những phần liên quan đến task. Tiết kiệm 60-80% tokens cho files lớn.

Strategy theo thứ tự ưu tiên:
- smart_truncate(): Bóc tách từng CodeUnit (function/class), chấm điểm bằng Graph,
  nhồi vào budget theo thứ tự ưu tiên. Đây là strategy tốt nhất.
- slice_file_by_symbols(): Cắt theo danh sách symbol name + padding.
- slice_file_by_line_range(): Cắt cứng theo dải dòng.
- auto_slice_file(): Tự động chọn strategy phù hợp (legacy).
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Set, TYPE_CHECKING

from domain.codemap.symbol_extractor import extract_symbols
from domain.codemap.types import Symbol
from domain.workflow.shared.code_unit_scorer import CodeUnit, score_code_unit

if TYPE_CHECKING:
    from domain.codemap.graph_builder import CodeMapBuilder

# Ngưỡng "file nhỏ" - file nhỏ hơn này sẽ được trả nguyên, không cắt
SMALL_FILE_THRESHOLD = 100000  # Tăng lên 100k dòng để tránh cắt nhầm code quan trọng


@dataclass(frozen=True, slots=True)
class FileSlice:
    """
    Một phần của file đã được cắt.

    Attributes:
        file_path: Đường dẫn tương đối của file
        content: Nội dung đã cắt
        start_line: Dòng bắt đầu (1-indexed)
        end_line: Dòng kết thúc (1-indexed)
        total_lines: Tổng số dòng của file gốc
        symbols_included: Tên các symbols nằm trong slice
        is_full_file: True nếu đây là toàn bộ file (không cắt)
    """

    file_path: str
    content: str
    start_line: int
    end_line: int
    total_lines: int
    symbols_included: List[str]
    is_full_file: bool


@lru_cache(maxsize=128)
def _get_file_symbols_cached(
    file_path: str, content_hash: int, content: str
) -> List[Symbol]:
    """Cache symbol extraction de tranh re-parse cung file.

    Nhan content truc tiep thay vi re-read tu disk de tranh TOCTOU race condition.
    Cache key dung content_hash de tiet kiem memory (lru_cache hash key).

    Args:
        file_path: Duong dan file (dung cho parser detect ngon ngu)
        content_hash: Hash cua content (dung lam cache key)
        content: Noi dung file da doc san
    """
    try:
        return extract_symbols(file_path, content)
    except Exception:
        return []


def smart_truncate(
    file_path: Path,
    target_tokens: int,
    codemap_builder: Optional["CodeMapBuilder"] = None,
    relevance_hints: Optional[Set[str]] = None,
    workspace_root: Optional[Path] = None,
) -> FileSlice:
    """
    Truncate thông minh: bóc tách CodeUnits từ file, chấm điểm bằng Graph,
    lần lượt nhồi từng unit theo thứ tự ưu tiên cho đến khi đầy token budget.

    Pipeline:
        Đọc file → extract_symbols (Tree-sitter AST) → build CodeUnits
        → score_code_unit (Graph + hints) → sort giảm dần → fill budget (greedy)
        → join kết quả với header per-unit → fallback hard-truncate nếu không parse được

    Thuật toán Fill Budget:
        Sử dụng Greedy Knapsack (Fractional Knapsack variant): sort theo score/token
        giảm dần rồi lần lượt nhét vào cho đến khi đầy. Complexity O(n log n).
        Đây là thuật toán tối ưu cho bài toán này vì:
        - Không cần giá trị chính xác (không làm 0/1 Knapsack chính xác O(2^n))
        - Đầu ra phải liên kết được (không chia nhỏ unit) nên dùng greedy theo score

    Args:
        file_path: Đường dẫn tuyệt đối đến file
        target_tokens: Số token tối đa cho phép
        codemap_builder: Graph builder đã build index (None = chỉ dùng hints)
        relevance_hints: Set tên symbols ưu tiên cao (từ workflow)
        workspace_root: Workspace root để tạo relative path

    Returns:
        FileSlice với content đã được tối ưu theo budget
    """
    rel_path = (
        file_path.relative_to(workspace_root).as_posix()
        if workspace_root
        else file_path.name
    )

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        total_lines = len(lines)

        # Nếu file đã nhỏ hơn budget, trả nguyên
        approx_tokens = len(content) // 4
        if approx_tokens <= target_tokens:
            return FileSlice(
                file_path=rel_path,
                content=content,
                start_line=1,
                end_line=total_lines,
                total_lines=total_lines,
                symbols_included=[],
                is_full_file=True,
            )

        # Bóc tách symbols từ AST (Tree-sitter, đa ngôn ngữ)
        content_hash = hash(content)
        symbols = _get_file_symbols_cached(str(file_path), content_hash, content)

        # Lọc chỉ lấy function và class (bỏ qua import, variable nhỏ)
        meaningful_symbols = [
            s for s in symbols if s.kind.value in ("function", "class", "method")
        ]

        # Nếu không parse được symbol gì, fallback hard-truncate
        if not meaningful_symbols:
            return _hard_truncate(content, lines, total_lines, rel_path, target_tokens)

        # Chuyển Symbol thành CodeUnit (bóc tách nội dung theo line range)
        units: List[CodeUnit] = []
        for sym in meaningful_symbols:
            # Trích xuất nội dung thực tế của symbol từ lines
            unit_lines = lines[sym.line_start - 1 : sym.line_end]
            unit_content = "\n".join(unit_lines)
            unit = CodeUnit(
                name=sym.name,
                kind=sym.kind.value,
                content=unit_content,
                line_start=sym.line_start,
                line_end=sym.line_end,
            )
            # Chấm điểm ngay sau khi tạo
            unit.score = score_code_unit(unit, codemap_builder, relevance_hints)
            units.append(unit)

        # Sort giảm dần theo score → unit quan trọng nhất được chọn trước
        units.sort(key=lambda u: u.score, reverse=True)

        # Greedy fill: nhồi units theo thứ tự ưu tiên vào budget
        selected: List[CodeUnit] = []
        total_used = 0
        for unit in units:
            if total_used + unit.estimated_tokens <= target_tokens:
                selected.append(unit)
                total_used += unit.estimated_tokens

        # Nếu không chọn được gì (unit nhỏ nhất đã vượt budget), fallback
        if not selected:
            return _hard_truncate(content, lines, total_lines, rel_path, target_tokens)

        # Sort lại theo line_start để output đúng thứ tự trong file gốc
        selected.sort(key=lambda u: u.line_start)

        # Nối các units lại, thêm header để AI hiểu context
        output_parts: List[str] = []
        for i, unit in enumerate(selected):
            # Thêm ghi chú nếu có khoảng trống giữa các units
            if i > 0:
                prev = selected[i - 1]
                if unit.line_start > prev.line_end + 1:
                    output_parts.append(
                        f"\n# ... [lines {prev.line_end + 1}-{unit.line_start - 1} skipped] ...\n"
                    )
            output_parts.append(f"# --- {unit.kind.upper()}: {unit.name} ---")
            output_parts.append(unit.content)

        joined_content = "\n".join(output_parts)

        return FileSlice(
            file_path=rel_path,
            content=joined_content,
            start_line=selected[0].line_start,
            end_line=selected[-1].line_end,
            total_lines=total_lines,
            symbols_included=[u.name for u in selected],
            is_full_file=False,
        )

    except Exception:
        return FileSlice(
            file_path=rel_path,
            content="[Error reading file]",
            start_line=1,
            end_line=1,
            total_lines=0,
            symbols_included=[],
            is_full_file=False,
        )


def _hard_truncate(
    content: str,
    lines: List[str],
    total_lines: int,
    rel_path: str,
    target_tokens: int,
) -> FileSlice:
    """
    Fallback: cắt cứng theo số ký tự khi không parse được AST.

    Dùng heuristic 4 ký tự/token. Luôn thêm comment [TRUNCATED] để AI biết
    rằng có phần code bị bỏ qua.

    Args:
        content: Toàn bộ nội dung file
        lines: Danh sách các dòng
        total_lines: Tổng số dòng
        rel_path: Relative path đã tính sẵn
        target_tokens: Số token tối đa
    """
    approx_chars = target_tokens * 4
    truncated = content[:approx_chars]
    truncated += "\n# [TRUNCATED - file too large to parse, showing first portion]"

    # Tính xấp xỉ end_line dựa trên số ký tự
    end_line = min(total_lines, truncated.count("\n") + 1)
    return FileSlice(
        file_path=rel_path,
        content=truncated,
        start_line=1,
        end_line=end_line,
        total_lines=total_lines,
        symbols_included=[],
        is_full_file=False,
    )


def slice_file_by_symbols(
    file_path: Path,
    target_symbols: Set[str],
    context_padding: int = 5,
    workspace_root: Optional[Path] = None,
) -> FileSlice:
    """
    Cắt file chỉ giữ lại các symbols được chỉ định + padding context.

    Args:
        file_path: Đường dẫn tuyệt đối đến file
        target_symbols: Set tên các symbols cần giữ (function, class names)
        context_padding: Số dòng padding trên/dưới mỗi symbol
        workspace_root: Workspace root để tạo relative path

    Returns:
        FileSlice chứa nội dung đã cắt
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        total_lines = len(lines)

        # Extract symbols - truyen content truc tiep, khong re-read tu disk
        content_hash = hash(content)
        symbols = _get_file_symbols_cached(str(file_path), content_hash, content)

        # Tìm symbols matching target
        matching_symbols = [s for s in symbols if s.name in target_symbols]

        if not matching_symbols:
            # Không tìm thấy symbols, trả về đầu file
            end = min(SMALL_FILE_THRESHOLD, total_lines)
            sliced_content = "\n".join(lines[:end])
            if end < total_lines:
                sliced_content += f"\n\n... [truncated {total_lines - end} lines]"

            rel_path = (
                file_path.relative_to(workspace_root).as_posix()
                if workspace_root
                else file_path.name
            )
            return FileSlice(
                file_path=rel_path,
                content=sliced_content,
                start_line=1,
                end_line=end,
                total_lines=total_lines,
                symbols_included=[],
                is_full_file=False,
            )

        # Merge line ranges với padding
        ranges = []
        for sym in matching_symbols:
            start = max(1, sym.line_start - context_padding)
            end = min(total_lines, sym.line_end + context_padding)
            ranges.append((start, end))

        # Merge overlapping ranges
        ranges.sort()
        merged = [ranges[0]]
        for start, end in ranges[1:]:
            if start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        # Build sliced content
        sliced_lines = []
        for i, (start, end) in enumerate(merged):
            if i > 0:
                sliced_lines.append(
                    f"\n... [skipped lines {merged[i - 1][1] + 1}-{start - 1}] ...\n"
                )
            sliced_lines.extend(lines[start - 1 : end])

        sliced_content = "\n".join(sliced_lines)
        rel_path = (
            file_path.relative_to(workspace_root).as_posix()
            if workspace_root
            else file_path.name
        )

        return FileSlice(
            file_path=rel_path,
            content=sliced_content,
            start_line=merged[0][0],
            end_line=merged[-1][1],
            total_lines=total_lines,
            symbols_included=[s.name for s in matching_symbols],
            is_full_file=False,
        )

    except Exception:
        # Fallback: trả empty slice
        rel_path = (
            file_path.relative_to(workspace_root).as_posix()
            if workspace_root
            else file_path.name
        )
        return FileSlice(
            file_path=rel_path,
            content="[Error reading file]",
            start_line=1,
            end_line=1,
            total_lines=0,
            symbols_included=[],
            is_full_file=False,
        )


def slice_file_by_line_range(
    file_path: Path,
    start_line: int,
    end_line: int,
    context_padding: int = 10,
    workspace_root: Optional[Path] = None,
) -> FileSlice:
    """
    Cắt file theo khoảng dòng cụ thể với context padding.

    Args:
        file_path: Đường dẫn tuyệt đối
        start_line: Dòng bắt đầu (1-indexed)
        end_line: Dòng kết thúc (1-indexed)
        context_padding: Số dòng thêm trên/dưới

    Returns:
        FileSlice chứa nội dung đã cắt
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        total_lines = len(lines)

        # Apply padding
        actual_start = max(1, start_line - context_padding)
        actual_end = min(total_lines, end_line + context_padding)

        sliced_lines = lines[actual_start - 1 : actual_end]
        sliced_content = "\n".join(sliced_lines)

        if actual_start > 1:
            sliced_content = (
                f"... [skipped lines 1-{actual_start - 1}] ...\n\n" + sliced_content
            )
        if actual_end < total_lines:
            sliced_content += (
                f"\n\n... [skipped lines {actual_end + 1}-{total_lines}] ..."
            )

        rel_path = (
            file_path.relative_to(workspace_root).as_posix()
            if workspace_root
            else file_path.name
        )

        return FileSlice(
            file_path=rel_path,
            content=sliced_content,
            start_line=actual_start,
            end_line=actual_end,
            total_lines=total_lines,
            symbols_included=[],
            is_full_file=False,
        )

    except Exception:
        rel_path = (
            file_path.relative_to(workspace_root).as_posix()
            if workspace_root
            else file_path.name
        )
        return FileSlice(
            file_path=rel_path,
            content="[Error reading file]",
            start_line=1,
            end_line=1,
            total_lines=0,
            symbols_included=[],
            is_full_file=False,
        )


def auto_slice_file(
    file_path: Path,
    relevance_hints: Optional[Set[str]] = None,
    max_lines: int = 100000,
    workspace_root: Optional[Path] = None,
) -> FileSlice:
    """
    Tự động quyết định strategy cắt file phù hợp (legacy API, vẫn giữ lại).

    Logic:
    1. File nhỏ (< SMALL_FILE_THRESHOLD dòng): trả nguyên
    2. Có relevance_hints (symbol names): dùng slice_file_by_symbols
    3. Không có hints: lấy max_lines dòng đầu + ghi chú "[truncated]"

    Note: Nên dùng smart_truncate() để có Graph-aware scoring tốt hơn.

    Args:
        file_path: Đường dẫn tuyệt đối
        relevance_hints: Optional tên symbols liên quan
        max_lines: Giới hạn dòng tối đa khi cắt
        workspace_root: Workspace root

    Returns:
        FileSlice tối ưu
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        total_lines = len(lines)

        rel_path = (
            file_path.relative_to(workspace_root).as_posix()
            if workspace_root
            else file_path.name
        )

        # Case 1: File nhỏ, trả nguyên
        if total_lines <= SMALL_FILE_THRESHOLD:
            return FileSlice(
                file_path=rel_path,
                content=content,
                start_line=1,
                end_line=total_lines,
                total_lines=total_lines,
                symbols_included=[],
                is_full_file=True,
            )

        # Case 2: Có relevance hints, slice by symbols
        if relevance_hints:
            return slice_file_by_symbols(
                file_path,
                relevance_hints,
                context_padding=5,
                workspace_root=workspace_root,
            )

        # Case 3: Không có hints, lấy đầu file
        end = min(max_lines, total_lines)
        sliced_content = "\n".join(lines[:end])
        if end < total_lines:
            sliced_content += f"\n\n... [truncated {total_lines - end} lines]"

        return FileSlice(
            file_path=rel_path,
            content=sliced_content,
            start_line=1,
            end_line=end,
            total_lines=total_lines,
            symbols_included=[],
            is_full_file=False,
        )

    except Exception:
        rel_path = (
            file_path.relative_to(workspace_root).as_posix()
            if workspace_root
            else file_path.name
        )
        return FileSlice(
            file_path=rel_path,
            content="[Error reading file]",
            start_line=1,
            end_line=1,
            total_lines=0,
            symbols_included=[],
            is_full_file=False,
        )
