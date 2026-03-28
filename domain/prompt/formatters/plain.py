"""
Plain Text Formatter - Render file contents thanh plain text.

Extracted tu: generate_file_contents_plain() trong core/prompt_generator.py
"""

from shared.types.prompt_types import FileEntry


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

    for entry in entries:
        file_header = f"===== FILE: {entry.display_path} ====="
        layer_info = f"LAYER: {entry.layer}\n" if entry.layer else ""
        role_info = f"ROLE: {entry.role}\n" if entry.role else ""
        deps_info = ""
        if entry.dependencies:
            deps_joined = ", ".join(entry.dependencies)
            deps_info = f"DEPENDS ON: {deps_joined}\n"

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

        # Ghép tất cả lại: Header, Metadata, rồi mới đến Code
        file_elements.append(
            f"{file_header}\n{layer_info}{role_info}{deps_info}\n{content_display}"
        )

    if not file_elements:
        return "No files selected."

    return "\n\n".join(file_elements)
