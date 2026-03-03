"""Shared infrastructure for workflow tools."""

from core.workflows.shared.file_slicer import (
    FileSlice,
    slice_file_by_symbols,
    slice_file_by_line_range,
    auto_slice_file,
    SMALL_FILE_THRESHOLD,
)
from core.workflows.shared.scope_detector import (
    ScopeResult,
    detect_scope_from_file_paths,
    detect_scope_from_git_diff,
    detect_scope_from_symbols,
)
from core.workflows.shared.token_budget_manager import (
    BudgetAllocation,
    BudgetResult,
    TokenBudgetManager,
)
from core.workflows.shared.handoff_formatter import (
    HandoffContext,
    format_handoff_xml,
    format_relationships_section,
)

__all__ = [
    "FileSlice",
    "slice_file_by_symbols",
    "slice_file_by_line_range",
    "auto_slice_file",
    "SMALL_FILE_THRESHOLD",
    "ScopeResult",
    "detect_scope_from_file_paths",
    "detect_scope_from_git_diff",
    "detect_scope_from_symbols",
    "BudgetAllocation",
    "BudgetResult",
    "TokenBudgetManager",
    "HandoffContext",
    "format_handoff_xml",
    "format_relationships_section",
]
