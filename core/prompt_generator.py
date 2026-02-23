"""
Prompt Generator - Thin adapter cho prompt pipeline.

Backward-compatible public API. Tat ca logic da chuyen sang:
- core.prompting.file_collector: Doc files tu disk
- core.prompting.formatters.*: Render theo format cu the
- core.prompting.prompt_assembler: Lap rap prompt hoan chinh

Giu lai trong file nay:
- generate_file_map() + tree helpers (khong bi trung lap)
- generate_smart_context() (tree-sitter specific)
"""

from pathlib import Path
from typing import Optional

from core.utils.file_utils import TreeItem, is_binary_file

# Single source of truth cho path display
from core.prompting.path_utils import path_for_display

from core.utils.language_utils import get_language_from_path
from core.utils.git_utils import GitDiffResult, GitLogResult
from config.output_format import OutputStyle

# === Pipeline imports ===
from core.prompting.file_collector import collect_files
from core.prompting.formatters.markdown import format_files_markdown
from core.prompting.delimiter_utils import calculate_markdown_delimiter
from core.prompting.formatters.xml import (
    format_files_xml,
)
from core.prompting.formatters.json_fmt import format_files_json
from core.prompting.formatters.plain import format_files_plain
from core.prompting.prompt_assembler import (
    assemble_prompt,
    assemble_smart_prompt,
)


# ===========================================================================
# Re-export calculate_markdown_delimiter for backward compatibility
# ===========================================================================
# Moved to core.prompting.delimiter_utils to avoid circular imports
# Re-exported here for backward compatibility with existing code
__all__ = ["calculate_markdown_delimiter"]


# ===========================================================================
# File Map - Tree visualization (giu nguyen, khong bi trung lap)
# ===========================================================================


def generate_file_map(
    tree: TreeItem,
    selected_paths: set[str],
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
) -> str:
    """
    Tao file map string tu tree structure.
    Chi hien thi cac items duoc chon hoac co children duoc chon.

    Args:
        tree: TreeItem root
        selected_paths: Set cac duong dan duoc tick
        workspace_root: Workspace root de convert sang relative path (optional)
        use_relative_paths: True = xuat path tuong doi workspace (tranh PII)

    Returns:
        File map string voi ASCII tree visualization
    """
    lines: list[str] = []

    # Neu root duoc chon hoac co descendants duoc chon
    if _has_selected_descendant(tree, selected_paths):
        root_display = path_for_display(
            Path(tree.path), workspace_root, use_relative_paths
        )
        lines.append(root_display)

        # Filter children
        filtered_children = _filter_selected_tree(tree.children, selected_paths)

        if filtered_children:
            _build_tree_string(filtered_children, "", lines)

    return "\n".join(lines)


def _has_selected_descendant(item: TreeItem, selected_set: set[str]) -> bool:
    """
    Kiem tra item hoac descendants co duoc chon khong.

    Uses any() for short-circuit evaluation (stops at first True).
    Safe because this is a pure predicate with no side effects.
    """
    if item.path in selected_set:
        return True
    return any(_has_selected_descendant(child, selected_set) for child in item.children)


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
    """Xay dung ASCII tree string voi connectors"""
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{item.label}")

        if item.children:
            new_prefix = prefix + ("    " if is_last else "│   ")
            _build_tree_string(item.children, new_prefix, lines)


# ===========================================================================
# File Contents - Cac adapter delegate sang collect + format
# ===========================================================================


def generate_file_contents(
    selected_paths: set[str],
    max_file_size: int = 1024 * 1024,
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
) -> str:
    """
    Tao file contents string cho cac files duoc chon (Markdown format).

    Delegate sang file_collector + markdown formatter.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)
        workspace_root: Workspace root cho relative paths
        use_relative_paths: Su dung relative paths

    Returns:
        File contents string voi markdown code blocks
    """
    entries = collect_files(
        selected_paths, max_file_size, workspace_root, use_relative_paths
    )
    return format_files_markdown(entries)


def generate_file_contents_xml(
    selected_paths: set[str],
    max_file_size: int = 1024 * 1024,
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
) -> str:
    """
    Tao file contents theo Repomix XML format.

    Delegate sang file_collector + XML formatter.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        File contents string voi XML structure
    """
    entries = collect_files(
        selected_paths, max_file_size, workspace_root, use_relative_paths
    )
    return format_files_xml(entries)


def generate_file_contents_json(
    selected_paths: set[str],
    max_file_size: int = 1024 * 1024,
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
) -> str:
    """
    Tao file contents theo JSON format.

    Delegate sang file_collector + JSON formatter.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        JSON string chua file paths va contents
    """
    entries = collect_files(
        selected_paths, max_file_size, workspace_root, use_relative_paths
    )
    return format_files_json(entries)


def generate_file_contents_plain(
    selected_paths: set[str],
    max_file_size: int = 1024 * 1024,
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
) -> str:
    """
    Tao file contents theo Plain Text format.

    Delegate sang file_collector + plain formatter.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        String chua file paths va contents dang plain text
    """
    entries = collect_files(
        selected_paths, max_file_size, workspace_root, use_relative_paths
    )
    return format_files_plain(entries)


# ===========================================================================
# Smart Context - Tree-sitter specific (giu nguyen logic rieng)
# ===========================================================================


def generate_smart_context(
    selected_paths: set[str],
    max_file_size: int = 1024 * 1024,
    include_relationships: bool = False,
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
) -> str:
    """
    Tao Smart Context string - chi chua code structure (signatures, docstrings).
    Dung Tree-sitter de parse va trich xuat cau truc thay vi raw content.

    Su dung Smart Markdown Delimiter de tranh broken markdown
    khi file content chua backticks.

    OPTIMIZATION: Parallel processing khi co >5 files.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)
        include_relationships: Neu True, append relationships section (CodeMaps)

    Returns:
        Smart context string voi code signatures
    """
    from concurrent.futures import ThreadPoolExecutor
    from core.smart_context import smart_parse, is_supported

    sorted_paths = sorted(selected_paths)

    def _process_single_file(path_str: str) -> tuple[Path, str | None, str | None]:
        """
        Process mot file va return (path, smart_content, error).
        Helper function cho parallel processing.
        """
        path = Path(path_str)

        try:
            if not path.is_file():
                return (path, None, "Not a file")

            # Skip binary files (check magic bytes)
            if is_binary_file(path):
                return (path, None, "Binary file")

            # Skip files qua lon
            try:
                file_size = path.stat().st_size
                if file_size > max_file_size:
                    return (path, None, f"File too large ({file_size // 1024}KB)")
            except OSError:
                pass

            # Doc raw content
            raw_content = path.read_text(encoding="utf-8", errors="replace")

            # Kiem tra ho tro Smart Context
            ext = path.suffix.lstrip(".")
            if not is_supported(ext):
                return (path, None, f"Smart Context not available for .{ext} files")

            # Try Smart Parse voi relationships neu enabled
            smart_content = smart_parse(
                path_str, raw_content, include_relationships=include_relationships
            )

            if smart_content:
                return (path, smart_content, None)
            else:
                return (path, None, "Smart Context parse failed")

        except (OSError, IOError) as e:
            return (path, None, f"Error reading file: {e}")

    # Phase 1: Process files (parallel neu >5 files, sequential neu it)
    file_data: list[tuple[Path, str | None, str | None]] = []
    all_contents: list[str] = []

    if len(sorted_paths) > 5:
        # PARALLEL processing voi ThreadPoolExecutor
        # Use executor.map() to maintain order automatically
        with ThreadPoolExecutor(max_workers=min(8, len(sorted_paths))) as executor:
            file_data = list(executor.map(_process_single_file, sorted_paths))
            all_contents = [result[1] for result in file_data if result[1]]
    else:
        # Sequential processing cho it files
        for path_str in sorted_paths:
            result = _process_single_file(path_str)
            file_data.append(result)
            if result[1]:
                all_contents.append(result[1])

    # Phase 2: Tinh Smart Markdown Delimiter
    delimiter = calculate_markdown_delimiter(all_contents)

    # Phase 3: Generate output voi dynamic delimiter
    contents: list[str] = []
    contents_append = contents.append

    for path, smart_content, error in file_data:
        path_display = path_for_display(path, workspace_root, use_relative_paths)
        if error:
            contents_append(f"File: {path_display}\n*** Skipped: {error} ***\n")
        elif smart_content is not None:
            language = get_language_from_path(str(path))
            contents_append(
                f"File: {path_display} [Smart Context]\n{delimiter}{language}\n{smart_content}\n{delimiter}\n"
            )

    return "\n".join(contents).strip()


# ===========================================================================
# Prompt Assembly - Delegate sang prompt_assembler
# ===========================================================================


def build_smart_prompt(
    smart_contents: str,
    file_map: str,
    user_instructions: str = "",
    git_diffs: Optional[GitDiffResult] = None,
    git_logs: Optional[GitLogResult] = None,
    project_rules: str = "",
    workspace_root: Optional[Path] = None,
) -> str:
    """
    Tao prompt day du cho Copy Smart.

    Delegate sang prompt_assembler.assemble_smart_prompt().

    Args:
        smart_contents: Output tu generate_smart_context()
        file_map: Output tu generate_file_map()
        user_instructions: Huong dan tu nguoi dung
        git_diffs: Optional git diffs
        git_logs: Optional git logs
        project_rules: Project rules
        workspace_root: Optional workspace root de doc memory.xml

    Returns:
        Prompt string day du
    """

    # Copy Smart does not include OPX formatting, so we do not inject memory
    # to avoid polluting the context without a way to update the memory.
    memory_content = None

    return assemble_smart_prompt(
        smart_contents=smart_contents,
        file_map=file_map,
        user_instructions=user_instructions,
        git_diffs=git_diffs,
        git_logs=git_logs,
        project_rules=project_rules,
        memory_content=memory_content,
    )


def generate_prompt(
    file_map: str,
    file_contents: str,
    user_instructions: str = "",
    include_xml_formatting: bool = False,
    git_diffs: Optional[GitDiffResult] = None,
    git_logs: Optional[GitLogResult] = None,
    output_style: OutputStyle = OutputStyle.XML,
    project_rules: str = "",
    workspace_root: Optional[Path] = None,
) -> str:
    """
    Tao prompt hoan chinh de gui cho LLM.

    Delegate sang prompt_assembler.assemble_prompt().

    Args:
        file_map: File map string tu generate_file_map()
        file_contents: File contents string tu formatter tuong ung
        user_instructions: Huong dan tu nguoi dung
        include_xml_formatting: Co bao gom OPX instructions khong
        git_diffs: Optional git diffs (work tree & staged)
        git_logs: Optional git logs
        output_style: Dinh dang dau ra
        project_rules: Project rules
        workspace_root: Optional workspace root de doc memory.xml

    Returns:
        Prompt hoan chinh
    """
    from services.settings_manager import load_app_settings

    settings = load_app_settings()
    enable_ai_memory = settings.enable_ai_memory

    memory_content = None
    if enable_ai_memory and workspace_root and include_xml_formatting:
        memory_file = workspace_root / ".synapse" / "memory.xml"
        if memory_file.exists():
            try:
                memory_content = memory_file.read_text(encoding="utf-8").strip()
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning("Failed to read memory file: %s", e)

    return assemble_prompt(
        file_map=file_map,
        file_contents=file_contents,
        user_instructions=user_instructions,
        include_xml_formatting=include_xml_formatting,
        git_diffs=git_diffs,
        git_logs=git_logs,
        output_style=output_style,
        project_rules=project_rules,
        memory_content=memory_content,
        enable_ai_memory=enable_ai_memory,
    )
