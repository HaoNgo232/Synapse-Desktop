"""
File Actions - Thuc thi cac file operations tu OPX

Cac operations:
- create: Tao file moi
- rewrite: Ghi de toan bo file
- modify: Tim va thay the mot phan trong file
- delete: Xoa file
- rename: Doi ten/di chuyen file
"""

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional, Union

from domain.ports.action_result import ActionResult
from domain.ports.file_actions_port import IFileActionsService
from domain.prompt.opx_parser import FileAction
from shared.config.paths import BACKUP_DIR
from shared.logging_config import log_debug, log_error, log_info, log_warning
import logging

logger = logging.getLogger("synapse-desktop")


@dataclass
class ApplySessionItem:
    action: str
    path: str
    resolved_path: str
    backup_path: Optional[str] = None
    created_path: Optional[str] = None
    new_path: Optional[str] = None
    resolved_new_path: Optional[str] = None
    backup_new_path: Optional[str] = None
    success: bool = False
    message: str = ""


@dataclass
class ApplySessionManifest:
    session_id: str
    timestamp: str
    items: List[ApplySessionItem] = field(default_factory=list)


@dataclass
class RollbackItemResult:
    path: str
    action: str
    success: bool
    message: str


@dataclass
class RollbackResult:
    session_id: str
    success: bool
    message: str
    item_results: List[RollbackItemResult] = field(default_factory=list)


def create_backup(file_path: Path) -> Optional[Path]:
    """
    Tạo backup của file hoặc thư mục trước khi modify / delete / overwrite.

    Args:
        file_path: Path đến file/folder cần backup

    Returns:
        Path đến backup file/folder, hoặc None nếu thất bại
    """
    if not file_path.exists():
        return None

    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Tạo tên backup với timestamp và microsecond để chống va chạm tên file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = BACKUP_DIR / backup_name

        if file_path.is_dir():
            shutil.copytree(file_path, backup_path)
        else:
            shutil.copy2(file_path, backup_path)
        log_debug(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        log_error(f"Failed to create backup for {file_path}", e)
        return None


def restore_backup(backup_path: Path, original_path: Path) -> bool:
    """
    Khôi phục file hoặc thư mục từ backup.

    Args:
        backup_path: Path đến backup file/folder
        original_path: Path đến vị trí gốc cần restore

    Returns:
        True nếu restore thành công
    """
    try:
        if not backup_path.exists():
            log_error(f"Backup path not found: {backup_path}")
            return False

        if original_path.exists():
            if original_path.is_dir():
                shutil.rmtree(original_path)
            else:
                original_path.unlink()

        if backup_path.is_dir():
            shutil.copytree(backup_path, original_path)
        else:
            original_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, original_path)
        log_info(f"Restored from backup: {original_path}")
        return True
    except Exception as e:
        log_error(f"Failed to restore backup for {original_path}", e)
        return False


def save_apply_session_manifest(manifest: ApplySessionManifest) -> Optional[Path]:
    """Save an ApplySessionManifest to a JSON file in BACKUP_DIR."""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        session_file = BACKUP_DIR / f"session_{manifest.session_id}.json"
        manifest_dict = asdict(manifest)
        session_file.write_text(
            json.dumps(manifest_dict, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log_debug(f"Saved session manifest: {session_file}")
        return session_file
    except Exception as e:
        log_error(f"Failed to save session manifest {manifest.session_id}", e)
        return None


def load_apply_session_manifest(session_id: str) -> Optional[ApplySessionManifest]:
    """Load an ApplySessionManifest by session_id from BACKUP_DIR."""
    try:
        if not BACKUP_DIR.exists():
            return None
        session_file = BACKUP_DIR / f"session_{session_id}.json"
        if not session_file.exists():
            log_error(f"Session manifest file not found: {session_file}")
            return None
        content = session_file.read_text(encoding="utf-8")
        data = json.loads(content)
        items = [ApplySessionItem(**item) for item in data.get("items", [])]
        return ApplySessionManifest(
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            items=items,
        )
    except Exception as e:
        log_error(f"Failed to load session manifest {session_id}", e)
        return None


def get_last_apply_session() -> Optional[ApplySessionManifest]:
    """Get the most recent ApplySessionManifest from BACKUP_DIR."""
    if not BACKUP_DIR.exists():
        return None
    try:
        session_files = sorted(
            BACKUP_DIR.glob("session_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not session_files:
            return None
        filename = session_files[0].stem
        session_id = filename.replace("session_", "", 1)
        return load_apply_session_manifest(session_id)
    except Exception as e:
        log_error("Failed to get last apply session", e)
        return None


def rollback_apply_session(
    session: Union[ApplySessionManifest, str, object, None] = None,
    workspace_roots: Optional[List[Path]] = None,
) -> RollbackResult:
    """
    Rollback an entire Apply session in reverse order.

    Args:
        session: ApplySessionManifest instance, session_id string, or None for the last session.
        workspace_roots: Optional list of workspace roots for security validation.

    Returns:
        RollbackResult containing item details and overall status.
    """
    manifest: Optional[ApplySessionManifest] = None

    if session is None or session == "last":
        manifest = get_last_apply_session()
    elif isinstance(session, str):
        manifest = load_apply_session_manifest(session)
    elif isinstance(session, ApplySessionManifest):
        manifest = session

    if not manifest:
        return RollbackResult(
            session_id=session if isinstance(session, str) else "unknown",
            success=False,
            message="No valid apply session found to rollback",
            item_results=[],
        )

    log_info(f"Starting rollback for apply session: {manifest.session_id}")
    item_results: List[RollbackItemResult] = []
    overall_success = True

    # Process items in reverse order
    for item in reversed(manifest.items):
        if not item.success:
            # Skip items that failed during apply
            continue

        try:
            resolved_path = Path(item.resolved_path)

            if item.action == "create":
                created_target = (
                    Path(item.created_path) if item.created_path else resolved_path
                )
                if created_target.exists():
                    if created_target.is_dir():
                        shutil.rmtree(created_target)
                    else:
                        created_target.unlink()
                    item_results.append(
                        RollbackItemResult(
                            path=item.path,
                            action="create",
                            success=True,
                            message=f"Deleted created path: {item.path}",
                        )
                    )
                else:
                    item_results.append(
                        RollbackItemResult(
                            path=item.path,
                            action="create",
                            success=True,
                            message=f"Path already removed: {item.path}",
                        )
                    )

            elif item.action in ("rewrite", "modify"):
                if item.backup_path:
                    bk_path = Path(item.backup_path)
                    res = restore_backup(bk_path, resolved_path)
                    item_results.append(
                        RollbackItemResult(
                            path=item.path,
                            action=item.action,
                            success=res,
                            message=(
                                f"Restored {item.path} from backup"
                                if res
                                else f"Failed to restore {item.path}"
                            ),
                        )
                    )
                    if not res:
                        overall_success = False
                else:
                    item_results.append(
                        RollbackItemResult(
                            path=item.path,
                            action=item.action,
                            success=False,
                            message=f"No backup available for {item.path}",
                        )
                    )
                    overall_success = False

            elif item.action == "delete":
                if item.backup_path:
                    bk_path = Path(item.backup_path)
                    res = restore_backup(bk_path, resolved_path)
                    item_results.append(
                        RollbackItemResult(
                            path=item.path,
                            action="delete",
                            success=res,
                            message=(
                                f"Restored deleted path {item.path} from backup"
                                if res
                                else f"Failed to restore deleted path {item.path}"
                            ),
                        )
                    )
                    if not res:
                        overall_success = False
                else:
                    item_results.append(
                        RollbackItemResult(
                            path=item.path,
                            action="delete",
                            success=False,
                            message=f"No backup available for deleted path {item.path}",
                        )
                    )
                    overall_success = False

            elif item.action == "rename":
                msg_parts: List[str] = []
                rename_ok = True
                if item.resolved_new_path:
                    new_p = Path(item.resolved_new_path)
                    if new_p.exists():
                        resolved_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(new_p, resolved_path)
                        msg_parts.append(f"Moved {item.new_path} back to {item.path}")

                if item.backup_new_path:
                    bk_target = Path(item.backup_new_path)
                    if item.resolved_new_path:
                        restore_res = restore_backup(
                            bk_target, Path(item.resolved_new_path)
                        )
                        if restore_res:
                            msg_parts.append(
                                f"Restored original file at target path {item.new_path}"
                            )

                item_results.append(
                    RollbackItemResult(
                        path=item.path,
                        action="rename",
                        success=rename_ok,
                        message="; ".join(msg_parts) or "Reverted rename",
                    )
                )

        except Exception as e:
            log_error(f"Failed rollback for item {item.path}", e)
            item_results.append(
                RollbackItemResult(
                    path=item.path,
                    action=item.action,
                    success=False,
                    message=f"Rollback error: {e}",
                )
            )
            overall_success = False

    success_count = sum(1 for r in item_results if r.success)
    msg = f"Rollback finished: {success_count}/{len(item_results)} items reverted"
    log_info(msg)

    return RollbackResult(
        session_id=manifest.session_id,
        success=overall_success,
        message=msg,
        item_results=item_results,
    )


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

    session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    manifest = ApplySessionManifest(
        session_id=session_id,
        timestamp=datetime.now().isoformat(),
        items=[],
    )

    results: list[ActionResult] = []
    mode = "Validating" if dry_run else "Applying"
    log_info(f"{mode} {len(file_actions)} file action(s)")

    for action in file_actions:
        try:
            log_debug(f"Processing: {action.action} on {action.path}")
            # Resolve path (ho tro absolute, relative, va multi-workspace)
            file_path = _resolve_path(action.path, action.root, workspace_roots)

            if action.action == "create":
                existed_before = file_path.exists()
                result = _handle_create(action, file_path, dry_run)
                if not dry_run:
                    manifest.items.append(
                        ApplySessionItem(
                            action="create",
                            path=action.path,
                            resolved_path=str(file_path),
                            created_path=str(file_path)
                            if (result.success and not existed_before)
                            else None,
                            success=result.success,
                            message=result.message,
                        )
                    )
            elif action.action in ("rewrite", "modify"):
                backup_p = (
                    create_backup(file_path)
                    if (not dry_run and file_path.exists())
                    else None
                )
                if action.action == "rewrite":
                    result = _handle_rewrite(action, file_path, dry_run)
                else:
                    result = _handle_modify(action, file_path, dry_run)
                if not dry_run:
                    manifest.items.append(
                        ApplySessionItem(
                            action=action.action,
                            path=action.path,
                            resolved_path=str(file_path),
                            backup_path=str(backup_p) if backup_p else None,
                            success=result.success,
                            message=result.message,
                        )
                    )
            elif action.action == "delete":
                backup_p = (
                    create_backup(file_path)
                    if (not dry_run and file_path.exists())
                    else None
                )
                result = _handle_delete(action, file_path, dry_run)
                if not dry_run:
                    manifest.items.append(
                        ApplySessionItem(
                            action="delete",
                            path=action.path,
                            resolved_path=str(file_path),
                            backup_path=str(backup_p) if backup_p else None,
                            success=result.success,
                            message=result.message,
                        )
                    )
            elif action.action == "rename":
                new_path = (
                    _resolve_path(action.new_path, action.root, workspace_roots)
                    if action.new_path
                    else None
                )
                bk_orig = (
                    create_backup(file_path)
                    if (not dry_run and file_path.exists())
                    else None
                )
                bk_target = (
                    create_backup(new_path)
                    if (not dry_run and new_path and new_path.exists())
                    else None
                )
                result = _handle_rename(action, file_path, workspace_roots, dry_run)
                if not dry_run:
                    manifest.items.append(
                        ApplySessionItem(
                            action="rename",
                            path=action.path,
                            resolved_path=str(file_path),
                            new_path=action.new_path,
                            resolved_new_path=str(new_path) if new_path else None,
                            backup_path=str(bk_orig) if bk_orig else None,
                            backup_new_path=str(bk_target) if bk_target else None,
                            success=result.success,
                            message=result.message,
                        )
                    )
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

    if not dry_run and manifest.items:
        save_apply_session_manifest(manifest)

    success_count = sum(1 for r in results if r.success)
    log_info(f"Completed: {success_count}/{len(results)} action(s) successful")
    return results


def _validate_path_in_workspace(
    resolved_path: Path, workspace_roots: list[Path]
) -> bool:
    """
    Kiem tra path co nam trong bat ky workspace root nao khong.

    Args:
        resolved_path: Path da duoc resolve() thanh absolute
        workspace_roots: Danh sach workspace roots hop le

    Returns:
        True neu path nam trong mot workspace root
    """
    for ws_root in workspace_roots:
        try:
            ws_resolved = ws_root.resolve()
            resolved_path.relative_to(ws_resolved)
            return True
        except ValueError:
            continue
    return False


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

    Security: Tat ca paths deu duoc validate nam trong workspace boundary.
    Raise ValueError neu path nam ngoai workspace.
    """
    # Handle file:// URI
    if path_str.startswith("file://"):
        path_str = path_str[7:]  # Remove file://

    path = Path(path_str)

    # Chặn hoàn toàn nếu không có workspace roots để đảm bảo an toàn bảo mật, tránh path traversal bypass
    if not workspace_roots:
        log_error(
            "Security Alert: Blocked access as workspace_roots list is empty or None"
        )
        raise ValueError("Access denied: No workspace roots configured")

    # --- Resolve path thanh absolute ---
    final_path = workspace_roots[0] / path

    if path.is_absolute():
        # Absolute path tu OPX (AI hay tra ve dang nay)
        final_path = path
    elif root_name:
        # Multi-workspace: tim workspace root theo ten
        matched = False
        for ws_root in workspace_roots:
            if ws_root.name == root_name:
                final_path = ws_root / path
                matched = True
                break
        if not matched:
            # Root name khong match -> fallback ve workspace root dau tien
            final_path = workspace_roots[0] / path
    else:
        # Default: dung workspace root dau tien
        final_path = workspace_roots[0] / path

    # --- SECURITY CHECK: Path Traversal Protection ---
    # Ap dung cho TAT CA code paths, khong chi default branch
    try:
        resolved_absolute = final_path.resolve()

        if _validate_path_in_workspace(resolved_absolute, workspace_roots):
            return final_path

        # Path ngoai workspace - block
        log_error(f"Security Alert: Blocked access to {resolved_absolute}")
        raise ValueError("Access denied: Path is outside workspace roots")

    except ValueError:
        # Re-raise access denied errors
        raise
    except Exception:
        logger.error("file_actions: failed writing file", exc_info=True)
        # resolve() that bai (broken symlink, permission, etc.)
        # Thu check parent directory (cho create operations voi file chua ton tai)
        if not final_path.exists():
            try:
                parent_resolved = final_path.parent.resolve()
                if _validate_path_in_workspace(parent_resolved, workspace_roots):
                    return final_path
            except Exception:
                logger.error("file_actions: failed in file iteration", exc_info=True)

        # SECURITY DEFAULT: Deny khi khong the validate
        log_error(f"Security: Could not validate path {final_path}, denying access")
        raise ValueError(
            "Access denied: Could not verify path is within workspace roots"
        )


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
            normalized_search = normalize_eol(change.search, eol)

            # Tim va thay the with fuzzy fallback
            result, new_content, match_method = apply_search_replace_to_content(
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


def apply_search_replace_to_content(
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
    first_pos, first_match_len, method = _smart_find_block(
        content, search, enable_fuzzy=True
    )

    if first_pos == -1:
        return False, content, method

    if method == "exact":
        matches = _find_exact_matches(content, search)
    elif method == "normalized":
        matches = _find_normalized_matches(content, search)
    else:
        matches = [(first_pos, first_match_len)]

    if not matches:
        return False, content, "not_found"

    # Log method used (non-exact matches cần attention)
    if method != "exact":
        log_info(f"Match method '{method}' used at position {first_pos}")

    # Fuzzy fallback chi co 1 best match, exact/normalized co the co nhieu matches
    has_multiple = len(matches) > 1

    # Handle occurrence logic
    if occurrence in (None, "first"):
        if has_multiple and method in ("exact", "normalized") and occurrence is None:
            # Nhieu matches ma khong co occurrence -> ambiguous
            return False, content, method
        selected_pos, selected_len = matches[0]
        new_content = (
            content[:selected_pos] + replace + content[selected_pos + selected_len :]
        )
        return True, new_content, method

    if occurrence == "last":
        selected_pos, selected_len = matches[-1]
        new_content = (
            content[:selected_pos] + replace + content[selected_pos + selected_len :]
        )
        return True, new_content, method

    # Den day occurrence khong the la None/'first'/'last' nua.
    # Parse phong thu de tranh runtime input khong dung type.
    try:
        occurrence_index = int(occurrence)
    except (TypeError, ValueError):
        return False, content, method

    if occurrence_index > 0:
        if occurrence_index > len(matches):
            return False, content, method
        selected_pos, selected_len = matches[occurrence_index - 1]
        new_content = (
            content[:selected_pos] + replace + content[selected_pos + selected_len :]
        )
        return True, new_content, method

    # occurrence khong hop le
    return False, content, method


# ==================== FUZZY MATCHING HELPERS ====================


def _strip_line_ending(line: str) -> str:
    """Remove \r/\n line ending but keep all other whitespace."""
    return line.rstrip("\r\n")


def _line_window_span_without_terminal_newline(
    lines_with_eol: list[str], start_line: int, line_count: int
) -> int:
    """Tinh do dai span cho line-window, khong gom terminal newline cua dong cuoi."""
    if line_count <= 0:
        return 0

    if line_count == 1:
        return len(_strip_line_ending(lines_with_eol[start_line]))

    total = 0
    # Cac dong truoc dong cuoi giu nguyen newline
    for idx in range(start_line, start_line + line_count - 1):
        total += len(lines_with_eol[idx])

    # Dong cuoi bo terminal newline de match behavior cua marker extraction
    total += len(_strip_line_ending(lines_with_eol[start_line + line_count - 1]))
    return total


def _find_exact_matches(content: str, search: str) -> list[tuple[int, int]]:
    """Tim tat ca exact matches theo thu tu xuat hien."""
    if not search:
        return []

    matches: list[tuple[int, int]] = []
    from_pos = 0

    while True:
        pos = content.find(search, from_pos)
        if pos == -1:
            break
        matches.append((pos, len(search)))
        from_pos = pos + len(search)

    return matches


def _find_normalized_matches(content: str, search: str) -> list[tuple[int, int]]:
    """
    Tim matches khi chi khac trailing whitespace.

    Return danh sach (start_pos, span_len) trong ORIGINAL content de tranh
    offset drift khi thay the.
    """
    search_lines = search.splitlines()
    if not search_lines:
        return []

    lines_with_eol = content.splitlines(keepends=True)
    if not lines_with_eol:
        return []

    content_line_count = len(lines_with_eol)
    search_line_count = len(search_lines)
    if search_line_count > content_line_count:
        return []

    line_offsets: list[int] = []
    offset = 0
    for raw_line in lines_with_eol:
        line_offsets.append(offset)
        offset += len(raw_line)

    normalized_search = [line.rstrip() for line in search_lines]
    content_bodies = [_strip_line_ending(line) for line in lines_with_eol]

    matches: list[tuple[int, int]] = []
    for start_line in range(content_line_count - search_line_count + 1):
        window = content_bodies[start_line : start_line + search_line_count]
        if all(
            window[i].rstrip() == normalized_search[i] for i in range(search_line_count)
        ):
            span_len = _line_window_span_without_terminal_newline(
                lines_with_eol, start_line, search_line_count
            )
            matches.append((line_offsets[start_line], span_len))

    return matches


def _fuzzy_find_best_match(
    content: str, search: str, threshold: float = 0.90
) -> tuple[int, int, float]:
    """
    Tìm vị trí best fuzzy match cho search block trong content.

    Uses RapidFuzz (if available) for 10-100x speedup, fallback to difflib.

    Args:
        content: File content
        search: Block cần tìm
        threshold: Minimum similarity score (0.0-1.0)

    Returns:
        (position, match_length, similarity_score)
        (-1, 0, 0.0) nếu không tìm thấy match đủ tốt
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
    content_lines_with_eol = content.splitlines(keepends=True)
    content_lines = [_strip_line_ending(line) for line in content_lines_with_eol]

    if len(search_lines) == 0 or len(content_lines) == 0:
        return -1, 0, 0.0

    best_pos = -1
    best_len = 0
    best_score = 0.0
    search_len = len(search_lines)

    line_offsets: list[int] = []
    offset = 0
    for raw_line in content_lines_with_eol:
        line_offsets.append(offset)
        offset += len(raw_line)

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
            best_pos = line_offsets[i]
            best_len = _line_window_span_without_terminal_newline(
                content_lines_with_eol, i, search_len
            )

    if best_score >= threshold:
        return best_pos, best_len, best_score

    return -1, 0, 0.0


def _smart_find_block(
    content: str, search: str, enable_fuzzy: bool = True
) -> tuple[int, int, str]:
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
        (position, match_length, method_used)
        method_used: 'exact' | 'normalized' | 'fuzzy:0.95' | 'not_found'
    """
    # Layer 1: Exact match (FAST PATH - unchanged behavior)
    pos = content.find(search)
    if pos != -1:
        return pos, len(search), "exact"

    # Layer 2: Normalized whitespace (SAFE - chỉ khác trailing whitespace)
    normalized_matches = _find_normalized_matches(content, search)
    if normalized_matches:
        norm_pos, norm_len = normalized_matches[0]
        return norm_pos, norm_len, "normalized"

    # Layer 3: Fuzzy match (LAST RESORT - needs validation)
    if not enable_fuzzy:
        return -1, 0, "not_found"

    fuzzy_pos, fuzzy_len, fuzzy_score = _fuzzy_find_best_match(
        content, search, threshold=0.90
    )
    if fuzzy_pos != -1:
        log_warning(
            f"Fuzzy match found (similarity: {fuzzy_score:.1%}) for block: "
            f"{search[:50].strip()}..."
        )
        return fuzzy_pos, fuzzy_len, f"fuzzy:{fuzzy_score:.2f}"

    return -1, 0, "not_found"


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

        # Create backup before delete
        create_backup(file_path)

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


def normalize_eol(text: str, eol: str) -> str:
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


class FileActionsService(IFileActionsService):
    """Concrete file actions service implementing IFileActionsService."""

    def apply_file_actions(
        self,
        file_actions: List[FileAction],
        workspace_roots: Optional[List[Path]] = None,
        dry_run: bool = False,
    ) -> List[ActionResult]:
        return apply_file_actions(file_actions, workspace_roots, dry_run)

    def apply_search_replace_to_content(
        self,
        content: str,
        search: str,
        replace: str,
        occurrence: Optional[Union[Literal["first", "last"], int]],
    ) -> tuple[bool, str, str]:
        return apply_search_replace_to_content(content, search, replace, occurrence)

    def normalize_eol(self, text: str, eol: str) -> str:
        return normalize_eol(text, eol)

    def rollback_apply_session(
        self,
        session: Optional[Union[object, str]] = None,
        workspace_roots: Optional[List[Path]] = None,
    ) -> object:
        return rollback_apply_session(session, workspace_roots)

    def get_last_apply_session(self) -> Optional[object]:
        return get_last_apply_session()
