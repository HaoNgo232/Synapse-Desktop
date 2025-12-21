"""
Prompt Generator - Tao context prompt cho LLM

Hỗ trợ nhiều output formats:
- Markdown: Code blocks với syntax highlighting (default)
- XML: Structured XML theo chuẩn Repomix
"""

import re
import html
import json
from pathlib import Path
from typing import List, Optional

from core.utils.file_utils import TreeItem, is_binary_by_extension
from core.opx_instruction import XML_FORMATTING_INSTRUCTIONS
from core.utils.language_utils import get_language_from_path
from core.utils.git_utils import GitDiffResult, GitLogResult
from config.output_format import OutputStyle


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
        # Tim tat ca cac day backticks trong content
        matches = re.findall(r"`+", content)
        if matches:
            # Lay do dai lon nhat cua day backticks
            max_backticks = max(max_backticks, max(len(m) for m in matches))

    # Delimiter phai lon hon max backticks tim thay, toi thieu 3
    return "`" * max(3, max_backticks + 1)


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

    Su dung Smart Markdown Delimiter de tranh broken markdown
    khi file content chua backticks.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        File contents string voi markdown code blocks
    """
    # Sort paths de thu tu nhat quan
    sorted_paths = sorted(selected_paths)

    # Phase 1: Doc tat ca file contents truoc de tinh delimiter
    file_data: list[tuple[Path, str | None, str | None]] = []  # (path, content, error)
    all_contents: list[str] = []

    for path_str in sorted_paths:
        path = Path(path_str)

        try:
            # Chi xu ly files
            if not path.is_file():
                continue

            # Skip binary files
            if is_binary_by_extension(path):
                file_data.append((path, None, "Binary file"))
                continue

            # Skip files that are too large
            try:
                file_size = path.stat().st_size
                if file_size > max_file_size:
                    file_data.append(
                        (path, None, f"File too large ({file_size // 1024}KB)")
                    )
                    continue
            except OSError:
                pass

            # Doc content
            content = path.read_text(encoding="utf-8", errors="replace")
            file_data.append((path, content, None))
            all_contents.append(content)

        except (OSError, IOError) as e:
            file_data.append((path, None, f"Error reading file: {e}"))

    # Phase 2: Tinh Smart Markdown Delimiter
    delimiter = calculate_markdown_delimiter(all_contents)

    # Phase 3: Generate output voi dynamic delimiter
    contents: list[str] = []
    contents_append = contents.append

    for path, content, error in file_data:
        if error:
            contents_append(f"File: {path}\n*** Skipped: {error} ***\n")
        elif content is not None:
            language = get_language_from_path(str(path))
            contents_append(
                f"File: {path}\n{delimiter}{language}\n{content}\n{delimiter}\n"
            )

    return "\n".join(contents).strip()


def generate_file_contents_xml(
    selected_paths: set[str], max_file_size: int = 1024 * 1024
) -> str:
    """
    Tạo file contents theo Repomix XML format.

    Output format:
    <files>
      <file path="src/main.py">
        content here
      </file>
    </files>

    Args:
        selected_paths: Set các đường dẫn file được tick
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        File contents string với XML structure
    """
    sorted_paths = sorted(selected_paths)
    file_elements: list[str] = []

    for path_str in sorted_paths:
        path = Path(path_str)

        try:
            if not path.is_file():
                continue

            # Skip binary files
            if is_binary_by_extension(path):
                file_elements.append(
                    f'<file path="{html.escape(str(path))}" skipped="true">Binary file</file>'
                )
                continue

            # Skip files that are too large
            try:
                file_size = path.stat().st_size
                if file_size > max_file_size:
                    file_elements.append(
                        f'<file path="{html.escape(str(path))}" skipped="true">File too large ({file_size // 1024}KB)</file>'
                    )
                    continue
            except OSError:
                pass

            # Read and escape content for XML
            content = path.read_text(encoding="utf-8", errors="replace")
            # Escape XML special characters trong content
            escaped_content = html.escape(content)
            file_elements.append(
                f'<file path="{html.escape(str(path))}">\n{escaped_content}\n</file>'
            )

        except (OSError, IOError) as e:
            file_elements.append(
                f'<file path="{html.escape(str(path))}" skipped="true">Error: {html.escape(str(e))}</file>'
            )

    if not file_elements:
        return "<files></files>"

    return "<files>\n" + "\n".join(file_elements) + "\n</files>"


def generate_file_contents_json(
    selected_paths: set[str], max_file_size: int = 1024 * 1024
) -> str:
    """
    Tạo file contents theo JSON format.

    Output format (serialized JSON string):
    {
        "path/to/file": "content",
        "path/to/another": "content"
    }

    Args:
        selected_paths: Set các đường dẫn file được tick
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        JSON string containing file paths and contents
    """
    sorted_paths = sorted(selected_paths)
    files_dict = {}

    for path_str in sorted_paths:
        path = Path(path_str)

        try:
            if not path.is_file():
                continue

            # Skip binary files
            if is_binary_by_extension(path):
                files_dict[str(path)] = "Binary file (skipped)"
                continue

            # Skip files that are too large
            try:
                file_size = path.stat().st_size
                if file_size > max_file_size:
                    files_dict[str(path)] = (
                        f"File too large ({file_size // 1024}KB) (skipped)"
                    )
                    continue
            except OSError:
                pass

            # Read content
            content = path.read_text(encoding="utf-8", errors="replace")
            files_dict[str(path)] = content

        except (OSError, IOError) as e:
            files_dict[str(path)] = f"Error reading file: {e}"

    return json.dumps(files_dict, ensure_ascii=False)


def generate_file_contents_plain(
    selected_paths: set[str], max_file_size: int = 1024 * 1024
) -> str:
    """
    Tạo file contents theo định dạng Plain Text.

    Format:
    File: path/to/file
    ----------------
    content
    ----------------

    Args:
        selected_paths: Set các đường dẫn file được tick
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        String containing file paths and contents in plain text format
    """
    sorted_paths = sorted(selected_paths)
    file_elements = []

    separator = "-" * 16

    for path_str in sorted_paths:
        path = Path(path_str)

        try:
            if not path.is_file():
                continue

            # Header cho mỗi file
            file_header = f"File: {path_str}\n{separator}"

            # Content handling
            content_display = ""

            # Skip binary files
            if is_binary_by_extension(path):
                content_display = "Binary file (skipped)"
            else:
                # Skip files that are too large
                try:
                    file_size = path.stat().st_size
                    if file_size > max_file_size:
                        content_display = (
                            f"File too large ({file_size // 1024}KB) (skipped)"
                        )
                    else:
                        # Read content
                        content_display = path.read_text(
                            encoding="utf-8", errors="replace"
                        ).strip()
                except OSError:
                    pass

            file_elements.append(f"{file_header}\n{content_display}\n{separator}")

        except (OSError, IOError) as e:
            file_elements.append(
                f"File: {path_str}\n{separator}\nError reading file: {e}\n{separator}"
            )

    if not file_elements:
        return "No files selected."

    return "\n\n".join(file_elements)


def generate_smart_context(
    selected_paths: set[str], max_file_size: int = 1024 * 1024
) -> str:
    """
    Tao Smart Context string - chi chua code structure (signatures, docstrings).
    Dung Tree-sitter de parse va trich xuat cau truc thay vi raw content.

    Su dung Smart Markdown Delimiter de tranh broken markdown
    khi file content chua backticks.

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        Smart context string voi code signatures
    """
    # Import lazy de tranh circular import va load cham
    from core.smart_context import smart_parse, is_supported

    sorted_paths = sorted(selected_paths)

    # Phase 1: Doc va parse tat ca files truoc
    file_data: list[tuple[Path, str | None, str | None]] = (
        []
    )  # (path, smart_content, error)
    all_contents: list[str] = []

    for path_str in sorted_paths:
        path = Path(path_str)

        try:
            if not path.is_file():
                continue

            # Skip binary files
            if is_binary_by_extension(path):
                file_data.append((path, None, "Binary file"))
                continue

            # Skip files that are too large
            try:
                file_size = path.stat().st_size
                if file_size > max_file_size:
                    file_data.append(
                        (path, None, f"File too large ({file_size // 1024}KB)")
                    )
                    continue
            except OSError:
                pass

            # Doc raw content
            raw_content = path.read_text(encoding="utf-8", errors="replace")

            # Kiem tra ho tro Smart Context
            ext = path.suffix.lstrip(".")
            if not is_supported(ext):
                file_data.append(
                    (path, None, f"Smart Context not available for .{ext} files")
                )
                continue

            # Try Smart Parse
            smart_content = smart_parse(path_str, raw_content)

            if smart_content:
                file_data.append((path, smart_content, None))
                all_contents.append(smart_content)
            else:
                file_data.append((path, None, "Smart Context parse failed"))

        except (OSError, IOError) as e:
            file_data.append((path, None, f"Error reading file: {e}"))

    # Phase 2: Tinh Smart Markdown Delimiter
    delimiter = calculate_markdown_delimiter(all_contents)

    # Phase 3: Generate output voi dynamic delimiter
    contents: list[str] = []
    contents_append = contents.append

    for path, smart_content, error in file_data:
        if error:
            contents_append(f"File: {path}\n*** Skipped: {error} ***\n")
        elif smart_content is not None:
            language = get_language_from_path(str(path))
            contents_append(
                f"File: {path} [Smart Context]\n{delimiter}{language}\n{smart_content}\n{delimiter}\n"
            )

    return "\n".join(contents).strip()


def generate_prompt(
    file_map: str,
    file_contents: str,
    user_instructions: str = "",
    include_xml_formatting: bool = False,
    git_diffs: Optional[GitDiffResult] = None,
    git_logs: Optional[GitLogResult] = None,
    output_style: OutputStyle = OutputStyle.XML,
) -> str:
    """
    Tao prompt hoan chinh de gui cho LLM.

    Args:
        file_map: File map string tu generate_file_map()
        file_contents: File contents string tu generate_file_contents() hoac generate_file_contents_xml()
        user_instructions: Huong dan tu nguoi dung
        include_xml_formatting: Co bao gom OPX instructions khong
        git_diffs: Optional git diffs (work tree & staged)
        git_logs: Optional git logs
        output_style: Dinh dang dau ra (MARKDOWN hoac XML)

    Returns:
        Prompt hoan chinh
    """
    # Tao prompt structure dua vao output_style
    if output_style == OutputStyle.XML:
        # XML format - structured tags
        prompt = f"""<directory_structure>
{file_map}
</directory_structure>

{file_contents}
"""
    elif output_style == OutputStyle.JSON:
        # JSON format
        # file_contents is already a JSON string of files dict
        # We construct a full JSON object including metadata
        try:
            files_data = json.loads(file_contents)
        except json.JSONDecodeError:
            files_data = {}

        prompt_data = {
            "directory_structure": file_map,
            "files": files_data,
        }

        if user_instructions:
            prompt_data["instructions"] = user_instructions

        # Git data
        if git_diffs:
            prompt_data["git_diffs"] = {
                "work_tree": git_diffs.work_tree_diff,
                "staged": git_diffs.staged_diff,
            }

        if git_logs:
            prompt_data["git_logs"] = git_logs.log_content

        if include_xml_formatting:
            # For JSON, we might want a different field or explanation,
            # but let's keep it as text instruction for now if requested
            prompt_data["formatting_instructions"] = XML_FORMATTING_INSTRUCTIONS

        return json.dumps(prompt_data, ensure_ascii=False, indent=2)

    elif output_style == OutputStyle.PLAIN:
        # Plain text format
        # No XML tags, just concatenated data
        prompt_parts = []

        if user_instructions:
            prompt_parts.append(f"Instructions:\n{user_instructions}")
            prompt_parts.append("-" * 32)

        prompt_parts.append(f"Directory Structure:\n{file_map}")
        prompt_parts.append("-" * 32)

        prompt_parts.append(f"File Contents:\n{file_contents}")

        # Git data
        if git_diffs:
            prompt_parts.append("-" * 32)
            prompt_parts.append(
                f"Git Diffs:\nWork Tree:\n{git_diffs.work_tree_diff}\n\nStaged:\n{git_diffs.staged_diff}"
            )

        if git_logs:
            prompt_parts.append("-" * 32)
            prompt_parts.append(f"Git Logs:\n{git_logs.log_content}")

        return "\n\n".join(prompt_parts)

    else:
        # Markdown format (default) - original behavior
        prompt = f"""<file_map>
{file_map}
</file_map>

<file_contents>
{file_contents}
</file_contents>
"""

    # Add Git Changes section
    if git_diffs or git_logs:
        prompt += "\n<git_changes>\n"

        if git_diffs:
            if git_diffs.work_tree_diff:
                prompt += f"<git_diff_worktree>\n{git_diffs.work_tree_diff}\n</git_diff_worktree>\n"
            if git_diffs.staged_diff:
                prompt += (
                    f"<git_diff_staged>\n{git_diffs.staged_diff}\n</git_diff_staged>\n"
                )

        if git_logs and git_logs.log_content:
            prompt += f"<git_log>\n{git_logs.log_content}\n</git_log>\n"

        prompt += "</git_changes>\n"

    if include_xml_formatting:
        prompt += f"\n{XML_FORMATTING_INSTRUCTIONS}"

    if user_instructions and user_instructions.strip():
        prompt += f"\n<user_instructions>\n{user_instructions.strip()}\n</user_instructions>\n"

    return prompt
