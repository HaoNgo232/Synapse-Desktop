"""
Diff Generator - Tinh toan visual diff lines (domain logic).
"""

import difflib
from typing import List
from shared.types.diff_types import DiffLine, DiffLineType

# Maximum lines to process for diff (performance guard)
MAX_DIFF_LINES = 10000
MAX_DIFF_OUTPUT_LINES = 2000


def generate_diff_lines(
    old_content: str, new_content: str, file_path: str = "", context_lines: int = 3
) -> List[DiffLine]:
    """
    Tao danh sach DiffLine tu old va new content.
    Su dung unified_diff de tinh toan thay doi.
    """
    # Split content thanh lines
    old_lines = old_content.splitlines(keepends=True) if old_content else []
    new_lines = new_content.splitlines(keepends=True) if new_content else []

    # Guard against very large files
    if len(old_lines) > MAX_DIFF_LINES or len(new_lines) > MAX_DIFF_LINES:
        return [
            DiffLine(
                content=f"[File too large for diff preview: {len(old_lines)}/{len(new_lines)} lines]",
                type=DiffLineType.UNCHANGED,  # Placeholder for Header which we don't have yet? Wait.
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
            result.append(
                DiffLine(content=line, type=DiffLineType.UNCHANGED)
            )  # Use UNCHANGED for headers in shared types
            # Parse @@ -old_start,old_count +new_start,new_count @@
            try:
                parts = line.split(" ")
                old_range = parts[1][1:]  # Remove -
                new_range = parts[2][1:]  # Remove +
                old_line_no = int(old_range.split(",")[0]) - 1
                new_line_no = int(new_range.split(",")[0]) - 1
            except (IndexError, ValueError):
                pass

        elif line.startswith("---") or line.startswith("+++"):
            continue

        elif line.startswith("+"):
            new_line_no += 1
            result.append(
                DiffLine(content=line, type=DiffLineType.ADDED, new_line_no=new_line_no)
            )

        elif line.startswith("-"):
            old_line_no += 1
            result.append(
                DiffLine(
                    content=line,
                    type=DiffLineType.REMOVED,
                    old_line_no=old_line_no,
                )
            )

        else:
            old_line_no += 1
            new_line_no += 1
            result.append(
                DiffLine(
                    content=line,
                    type=DiffLineType.UNCHANGED,
                    old_line_no=old_line_no,
                    new_line_no=new_line_no,
                )
            )

        if len(result) >= MAX_DIFF_OUTPUT_LINES:
            result.append(
                DiffLine(
                    content=f"[... truncated, showing first {MAX_DIFF_OUTPUT_LINES} lines ...]",
                    type=DiffLineType.UNCHANGED,
                )
            )
            break

    return result


def generate_create_diff_lines(new_content: str, file_path: str = "") -> List[DiffLine]:
    return generate_diff_lines("", new_content, file_path)


def generate_delete_diff_lines(old_content: str, file_path: str = "") -> List[DiffLine]:
    return generate_diff_lines(old_content, "", file_path)
