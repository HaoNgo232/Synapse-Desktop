"""
Path Utilities - Single source of truth cho viec hien thi duong dan.

Module nay cung cap function path_for_display() dung chung cho
prompt_generator, git_utils, va bat ky module nao can hien thi
duong dan tuong doi/absolute cho nguoi dung.

Thay the cac ban sao _path_for_display() truoc day nam rai rac o:
- core/prompt_generator.py
- core/utils/git_utils.py
"""

from pathlib import Path
from typing import Optional


def path_for_display(
    path: Path,
    workspace_root: Optional[Path],
    use_relative_paths: bool,
) -> str:
    """
    Tra ve path de hien thi trong prompt/XML/output.

    Khi use_relative_paths=True va workspace_root duoc cung cap, tra ve path
    tuong doi tu workspace root (tranh PII - absolute path chua username/machine).
    Fallback: tra ve absolute path nhu logic cu.

    Args:
        path: Duong dan file/dir
        workspace_root: Workspace root (None neu khong co)
        use_relative_paths: True = xuat relative, False = xuat absolute

    Returns:
        Path string de dung trong output
    """
    if not use_relative_paths or not workspace_root:
        return str(path)
    try:
        resolved = path.resolve()
        root_resolved = Path(workspace_root).resolve()
        rel = str(resolved.relative_to(root_resolved))
        # Root "." -> hien thi ten folder workspace (vd. synapse-desktop) cho ro rang
        if rel == ".":
            return root_resolved.name.lower()
        return rel
    except ValueError:
        # Path khong nam trong workspace (vd. symlink) -> fallback absolute
        return str(path)
