"""
File Actions - Thuc thi cac file operations tu OPX

Cac operations:
- create: Tao file moi
- rewrite: Ghi de toan bo file
- modify: Tim va thay the mot phan trong file
- delete: Xoa file
- rename: Doi ten/di chuyen file
"""

import os
import re
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal, Union
from datetime import datetime

from core.opx_parser import FileAction, ChangeBlock
from core.logging_config import log_error, log_info, log_debug, log_warning
from config.paths import BACKUP_DIR


def create_backup(file_path: Path) -> Optional[Path]:
    """
    Tạo backup của file trước khi modify.

    Args:
        file_path: Path đến file cần backup

    Returns:
        Path đến backup file, hoặc None nếu thất bại
    """
    if not file_path.exists():
        return None

    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Tạo tên backup với timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = BACKUP_DIR / backup_name

        shutil.copy2(file_path, backup_path)
        log_debug(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        log_error(f"Failed to create backup for {file_path}", e)
        return None


def restore_backup(backup_path: Path, original_path: Path) -> bool:
    """
    Khôi phục file từ backup.

    Args:
        backup_path: Path đến backup file
        original_path: Path đến file gốc cần restore

    Returns:
        True nếu restore thành công
    """
    try:
        if not backup_path.exists():
            log_error(f"Backup file not found: {backup_path}")
            return False

        # Basic validation: check file is readable and not empty
        file_size = backup_path.stat().st_size
        if file_size == 0:
            log_warning(f"Backup file is empty: {backup_path}")
            # Still allow restore of empty files - might be intentional

        shutil.copy2(backup_path, original_path)
        log_info(f"Restored from backup: {original_path}")
        return True
    except Exception as e:
        log_error(f"Failed to restore backup for {original_path}", e)
    return False


def list_backups(file_name: Optional[str] = None) -> list[Path]:
    """
    List all backup files, optionally filtered by original file name.

    Args:
        file_name: Optional original file name to filter by

    Returns:
        List of backup file paths, sorted by modification time (newest first)
    """
    if not BACKUP_DIR.exists():
        return []

    try:
        backups = list(BACKUP_DIR.glob("*.bak"))

        if file_name:
            # Filter by file name (backup format: filename.timestamp.bak)
            backups = [b for b in backups if b.name.startswith(file_name + ".")]

        # Sort by modification time, newest first
        backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return backups
    except Exception as e:
        log_error("Failed to list backups", e)
        return []


def cleanup_old_backups(max_age_days: int = 7, max_count: int = 100) -> int:
    """
    Cleanup backup files cũ hơn max_age_days hoặc vượt quá max_count.

    Args:
        max_age_days: Số ngày tối đa giữ backup (default 7)
        max_count: Số lượng backup tối đa giữ lại (default 100)

    Returns:
        Số lượng files đã xóa
    """
    if not BACKUP_DIR.exists():
        return 0

    deleted_count = 0
    now = datetime.now()

    try:
        # List all backup files sorted by modification time (oldest first)
        backup_files = sorted(BACKUP_DIR.glob("*.bak"), key=lambda f: f.stat().st_mtime)

        # Delete files older than max_age_days
        cutoff_time = now.timestamp() - (max_age_days * 24 * 60 * 60)
        for backup_file in backup_files[:]:
            if backup_file.stat().st_mtime < cutoff_time:
                try:
                    backup_file.unlink()
                    deleted_count += 1
                    backup_files.remove(backup_file)
                    log_debug(f"Deleted old backup: {backup_file.name}")
                except Exception:
                    pass

        # Delete oldest files if count exceeds max_count
        while len(backup_files) > max_count:
            oldest = backup_files.pop(0)
            try:
                oldest.unlink()
                deleted_count += 1
                log_debug(f"Deleted excess backup: {oldest.name}")
            except Exception:
                pass

        if deleted_count > 0:
            log_info(f"Cleaned up {deleted_count} old backup file(s)")

    except Exception as e:
        log_error("Failed to cleanup backups", e)

    return deleted_count


@dataclass
class ActionResult:
    """Ket qua thuc thi mot file action"""

    path: str
    action: str
    success: bool
    message: str
    new_path: Optional[str] = None  # Cho rename action


def apply_file_actions(
    file_actions: list[FileAction],
    workspace_roots: Optional[list[Path]] = None,
    dry_run: bool = False,
) -> list[ActionResult]:
    """
    Thuc thi danh sach file actions.

    Args:
        file_actions: Danh sach FileAction tu OPX parser
        workspace_roots: Danh sach workspace roots (multi-workspace support)
        dry_run: Neu True, chi validate khong thuc su apply

    Returns:
        Danh sach ActionResult cho tung action
    """
    # Cleanup old backups before creating new ones (skip in dry-run)
    if not dry_run:
        cleanup_old_backups()

    results: list[ActionResult] = []
    mode = "Validating" if dry_run else "Applying"
    log_info(f"{mode} {len(file_actions)} file action(s)")

    for action in file_actions:
        try:
            log_debug(f"Processing: {action.action} on {action.path}")
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
            log_error(f"Action failed: {action.action} on {action.path}", e)
            results.append(
                ActionResult(
                    path=action.path,
                    action=action.action,
                    success=False,
                    message=str(e),
                )
            )

    success_count = sum(1 for r in results if r.success)
    log_info(f"Completed: {success_count}/{len(results)} action(s) successful")
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

        # Create backup before rewrite
        create_backup(file_path)

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

        # Create backup before modify
        create_backup(file_path)

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
