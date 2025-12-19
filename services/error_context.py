"""
Error Context Builder - Tao context loi cho AI de fix

Port tu: /home/hao/Desktop/labs/overwrite/src/webview-ui/src/components/apply-tab/preview-table.tsx

Tao error context day du de AI co the hieu va fix ngay:
- Thong tin loi chi tiet
- Previous operations da thanh cong
- Search patterns that failed
- Instructions ro rang de fix
"""

from dataclasses import dataclass
from typing import List, Optional

from services.preview_analyzer import PreviewRow, PreviewData
from core.file_actions import ActionResult
from services.clipboard_utils import copy_to_clipboard


@dataclass
class ApplyRowResult:
    """Ket qua apply mot row"""

    row_index: int
    path: str
    action: str
    success: bool
    message: str
    is_cascade_failure: bool = False


def build_error_context_for_ai(
    preview_data: PreviewData,
    row_results: List[ApplyRowResult],
    original_opx: str = "",
    include_opx: bool = True,
) -> str:
    """
    Build context day du de AI hieu va fix loi.

    Args:
        preview_data: Preview data tu analyzer
        row_results: Ket qua apply cac rows
        original_opx: OPX goc (optional)
        include_opx: Co bao gom OPX instructions khong

    Returns:
        String context cho AI
    """
    sections: List[str] = []

    # Header summary
    success_count = sum(1 for r in row_results if r.success)
    failed_count = sum(1 for r in row_results if not r.success)

    sections.extend(
        [
            "## Apply Results Summary",
            f"- Successful operations: {success_count}",
            f"- Failed operations: {failed_count}",
            f"- Total operations: {len(row_results)}",
            "",
            "---",
            "",
        ]
    )

    # Successful operations (important for context)
    success_rows = [r for r in row_results if r.success]
    if success_rows:
        sections.extend(_build_success_section(success_rows, preview_data))

    # Failed operations (need fixing)
    failed_rows = [r for r in row_results if not r.success]
    if failed_rows:
        sections.extend(_build_failed_section(failed_rows, preview_data, row_results))

    # Original OPX reference
    if include_opx and original_opx:
        sections.extend(
            [
                "",
                "---",
                "",
                "## Original OPX (For Reference)",
                "",
                "```xml",
                original_opx.strip(),
                "```",
                "",
            ]
        )

    # Fix instructions
    sections.extend(_build_fix_instructions(include_opx))

    return "\n".join(sections)


def _build_success_section(
    success_rows: List[ApplyRowResult], preview_data: PreviewData
) -> List[str]:
    """Build section cho cac operations thanh cong"""
    section = [
        "## Successfully Applied Operations",
        "",
        "**These operations completed successfully. The files below have ALREADY been modified.**",
        "**When fixing failed operations, account for these changes that are now in the codebase.**",
        "",
    ]

    for result in success_rows:
        row = _find_preview_row(preview_data, result.row_index)

        section.extend(
            [
                f"### Row {result.row_index + 1}: {result.action.upper()} `{result.path}`",
                "- Status: SUCCESS",
                f"- Operation: {result.action}",
            ]
        )

        if row and row.description:
            section.append(f"- Description: {row.description}")

        section.append("")

    section.extend(["---", "", ""])
    return section


def _build_failed_section(
    failed_rows: List[ApplyRowResult],
    preview_data: PreviewData,
    all_results: List[ApplyRowResult],
) -> List[str]:
    """Build section cho cac operations that bai"""
    section = [
        "## FAILED Operations (NEEDS FIXING)",
        "",
        "**The following operations failed and need to be corrected:**",
        "",
    ]

    # Group by file
    file_errors: dict = {}
    for result in failed_rows:
        if result.path not in file_errors:
            file_errors[result.path] = []
        file_errors[result.path].append(result)

    for file_path, errors in file_errors.items():
        section.extend(
            [
                f"### File: `{file_path}`",
                "",
            ]
        )

        for result in errors:
            row = _find_preview_row(preview_data, result.row_index)

            section.extend(
                [
                    f"#### Row {result.row_index + 1}: {result.action.upper()}",
                    f"- **Error**: {result.message}",
                ]
            )

            if result.is_cascade_failure:
                # Find previous successful ops on same file
                prev_success = [
                    r
                    for r in all_results[: result.row_index]
                    if r.path == file_path and r.success
                ]
                section.append(
                    "- **CASCADE FAILURE**: Previous row(s) modified this file"
                )
                if prev_success:
                    section.append("- Previous successful operations:")
                    for prev in prev_success:
                        section.append(f"  - Row {prev.row_index + 1}: {prev.action}")

            if row and row.change_blocks:
                section.append("")
                section.append("**Attempted changes:**")
                for i, block in enumerate(row.change_blocks):
                    section.extend(_build_change_block_details(block, i + 1))

            section.extend(["", "---", ""])

    return section


def _build_change_block_details(block: dict, index: int) -> List[str]:
    """Build chi tiet cho mot change block"""
    details = [f"Change block {index}: {block.get('description', 'N/A')}"]

    search = block.get("search")
    content = block.get("content", "")

    if search:
        details.extend(
            [
                "Search pattern (NOT FOUND):",
                "```",
                search,
                "```",
                "Intended replacement:",
                "```",
                content,
                "```",
            ]
        )
    else:
        details.extend(
            [
                "Intended content:",
                "```",
                content,
                "```",
            ]
        )

    return details


def _build_fix_instructions(include_opx: bool) -> List[str]:
    """Build instructions cho AI de fix"""
    instructions = [
        "",
        "# Instructions to Fix",
        "",
        "Please analyze the errors above and understand the current state of each file.",
        "",
        "**Key points to fix:**",
        "1. Search patterns that failed - they need to match the CURRENT file content",
        "2. Cascade failures - previous operations changed the file, update your patterns accordingly",
        "3. File structure - ensure you understand the full context of each file",
        "",
        "**For cascade failures:**",
        "- Update search patterns to match the file state AFTER previous operations",
        '- Consider using occurrence="last" if multiple matches exist',
        "- Make search patterns more specific by including more surrounding context",
        "",
    ]

    if include_opx:
        instructions.append(
            "Generate new OPX with corrected operations based on the current file states."
        )
    else:
        instructions.append(
            "Provide the corrected code changes that should be applied to fix these issues."
        )

    return instructions


def _find_preview_row(
    preview_data: PreviewData, row_index: int
) -> Optional[PreviewRow]:
    """Tim preview row theo index"""
    if row_index < len(preview_data.rows):
        return preview_data.rows[row_index]
    return None


def build_general_error_context(
    error_type: str,
    error_message: str,
    file_path: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> str:
    """
    Build context cho loi bat ky trong app (khong chi Apply).

    Args:
        error_type: Loai loi (e.g., "Parse Error", "File Error")
        error_message: Message loi
        file_path: File lien quan (optional)
        additional_context: Context them (optional)

    Returns:
        String context cho AI
    """
    sections = [
        f"## Error Type: {error_type}",
        "",
        f"**Error Message:**",
        "```",
        error_message,
        "```",
        "",
    ]

    if file_path:
        sections.extend(
            [
                f"**Related File:** `{file_path}`",
                "",
            ]
        )

    if additional_context:
        sections.extend(
            [
                "**Additional Context:**",
                additional_context,
                "",
            ]
        )

    sections.extend(
        [
            "---",
            "",
            "# Instructions",
            "",
            "Please analyze this error and provide:",
            "1. Root cause of the error",
            "2. Step-by-step fix instructions",
            "3. Any code changes needed (in OPX format if applicable)",
            "",
        ]
    )

    return "\n".join(sections)


def copy_error_to_clipboard(context: str) -> bool:
    """
    Copy error context to clipboard.

    Returns:
        True neu thanh cong, False neu that bai
    """
    success, _ = copy_to_clipboard(context)
    return success
