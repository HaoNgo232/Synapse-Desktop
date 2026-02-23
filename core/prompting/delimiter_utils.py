"""
Delimiter Utilities - Shared utilities for markdown delimiter calculation.

Extracted to avoid circular imports between prompt_generator and formatters.
"""


def calculate_markdown_delimiter(contents: list[str]) -> str:
    """
    Tinh toan delimiter an toan cho markdown code blocks.

    Khi file content chua backticks (```), can dung nhieu backticks hon
    cho code block wrapper de tranh broken markdown.

    Port tu Repomix (src/core/output/outputGenerate.ts lines 26-31)

    Args:
        contents: Danh sach noi dung files

    Returns:
        Delimiter string (toi thieu 3 backticks, hoac nhieu hon neu can)
    """
    max_backticks = 0

    for content in contents:
        # Character scan O(n) instead of regex overhead
        current_count = 0
        for char in content:
            if char == "`":
                current_count += 1
            else:
                if current_count > max_backticks:
                    max_backticks = current_count
                current_count = 0
        # Check final sequence
        if current_count > max_backticks:
            max_backticks = current_count

    # Delimiter phai lon hon max backticks tim thay, toi thieu 3
    return "`" * max(3, max_backticks + 1)
