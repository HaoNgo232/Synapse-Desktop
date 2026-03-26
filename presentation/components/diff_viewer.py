"""
DiffViewer Component - Hien thi visual diff cho file changes

DiffColors (UI concern) duoc dinh nghia o day.
DiffLine, DiffLineType va generator functions da chuyen sang domain/diff/
de tuong thich voi Clean Architecture (khong phu thuoc UI tu Application layer).

Re-export tu domain/diff/ de backward compatibility.
"""

from domain.diff.types import (
    DiffLine,
    DiffLineType,
    MAX_DIFF_LINES,
    MAX_DIFF_OUTPUT_LINES,
)
from domain.diff.generator import (
    generate_diff_lines,
    generate_create_diff_lines,
    generate_delete_diff_lines,
)

__all__ = [
    "DiffLine",
    "DiffLineType",
    "MAX_DIFF_LINES",
    "MAX_DIFF_OUTPUT_LINES",
    "generate_diff_lines",
    "generate_create_diff_lines",
    "generate_delete_diff_lines",
    "DiffColors",
]


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
