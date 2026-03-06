"""
Plain Text Formatter - Render file contents thanh plain text.

Extracted tu: generate_file_contents_plain() trong core/prompt_generator.py
"""

from core.prompting.types import FileEntry


def format_files_plain(entries: list[FileEntry]) -> str:
    """
    Render List[FileEntry] thanh plain text format.

    Format:
        File: path/to/file
        ----------------
        content
        ----------------

    Args:
        entries: List file entries da doc tu file_collector

    Returns:
        String chua file paths va contents dang plain text
    """
    file_elements: list[str] = []
    separator = "-" * 16

    for entry in entries:
        file_header = f"File: {entry.display_path}\n{separator}"

        if entry.error:
            if entry.error == "Binary file":
                content_display = "Binary file (skipped)"
            elif entry.error.startswith("File too large"):
                content_display = f"{entry.error} (skipped)"
            else:
                content_display = entry.error
        elif entry.content is not None:
            content_display = entry.content.strip()
        else:
            content_display = ""

        file_elements.append(f"{file_header}\n{content_display}\n{separator}")

    if not file_elements:
        return "No files selected."

    return "\n\n".join(file_elements)
