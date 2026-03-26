"""
File Slicer - Cắt file thông minh theo symbol hoặc line range.

Thay vì gửi toàn bộ file lớn (2000+ dòng) cho LLM, chỉ gửi
những phần liên quan đến task. Tiết kiệm 60-80% tokens cho files lớn.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Set

from domain.codemap.symbol_extractor import extract_symbols
from domain.codemap.types import Symbol

SMALL_FILE_THRESHOLD = 200


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
    max_lines: int = 300,
    workspace_root: Optional[Path] = None,
) -> FileSlice:
    """
    Tự động quyết định strategy cắt file phù hợp.

    Logic:
    1. File nhỏ (< SMALL_FILE_THRESHOLD dòng): trả nguyên
    2. Có relevance_hints (symbol names): dùng slice_file_by_symbols
    3. Không có hints: lấy max_lines dòng đầu + ghi chú "[truncated]"

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
