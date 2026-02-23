"""
Tree Map Generator - Tao tree map string cho LLM (khong co file contents)

Cung cap tinh nang copy chi tree map de LLM hieu cau truc project ma khong
can noi dung files. Huu ich khi:
- Hoi ve architecture/structure
- Token budget han che
- Khong can AI doc code cu the
"""

from pathlib import Path
from typing import Optional

from core.utils.file_utils import TreeItem
from core.prompt_generator import generate_file_map


def generate_tree_map_only(
    tree: TreeItem,
    selected_paths: set[str],
    user_instructions: str = "",
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
) -> str:
    """
    Tao prompt chi co tree map (khong co file contents).

    Args:
        tree: TreeItem root cua file tree
        selected_paths: Set cac duong dan duoc chon
        user_instructions: Huong dan tu nguoi dung (optional)
        workspace_root: Workspace root de convert sang relative path (optional)
        use_relative_paths: True = xuat path tuong doi workspace (tranh PII)

    Returns:
        Prompt string chi chua file_map va user_instructions
    """
    file_map = generate_file_map(
        tree,
        selected_paths,
        workspace_root=workspace_root,
        use_relative_paths=use_relative_paths,
    )

    prompt = f"""<file_map>
{file_map}
</file_map>
"""

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"

    return prompt


def generate_tree_map_with_summary(
    tree: TreeItem,
    selected_paths: set[str],
    user_instructions: str = "",
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
) -> str:
    """
    Tao prompt co tree map va summary count (khong co file contents).
    Huu ich khi muon LLM biet so luong files.

    Args:
        tree: TreeItem root cua file tree
        selected_paths: Set cac duong dan duoc chon
        user_instructions: Huong dan tu nguoi dung (optional)
        workspace_root: Workspace root de convert sang relative path (optional)
        use_relative_paths: True = xuat path tuong doi workspace (tranh PII)

    Returns:
        Prompt string chua file_map, summary va user_instructions
    """
    # Build is_dir_map once for O(n) instead of O(m * n^2)
    is_dir_map: dict[str, bool] = {}

    def _build_map(item: TreeItem) -> None:
        is_dir_map[item.path] = item.is_dir
        for child in item.children:
            _build_map(child)

    _build_map(tree)

    file_map = generate_file_map(
        tree,
        selected_paths,
        workspace_root=workspace_root,
        use_relative_paths=use_relative_paths,
    )

    # Count files va folders using pre-built map (O(m) instead of O(m * n^2))
    file_count = sum(1 for p in selected_paths if not is_dir_map.get(p, False))
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


def tree_item_is_dir(
    tree: TreeItem, path: str, is_dir_map: dict[str, bool] | None = None
) -> bool:
    """
    Kiem tra path co phai la directory trong tree khong.

    Args:
        tree: TreeItem root
        path: Path can kiem tra
        is_dir_map: Pre-built map {path: is_dir} de tra cuu O(1)

    Returns:
        True neu la directory, False neu la file
    """
    # Use pre-built map if available (O(1) lookup)
    if is_dir_map is not None:
        return is_dir_map.get(path, False)

    # Fallback: simple O(n) recursive search
    if tree.path == path:
        return tree.is_dir

    for child in tree.children:
        if child.path == path:
            return child.is_dir
        if child.is_dir:
            result = tree_item_is_dir(child, path, None)
            if result:  # Found in subtree
                return True

    return False


def _tree_contains_path(tree: TreeItem, path: str) -> bool:
    """Check xem tree co chua path khong (helper cho tree_item_is_dir)."""
    if tree.path == path:
        return True
    for child in tree.children:
        if _tree_contains_path(child, path):
            return True
    return False
