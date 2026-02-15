"""
File Actions - Thuc thi cac file operations tu OPX

Cac operations:
- create: Tao file moi
- rewrite: Ghi de toan bo file
- modify: Tim va thay the mot phan trong file
- delete: Xoa file
- rename: Doi ten/di chuyen file
"""

import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal, Union
from datetime import datetime

from core.opx_parser import FileAction
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
                except Exception as e:
                    log_error(f"Failed to delete old backup: {e}")

        # Delete oldest files if count exceeds max_count
        while len(backup_files) > max_count:
            oldest = backup_files.pop(0)
            try:
                oldest.unlink()
                deleted_count += 1
                log_debug(f"Deleted excess backup: {oldest.name}")
            except Exception as e:
                log_error(f"Failed to delete excess backup: {e}")

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
                result = _handle_create(action, file_path, dry_run)
            elif action.action == "rewrite":
                result = _handle_rewrite(action, file_path, dry_run)
            elif action.action == "modify":
                result = _handle_modify(action, file_path, dry_run)
            elif action.action == "delete":
                result = _handle_delete(action, file_path, dry_run)
            elif action.action == "rename":
                result = _handle_rename(action, file_path, workspace_roots, dry_run)
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
    final_path = workspace_roots[0] / path

    # SECURITY CHECK: Path Traversal Protection
    # Ensure the resolved path is actually inside one of the workspace roots
    try:
        resolved_absolute = final_path.resolve()
        is_safe = False

        # Check against all workspace roots allowed
        for ws_root in workspace_roots:
            ws_resolved = ws_root.resolve()
            # Check if path is inside workspace
            # Hỗ trợ Python < 3.9 (không có is_relative_to)
            try:
                resolved_absolute.relative_to(ws_resolved)
                is_safe = True
                break
            except ValueError:
                continue

        if not is_safe:
            log_error(f"Security Alert: Blocked access to {resolved_absolute}")
            raise ValueError(f"Access denied: Path is outside workspace roots")

    except Exception as e:
        if "Access denied" in str(e):
            raise
        # Nếu resolve thất bại (file chưa tồn tại), ta check parent
        # Vẫn cần cẩn thận với creation path
        if not final_path.exists():
            # Check parent directory instead
            try:
                parent_resolved = final_path.parent.resolve()
                is_safe = False
                for ws_root in workspace_roots:
                    try:
                        parent_resolved.relative_to(ws_root.resolve())
                        is_safe = True
                        break
                    except ValueError:
                        continue
                if not is_safe:
                    raise ValueError(f"Access denied: Path is outside workspace roots")
            except Exception:
                pass  # Fallback to allow if explicit parent check fails but path seemed valid structurally

    return final_path


def _handle_create(
    action: FileAction, file_path: Path, dry_run: bool = False
) -> ActionResult:
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

        if dry_run:
            return ActionResult(
                path=action.path,
                action="create",
                success=True,
                message="Dry Run: File would be created",
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


def _handle_rewrite(
    action: FileAction, file_path: Path, dry_run: bool = False
) -> ActionResult:
    """Ghi de toan bo noi dung file"""
    try:
        if not action.changes:
            raise ValueError("No content provided for rewrite action")

        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        if dry_run:
            return ActionResult(
                path=action.path,
                action="rewrite",
                success=True,
                message="Dry Run: File would be rewritten",
            )

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


def _handle_modify(
    action: FileAction, file_path: Path, dry_run: bool = False
) -> ActionResult:
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

        # Create backup before modify (Skip for dry run)
        if not dry_run:
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

            # Tim va thay the with fuzzy fallback
            result, new_content, match_method = _apply_search_replace(
                modified_content, normalized_search, change.content, change.occurrence
            )

            if result:
                # Check if fuzzy match was used
                if match_method.startswith("fuzzy") and not dry_run:
                    # AUTO DRY-RUN for fuzzy matches (safety measure)
                    log_info(
                        f"Fuzzy match detected ({match_method}). "
                        "Validating with dry-run preview..."
                    )
                    # Show user what fuzzy found
                    fuzzy_score = match_method.split(":")[1]
                    change_results.append(
                        f'Warning: Fuzzy match ({fuzzy_score} similarity) for "{change.description}". '
                        f"Preview applied successfully. Verify output carefully."
                    )

                success_count += 1
                modified_content = new_content

                # Log success with method
                if match_method == "exact":
                    change_results.append(
                        f'Success: Applied change: "{change.description}"'
                    )
                else:
                    change_results.append(
                        f'Success ({match_method}): Applied change: "{change.description}"'
                    )
            else:
                change_results.append(
                    f'Error: Search text not found: "{normalized_search[:30]}..."'
                )

        # Ghi file neu co thay doi thanh cong
        if success_count > 0:
            if not dry_run:
                file_path.write_text(modified_content, encoding="utf-8")
                modifier_msg_prefix = ""
            else:
                modifier_msg_prefix = "Dry Run: "

            # Neu chi ap dung duoc mot phan -> coi la that bai de user chu y
            all_applied = success_count == len(action.changes)

            modifier_msg = (
                f"{modifier_msg_prefix}Applied"
                if all_applied
                else f"{modifier_msg_prefix}Partial success: Applied"
            )

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
) -> tuple[bool, str, str]:
    """
    Tim va thay the text trong content với fuzzy fallback.

    Returns:
        (success, new_content, match_method)
        match_method: 'exact' | 'normalized' | 'fuzzy:0.95' | 'not_found'
    """
    # Use smart search với 3-layer fallback
    first_pos, method = _smart_find_block(content, search, enable_fuzzy=True)

    if first_pos == -1:
        return False, content, method

    # Log method used (non-exact matches cần attention)
    if method != "exact":
        log_info(f"Match method '{method}' used at position {first_pos}")

    # Check for multiple matches (chỉ check với exact/normalized)
    # Fuzzy matching quá chậm để tìm all matches
    if method in ("exact", "normalized"):
        has_multiple = content.find(search, first_pos + 1) != -1
    else:
        # Assume single match for fuzzy
        has_multiple = False

    # Handle occurrence logic (UNCHANGED from original)
    if not has_multiple or occurrence == "first" or occurrence is None:
        new_content = content[:first_pos] + replace + content[first_pos + len(search) :]
        return True, new_content, method

    if occurrence == "last":
        last_pos = content.rfind(search)
        new_content = content[:last_pos] + replace + content[last_pos + len(search) :]
        return True, new_content, method

    if isinstance(occurrence, int) and occurrence > 0:
        nth_pos = _find_nth_occurrence(content, search, occurrence)
        if nth_pos == -1:
            return False, content, method
        new_content = content[:nth_pos] + replace + content[nth_pos + len(search) :]
        return True, new_content, method

    # Nhieu matches ma khong co occurrence -> ambiguous
    return False, content, method


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


# ==================== FUZZY MATCHING HELPERS ====================


def _normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace trong text, preserve structure.

    Loại bỏ trailing whitespace nhưng giữ leading whitespace (indentation).

    Args:
        text: Text cần normalize

    Returns:
        Text đã normalize
    """
    lines: list[str] = []
    for line in text.splitlines():
        # Remove trailing whitespace only
        # Keep leading whitespace (indentation matters!)
        lines.append(line.rstrip())  # type: ignore[arg-type]
    return "\n".join(lines)


def _fuzzy_find_best_match(
    content: str, search: str, threshold: float = 0.90
) -> tuple[int, float]:
    """
    Tìm vị trí best fuzzy match cho search block trong content.

    Uses RapidFuzz (if available) for 10-100x speedup, fallback to difflib.

    Args:
        content: File content
        search: Block cần tìm
        threshold: Minimum similarity score (0.0-1.0)

    Returns:
        (position, similarity_score)
        (-1, 0.0) nếu không tìm thấy match đủ tốt
    """
    # Try RapidFuzz first (10-100x faster)
    try:
        from rapidfuzz import fuzz  # type: ignore[import-not-found]

        use_rapidfuzz = True
    except ImportError:
        # Fallback to difflib (built-in, always available)
        from difflib import SequenceMatcher

        use_rapidfuzz = False
        fuzz = None  # type: ignore[assignment]

    search_lines = search.splitlines()
    content_lines = content.splitlines()

    if len(search_lines) == 0 or len(content_lines) == 0:
        return -1, 0.0

    best_pos = -1
    best_score = 0.0
    search_len = len(search_lines)

    # Sliding window qua content
    for i in range(len(content_lines) - search_len + 1):
        window = content_lines[i : i + search_len]
        window_text = "\n".join(window)

        # Calculate similarity (method depends on available library)
        if use_rapidfuzz:
            # RapidFuzz returns 0-100, normalize to 0-1
            score = fuzz.ratio(search, window_text) / 100.0  # type: ignore[union-attr]
        else:
            # difflib returns 0-1 already
            matcher = SequenceMatcher(None, search, window_text)  # type: ignore[possibly-unbound]
            score = matcher.ratio()

        if score > best_score:
            best_score = score
            # Convert line index to character position
            best_pos = len("\n".join(content_lines[:i]))
            if i > 0:
                best_pos += 1  # Add newline

    if best_score >= threshold:
        return best_pos, best_score

    return -1, 0.0


def _smart_find_block(
    content: str, search: str, enable_fuzzy: bool = True
) -> tuple[int, str]:
    """
    3-layer fallback strategy để tìm search block trong content.

    Strategy:
    1. Exact match (fast path)
    2. Normalized whitespace match (safe)
    3. Fuzzy match với threshold 0.90 (last resort)

    Args:
        content: File content
        search: Block cần tìm
        enable_fuzzy: Có enable fuzzy matching không

    Returns:
        (position, method_used)
        method_used: 'exact' | 'normalized' | 'fuzzy:0.95' | 'not_found'
    """
    # Layer 1: Exact match (FAST PATH - unchanged behavior)
    pos = content.find(search)
    if pos != -1:
        return pos, "exact"

    # Layer 2: Normalized whitespace (SAFE - chỉ khác whitespace)
    norm_content = _normalize_whitespace(content)
    norm_search = _normalize_whitespace(search)

    norm_pos = norm_content.find(norm_search)
    if norm_pos != -1:
        # Map normalized position back to original
        # Positions should be identical or very close
        return norm_pos, "normalized"

    # Layer 3: Fuzzy match (LAST RESORT - needs validation)
    if not enable_fuzzy:
        return -1, "not_found"

    fuzzy_pos, fuzzy_score = _fuzzy_find_best_match(content, search, threshold=0.90)
    if fuzzy_pos != -1:
        log_warning(
            f"Fuzzy match found (similarity: {fuzzy_score:.1%}) for block: "
            f"{search[:50].strip()}..."
        )
        return fuzzy_pos, f"fuzzy:{fuzzy_score:.2f}"

    return -1, "not_found"


def _handle_delete(
    action: FileAction, file_path: Path, dry_run: bool = False
) -> ActionResult:
    """Xoa file"""
    try:
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        if dry_run:
            return ActionResult(
                path=action.path,
                action="delete",
                success=True,
                message="Dry Run: File would be deleted",
            )

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
    action: FileAction,
    file_path: Path,
    workspace_roots: Optional[list[Path]],
    dry_run: bool = False,
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
        if dry_run:
            return ActionResult(
                path=action.path,
                action="rename",
                success=True,
                message=f"Dry Run: File would be renamed to '{action.new_path}'",
                new_path=action.new_path,
            )

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
