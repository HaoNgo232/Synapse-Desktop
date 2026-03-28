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

from infrastructure.filesystem.file_utils import is_binary_file
from shared.types.prompt_types import FileEntry
from shared.utils.import_parser import extract_local_imports
from shared.utils.language_utils import get_language_from_path
from shared.utils.metadata_utils import (
    extract_layer_from_path,
    extract_role_from_content,
)


# Logics metadata (layer, role) da duoc move sang shared/utils/metadata_utils.py
# de de dang quan ly heuristics cho nhieu loai project (Web, Python, DDD).


def _path_to_dotted(path_str: str) -> str:
    """Chuyen doi path sang dotted notation (e.g., domain/prompt -> domain.prompt)."""
    p = Path(path_str)
    # Strip cac extension pho bien cua source code
    known_extensions = {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".mts",
        ".cts",
    }
    if p.suffix.lower() in known_extensions:
        path_str = str(p.with_suffix(""))

    return path_str.replace("/", ".").replace("\\", ".")


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
    - Trich xuat layer, role, dependencies
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

    # print(f"DEBUG: selected_paths types: {[type(p) for p in selected_paths]}")
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

            # Trich xuat metadata tu shared utility
            layer = extract_layer_from_path(display, workspace_root)
            role = extract_role_from_content(path, content)
            deps: list[str] = []
            if workspace_root:
                raw_deps = extract_local_imports(path, workspace_root)
                deps = []
                for rd in raw_deps:
                    dotted = _path_to_dotted(rd)
                    if dotted.endswith(".__init__"):
                        dotted = dotted[:-9]
                    deps.append(dotted)

            return FileEntry(
                path=path,
                display_path=display,
                content=content,
                error=None,
                language=language,
                layer=layer,
                role=role,
                dependencies=deps,
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
