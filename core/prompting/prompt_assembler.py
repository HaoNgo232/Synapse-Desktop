"""
Prompt Assembler - Lap rap cac sections thanh prompt hoan chinh.

Consolidates logic tu:
- generate_prompt() (XML / JSON / Plain / Markdown)
- build_smart_prompt() (Smart Context)

Moi assembler nhan cac section da render (file_map, file_contents, ...)
va ghep thanh prompt cuoi cung.
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
    - XML: file_summary + directory_structure + files + git_changes + instructions
    - JSON: Tat ca gom thanh 1 JSON object
    - Plain: Noi cac phan bang separator
    - Markdown: Tuong tu XML nhung khong co file_summary

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
    Lap rap prompt cho Copy Smart - gom file_summary, directory_structure,
    smart contents, git changes va user_instructions.

    Args:
        smart_contents: Output tu generate_smart_context()
        file_map: Output tu generate_file_map()
        user_instructions: Huong dan tu nguoi dung
        git_diffs: Optional git diffs
        git_logs: Optional git logs

    Returns:
        Prompt string day du
    """
    file_summary = generate_smart_summary_xml()
    prompt = f"""{file_summary}
<directory_structure>
{file_map}
</directory_structure>

<smart_context>
{smart_contents}
</smart_context>
"""
    prompt = _append_git_changes(prompt, git_diffs, git_logs)

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"
    return prompt.strip()


# === Private helpers ===


def _append_git_changes(
    prompt: str,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
) -> str:
    """Them section git_changes vao prompt neu co data."""
    if git_diffs or git_logs:
        prompt += "\n<git_changes>\n"
        if git_diffs:
            if git_diffs.work_tree_diff:
                prompt += f"<git_diff_worktree>\n{git_diffs.work_tree_diff}\n</git_diff_worktree>\n"
            if git_diffs.staged_diff:
                prompt += (
                    f"<git_diff_staged>\n{git_diffs.staged_diff}\n</git_diff_staged>\n"
                )
        if git_logs and git_logs.log_content:
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
) -> str:
    """Lap rap prompt theo XML format voi AI-Friendly header."""
    file_summary = generate_file_summary_xml()
    prompt = f"""{file_summary}
<directory_structure>
{file_map}
</directory_structure>

{file_contents}
"""
    prompt = _append_git_changes(prompt, git_diffs, git_logs)

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
    """Lap rap prompt theo JSON format."""
    try:
        files_data = json.loads(file_contents)
    except json.JSONDecodeError:
        files_data = {}

    prompt_data = {
        "directory_structure": file_map,
        "files": files_data,
    }

    if user_instructions:
        prompt_data["instructions"] = user_instructions

    if git_diffs:
        prompt_data["git_diffs"] = {
            "work_tree": git_diffs.work_tree_diff,
            "staged": git_diffs.staged_diff,
        }

    if git_logs:
        prompt_data["git_logs"] = git_logs.log_content

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
    """Lap rap prompt theo Plain Text format."""
    prompt_parts = []

    if user_instructions:
        prompt_parts.append(f"Instructions:\n{user_instructions}")
        prompt_parts.append("-" * 32)

    prompt_parts.append(f"Directory Structure:\n{file_map}")
    prompt_parts.append("-" * 32)

    prompt_parts.append(f"File Contents:\n{file_contents}")

    if git_diffs:
        prompt_parts.append("-" * 32)
        prompt_parts.append(
            f"Git Diffs:\nWork Tree:\n{git_diffs.work_tree_diff}\n\nStaged:\n{git_diffs.staged_diff}"
        )

    if git_logs:
        prompt_parts.append("-" * 32)
        prompt_parts.append(f"Git Logs:\n{git_logs.log_content}")

    return "\n\n".join(prompt_parts)


def _assemble_markdown(
    file_map: str,
    file_contents: str,
    user_instructions: str,
    include_xml_formatting: bool,
    git_diffs: Optional[GitDiffResult],
    git_logs: Optional[GitLogResult],
) -> str:
    """Lap rap prompt theo Markdown format (default)."""
    prompt = f"""<file_map>
{file_map}
</file_map>

<file_contents>
{file_contents}
</file_contents>
"""
    prompt = _append_git_changes(prompt, git_diffs, git_logs)

    if include_xml_formatting:
        prompt += f"\n{XML_FORMATTING_INSTRUCTIONS}\n"

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"

    return prompt
