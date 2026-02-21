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

import json
from typing import Optional

from core.utils.git_utils import GitDiffResult, GitLogResult
from core.opx_instruction import XML_FORMATTING_INSTRUCTIONS
from config.output_format import OutputStyle
from core.prompting.formatters.xml import (
    generate_file_summary_xml,
    generate_smart_summary_xml,
)
from core.prompting.formatters.system_prompts import (
    AGENT_ROLE_INSTRUCTION,
    GENERATION_HEADER,
    SUMMARY_PURPOSE,
    SUMMARY_FILE_FORMAT_MARKDOWN,
    SUMMARY_FILE_FORMAT_JSON,
    SUMMARY_FILE_FORMAT_PLAIN,
    SUMMARY_USAGE_GUIDELINES,
    SUMMARY_NOTES,
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
) -> str:
    """
    Lap rap prompt hoan chinh tu cac sections.

    Tuy thuoc vao output_style, su dung cau truc khac nhau:
    - XML: file_summary (voi agent_role) + directory_structure + files + git_changes + instructions
    - JSON: system_instruction + file_summary + directory_structure + files + git + instructions
    - Plain: Summary header + directory + files + git + instructions
    - Markdown: Summary header + file_map + file_contents + git_changes + instructions

    Args:
        file_map: File map string tu generate_file_map()
        file_contents: File contents string tu formatter tuong ung
        user_instructions: Huong dan tu nguoi dung
        include_xml_formatting: Co bao gom OPX instructions khong
        git_diffs: Optional git diffs (work tree & staged)
        git_logs: Optional git logs
        output_style: Dinh dang dau ra

    Returns:
        Prompt hoan chinh
    """
    if output_style == OutputStyle.XML:
        return _assemble_xml(
            file_map,
            file_contents,
            user_instructions,
            include_xml_formatting,
            git_diffs,
            git_logs,
        )
    elif output_style == OutputStyle.JSON:
        return _assemble_json(
            file_map,
            file_contents,
            user_instructions,
            include_xml_formatting,
            git_diffs,
            git_logs,
        )
    elif output_style == OutputStyle.PLAIN:
        return _assemble_plain(
            file_map,
            file_contents,
            user_instructions,
            git_diffs,
            git_logs,
        )
    else:
        return _assemble_markdown(
            file_map,
            file_contents,
            user_instructions,
            include_xml_formatting,
            git_diffs,
            git_logs,
        )


def assemble_smart_prompt(
    smart_contents: str,
    file_map: str,
    user_instructions: str = "",
    git_diffs: Optional[GitDiffResult] = None,
    git_logs: Optional[GitLogResult] = None,
) -> str:
    """
    Lap rap prompt cho Copy Smart - gom file_summary (voi agent_role),
    directory_structure, smart contents, git changes va user_instructions.

    Args:
        smart_contents: Output tu generate_smart_context()
        file_map: Output tu generate_file_map()
        user_instructions: Huong dan tu nguoi dung
        git_diffs: Optional git diffs
        git_logs: Optional git logs

    Returns:
        Prompt string day du
    """
    # generate_smart_summary_xml() da bao gom agent_role
    file_summary = generate_smart_summary_xml()
    prompt = f"""{file_summary}
<directory_structure>
{file_map}
</directory_structure>

<smart_context>
{smart_contents}
</smart_context>
"""
    prompt = _append_git_changes_xml(prompt, git_diffs, git_logs)

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"
    return prompt.strip()


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


def _append_git_changes_markdown(
    prompt: str,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
) -> str:
    """
    Them section git_changes vao prompt dang Markdown voi instruction text.

    Luu y: Su dung hybrid format - noi dung Markdown (headers, code blocks)
    duoc boc trong XML semantic tags (<git_changes>) de AI de dang
    nhan dien ranh gioi cac section. Day la thiet ke co y do.
    """
    # Kiem tra co du lieu thuc su truoc khi tao section
    has_diffs = git_diffs and (git_diffs.work_tree_diff or git_diffs.staged_diff)
    has_logs = git_logs and git_logs.log_content

    if has_diffs or has_logs:
        prompt += "\n<git_changes>\n"
        if has_diffs:
            assert git_diffs is not None  # type narrowing cho Pyrefly
            prompt += f"> {GIT_DIFF_INSTRUCTION}\n\n"
            if git_diffs.work_tree_diff:
                prompt += f"### Git Diff (Work Tree)\n```diff\n{git_diffs.work_tree_diff}\n```\n\n"
            if git_diffs.staged_diff:
                prompt += (
                    f"### Git Diff (Staged)\n```diff\n{git_diffs.staged_diff}\n```\n\n"
                )
        if has_logs:
            assert git_logs is not None  # type narrowing cho Pyrefly
            prompt += f"> {GIT_LOG_INSTRUCTION}\n\n"
            prompt += f"### Git Log\n```\n{git_logs.log_content}\n```\n\n"
        prompt += "</git_changes>\n"
    return prompt


def _assemble_xml(
    file_map: str,
    file_contents: str,
    user_instructions: str,
    include_xml_formatting: bool,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
) -> str:
    """Lap rap prompt theo XML format voi AI-Friendly header va Agent Role."""
    # generate_file_summary_xml() da bao gom agent_role ben trong
    file_summary = generate_file_summary_xml()
    prompt = f"""{file_summary}
<directory_structure>
{file_map}
</directory_structure>

{file_contents}
"""
    prompt = _append_git_changes_xml(prompt, git_diffs, git_logs)

    if include_xml_formatting:
        prompt += f"\n{XML_FORMATTING_INSTRUCTIONS}\n"

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"

    return prompt


def _assemble_json(
    file_map: str,
    file_contents: str,
    user_instructions: str,
    include_xml_formatting: bool,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
) -> str:
    """Lap rap prompt theo JSON format voi system_instruction va file_summary."""
    try:
        files_data = json.loads(file_contents)
    except json.JSONDecodeError:
        files_data = {}

    # Them system instruction va file summary vao JSON output
    prompt_data = {
        "system_instruction": AGENT_ROLE_INSTRUCTION,
        "file_summary": {
            "generated_by": "Synapse Desktop",
            "purpose": SUMMARY_PURPOSE,
            "file_format": SUMMARY_FILE_FORMAT_JSON,
            "usage_guidelines": SUMMARY_USAGE_GUIDELINES,
            "notes": SUMMARY_NOTES,
        },
        "directory_structure": file_map,
        "files": files_data,
    }

    if user_instructions:
        prompt_data["instructions"] = user_instructions

    # Them git context voi instruction text
    if git_diffs:
        prompt_data["git_diffs"] = {
            "instruction": GIT_DIFF_INSTRUCTION,
            "work_tree": git_diffs.work_tree_diff,
            "staged": git_diffs.staged_diff,
        }

    if git_logs:
        prompt_data["git_logs"] = {
            "instruction": GIT_LOG_INSTRUCTION,
            "content": git_logs.log_content,
        }

    if include_xml_formatting:
        prompt_data["formatting_instructions"] = XML_FORMATTING_INSTRUCTIONS

    return json.dumps(prompt_data, ensure_ascii=False, indent=2)


def _assemble_plain(
    file_map: str,
    file_contents: str,
    user_instructions: str,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
) -> str:
    """Lap rap prompt theo Plain Text format voi Summary header va Git instructions."""
    prompt_parts = []

    # Them Agent Role va File Summary o dau prompt
    prompt_parts.append(
        f"{'=' * 48}\nSYSTEM INSTRUCTION\n{'=' * 48}\n{AGENT_ROLE_INSTRUCTION}"
    )

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

    prompt_parts.append(f"{'-' * 32}\nDirectory Structure:\n{file_map}")

    prompt_parts.append(f"{'-' * 32}\nFile Contents:\n{file_contents}")

    # Them Git context voi instruction text, guard None values
    has_diffs = git_diffs and (git_diffs.work_tree_diff or git_diffs.staged_diff)
    if has_diffs:
        assert git_diffs is not None  # type narrowing cho Pyrefly
        prompt_parts.append(
            f"{'-' * 32}\n"
            f"{GIT_DIFF_INSTRUCTION}\n\n"
            f"Work Tree Diff:\n{git_diffs.work_tree_diff or '(no changes)'}\n\n"
            f"Staged Diff:\n{git_diffs.staged_diff or '(no changes)'}"
        )

    has_logs = git_logs and git_logs.log_content
    if has_logs:
        assert git_logs is not None  # type narrowing cho Pyrefly
        prompt_parts.append(
            f"{'-' * 32}\n{GIT_LOG_INSTRUCTION}\n\nGit Logs:\n{git_logs.log_content}"
        )

    # User instructions o cuoi cung (recency bias giup LLM xu ly tot hon)
    if user_instructions:
        prompt_parts.append(f"{'-' * 32}\nInstructions:\n{user_instructions}")

    return "\n\n".join(prompt_parts)


def _assemble_markdown(
    file_map: str,
    file_contents: str,
    user_instructions: str,
    include_xml_formatting: bool,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
) -> str:
    """Lap rap prompt theo Markdown format voi File Summary va Agent Role."""
    # Header voi Agent Role va File Summary
    prompt = f"""<system_instruction>
{AGENT_ROLE_INSTRUCTION}
</system_instruction>

<file_summary>
{GENERATION_HEADER}

Purpose: {SUMMARY_PURPOSE}

File Format: {SUMMARY_FILE_FORMAT_MARKDOWN}

Usage Guidelines:
{SUMMARY_USAGE_GUIDELINES}

Notes:
{SUMMARY_NOTES}
</file_summary>

<file_map>
{file_map}
</file_map>

<file_contents>
{file_contents}
</file_contents>
"""
    prompt = _append_git_changes_markdown(prompt, git_diffs, git_logs)

    if include_xml_formatting:
        prompt += f"\n{XML_FORMATTING_INSTRUCTIONS}\n"

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"

    return prompt
