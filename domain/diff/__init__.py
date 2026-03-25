"""
Domain Diff - Types và generator functions cho diff operations.

Module này chứa pure domain logic cho diff computation,
không phụ thuộc vào UI hay infrastructure.
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
]
