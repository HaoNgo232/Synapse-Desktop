"""
Prompt Assembler - Lap rap cac sections thanh prompt hoan chinh.

Consolidates logic tu:
- generate_prompt() (XML / JSON / Plain / Markdown)
- build_smart_prompt() (Smart Context)

Moi assembler nhan cac section da render (file_map, file_contents, ...)
va ghep thanh prompt cuoi cung.

Tat ca format deu bao gom:
- Agent Role / System Instruction
- File Summary (Purpose, Guidelines, Notes)
- Git Diff / Git Log instructions (neu co)
"""

import re
from pathlib import Path
from typing import Optional

from infrastructure.git.git_utils import GitDiffResult, GitLogResult

from domain.prompt.opx_instruction import XML_FORMATTING_INSTRUCTIONS
from presentation.config.output_format import OutputStyle
from domain.prompt.formatters.xml import (
    generate_file_summary_xml,
    generate_smart_summary_xml,
    generate_file_summary_xml_minimal,
)
from domain.prompt.formatters.system_prompts import (
    AGENT_ROLE_INSTRUCTION,
    GENERATION_HEADER,
    SUMMARY_PURPOSE,
    SUMMARY_FILE_FORMAT_PLAIN,
    SUMMARY_USAGE_GUIDELINES,
    SUMMARY_NOTES,
    SMART_SUMMARY_PURPOSE,
    SMART_SUMMARY_FORMAT,
    GIT_DIFF_INSTRUCTION,
    GIT_LOG_INSTRUCTION,
)


def assemble_prompt(
    file_map: str,
    file_contents: str,
    user_instructions: str = "",
    include_xml_formatting: bool = False,
    git_diffs: Optional[GitDiffResult] = None,
    git_logs: Optional[GitLogResult] = None,
    output_style: OutputStyle = OutputStyle.XML,
    project_rules: str = "",
    instructions_at_top: bool = False,
    workspace_root: Optional[Path] = None,
    semantic_index: str = "",
) -> str:
    """
    Lắp ráp prompt hoàn chỉnh từ các sections.
    """

    # Ensure user_instructions is cleaned of any legacy output formats
    if user_instructions:
        idx = user_instructions.find("## Output format")
        if idx != -1:
            user_instructions = user_instructions[:idx].strip()
        idx = user_instructions.find("## REPORT STRUCTURE")
        if idx != -1:
            user_instructions = user_instructions[:idx].strip()

    if output_style == OutputStyle.XML:
        return _assemble_xml(
            file_map=file_map,
            file_contents=file_contents,
            user_instructions=user_instructions,
            include_xml_formatting=include_xml_formatting,
            git_diffs=git_diffs,
            git_logs=git_logs,
            project_rules=project_rules,
            instructions_at_top=instructions_at_top,
            workspace_root=workspace_root,
            semantic_index=semantic_index,
        )
    elif output_style == OutputStyle.PLAIN:
        return _assemble_plain(
            file_map,
            file_contents,
            user_instructions,
            include_xml_formatting,
            git_diffs,
            git_logs,
            project_rules,
            instructions_at_top,
            semantic_index=semantic_index,
        )
    else:
        # Fallback to XML for unknown formats
        return _assemble_xml(
            file_map=file_map,
            file_contents=file_contents,
            user_instructions=user_instructions,
            include_xml_formatting=include_xml_formatting,
            git_diffs=git_diffs,
            git_logs=git_logs,
            project_rules=project_rules,
            instructions_at_top=instructions_at_top,
            workspace_root=workspace_root,
            semantic_index=semantic_index,
        )


def assemble_smart_prompt(
    smart_contents: str,
    file_map: str,
    user_instructions: str = "",
    git_diffs: Optional[GitDiffResult] = None,
    git_logs: Optional[GitLogResult] = None,
    project_rules: str = "",
    instructions_at_top: bool = False,
    semantic_index: str = "",
    output_style: OutputStyle = OutputStyle.XML,
) -> str:
    """
    Lắp ráp prompt cho Copy Smart (hỗ trợ cả XML và Plaintext).
    """
    if output_style == OutputStyle.PLAIN:
        return _assemble_smart_plain(
            smart_contents=smart_contents,
            file_map=file_map,
            user_instructions=user_instructions,
            git_diffs=git_diffs,
            git_logs=git_logs,
            project_rules=project_rules,
            instructions_at_top=instructions_at_top,
            semantic_index=semantic_index,
        )

    file_summary = generate_smart_summary_xml()

    prompt = ""
    # Nếu instructions_at_top=True
    if instructions_at_top:
        if user_instructions and user_instructions.strip():
            prompt += f"<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"
        if project_rules and project_rules.strip():
            prompt += f"<project_rules>\n{project_rules.strip()}\n</project_rules>\n"
        if semantic_index and semantic_index.strip():
            prompt += f"{semantic_index.strip()}\n"
        if prompt:
            prompt += "\n"

    prompt += f"""{file_summary}

<structure>
{file_map}
</structure>

<smart_context>
{smart_contents}
</smart_context>
"""
    # Git changes section
    prompt = _append_git_changes_xml(prompt, git_diffs, git_logs)

    if not instructions_at_top and project_rules and project_rules.strip():
        prompt += f"\n<project_rules>\n{project_rules.strip()}\n</project_rules>\n"

    if not instructions_at_top and semantic_index and semantic_index.strip():
        prompt += f"\n{semantic_index.strip()}\n"

    if not instructions_at_top and user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"
    return prompt.strip()


def _assemble_smart_plain(
    smart_contents: str,
    file_map: str,
    user_instructions: str = "",
    git_diffs: Optional[GitDiffResult] = None,
    git_logs: Optional[GitLogResult] = None,
    project_rules: str = "",
    instructions_at_top: bool = False,
    semantic_index: str = "",
) -> str:
    """Lắp ráp prompt Copy Smart theo Plain Text format."""
    prompt_parts: list[str] = []

    # System/Role info
    prompt_parts.append(
        f"{'=' * 48}\nSYSTEM INSTRUCTION (SMART CONTEXT)\n{'=' * 48}\n{AGENT_ROLE_INSTRUCTION}"
    )

    prompt_parts.append(
        f"{'=' * 48}\n"
        f"CONTEXT SUMMARY\n"
        f"{'=' * 48}\n"
        f"Purpose: {SMART_SUMMARY_PURPOSE}\n\n"
        f"Format: {SMART_SUMMARY_FORMAT}\n\n"
        f"Guidelines: {SUMMARY_USAGE_GUIDELINES}"
    )

    if instructions_at_top:
        if user_instructions and user_instructions.strip():
            prompt_parts.append(
                f"{'=' * 48}\nINSTRUCTIONS\n{'=' * 48}\n{user_instructions.strip()}"
            )
        if project_rules and project_rules.strip():
            prompt_parts.append(
                f"{'=' * 48}\nPROJECT RULES\n{'=' * 48}\n{project_rules.strip()}"
            )

    if semantic_index and semantic_index.strip():
        prompt_parts.append(
            f"{'=' * 48}\nSEMANTIC INDEX\n{'=' * 48}\n{_strip_xml_simple(semantic_index)}"
        )

    # Structure
    prompt_parts.append(f"{'=' * 48}\nDIRECTORY STRUCTURE\n{'=' * 48}\n{file_map}")

    # Compressed Contents
    prompt_parts.append(
        f"{'=' * 48}\nCOMPRESSED FILE CONTEXT\n{'=' * 48}\n{smart_contents}"
    )

    # Git changes
    has_diffs = git_diffs and (git_diffs.work_tree_diff or git_diffs.staged_diff)
    if has_diffs:
        assert git_diffs is not None
        prompt_parts.append(
            f"{'=' * 48}\nGIT CHANGES\n{'=' * 48}\n{git_diffs.work_tree_diff or ''}\n{git_diffs.staged_diff or ''}"
        )

    if not instructions_at_top:
        if project_rules and project_rules.strip():
            prompt_parts.append(
                f"{'=' * 48}\nPROJECT RULES\n{'=' * 48}\n{project_rules.strip()}"
            )
        if user_instructions and user_instructions.strip():
            prompt_parts.append(
                f"{'=' * 48}\nUSER INSTRUCTIONS\n{'=' * 48}\n{user_instructions.strip()}"
            )

    return "\n\n".join(prompt_parts)


# === Private helpers ===


def _append_git_changes_xml(
    prompt: str,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
) -> str:
    """Them section git_changes vao prompt dang XML voi instruction text."""
    # Kiem tra co du lieu thuc su truoc khi tao section
    has_diffs = git_diffs and (git_diffs.work_tree_diff or git_diffs.staged_diff)
    has_logs = git_logs and git_logs.log_content

    if has_diffs or has_logs:
        prompt += "\n<git_changes>\n"
        if has_diffs:
            assert git_diffs is not None  # type narrowing cho Pyrefly
            prompt += f"<git_diff_instruction>\n{GIT_DIFF_INSTRUCTION}\n</git_diff_instruction>\n"
            if git_diffs.work_tree_diff:
                prompt += f"<git_diff_worktree>\n{git_diffs.work_tree_diff}\n</git_diff_worktree>\n"
            if git_diffs.staged_diff:
                prompt += (
                    f"<git_diff_staged>\n{git_diffs.staged_diff}\n</git_diff_staged>\n"
                )
        if has_logs:
            assert git_logs is not None  # type narrowing cho Pyrefly
            prompt += f"<git_log_instruction>\n{GIT_LOG_INSTRUCTION}\n</git_log_instruction>\n"
            prompt += f"<git_log>\n{git_logs.log_content}\n</git_log>\n"
        prompt += "</git_changes>\n"
    return prompt


def _assemble_xml(
    file_map: str,
    file_contents: str,
    user_instructions: str,
    include_xml_formatting: bool,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
    project_rules: str = "",
    instructions_at_top: bool = False,
    workspace_root: Optional[Path] = None,
    semantic_index: str = "",
) -> str:
    """Lắp ráp prompt theo XML format với semantic_index ở đầu."""
    from datetime import datetime
    import html

    project_name = (
        html.escape(workspace_root.name) if workspace_root else "unknown-project"
    )
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Minimizing Agent Role logic (unified logic for all formats)
    role = (
        AGENT_ROLE_INSTRUCTION
        if not include_xml_formatting
        else "Analyze the provided codebase."
    )

    if include_xml_formatting:
        file_summary_content = generate_file_summary_xml_minimal()
        # In OPX mode, we still want to clarify the agent role if it's missing from minimal summary
        if "<agent_role>" not in file_summary_content:
            file_summary_content = file_summary_content.replace(
                "<file_summary>", f"<file_summary>\n<agent_role>\n{role}\n</agent_role>"
            )
        file_summary = file_summary_content
    else:
        file_summary = generate_file_summary_xml()

    prompt = "<project>\n"
    prompt += f"  <metadata>\n    <name>{project_name}</name>\n    <generated_at>{current_date}</generated_at>\n  </metadata>\n\n"

    # 1. Instructions and Rules at top
    if instructions_at_top:
        if user_instructions and user_instructions.strip():
            prompt += f"  <user_instructions>\n{user_instructions.strip()}\n  </user_instructions>\n"
        if project_rules and project_rules.strip():
            prompt += (
                f"  <project_rules>\n{project_rules.strip()}\n  </project_rules>\n"
            )
        if semantic_index and semantic_index.strip():
            prompt += f"  {semantic_index.strip()}\n"
        prompt += "\n"

    # 2. File Summary (Role, Purpose, Guidelines)
    prompt += f"{file_summary}\n\n"

    # 3. Semantic Index (neu khong phai instructions_at_top thi dat o day cung duoc, hoac de sau summary)
    if not instructions_at_top and semantic_index and semantic_index.strip():
        prompt += f"  {semantic_index.strip()}\n\n"

    # 4. Structure and Files
    prompt += f"<structure>\n{file_map}\n</structure>\n\n"
    prompt += f"{file_contents}\n"

    # 5. Git changes
    prompt = _append_git_changes_xml(prompt, git_diffs, git_logs)

    # 6. Project Rules (bottom)
    if not instructions_at_top and project_rules and project_rules.strip():
        prompt += f"\n  <project_rules>\n{project_rules.strip()}\n  </project_rules>\n"

    # 7. Output Format Instructions
    if include_xml_formatting:
        prompt += f"\n{XML_FORMATTING_INSTRUCTIONS}\n"
    else:
        from domain.prompt.template_manager import _get_output_format_only

        fmt = _get_output_format_only()
        if fmt:
            prompt += f"\n<output_format>\n{fmt}\n</output_format>\n"

    # 8. User Instructions (bottom)
    if user_instructions and user_instructions.strip():
        if instructions_at_top:
            prompt += "\n  <reminder>\n    REITERATION: Please follow the user_instructions provided at the beginning of this prompt.\n  </reminder>\n"
        else:
            prompt += f"\n  <user_instructions>\n{user_instructions.strip()}\n  </user_instructions>\n"

    prompt += "\n</project>"
    return prompt


def _assemble_plain(
    file_map: str,
    file_contents: str,
    user_instructions: str,
    include_xml_formatting: bool,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
    project_rules: str = "",
    instructions_at_top: bool = False,
    semantic_index: str = "",
) -> str:
    """Lắp ráp prompt theo Plain Text format với Summary header và Git instructions."""
    prompt_parts: list[str] = []

    # Nếu instructions_at_top=True, đưa lên đầu cùng (trước SYSTEM INSTRUCTION)
    if instructions_at_top:
        if user_instructions and user_instructions.strip():
            prompt_parts.append(
                f"{'=' * 48}\nINSTRUCTIONS\n{'=' * 48}\n{user_instructions.strip()}"
            )
        if project_rules and project_rules.strip():
            prompt_parts.append(
                f"{'=' * 48}\nPROJECT RULES\n{'=' * 48}\n{project_rules.strip()}"
            )
        if semantic_index and semantic_index.strip():
            prompt_parts.append(
                f"{'=' * 48}\nSEMANTIC INDEX\n{'=' * 48}\n{_strip_xml_simple(semantic_index)}"
            )

    # Minimizing Agent Role in OPX mode
    role = (
        AGENT_ROLE_INSTRUCTION
        if not include_xml_formatting
        else "Analyze the provided codebase."
    )

    # Thêm Agent Role và File Summary ở đầu prompt
    prompt_parts.append(f"{'=' * 48}\nSYSTEM INSTRUCTION\n{'=' * 48}\n{role}")

    prompt_parts.append(
        f"{'=' * 48}\n"
        f"FILE SUMMARY\n"
        f"{'=' * 48}\n"
        f"{GENERATION_HEADER}\n\n"
        f"Purpose:\n{SUMMARY_PURPOSE}\n\n"
        f"File Format:\n{SUMMARY_FILE_FORMAT_PLAIN}\n\n"
        f"Usage Guidelines:\n{SUMMARY_USAGE_GUIDELINES}\n\n"
        f"Notes:\n{SUMMARY_NOTES}"
    )

    if not instructions_at_top and semantic_index and semantic_index.strip():
        # Clean tags for plain text mode
        prompt_parts.append(
            f"{'=' * 48}\nSEMANTIC INDEX\n{'=' * 48}\n{_strip_xml_simple(semantic_index)}"
        )

    prompt_parts.append(f"{'=' * 48}\nDIRECTORY STRUCTURE\n{'=' * 48}\n{file_map}")

    prompt_parts.append(f"{'=' * 48}\nFILE CONTEXT\n{'=' * 48}\n{file_contents}")

    # Them Git context voi instruction text, guard None values
    has_diffs = git_diffs and (git_diffs.work_tree_diff or git_diffs.staged_diff)
    if has_diffs:
        assert git_diffs is not None  # type narrowing cho Pyrefly
        prompt_parts.append(
            f"{'=' * 48}\n"
            f"{GIT_DIFF_INSTRUCTION}\n\n"
            f"Work Tree Diff:\n{git_diffs.work_tree_diff or '(no changes)'}\n\n"
            f"Staged Diff:\n{git_diffs.staged_diff or '(no changes)'}"
        )

    has_logs = git_logs and git_logs.log_content
    if has_logs:
        assert git_logs is not None  # type narrowing cho Pyrefly
        prompt_parts.append(
            f"{'=' * 48}\n{GIT_LOG_INSTRUCTION}\n\nGit Logs:\n{git_logs.log_content}"
        )

    if include_xml_formatting:
        prompt_parts.append(f"{'=' * 48}\n{XML_FORMATTING_INSTRUCTIONS}")

    if not instructions_at_top and project_rules and project_rules.strip():
        prompt_parts.append(
            f"{'=' * 48}\nPROJECT RULES\n{'=' * 48}\n{project_rules.strip()}"
        )

    # Output Format (Single Source of Truth)
    if not include_xml_formatting:
        from domain.prompt.template_manager import _get_output_format_only

        fmt = _get_output_format_only()
        if fmt:
            prompt_parts.append(f"{'=' * 48}\nOUTPUT FORMAT:\n{fmt}")

    # User instructions ở cuối cùng (recency bias giúp LLM xử lý tốt hơn)
    if user_instructions and user_instructions.strip():
        if instructions_at_top:
            prompt_parts.append(
                f"{'=' * 48}\nREMINDER\n{'=' * 48}\nREITERATION: Please follow the user_instructions provided at the beginning of this prompt."
            )
        else:
            prompt_parts.append(
                f"{'=' * 48}\nUSER INSTRUCTIONS\n{'=' * 48}\n{user_instructions.strip()}"
            )

    return "\n\n".join(prompt_parts)


def _strip_xml_simple(text: str) -> str:
    """Loại bỏ các thẻ XML cơ bản để chuyển sang văn bản thuần túy."""
    if not text:
        return ""

    # 1. Capture attribute values like total_files="1" or path="a.py"
    # if the main content is empty after stripping tags.
    attr_pattern = r'(\w+)="([^"]+)"'
    attrs = re.findall(attr_pattern, text)
    attr_summary = ""
    if attrs:
        attr_summary = ", ".join(
            [
                f"{k}: {v}"
                for k, v in attrs
                if k in ("total_files", "total_edges", "path", "dependents")
            ]
        )

    # 2. Strip tags but keep inner content
    stripped = re.sub(r"<[^>]+>", "", text).strip()

    if not stripped and attr_summary:
        return f"Metadata: {attr_summary}"

    # Clean up multiple newlines to max 2
    stripped = re.sub(r"\n\s*\n", "\n\n", stripped)
    return stripped
