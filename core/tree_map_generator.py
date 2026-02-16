"""
Tree Map Generator - Tao tree map string cho LLM (khong co file contents)

Cung cap tinh nang copy chi tree map de LLM hieu cau truc project ma khong
can noi dung files. Huu ich khi:
- Hoi ve architecture/structure
- Token budget han che
- Khong can AI doc code cu the
"""

from core.utils.file_utils import TreeItem
from core.prompt_generator import generate_file_map


def generate_tree_map_only(
    tree: TreeItem, selected_paths: set[str], user_instructions: str = ""
) -> str:
    """
    Tao prompt chi co tree map (khong co file contents).

    Args:
        tree: TreeItem root cua file tree
        selected_paths: Set cac duong dan duoc chon
        user_instructions: Huong dan tu nguoi dung (optional)

    Returns:
        Prompt string chi chua file_map va user_instructions
    """
    file_map = generate_file_map(tree, selected_paths)

    prompt = f"""<file_map>
{file_map}
</file_map>
"""

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"

    return prompt


def generate_tree_map_with_summary(
    tree: TreeItem, selected_paths: set[str], user_instructions: str = ""
) -> str:
    """
    Tao prompt co tree map va summary count (khong co file contents).
    Huu ich khi muon LLM biet so luong files.

    Args:
        tree: TreeItem root cua file tree
        selected_paths: Set cac duong dan duoc chon
        user_instructions: Huong dan tu nguoi dung (optional)

    Returns:
        Prompt string chua file_map, summary va user_instructions
    """
    file_map = generate_file_map(tree, selected_paths)

    # Count files va folders
    file_count = sum(1 for p in selected_paths if not tree_item_is_dir(tree, p))
    total_selected = len(selected_paths)
    folder_count = total_selected - file_count

    summary = f"Selected: {file_count} files, {folder_count} folders"

    prompt = f"""<file_map>
{file_map}
</file_map>

<summary>
{summary}
</summary>
"""

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"

    return prompt


def tree_item_is_dir(tree: TreeItem, path: str) -> bool:
    """
    Kiem tra path co phai la directory trong tree khong.
    Traverse tree de tim item theo path.
    """
    if tree.path == path:
        return tree.is_dir

    for child in tree.children:
        result = tree_item_is_dir(child, path)
        if result is not None:
            return result

    # Fallback: check path directly
    from pathlib import Path

    return Path(path).is_dir()
