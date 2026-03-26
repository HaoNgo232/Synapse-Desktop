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

from shared.types.prompt_types import FileEntry
from infrastructure.filesystem.file_utils import is_binary_file
from shared.utils.language_utils import get_language_from_path


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
    - Parallel I/O khi co >5 files de tang toc do

    Args:
        selected_paths: Set cac duong dan file duoc tick
        max_file_size: Kich thuoc toi da cua file (default 1MB)
        workspace_root: Thu muc goc de tinh relative paths
        use_relative_paths: Co dung relative paths khong

    Returns:
        List[FileEntry] da sort theo path
    """
    from concurrent.futures import ThreadPoolExecutor
    from shared.utils.path_utils import path_for_display

    sorted_paths = sorted(selected_paths)

    def _process(path_str: str) -> Optional[FileEntry]:
        path = Path(path_str)
        display = path_for_display(path, workspace_root, use_relative_paths)
        language = get_language_from_path(str(path))

        try:
            if not path.is_file():
                return None  # Skip, khong them entry (giong behavior cu)

            if is_binary_file(path):
                return FileEntry(
                    path=path,
                    display_path=display,
                    content=None,
                    error="Binary file",
                    language=language,
                )

            try:
                file_size = path.stat().st_size
                if file_size > max_file_size:
                    return FileEntry(
                        path=path,
                        display_path=display,
                        content=None,
                        error=f"File too large ({file_size // 1024}KB)",
                        language=language,
                    )
                if file_size == 0:
                    return FileEntry(
                        path=path,
                        display_path=display,
                        content="",
                        error=None,
                        language=language,
                    )
            except OSError:
                pass

            content = path.read_text(encoding="utf-8", errors="replace")
            return FileEntry(
                path=path,
                display_path=display,
                content=content,
                error=None,
                language=language,
            )

        except (OSError, IOError) as e:
            return FileEntry(
                path=path,
                display_path=display,
                content=None,
                error=f"Error reading file: {e}",
                language=language,
            )

    if len(sorted_paths) > 5:
        with ThreadPoolExecutor(max_workers=min(8, len(sorted_paths))) as executor:
            return [e for e in executor.map(_process, sorted_paths) if e is not None]
    else:
        return [e for e in (_process(p) for p in sorted_paths) if e is not None]
