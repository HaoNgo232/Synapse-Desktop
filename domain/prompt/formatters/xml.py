"""
XML Formatter - Render file contents thanh Repomix XML format.

Bao gom:
- format_files_xml(): File contents dang XML
- generate_file_summary_xml(): AI-friendly file_summary section
- generate_smart_summary_xml(): Smart Context file_summary section

Import noi dung van ban tu system_prompts.py de dam bao nhat quan.
"""

import html
from shared.types.prompt_types import FileEntry

__all__ = [
    "format_files_xml",
    "format_files_xml_elements",
    "generate_file_summary_xml",
    "generate_smart_summary_xml",
    "generate_file_summary_xml_minimal",
]

from domain.prompt.formatters.system_prompts import (
    AGENT_ROLE_INSTRUCTION,
    GENERATION_HEADER,
    SUMMARY_PURPOSE,
    SUMMARY_FILE_FORMAT,
    SUMMARY_USAGE_GUIDELINES,
    SUMMARY_NOTES,
    SMART_SUMMARY_PURPOSE,
    SMART_SUMMARY_FORMAT,
    SMART_SUMMARY_NOTES,
)


def format_files_xml_elements(entries: list[FileEntry]) -> list[str]:
    """
    Render List[FileEntry] thanh cac phan tu XML (<file> nodes).
    """
    file_elements: list[str] = []

    for entry in entries:
        escaped_path = html.escape(entry.display_path)

        if entry.error:
            file_elements.append(
                f'  <file path="{escaped_path}" skipped="true">{entry.error}</file>'
            )
        elif entry.content is not None:
            deps_xml = ""
            if entry.dependencies:
                deps_xml = "    <dependencies>\n"
                for dep in entry.dependencies:
                    deps_xml += f"      <import>{html.escape(dep)}</import>\n"
                deps_xml += "    </dependencies>\n"

            # Content using CDATA
            safe_content = entry.content.replace("]]>", "]]]]><![CDATA[>")
            content_xml = f"    <content><![CDATA[\n{safe_content}\n]]></content>"

            file_elements.append(
                f'  <file path="{escaped_path}">\n{deps_xml}{content_xml}\n  </file>'
            )

    return file_elements


def format_files_xml(entries: list[FileEntry]) -> str:
    """
    Render List[FileEntry] thanh Repomix XML format nang cao.
    """
    file_elements = format_files_xml_elements(entries)
    if not file_elements:
        return "<files></files>"

    return "<files>\n" + "\n".join(file_elements) + "\n</files>"


def generate_file_summary_xml() -> str:
    """
    Tao section file_summary theo chuan Repomix AI-Friendly format.

    Section nay giup LLM hieu:
    - Vai tro cua AI khi xu ly context nay (Agent Role)
    - Muc dich cua file context
    - Cau truc du lieu ben trong
    - Cach su dung dung cach
    - Cac luu y quan trong

    Returns:
        XML string chua file_summary section voi agent role
    """
    return f"""<file_summary>
{GENERATION_HEADER}

<agent_role>
{AGENT_ROLE_INSTRUCTION}
</agent_role>

<purpose>
{SUMMARY_PURPOSE}
</purpose>

<file_format>
{SUMMARY_FILE_FORMAT}
</file_format>

<usage_guidelines>
{SUMMARY_USAGE_GUIDELINES}
</usage_guidelines>

<notes>
{SUMMARY_NOTES}
</notes>
</file_summary>
"""


def generate_smart_summary_xml() -> str:
    """
    Tao file_summary cho Smart Context mode.

    Mo ta rang day la code structure (signatures, docstrings) chu khong phai full content.
    Bao gom Agent Role de AI hieu nhiem vu cua minh.

    Returns:
        XML string chua file_summary section cho Smart Context
    """
    return f"""<file_summary>
{GENERATION_HEADER}

<agent_role>
{AGENT_ROLE_INSTRUCTION}
</agent_role>

<purpose>
{SMART_SUMMARY_PURPOSE}
</purpose>

<file_format>
{SMART_SUMMARY_FORMAT}
</file_format>

<usage_guidelines>
{SUMMARY_USAGE_GUIDELINES}
</usage_guidelines>

<notes>
{SMART_SUMMARY_NOTES}
</notes>
</file_summary>
"""


def generate_file_summary_xml_minimal() -> str:
    """
    Tao section file_summary toi gian cho che do OPX.
    Loai bo agent role de tranh xung dot voi system prompt.

    Returns:
        XML string chua file_summary section cho OPX
    """
    return f"""<file_summary>
{GENERATION_HEADER}

<purpose>
This file contains code context for generating OPX (Overwrite Patch XML) modifications.
Use the provided code to understand structure, then generate precise XML patches.
</purpose>

<usage_guidelines>
- Analyze code structure and identify exact modification points
- Generate OPX patches using precise search patterns from provided code
- Ensure all file paths and code snippets match exactly
</usage_guidelines>
</file_summary>
"""
