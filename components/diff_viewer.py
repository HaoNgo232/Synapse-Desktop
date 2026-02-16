"""
DiffViewer Component - Hien thi visual diff cho file changes

Su dung difflib de tinh toan diff.
Mau sac:
- Xanh la (#DCFCE7): Dong duoc them (+)
- Do nhat (#FEE2E2): Dong bi xoa (-)
- Xam (#F3F4F6): Context lines
"""

import difflib
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class DiffLineType(Enum):
    """
    Loai dong trong diff output.
    - ADDED: Dong duoc them vao (bat dau bang +)
    - REMOVED: Dong bi xoa (bat dau bang -)
    - CONTEXT: Dong khong thay doi (context)
    - HEADER: Header line (@@...@@)
    """

    ADDED = "added"
    REMOVED = "removed"
    CONTEXT = "context"
    HEADER = "header"


@dataclass
class DiffLine:
    """
    Mot dong trong diff output.

    Attributes:
        content: Noi dung dong (bao gom prefix +/-/space)
        line_type: Loai dong (ADDED, REMOVED, CONTEXT, HEADER)
        old_line_no: So dong trong file cu (None neu la dong moi)
        new_line_no: So dong trong file moi (None neu la dong bi xoa)
    """

    content: str
    line_type: DiffLineType
    old_line_no: Optional[int] = None
    new_line_no: Optional[int] = None


class DiffColors:
    """
    Mau sac cho cac loai dong trong diff.
    Dark Mode colors - van xai dark bg voi text mau ro rang.
    """

    ADDED_BG = "#052E16"  # Dark green bg - dong duoc them
    REMOVED_BG = "#450A0A"  # Dark red bg - dong bi xoa
    CONTEXT_BG = "#1E293B"  # Slate 800 - context (same as surface)
    HEADER_BG = "#1E3A5F"  # Dark blue - header @@

    # Text colors for contrast on dark backgrounds
    ADDED_TEXT = "#86EFAC"  # Light green text
    REMOVED_TEXT = "#FCA5A5"  # Light red text
    HEADER_TEXT = "#93C5FD"  # Light blue text


# Maximum lines to process for diff (performance guard)
MAX_DIFF_LINES = 10000
MAX_DIFF_OUTPUT_LINES = 2000


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
