"""
Error Context Builder - Tao context loi cho AI de fix

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
    focused_mode: bool = True,
) -> str:
    """
    Build context day du de AI hieu va fix loi.
    
    FOCUSED MODE (default): Chỉ cung cấp thông tin cần thiết để fix,
    giảm context không liên quan để AI tập trung hơn.

    Args:
        preview_data: Preview data tu analyzer
        row_results: Ket qua apply cac rows
        original_opx: OPX goc (optional)
        include_opx: Co bao gom OPX instructions khong
        focused_mode: Neu True, chi hien thi thong tin can thiet de fix

    Returns:
        String context cho AI
    """
    sections: List[str] = []

    # Header summary
    success_count = sum(1 for r in row_results if r.success)
    failed_count = sum(1 for r in row_results if not r.success)
    
    # FOCUSED MODE: Ngắn gọn, đi thẳng vào vấn đề
    if focused_mode and failed_count > 0:
        sections.extend(_build_focused_error_context(
            row_results, preview_data, original_opx, include_opx
        ))
        return "\n".join(sections)

    # FULL MODE: Chi tiết đầy đủ (legacy behavior)
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


def _build_focused_error_context(
    row_results: List[ApplyRowResult],
    preview_data: PreviewData,
    original_opx: str,
    include_opx: bool,
) -> List[str]:
    """
    Build focused error context - chỉ thông tin cần thiết để fix.
    
    Format tối ưu cho AI:
    1. WHAT FAILED: File + action + error message
    2. SEARCH BLOCK that failed (exact text)
    3. HINT: Possible cause
    4. ACTION REQUIRED: Cụ thể cần làm gì
    """
    sections: List[str] = []
    failed_rows = [r for r in row_results if not r.success]
    
    sections.append("# OPX APPLY FAILED - FIX REQUIRED")
    sections.append("")
    sections.append(f"**{len(failed_rows)} operation(s) failed.**")
    sections.append("")
    
    for i, result in enumerate(failed_rows, 1):
        row = _find_preview_row(preview_data, result.row_index)
        
        sections.append(f"## Error {i}: {result.action.upper()} `{result.path}`")
        sections.append("")
        
        # Error message - làm nổi bật
        sections.append(f"**ERROR:** `{result.message}`")
        sections.append("")
        
        # Cascade failure hint
        if result.is_cascade_failure:
            sections.append("⚠️ **CASCADE FAILURE**: A previous operation modified this file.")
            sections.append("The search pattern may no longer match the current file content.")
            sections.append("")
        
        # Show search block that failed
        if row and row.change_blocks:
            for j, block in enumerate(row.change_blocks):
                search = block.get("search")
                if search:
                    sections.append(f"**Search block that FAILED to match:**")
                    sections.append("```")
                    # Chỉ hiện 10 dòng đầu nếu quá dài
                    search_lines = search.split("\n")
                    if len(search_lines) > 10:
                        sections.append("\n".join(search_lines[:10]))
                        sections.append(f"... ({len(search_lines) - 10} more lines)")
                    else:
                        sections.append(search)
                    sections.append("```")
                    sections.append("")
                    
                    # Intended replacement
                    content = block.get("content", "")
                    if content:
                        sections.append("**Intended replacement:**")
                        sections.append("```")
                        content_lines = content.split("\n")
                        if len(content_lines) > 10:
                            sections.append("\n".join(content_lines[:10]))
                            sections.append(f"... ({len(content_lines) - 10} more lines)")
                        else:
                            sections.append(content)
                        sections.append("```")
                        sections.append("")
        
        sections.append("---")
        sections.append("")
    
    # Action required - cụ thể
    sections.append("# ACTION REQUIRED")
    sections.append("")
    sections.append("1. **Read the current file content** to see what changed")
    sections.append("2. **Update the `<find>` block** to match the CURRENT file state")
    sections.append("3. **Regenerate OPX** with corrected search patterns")
    sections.append("")
    
    if include_opx:
        sections.append("Generate corrected OPX. Use `op=\"patch\"` with updated `<find>` blocks.")
    
    return sections


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
