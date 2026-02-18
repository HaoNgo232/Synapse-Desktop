"""
JSON Formatter - Render file contents thanh JSON format.

Extracted tu: generate_file_contents_json() trong core/prompt_generator.py
"""

import json

from core.prompting.types import FileEntry


def format_files_json(entries: list[FileEntry]) -> str:
    """
    Render List[FileEntry] thanh JSON string.

    Output format (serialized JSON):
        {
            "path/to/file": "content",
            "path/to/another": "content"
        }

    Files bi skip se co gia tri "Binary file (skipped)" hoac tuong tu.

    Args:
        entries: List file entries da doc tu file_collector

    Returns:
        JSON string chua file paths va contents
    """
    files_dict: dict[str, str] = {}

    for entry in entries:
        if entry.error:
            if entry.error == "Binary file":
                files_dict[entry.display_path] = "Binary file (skipped)"
            elif entry.error.startswith("File too large"):
                files_dict[entry.display_path] = f"{entry.error} (skipped)"
            else:
                files_dict[entry.display_path] = entry.error
        elif entry.content is not None:
            files_dict[entry.display_path] = entry.content

    return json.dumps(files_dict, ensure_ascii=False)
