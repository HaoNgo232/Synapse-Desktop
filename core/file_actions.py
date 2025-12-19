"""
File Actions - Thuc thi cac file operations tu OPX

Port tu: /home/hao/Desktop/labs/overwrite/src/providers/file-explorer/file-action-handler.ts

Cac operations:
- create: Tao file moi
- rewrite: Ghi de toan bo file
- modify: Tim va thay the mot phan trong file
- delete: Xoa file
- rename: Doi ten/di chuyen file
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal, Union

from core.opx_parser import FileAction, ChangeBlock


@dataclass
class ActionResult:
    """Ket qua thuc thi mot file action"""

    path: str
    action: str
    success: bool
    message: str
    new_path: Optional[str] = None  # Cho rename action


def apply_file_actions(
    file_actions: list[FileAction], workspace_roots: Optional[list[Path]] = None
) -> list[ActionResult]:
    """
    Thuc thi danh sach file actions.

    Args:
        file_actions: Danh sach FileAction tu OPX parser
        workspace_roots: Danh sach workspace roots (multi-workspace support)

    Returns:
        Danh sach ActionResult cho tung action
    """
    results: list[ActionResult] = []

    for action in file_actions:
        try:
            # Resolve path (ho tro absolute, relative, va multi-workspace)
            file_path = _resolve_path(action.path, action.root, workspace_roots)

            if action.action == "create":
                result = _handle_create(action, file_path)
            elif action.action == "rewrite":
                result = _handle_rewrite(action, file_path)
            elif action.action == "modify":
                result = _handle_modify(action, file_path)
            elif action.action == "delete":
                result = _handle_delete(action, file_path)
            elif action.action == "rename":
                result = _handle_rename(action, file_path, workspace_roots)
            else:
                result = ActionResult(
                    path=action.path,
                    action=action.action,
                    success=False,
                    message=f"Unknown action: {action.action}",
                )

            results.append(result)

        except Exception as e:
            results.append(
                ActionResult(
                    path=action.path,
                    action=action.action,
                    success=False,
                    message=str(e),
                )
            )

    return results


def _resolve_path(
    path_str: str, root_name: Optional[str], workspace_roots: Optional[list[Path]]
) -> Path:
    """
    Resolve path tu OPX thanh absolute Path.

    Ho tro:
    - Absolute paths
    - file:// URIs
    - Relative paths (resolved against workspace root)
    - Multi-workspace voi root attribute
    """
    # Handle file:// URI
    if path_str.startswith("file://"):
        path_str = path_str[7:]  # Remove file://

    path = Path(path_str)

    # Neu la absolute path, tra ve luon
    if path.is_absolute():
        return path

    # Neu khong co workspace roots, coi nhu relative to cwd
    if not workspace_roots:
        return Path.cwd() / path

    # Neu co root name, tim workspace root tuong ung
    if root_name:
        for ws_root in workspace_roots:
            if ws_root.name == root_name:
                return ws_root / path

    # Default: dung workspace root dau tien
    return workspace_roots[0] / path


def _handle_create(action: FileAction, file_path: Path) -> ActionResult:
    """Tao file moi"""
    try:
        if not action.changes:
            raise ValueError("No content provided for create action")

        content = action.changes[0].content

        # Tao parent directories neu chua ton tai
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Neu file da ton tai, skip (idempotent)
        if file_path.exists():
            return ActionResult(
                path=action.path,
                action="create",
                success=True,
                message="File already exists (skipped create)",
            )

        # Ghi file
        file_path.write_text(content, encoding="utf-8")

        return ActionResult(
            path=action.path,
            action="create",
            success=True,
            message="File created successfully",
        )

    except Exception as e:
        return ActionResult(
            path=action.path,
            action="create",
            success=False,
            message=_get_friendly_error(e),
        )


def _handle_rewrite(action: FileAction, file_path: Path) -> ActionResult:
    """Ghi de toan bo noi dung file"""
    try:
        if not action.changes:
            raise ValueError("No content provided for rewrite action")

        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        content = action.changes[0].content
        file_path.write_text(content, encoding="utf-8")

        return ActionResult(
            path=action.path,
            action="rewrite",
            success=True,
            message="File rewritten successfully",
        )

    except Exception as e:
        return ActionResult(
            path=action.path, action="rewrite", success=False, message=str(e)
        )


def _handle_modify(action: FileAction, file_path: Path) -> ActionResult:
    """Tim va thay the mot phan trong file"""
    try:
        if not action.changes:
            return ActionResult(
                path=action.path,
                action="modify",
                success=False,
                message="No changes provided for modify action",
            )

        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        # Doc file hien tai
        current_content = file_path.read_text(encoding="utf-8")
        eol = "\r\n" if "\r\n" in current_content else "\n"

        success_count = 0
        change_results: list[str] = []
        modified_content = current_content

        for change in action.changes:
            if not change.search:
                change_results.append("Error: Search block missing in a change")
                continue

            # Normalize EOL in search string
            normalized_search = _normalize_eol(change.search, eol)

            # Tim va thay the
            result, new_content = _apply_search_replace(
                modified_content, normalized_search, change.content, change.occurrence
            )

            if result:
                success_count += 1
                modified_content = new_content
                change_results.append(
                    f'Success: Applied change: "{change.description}"'
                )
            else:
                change_results.append(
                    f'Error: Search text not found: "{normalized_search[:30]}..."'
                )

        # Ghi file neu co thay doi thanh cong
        if success_count > 0:
            file_path.write_text(modified_content, encoding="utf-8")

            # Neu chi ap dung duoc mot phan -> coi la that bai de user chu y
            all_applied = success_count == len(action.changes)

            modifier_msg = "Applied" if all_applied else "Partial success: Applied"

            return ActionResult(
                path=action.path,
                action="modify",
                success=all_applied,
                message=f"{modifier_msg} {success_count}/{len(action.changes)} modifications. {'; '.join(change_results)}",
            )
        else:
            return ActionResult(
                path=action.path,
                action="modify",
                success=False,
                message=f"Failed to apply any modifications. {'; '.join(change_results)}",
            )

    except Exception as e:
        return ActionResult(
            path=action.path, action="modify", success=False, message=str(e)
        )


def _apply_search_replace(
    content: str,
    search: str,
    replace: str,
    occurrence: Optional[Union[Literal["first", "last"], int]],
) -> tuple[bool, str]:
    """
    Tim va thay the text trong content.

    Returns:
        (success, new_content)
    """
    first_pos = content.find(search)
    if first_pos == -1:
        return False, content

    has_multiple = content.find(search, first_pos + 1) != -1

    # Neu chi co 1 match hoac occurrence la first/undefined
    if not has_multiple or occurrence == "first" or occurrence is None:
        new_content = content[:first_pos] + replace + content[first_pos + len(search) :]
        return True, new_content

    # Occurrence = last
    if occurrence == "last":
        last_pos = content.rfind(search)
        new_content = content[:last_pos] + replace + content[last_pos + len(search) :]
        return True, new_content

    # Occurrence = number
    if isinstance(occurrence, int) and occurrence > 0:
        nth_pos = _find_nth_occurrence(content, search, occurrence)
        if nth_pos == -1:
            return False, content
        new_content = content[:nth_pos] + replace + content[nth_pos + len(search) :]
        return True, new_content

    # Nhieu matches ma khong co occurrence -> ambiguous
    return False, content


def _find_nth_occurrence(haystack: str, needle: str, n: int) -> int:
    """
    Tim vi tri occurrence thu n cua needle trong haystack.
    Port truc tiep tu TypeScript.
    """
    idx = -1
    from_pos = 0

    for _ in range(n):
        idx = haystack.find(needle, from_pos)
        if idx == -1:
            return -1
        from_pos = idx + len(needle)

    return idx


def _handle_delete(action: FileAction, file_path: Path) -> ActionResult:
    """Xoa file"""
    try:
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        if file_path.is_dir():
            import shutil

            shutil.rmtree(file_path)
        else:
            file_path.unlink()

        return ActionResult(
            path=action.path,
            action="delete",
            success=True,
            message="File deleted successfully",
        )

    except Exception as e:
        return ActionResult(
            path=action.path, action="delete", success=False, message=str(e)
        )


def _handle_rename(
    action: FileAction, file_path: Path, workspace_roots: Optional[list[Path]]
) -> ActionResult:
    """Doi ten/di chuyen file"""
    try:
        if not action.new_path:
            raise ValueError("Missing new path for rename operation")

        if not file_path.exists():
            raise FileNotFoundError(f"Original file does not exist: {file_path}")

        # Resolve new path
        new_path = _resolve_path(action.new_path, action.root, workspace_roots)

        # Tao parent directories neu chua ton tai
        new_path.parent.mkdir(parents=True, exist_ok=True)

        # Rename/move
        file_path.rename(new_path)

        return ActionResult(
            path=action.path,
            action="rename",
            success=True,
            message=f"File renamed successfully to '{action.new_path}'",
            new_path=action.new_path,
        )

    except Exception as e:
        return ActionResult(
            path=action.path,
            action="rename",
            success=False,
            message=str(e),
            new_path=action.new_path,
        )


def _normalize_eol(text: str, eol: str) -> str:
    """Normalize EOL characters trong text"""
    # Chuyen tat ca ve LF truoc
    lf = text.replace("\r\n", "\n")
    # Chuyen ve EOL mong muon
    if eol == "\r\n":
        return lf.replace("\n", "\r\n")
    return lf


def _get_friendly_error(error: Exception) -> str:
    """Chuyen error thanh message de hieu"""
    msg = str(error)

    if "ENOSPC" in msg or "no space" in msg.lower():
        return "Disk full: Not enough space to create file"
    if "EACCES" in msg or "permission" in msg.lower():
        return "Permission denied: Cannot write to this location"
    if "EBUSY" in msg or "locked" in msg.lower():
        return "File is locked by another process"
    if "EROFS" in msg or "read-only" in msg.lower():
        return "Read-only file system: Cannot create file"

    return msg
