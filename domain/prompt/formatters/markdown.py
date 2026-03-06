"""
Markdown Formatter - Render file contents thanh markdown code blocks.

Bao gom Smart Markdown Delimiter de tranh broken markdown
khi file content chua backticks.

Extracted tu: generate_file_contents() trong core/prompt_generator.py
"""

from io import StringIO

from core.prompting.types import FileEntry
from core.prompting.delimiter_utils import calculate_markdown_delimiter


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

    # Tinh delimiter tu tat ca contents using shared function
    contents = [entry.content for entry in entries if entry.content]
    delimiter = calculate_markdown_delimiter(contents)

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
