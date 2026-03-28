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

import logging
from pathlib import Path
from typing import Optional, Set

from infrastructure.filesystem.file_utils import TreeItem, is_binary_file

# Single source of truth cho path display
from shared.utils.path_utils import path_for_display

from shared.utils.language_utils import get_language_from_path
from infrastructure.git.git_utils import GitDiffResult, GitLogResult
from presentation.config.output_format import OutputStyle

# === Pipeline imports ===
from domain.prompt.file_collector import collect_files
from domain.prompt.formatters.markdown import format_files_markdown
from shared.utils.delimiter_utils import calculate_markdown_delimiter
from domain.prompt.formatters.xml import (
    format_files_xml,
)
from domain.prompt.formatters.json_fmt import format_files_json
from domain.prompt.formatters.plain import format_files_plain
from domain.prompt.assembler import (
    assemble_prompt,
    assemble_smart_prompt,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Re-export calculate_markdown_delimiter for backward compatibility
# ===========================================================================
# Moved to core.prompting.delimiter_utils to avoid circular imports
# Re-exported here for backward compatibility with existing code
__all__ = ["calculate_markdown_delimiter"]


# ===========================================================================
# File Map - Tree visualization (giu nguyen, khong bi trung lap)
# ===========================================================================


def generate_file_structure_xml(
    tree: TreeItem,
    selected_paths: Set[str],
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
    show_all: bool = True,
) -> str:
    """
    Tao cau truc thu muc dang XML long nhau cho prompt structure moi.

    Args:
        tree: TreeItem root
        selected_paths: Set cac duong dan duoc tick (chi dung neu show_all=False)
        workspace_root: Workspace root
        use_relative_paths: Co dung relative paths khong
        show_all: Neu True, hien thi toan bộ tree ma khong loc theo selected_paths

    Returns:
        XML string chua <folder> va <file> long nhau
    """
    import html

    def _build_xml(item: TreeItem, indent: str = "") -> str:
        name = html.escape(item.label)
        if item.is_dir:
            children_xml = ""
            for child in item.children:
                if show_all or _has_selected_descendant(child, selected_paths):
                    children_xml += _build_xml(child, indent + "  ")

            if children_xml:
                return (
                    f'{indent}<folder name="{name}">\n{children_xml}{indent}</folder>\n'
                )
            else:
                return f'{indent}<folder name="{name}"/>\n'
        else:
            path = path_for_display(Path(item.path), workspace_root, use_relative_paths)
            return f'{indent}<file path="{html.escape(path)}"/>\n'

    if not show_all and not _has_selected_descendant(tree, selected_paths):
        return "<structure/>"

    # Bat dau tu root
    xml_content = _build_xml(tree)
    return f"<structure>\n{xml_content}</structure>"


def generate_file_map(
    tree: TreeItem,
    selected_paths: set[str],
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
    show_all: bool = True,
) -> str:
    """
    Tao file map string tu tree structure.

    Args:
        tree: TreeItem root
        selected_paths: Set cac duong dan duoc tick (chi dung khi show_all=False)
        workspace_root: Workspace root
        use_relative_paths: True = xuat path tuong doi workspace
        show_all: Neu True, hien thi toan bo cây (van respect ignore engine)

    Returns:
        File map string voi ASCII tree visualization
    """
    lines: list[str] = []

    # Neu show_all=True hoặc root duoc chon/co descendants duoc chon
    if show_all or _has_selected_descendant(tree, selected_paths):
        root_display = path_for_display(
            Path(tree.path), workspace_root, use_relative_paths
        )
        lines.append(root_display)

        # Filter children (neu show_all=True thi không filter)
        if show_all:
            filtered_children = tree.children
        else:
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
    codemap_paths: Optional[Set[str]] = None,
) -> str:
    """
    Tao file contents theo Repomix XML format.

    Delegate sang file_collector + XML formatter.
    Khi codemap_paths duoc chi dinh, cac file trong set do
    se chi co AST signatures (codemap) thay vi full content.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)
        workspace_root: Workspace root cho relative paths
        use_relative_paths: Su dung relative paths
        codemap_paths: Optional set cac file paths chi lay codemap (AST signatures).
                       Paths co the la absolute hoac relative tuy theo use_relative_paths.

    Returns:
        File contents string voi XML structure
    """
    if codemap_paths:
        # Normalize ca hai set ve cung format de tranh silent failure
        def _normalize(p: str) -> str:
            pp = Path(p)
            if not pp.is_absolute() and workspace_root:
                return str((workspace_root / pp).resolve())
            return str(pp.resolve())

        normalized_selected = {_normalize(p) for p in selected_paths}
        normalized_codemap = {_normalize(p) for p in codemap_paths}

        full_paths_normalized = normalized_selected - normalized_codemap
        codemap_only_normalized = normalized_selected & normalized_codemap

        # Map nguoc ve original paths de truyen cho collect_files
        # Fix BUG #2: Detect collision khi nhieu paths normalize ve cung key
        norm_to_orig: dict[str, str] = {}
        for p in selected_paths:
            key = _normalize(p)
            if key in norm_to_orig and norm_to_orig[key] != p:
                raise ValueError(
                    f"Path collision: '{norm_to_orig[key]}' and '{p}' resolve to the same file. "
                    "Please remove the duplicate from your selection."
                )
            else:
                norm_to_orig[key] = p

        full_paths = {
            norm_to_orig[n] for n in full_paths_normalized if n in norm_to_orig
        }
        codemap_only = {
            norm_to_orig[n] for n in codemap_only_normalized if n in norm_to_orig
        }

        parts: list[str] = []

        # Generate full content cho non-codemap files
        if full_paths:
            entries = collect_files(
                full_paths, max_file_size, workspace_root, use_relative_paths
            )
            full_xml = format_files_xml(entries)
            if full_xml.strip():
                parts.append(full_xml)

        # Generate codemap cho codemap-only files
        if codemap_only:
            codemap_xml = _generate_codemap_xml(
                codemap_only, max_file_size, workspace_root, use_relative_paths
            )
            if codemap_xml.strip():
                parts.append(codemap_xml)

        return "\n\n".join(parts)
    else:
        entries = collect_files(
            selected_paths, max_file_size, workspace_root, use_relative_paths
        )
        return format_files_xml(entries)


def _generate_codemap_xml(
    paths: set[str],
    max_file_size: int,
    workspace_root: Optional[Path],
    use_relative_paths: bool,
) -> str:
    """
    Generate XML output cho codemap-only files.

    Su dung Tree-sitter smart_parse de extract AST signatures,
    roi wrap trong XML tags voi attribute context="codemap".

    Args:
        paths: Set file paths can codemap
        max_file_size: Max file size
        workspace_root: Workspace root
        use_relative_paths: Co dung relative paths khong

    Returns:
        XML string voi codemap content
    """
    from domain.smart_context import smart_parse, is_supported
    from xml.sax.saxutils import escape as xml_escape

    def _xml_attr_escape(s: str) -> str:
        """Escape string for XML attribute value."""
        return xml_escape(s, {'"': "&quot;"})

    parts: list[str] = []

    for path_str in sorted(paths):
        path = Path(path_str)

        try:
            if not path.is_file():
                continue

            if is_binary_file(path):
                continue

            try:
                file_size = path.stat().st_size
                if file_size > max_file_size:
                    continue
            except OSError:
                continue  # Khong doc duoc metadata -> skip an toan

            display_path = path_for_display(path, workspace_root, use_relative_paths)

            # Doc file 1 lan duy nhat
            raw_content = path.read_text(encoding="utf-8", errors="replace")

            # Try smart parse (AST signatures)
            ext = path.suffix.lstrip(".")
            if is_supported(ext):
                smart_content = smart_parse(
                    path_str, raw_content, include_relationships=False
                )
                if smart_content:
                    parts.append(
                        f'<file path="{_xml_attr_escape(display_path)}" context="codemap">\n'
                        f"{smart_content}\n"
                        f"</file>"
                    )
                    continue

            # Fallback: neu smart_parse khong ho tro, su dung raw_content da doc
            parts.append(
                f'<file path="{_xml_attr_escape(display_path)}" context="codemap-fallback">\n'
                f"{raw_content}\n"
                f"</file>"
            )

        except (OSError, IOError):
            continue

    return "\n\n".join(parts)


def generate_file_contents_json(
    selected_paths: set[str],
    max_file_size: int = 1024 * 1024,
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
    codemap_paths: Optional[Set[str]] = None,
) -> str:
    """
    Tao file contents theo JSON format.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)
        workspace_root: Workspace root
        use_relative_paths: Su dung relative paths
        codemap_paths: Optional set cac file paths chi lay codemap

    Returns:
        JSON string chua file paths va contents
    """
    if codemap_paths:
        import json as _json

        # Normalize ca hai set ve cung format
        def _normalize(p: str) -> str:
            pp = Path(p)
            if not pp.is_absolute() and workspace_root:
                return str((workspace_root / pp).resolve())
            return str(pp.resolve())

        normalized_selected = {_normalize(p) for p in selected_paths}
        normalized_codemap = {_normalize(p) for p in codemap_paths}

        full_paths_normalized = normalized_selected - normalized_codemap
        codemap_only_normalized = normalized_selected & normalized_codemap

        # Map nguoc ve original paths
        # Fix BUG #2: Detect collision
        norm_to_orig: dict[str, str] = {}
        for p in selected_paths:
            key = _normalize(p)
            if key in norm_to_orig and norm_to_orig[key] != p:
                raise ValueError(
                    f"Path collision: '{norm_to_orig[key]}' and '{p}' resolve to the same file. "
                    "Please remove the duplicate from your selection."
                )
            else:
                norm_to_orig[key] = p

        full_paths = {
            norm_to_orig[n] for n in full_paths_normalized if n in norm_to_orig
        }
        codemap_only = {
            norm_to_orig[n] for n in codemap_only_normalized if n in norm_to_orig
        }

        all_entries: list[dict] = []

        # Full content files
        if full_paths:
            entries = collect_files(
                full_paths, max_file_size, workspace_root, use_relative_paths
            )
            for entry in entries:
                all_entries.append(
                    {
                        "path": entry.display_path,
                        "content": entry.content or "",
                        "context": "full",
                    }
                )

        # Codemap files
        if codemap_only:
            from domain.smart_context import smart_parse, is_supported

            for path_str in sorted(codemap_only):
                path = Path(path_str)
                try:
                    if not path.is_file() or is_binary_file(path):
                        continue

                    display_path = path_for_display(
                        path, workspace_root, use_relative_paths
                    )
                    ext = path.suffix.lstrip(".")
                    raw_content = path.read_text(encoding="utf-8", errors="replace")

                    if is_supported(ext):
                        smart_content = smart_parse(
                            path_str, raw_content, include_relationships=False
                        )
                        if smart_content:
                            all_entries.append(
                                {
                                    "path": display_path,
                                    "content": smart_content,
                                    "context": "codemap",
                                }
                            )
                            continue

                    # Fallback to full content
                    all_entries.append(
                        {
                            "path": display_path,
                            "content": raw_content,
                            "context": "codemap-fallback",
                        }
                    )

                except (OSError, IOError):
                    continue

        return _json.dumps(all_entries, indent=2)
    else:
        entries = collect_files(
            selected_paths, max_file_size, workspace_root, use_relative_paths
        )
        return format_files_json(entries)


def generate_file_contents_plain(
    selected_paths: set[str],
    max_file_size: int = 1024 * 1024,
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
    codemap_paths: Optional[Set[str]] = None,
) -> str:
    """
    Tao file contents theo Plain Text format.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)
        workspace_root: Workspace root
        use_relative_paths: Su dung relative paths
        codemap_paths: Optional set cac file paths chi lay codemap

    Returns:
        String chua file paths va contents dang plain text
    """
    if codemap_paths:
        # Normalize ca hai set ve cung format
        def _normalize(p: str) -> str:
            pp = Path(p)
            if not pp.is_absolute() and workspace_root:
                return str((workspace_root / pp).resolve())
            return str(pp.resolve())

        normalized_selected = {_normalize(p) for p in selected_paths}
        normalized_codemap = {_normalize(p) for p in codemap_paths}

        full_paths_normalized = normalized_selected - normalized_codemap
        codemap_only_normalized = normalized_selected & normalized_codemap

        # Map nguoc ve original paths
        # Fix BUG #2: Detect collision
        norm_to_orig: dict[str, str] = {}
        for p in selected_paths:
            key = _normalize(p)
            if key in norm_to_orig and norm_to_orig[key] != p:
                raise ValueError(
                    f"Path collision: '{norm_to_orig[key]}' and '{p}' resolve to the same file. "
                    "Please remove the duplicate from your selection."
                )
            else:
                norm_to_orig[key] = p

        full_paths = {
            norm_to_orig[n] for n in full_paths_normalized if n in norm_to_orig
        }
        codemap_only = {
            norm_to_orig[n] for n in codemap_only_normalized if n in norm_to_orig
        }

        parts: list[str] = []

        # Full content files
        if full_paths:
            entries = collect_files(
                full_paths, max_file_size, workspace_root, use_relative_paths
            )
            full_text = format_files_plain(entries)
            if full_text.strip():
                parts.append(full_text)

        # Codemap files
        if codemap_only:
            from domain.smart_context import smart_parse, is_supported

            for path_str in sorted(codemap_only):
                path = Path(path_str)
                try:
                    if not path.is_file() or is_binary_file(path):
                        continue

                    display_path = path_for_display(
                        path, workspace_root, use_relative_paths
                    )
                    ext = path.suffix.lstrip(".")
                    raw_content = path.read_text(encoding="utf-8", errors="replace")

                    if is_supported(ext):
                        smart_content = smart_parse(
                            path_str, raw_content, include_relationships=False
                        )
                        if smart_content:
                            parts.append(
                                f"{display_path} [codemap]\n"
                                f"{'-' * len(display_path)}\n"
                                f"{smart_content}"
                            )
                            continue

                    # Fallback
                    parts.append(
                        f"{display_path} [codemap-fallback]\n"
                        f"{'-' * len(display_path)}\n"
                        f"{raw_content}"
                    )

                except (OSError, IOError):
                    continue

        return "\n\n".join(parts)
    else:
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
    from domain.smart_context import smart_parse, is_supported

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
    instructions_at_top: bool = False,
) -> str:
    """
    Tạo prompt đầy đủ cho Copy Smart.

    Delegate sang prompt_assembler.assemble_smart_prompt().

    Args:
        smart_contents: Output từ generate_smart_context()
        file_map: Output từ generate_file_map()
        user_instructions: Hướng dẫn từ người dùng
        git_diffs: Optional git diffs
        git_logs: Optional git logs
        project_rules: Project rules
        workspace_root: Optional workspace root (kept for API compatibility)
        instructions_at_top: Di chuyển instructions lên đầu

    Returns:
        Prompt string day du
    """
    return assemble_smart_prompt(
        smart_contents=smart_contents,
        file_map=file_map,
        user_instructions=user_instructions,
        git_diffs=git_diffs,
        git_logs=git_logs,
        project_rules=project_rules,
        instructions_at_top=instructions_at_top,
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
    instructions_at_top: bool = False,
) -> str:
    """
    Tạo prompt hoàn chỉnh để gửi cho LLM.

    Delegate sang prompt_assembler.assemble_prompt().

    Args:
        file_map: File map string từ generate_file_map()
        file_contents: File contents string từ formatter tương ứng
        user_instructions: Hướng dẫn từ người dùng
        include_xml_formatting: Có bao gồm OPX instructions không
        git_diffs: Optional git diffs (work tree & staged)
        git_logs: Optional git logs
        output_style: Định dạng đầu ra
        project_rules: Project rules
        workspace_root: Optional workspace root (kept for API compatibility)
        instructions_at_top: Di chuyển instructions lên đầu

    Returns:
        Prompt hoan chinh
    """
    return assemble_prompt(
        file_map=file_map,
        file_contents=file_contents,
        user_instructions=user_instructions,
        include_xml_formatting=include_xml_formatting,
        git_diffs=git_diffs,
        git_logs=git_logs,
        output_style=output_style,
        project_rules=project_rules,
        instructions_at_top=instructions_at_top,
        workspace_root=workspace_root,
    )
