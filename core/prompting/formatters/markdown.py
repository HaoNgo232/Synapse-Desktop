"""
Markdown Formatter - Render file contents thanh markdown code blocks.

Bao gom Smart Markdown Delimiter de tranh broken markdown
khi file content chua backticks.

Extracted tu: generate_file_contents() trong core/prompt_generator.py
"""

import re
from io import StringIO

from core.prompting.types import FileEntry


def _calculate_max_backticks(entries: list[FileEntry]) -> int:
    """
    Tinh so backticks toi da can dung cho delimiter.

    Khi file content chua backticks (```), can nhieu backticks hon
    cho code block wrapper de tranh broken markdown.

    Args:
        entries: List file entries da doc

    Returns:
        So backticks toi thieu can dung (min 3)
    """
    max_backticks = 3
    for entry in entries:
        if entry.content and "`" in entry.content:
            matches = re.findall(r"`+", entry.content)
            if matches:
                max_backticks = max(max_backticks, max(len(m) for m in matches) + 1)
    return max_backticks


def format_files_markdown(entries: list[FileEntry]) -> str:
    """
    Render List[FileEntry] thanh markdown code blocks.

    Format:
        File: path/to/file
        ```language
        content
        ```

    Su dung Smart Markdown Delimiter de dam bao an toan
    khi content chua backticks.

    Args:
        entries: List file entries da doc tu file_collector

    Returns:
        File contents string voi markdown code blocks
    """
    if not entries:
        return ""

    # Tinh delimiter tu tat ca contents
    max_bt = _calculate_max_backticks(entries)
    delimiter = "`" * max(3, max_bt)

    output = StringIO()
    first = True

    for entry in entries:
        if not first:
            output.write("\n")
        first = False

        if entry.error:
            output.write(
                f"File: {entry.display_path}\n*** Skipped: {entry.error} ***\n"
            )
        elif entry.content is not None:
            output.write(
                f"File: {entry.display_path}\n"
                f"{delimiter}{entry.language}\n"
                f"{entry.content}\n"
                f"{delimiter}\n"
            )

    return output.getvalue().strip()
