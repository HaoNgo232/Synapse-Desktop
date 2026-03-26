"""
Diff Generator - Tao DiffLine lists tu content changes.

Pure domain functions, khong phu thuoc UI hay infrastructure.
"""

import difflib
from typing import List

from domain.diff.types import (
    DiffLine,
    DiffLineType,
    MAX_DIFF_LINES,
    MAX_DIFF_OUTPUT_LINES,
)


def generate_diff_lines(
    old_content: str, new_content: str, file_path: str = "", context_lines: int = 3
) -> List[DiffLine]:
    """
    Tao danh sach DiffLine tu old va new content.
    Su dung unified_diff de tinh toan thay doi.

    Args:
        old_content: Noi dung file cu (hoac empty string neu tao moi)
        new_content: Noi dung file moi
        file_path: Duong dan file (dung cho header)
        context_lines: So dong context xung quanh thay doi

    Returns:
        List DiffLine de hien thi
    """
    # Split content thanh lines
    old_lines = old_content.splitlines(keepends=True) if old_content else []
    new_lines = new_content.splitlines(keepends=True) if new_content else []

    # Guard against very large files
    if len(old_lines) > MAX_DIFF_LINES or len(new_lines) > MAX_DIFF_LINES:
        return [
            DiffLine(
                content=f"[File too large for diff preview: {len(old_lines)}/{len(new_lines)} lines]",
                line_type=DiffLineType.HEADER,
            )
        ]

    # Tao unified diff
    diff_generator = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{file_path}" if file_path else "a/file",
        tofile=f"b/{file_path}" if file_path else "b/file",
        lineterm="",
        n=context_lines,
    )

    # Parse diff output
    result: List[DiffLine] = []
    old_line_no = 0
    new_line_no = 0

    for line in diff_generator:
        # Strip trailing newline for display
        line = line.rstrip("\n\r")

        if line.startswith("@@"):
            # Header line - parse line numbers
            result.append(DiffLine(content=line, line_type=DiffLineType.HEADER))
            # Parse @@ -old_start,old_count +new_start,new_count @@
            # Reset line counters based on header
            try:
                parts = line.split(" ")
                old_range = parts[1][1:]  # Remove -
                new_range = parts[2][1:]  # Remove +
                old_line_no = int(old_range.split(",")[0]) - 1
                new_line_no = int(new_range.split(",")[0]) - 1
            except (IndexError, ValueError):
                pass

        elif line.startswith("---") or line.startswith("+++"):
            # File headers - skip them
            continue

        elif line.startswith("+"):
            # Dong duoc them
            new_line_no += 1
            result.append(
                DiffLine(
                    content=line, line_type=DiffLineType.ADDED, new_line_no=new_line_no
                )
            )

        elif line.startswith("-"):
            # Dong bi xoa
            old_line_no += 1
            result.append(
                DiffLine(
                    content=line,
                    line_type=DiffLineType.REMOVED,
                    old_line_no=old_line_no,
                )
            )

        else:
            # Context line (bat dau bang space)
            old_line_no += 1
            new_line_no += 1
            result.append(
                DiffLine(
                    content=line,
                    line_type=DiffLineType.CONTEXT,
                    old_line_no=old_line_no,
                    new_line_no=new_line_no,
                )
            )

        # Early termination for very large diffs
        if len(result) >= MAX_DIFF_OUTPUT_LINES:
            result.append(
                DiffLine(
                    content=f"[... truncated, showing first {MAX_DIFF_OUTPUT_LINES} lines ...]",
                    line_type=DiffLineType.HEADER,
                )
            )
            break

    return result


def generate_create_diff_lines(new_content: str, file_path: str = "") -> List[DiffLine]:
    """
    Tao diff lines cho CREATE action (toan bo noi dung la moi).

    Args:
        new_content: Noi dung file moi
        file_path: Duong dan file

    Returns:
        List DiffLine voi tat ca dong la ADDED
    """
    return generate_diff_lines("", new_content, file_path)


def generate_delete_diff_lines(old_content: str, file_path: str = "") -> List[DiffLine]:
    """
    Tao diff lines cho DELETE action (toan bo noi dung bi xoa).

    Args:
        old_content: Noi dung file cu
        file_path: Duong dan file

    Returns:
        List DiffLine voi tat ca dong la REMOVED
    """
    return generate_diff_lines(old_content, "", file_path)
