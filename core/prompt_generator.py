"""
Prompt Generator - Tao context prompt cho LLM

"""

from pathlib import Path
from typing import Optional

from core.file_utils import TreeItem, is_binary_by_extension
from core.opx_instruction import XML_FORMATTING_INSTRUCTIONS
from core.language_utils import get_language_from_path


def generate_file_map(tree: TreeItem, selected_paths: set[str]) -> str:
    """
    Tao file map string tu tree structure.
    Chi hien thi cac items duoc chon hoac co children duoc chon.

    Args:
        tree: TreeItem root
        selected_paths: Set cac duong dan duoc tick

    Returns:
        File map string voi ASCII tree visualization
    """
    lines: list[str] = []

    # Neu root duoc chon hoac co descendants duoc chon
    if _has_selected_descendant(tree, selected_paths):
        lines.append(tree.path)  # Root path

        # Filter children
        filtered_children = _filter_selected_tree(tree.children, selected_paths)

        if filtered_children:
            _build_tree_string(filtered_children, "", lines)

    return "\n".join(lines)


def _has_selected_descendant(item: TreeItem, selected_paths: set[str]) -> bool:
    """Kiem tra item hoac descendants co duoc chon khong"""
    if item.path in selected_paths:
        return True

    for child in item.children:
        if _has_selected_descendant(child, selected_paths):
            return True

    return False


def _filter_selected_tree(
    items: list[TreeItem], selected_paths: set[str]
) -> list[TreeItem]:
    """Loc chi giu lai cac items duoc chon hoac co descendants duoc chon"""
    result: list[TreeItem] = []

    for item in items:
        is_selected = item.path in selected_paths
        has_selected_children = any(
            _has_selected_descendant(child, selected_paths) for child in item.children
        )

        if is_selected or has_selected_children:
            # Tao copy voi filtered children
            filtered_item = TreeItem(
                label=item.label,
                path=item.path,
                is_dir=item.is_dir,
                children=(
                    _filter_selected_tree(item.children, selected_paths)
                    if item.children
                    else []
                ),
            )
            result.append(filtered_item)

    return result


def _build_tree_string(items: list[TreeItem], prefix: str, lines: list[str]) -> None:
    """Xay dung ASCII tree string voi connectors (├──, └──, │)"""
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        # Connector: └── cho item cuoi, ├── cho cac item khac
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{item.label}")

        if item.children:
            # Prefix moi: "    " neu la item cuoi (khong can duong doc), "│   " neu con item khac
            new_prefix = prefix + ("    " if is_last else "│   ")
            _build_tree_string(item.children, new_prefix, lines)


def generate_file_contents(
    selected_paths: set[str], max_file_size: int = 1024 * 1024
) -> str:
    """
    Tao file contents string cho cac files duoc chon.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        File contents string voi markdown code blocks
    """
    # Pre-allocate list with estimated size for better performance
    contents: list[str] = []
    contents_append = contents.append  # Local reference for faster append

    # Sort paths de thu tu nhat quan
    sorted_paths = sorted(selected_paths)

    for path_str in sorted_paths:
        path = Path(path_str)

        try:
            # Chi xu ly files
            if not path.is_file():
                continue

            # Skip binary files
            if is_binary_by_extension(path):
                contents_append(f"File: {path}\n*** Skipped: Binary file ***\n")
                continue

            # Skip files that are too large
            try:
                file_size = path.stat().st_size
                if file_size > max_file_size:
                    contents_append(
                        f"File: {path}\n*** Skipped: File too large ({file_size // 1024}KB) ***\n"
                    )
                    continue
            except OSError:
                pass

            # Doc va format content với language detection
            content = path.read_text(encoding="utf-8", errors="replace")
            language = get_language_from_path(path_str)
            contents_append(f"File: {path}\n```{language}\n{content}\n```\n")

        except (OSError, IOError) as e:
            contents_append(f"File: {path}\n*** Error reading file: {e} ***\n")

    return "\n".join(contents).strip()


def generate_prompt(
    file_map: str,
    file_contents: str,
    user_instructions: str = "",
    include_xml_formatting: bool = False,
) -> str:
    """
    Tao prompt hoan chinh de gui cho LLM.

    Args:
        file_map: File map string tu generate_file_map()
        file_contents: File contents string tu generate_file_contents()
        user_instructions: Huong dan tu nguoi dung
        include_xml_formatting: Co bao gom OPX instructions khong

    Returns:
        Prompt hoan chinh
    """
    prompt = f"""<file_map>
{file_map}
</file_map>

<file_contents>
{file_contents}
</file_contents>
"""

    if include_xml_formatting:
        prompt += f"\n{XML_FORMATTING_INSTRUCTIONS}"

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"

    return prompt
