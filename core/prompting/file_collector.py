"""
File Collector - Doc va thu thap files tu disk cho prompt pipeline.

Thay the logic doc file bi trung lap 4 lan trong:
- generate_file_contents() (Markdown)
- generate_file_contents_xml() (XML)
- generate_file_contents_json() (JSON)
- generate_file_contents_plain() (Plain)

Moi formatter goi collect_files() MOT LAN, roi format theo cach rieng.
"""

from pathlib import Path
from typing import Optional

from core.prompting.types import FileEntry
from core.utils.file_utils import is_binary_file
from core.utils.language_utils import get_language_from_path


def collect_files(
    selected_paths: set[str],
    max_file_size: int = 1024 * 1024,
    workspace_root: Optional[Path] = None,
    use_relative_paths: bool = False,
) -> list[FileEntry]:
    """
    Doc va thu thap cac files tu disk thanh List[FileEntry].

    Xu ly chung cho tat ca formatters:
    - Sort paths de thu tu nhat quan
    - Kiem tra is_file, is_binary, file_size
    - Doc content (utf-8 with replace)
    - Xac dinh language tu extension

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Kich thuoc toi da cua file (default 1MB)
        workspace_root: Thu muc goc de tinh relative paths
        use_relative_paths: Co dung relative paths khong

    Returns:
        List[FileEntry] da sort theo path
    """
    from core.prompting.path_utils import path_for_display

    sorted_paths = sorted(selected_paths)
    entries: list[FileEntry] = []

    for path_str in sorted_paths:
        path = Path(path_str)

        try:
            # Chi xu ly files
            if not path.is_file():
                continue

            display = path_for_display(path, workspace_root, use_relative_paths)
            language = get_language_from_path(str(path))

            # Skip binary files (check magic bytes)
            if is_binary_file(path):
                entries.append(
                    FileEntry(
                        path=path,
                        display_path=display,
                        content=None,
                        error="Binary file",
                        language=language,
                    )
                )
                continue

            # Skip files qua lon
            try:
                file_size = path.stat().st_size
                if file_size > max_file_size:
                    entries.append(
                        FileEntry(
                            path=path,
                            display_path=display,
                            content=None,
                            error=f"File too large ({file_size // 1024}KB)",
                            language=language,
                        )
                    )
                    continue
                # File rong
                if file_size == 0:
                    entries.append(
                        FileEntry(
                            path=path,
                            display_path=display,
                            content="",
                            error=None,
                            language=language,
                        )
                    )
                    continue
            except OSError:
                pass

            # Doc content
            content = path.read_text(encoding="utf-8", errors="replace")
            entries.append(
                FileEntry(
                    path=path,
                    display_path=display,
                    content=content,
                    error=None,
                    language=language,
                )
            )

        except (OSError, IOError) as e:
            display = path_for_display(path, workspace_root, use_relative_paths)
            language = get_language_from_path(str(path))
            entries.append(
                FileEntry(
                    path=path,
                    display_path=display,
                    content=None,
                    error=f"Error reading file: {e}",
                    language=language,
                )
            )

    return entries
