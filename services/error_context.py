"""
Error Context Builder - Tao context loi cho AI de fix

Tao error context day du de AI co the hieu va fix ngay:
- Thong tin loi chi tiet
- Previous operations da thanh cong
- Search patterns that failed
- Instructions ro rang de fix
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from services.preview_analyzer import PreviewRow, PreviewData
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
    workspace_path: Optional[str] = None,
    include_file_content: bool = True,
) -> str:
    """
    Build context day du de AI hieu va fix loi.

    FOCUSED MODE (default): Chỉ cung cấp thông tin cần thiết để fix,
    giảm context không liên quan để AI tập trung hơn.

    ENHANCED: Include current file content để AI có thể fix ngay mà không cần
    hỏi thêm về nội dung file.

    Args:
        preview_data: Preview data tu analyzer
        row_results: Ket qua apply cac rows
        original_opx: OPX goc (optional)
        include_opx: Co bao gom OPX instructions khong
        focused_mode: Neu True, chi hien thi thong tin can thiet de fix
        workspace_path: Path to workspace (for reading current file content)
        include_file_content: Include current content of failed files

    Returns:
        String context cho AI
    """
    sections: List[str] = []

    # Header summary
    success_count = sum(1 for r in row_results if r.success)
    failed_count = sum(1 for r in row_results if not r.success)

    # FOCUSED MODE: Ngắn gọn, đi thẳng vào vấn đề
    if focused_mode and failed_count > 0:
        sections.extend(
            _build_focused_error_context(
                row_results,
                preview_data,
                original_opx,
                include_opx,
                workspace_path,
                include_file_content,
            )
        )
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
    _original_opx: str,
    include_opx: bool,
    workspace_path: Optional[str] = None,
    include_file_content: bool = True,
) -> List[str]:
    """
    Build focused error context - chỉ thông tin cần thiết để fix.

    Format tối ưu cho AI:
    1. WHAT FAILED: File + action + error message
    2. CURRENT FILE CONTENT (so AI can see actual state)
    3. SEARCH BLOCK that failed (exact text)
    4. HINT: Possible cause
    5. ACTION REQUIRED: Cụ thể cần làm gì
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
            sections.append(
                "⚠️ **CASCADE FAILURE**: A previous operation modified this file."
            )
            sections.append(
                "The search pattern may no longer match the current file content."
            )
            sections.append("")

        # NEW: Include current file content để AI có thể fix ngay
        if include_file_content and workspace_path:
            current_content = _read_current_file_content(result.path, workspace_path)
            if current_content:
                sections.append(
                    "**CURRENT FILE CONTENT (after any successful operations):**"
                )
                sections.append("```")
                # Limit to 200 lines for readability
                content_lines = current_content.split("\n")
                if len(content_lines) > 200:
                    sections.append("\n".join(content_lines[:200]))
                    sections.append(f"... ({len(content_lines) - 200} more lines)")
                else:
                    sections.append(current_content)
                sections.append("```")
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
                            sections.append(
                                f"... ({len(content_lines) - 10} more lines)"
                            )
                        else:
                            sections.append(content)
                        sections.append("```")
                        sections.append("")

        sections.append("---")
        sections.append("")

    # Successful operations context (AI can biet file nao da thay doi)
    success_rows = [r for r in row_results if r.success]
    if success_rows:
        sections.append("## Successfully Applied (already in codebase)")
        sections.append("")
        for sr in success_rows:
            sections.append(f"- {sr.action.upper()} `{sr.path}` - {sr.message}")
        sections.append("")
        sections.append(
            "**Note:** These changes are already applied. "
            "Account for them when fixing failed operations."
        )
        sections.append("")
        sections.append("---")
        sections.append("")

    # Action required - huong dan ro rang cho IDE agent (da co edit tool san)
    sections.append("# ACTION REQUIRED")
    sections.append("")
    sections.append(
        "Fix the failed operations above. All information you need is provided. "
        "Do NOT ask questions - start fixing immediately."
    )
    sections.append("")
    sections.append("**For each failed operation:**")
    sections.append(
        "1. Open the file listed above"
    )
    sections.append(
        "2. Find the section that needs to be changed "
        "(use the CURRENT FILE CONTENT and the failed search block as reference)"
    )
    sections.append(
        "3. Apply the intended replacement shown above"
    )
    sections.append(
        "4. If a cascade failure occurred, the file was already modified by "
        "a previous operation - find the NEW text in the file and apply the change there"
    )
    sections.append("")
    sections.append(
        "**IMPORTANT:** Only fix the FAILED operations. "
        "Successful operations are already applied - do NOT touch them."
    )
    sections.append("")

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
    """Build instructions cho IDE agent de fix truc tiep."""
    instructions = [
        "",
        "# Instructions to Fix",
        "",
        "Analyze the errors above and fix the failed operations directly.",
        "Do NOT ask questions - all information you need is above.",
        "",
        "**Steps:**",
        "1. Open each failed file",
        "2. Find the code section that needs changing (refer to the search patterns and current file state)",
        "3. Apply the intended replacement using your edit tools",
        "",
        "**For cascade failures:**",
        "- A previous operation already changed the file",
        "- Find the NEW text in the file (after previous changes) and apply the fix there",
        "",
        "**IMPORTANT:** Only fix FAILED operations. Successful ones are already applied.",
        "",
    ]

    return instructions


def _read_current_file_content(file_path: str, workspace_path: str) -> Optional[str]:
    """
    Đọc nội dung hiện tại của file để AI có thể thấy state thực.

    Args:
        file_path: Relative or absolute path to file
        workspace_path: Workspace root path

    Returns:
        File content or None if cannot read
    """
    try:
        # Try as absolute path first
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(workspace_path) / file_path

        if not path.exists() or not path.is_file():
            return None

        # Check file size (limit to 100KB)
        if path.stat().st_size > 100000:
            return None

        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


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
    workspace_path: Optional[str] = None,
) -> str:
    """
    Build context day du cho loi bat ky trong app.

    Cung cap du thong tin de AI co the fix ngay ma khong can hoi lai:
    - Error details
    - File content hien tai (neu co OPX -> extract file paths -> doc content)
    - OPX goc duoc format trong code block
    - Prompt ro rang yeu cau respond bang OPX format

    Args:
        error_type: Loai loi (e.g., "Parse Error", "Apply Error")
        error_message: Message loi
        file_path: File lien quan (optional)
        additional_context: Context them, thuong la OPX goc (optional)
        workspace_path: Workspace root path de doc file content (optional)

    Returns:
        String context day du cho AI fix ngay
    """
    sections = [
        f"# {error_type.upper()} - FIX REQUIRED",
        "",
        f"**Error:** `{error_message}`",
        "",
    ]

    if file_path:
        sections.extend(
            [
                f"**Related File:** `{file_path}`",
                "",
            ]
        )

    # Neu additional_context la OPX, extract file paths va doc content hien tai
    if additional_context and workspace_path:
        affected_files = _extract_file_paths_from_opx(additional_context)
        if affected_files:
            sections.append("## Current File Contents")
            sections.append("")
            sections.append(
                "Below are the CURRENT contents of files that need to be fixed. "
                "Use these to locate the exact code sections that need changes."
            )
            sections.append("")
            for fp in affected_files:
                content = _read_current_file_content(fp, workspace_path)
                if content:
                    sections.append(f"### `{fp}`")
                    sections.append("```")
                    content_lines = content.split("\n")
                    if len(content_lines) > 300:
                        sections.append("\n".join(content_lines[:300]))
                        sections.append(
                            f"... ({len(content_lines) - 300} more lines)"
                        )
                    else:
                        sections.append(content)
                    sections.append("```")
                    sections.append("")

    # OPX goc (format trong code block)
    if additional_context:
        sections.extend(
            [
                "## Original OPX (Failed)",
                "",
                "```xml",
                additional_context.strip(),
                "```",
                "",
            ]
        )

    # Prompt huong dan cho IDE agent (da co edit tool san, khong can OPX)
    sections.extend(
        [
            "---",
            "",
            "# ACTION REQUIRED",
            "",
            "Fix the failed operations based on the error and current file contents above.",
            "All information you need is provided. Do NOT ask questions - start fixing immediately.",
            "",
            "**For each failed operation:**",
            "1. Open the affected file",
            "2. Find the section that needs to be changed (use the current file contents "
            "and the original OPX intent as reference)",
            "3. Apply the intended change directly using your edit tools",
            "",
            "**IMPORTANT:** Only fix the FAILED operations. "
            "Successful operations (if any) are already applied - do NOT touch them.",
            "",
        ]
    )

    return "\n".join(sections)


def _extract_file_paths_from_opx(opx_text: str) -> List[str]:
    """
    Extract danh sach file paths tu OPX text.
    Tim cac attribute file="..." trong <edit> tags.
    """
    import re
    pattern = re.compile(r'<\s*edit\b[^>]*\bfile\s*=\s*"([^"]*)"', re.IGNORECASE)
    paths = []
    seen: set = set()
    for match in pattern.finditer(opx_text):
        fp = match.group(1)
        if fp and fp not in seen:
            paths.append(fp)
            seen.add(fp)
    return paths


def copy_error_to_clipboard(context: str) -> bool:
    """
    Copy error context to clipboard.

    Returns:
        True neu thanh cong, False neu that bai
    """
    success, _ = copy_to_clipboard(context)
    return success
