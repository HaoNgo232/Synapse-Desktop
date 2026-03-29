"""
Prompt Helpers - Tách logic đếm token per-file và các utility ra khỏi PromptBuildService.
"""

from pathlib import Path
from typing import List, Optional, Set, Dict, Any
from shared.types.prompt_types_extra import FileTokenInfo
from domain.prompt.file_collector import collect_files
import logging

logger = logging.getLogger(__name__)


def count_per_file_tokens(
    file_paths: List[Path],
    workspace: Path,
    use_relative_paths: bool,
    dep_path_set: set[str],
    tokenization_service: Any,
    codemap_paths: Optional[Set[str]] = None,
) -> List[FileTokenInfo]:
    """
    Dem token cho tung file rieng le de cung cap metadata chi tiet.
    """
    entries = collect_files(
        selected_paths={str(p) for p in file_paths},
        workspace_root=workspace,
        use_relative_paths=use_relative_paths,
    )

    codemap_set = codemap_paths or set()

    result: list[FileTokenInfo] = []
    for entry in entries:
        entry_path_abs = str(entry.path)
        if not Path(entry_path_abs).is_absolute():
            entry_path_abs = str((workspace / entry_path_abs).resolve())

        is_codemap_file = entry_path_abs in codemap_set
        tokens = 0

        if is_codemap_file and entry.content:
            from domain.smart_context import smart_parse, is_supported

            ext = Path(str(entry.path)).suffix.lstrip(".")
            if is_supported(ext):
                smart = smart_parse(
                    str(entry.path), entry.content, include_relationships=False
                )
                if smart:
                    tokens = tokenization_service.count_tokens(smart)
                else:
                    tokens = tokenization_service.count_tokens(entry.content)
            else:
                tokens = tokenization_service.count_tokens(entry.content)
        elif entry.content:
            tokens = tokenization_service.count_tokens(entry.content)

        result.append(
            FileTokenInfo(
                path=entry.display_path,
                tokens=tokens,
                is_dependency=str(entry.path) in dep_path_set,
                was_trimmed=False,
                is_codemap=is_codemap_file,
            )
        )

    return result


def reconstruct_file_contents(
    trimmed_contents: Dict[str, str], output_format: str
) -> str:
    """
    Re-format trimmed dictionary content vao string theo output_format.
    """
    if not trimmed_contents:
        return ""

    parts = []
    if output_format == "xml":
        for path, content in trimmed_contents.items():
            parts.append(f'<file path="{path}">\n{content}\n</file>')
        return "\n\n".join(parts)
    elif output_format == "json":
        import json as _json

        arr = []
        for path, content in trimmed_contents.items():
            arr.append({"path": path, "content": content})
        return _json.dumps(arr, indent=2)
    else:
        # plain
        for path, content in trimmed_contents.items():
            parts.append(f"{path}\n" + "-" * len(path) + f"\n{content}")
        return "\n\n".join(parts)
