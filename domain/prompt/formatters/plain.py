"""
Plain Text Formatter - Render file contents thanh plain text.

Extracted tu: generate_file_contents_plain() trong core/prompt_generator.py
"""

from shared.types.prompt_types import FileEntry


def format_files_plain(entries: list[FileEntry]) -> str:
    """
    Render List[FileEntry] thanh plain text format.

    Format:
        FILE: path/to/file
        ------------------
        LAYER: ...
        ROLE: ...
        DEPENDS ON: ...

        content

    Args:
        entries: List file entries da doc tu file_collector

    Returns:
        String chua file paths va contents dang plain text
    """
    file_elements: list[str] = []

    for entry in entries:
        if entry.error:
            if entry.error == "Binary file":
                content_display = "Binary file (skipped)"
            elif entry.error.startswith("File too large"):
                content_display = f"{entry.error} (skipped)"
            else:
                content_display = entry.error
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
            content_display = f"{meta_block}\n{entry.content.strip()}"
        else:
            content_display = ""

        # Ghép tất cả lại: Header ranh giới, Metadata, rồi mới đến Code
        file_elements.append(
            f"FILE: {entry.display_path}\n{'-' * (len(entry.display_path) + 6)}\n{content_display}"
        )

    if not file_elements:
        return "No files selected."

    return "\n\n".join(file_elements)
