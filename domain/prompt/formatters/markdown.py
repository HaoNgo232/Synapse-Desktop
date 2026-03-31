"""
Markdown Formatter - Render file contents thanh markdown code blocks.

Bao gom Smart Markdown Delimiter de tranh broken markdown
khi file content chua backticks.

Extracted tu: generate_file_contents() trong core/prompt_generator.py
"""

from io import StringIO

from shared.types.prompt_types import FileEntry
from shared.utils.delimiter_utils import calculate_markdown_delimiter


def format_files_markdown(entries: list[FileEntry]) -> str:
    """
    Render List[FileEntry] thanh markdown code blocks.

    Format:
        ### File path: path/to/file
        LAYER: ...
        ROLE: ...
        DEPENDS ON: ...
        ```language
        content
        ```

    Su dung Smart Markdown Delimiter de dam bao an toan
    khi content chua backticks.

    Args:
        entries: List file entries da doc tu file_collector

    Returns:
        File contents string voi markdown code blocks Vo dấu markdown
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
            # Metadata header
            meta_lines = []
            if entry.layer:
                meta_lines.append(f"LAYER: {entry.layer}")
            if entry.role:
                meta_lines.append(f"ROLE: {entry.role}")
            if entry.dependencies:
                meta_lines.append(f"DEPENDS ON: {', '.join(entry.dependencies)}")
            meta_block = "\n".join(meta_lines) + "\n" if meta_lines else ""

            output.write(
                f"### File path: {entry.display_path}\n"
                f"{meta_block}"
                f"{delimiter}{entry.language}\n"
                f"{entry.content}\n"
                f"{delimiter}\n"
            )

    return output.getvalue().strip()
