"""
Preview Analyzer - Phan tich va tao diff preview cho file actions

Port tu: /home/hao/Desktop/labs/overwrite/src/services/preview-analyzer.ts
Hien thi +lines/-lines thay doi truoc khi apply.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from core.opx_parser import FileAction, ChangeBlock


@dataclass
class ChangeSummary:
    """Thong ke so dong thay doi"""

    added: int = 0
    removed: int = 0


@dataclass
class PreviewRow:
    """
    Mot row trong preview table.
    Hien thi thong tin ve file action va so dong thay doi.
    """

    path: str
    action: str  # create, modify, rewrite, delete, rename
    description: str
    changes: ChangeSummary
    new_path: Optional[str] = None
    has_error: bool = False
    error_message: Optional[str] = None
    change_blocks: List[dict] = field(default_factory=list)


@dataclass
class PreviewData:
    """Ket qua phan tich preview"""

    rows: List[PreviewRow] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def analyze_file_actions(
    file_actions: List[FileAction], workspace_root: Optional[Path] = None
) -> PreviewData:
    """
    Phan tich cac file actions va tao preview data.

    Args:
        file_actions: List FileAction tu OPX parser
        workspace_root: Optional workspace root de resolve paths

    Returns:
        PreviewData voi rows va errors
    """
    rows: List[PreviewRow] = []
    errors: List[str] = []

    for action in file_actions:
        try:
            row = _analyze_file_action(action, workspace_root)
            rows.append(row)
        except Exception as e:
            errors.append(f"Error analyzing {action.path}: {str(e)}")

    return PreviewData(rows=rows, errors=errors)


def _analyze_file_action(
    file_action: FileAction, workspace_root: Optional[Path] = None
) -> PreviewRow:
    """Phan tich mot file action"""
    try:
        changes = _calculate_change_summary(file_action, workspace_root)
        description = _generate_description(file_action)

        # Extract change blocks cho error context
        change_blocks = []
        if file_action.changes:
            for c in file_action.changes:
                change_blocks.append(
                    {
                        "description": c.description,
                        "search": c.search,
                        "content": c.content,
                    }
                )

        return PreviewRow(
            path=file_action.path,
            action=file_action.action,
            description=description,
            changes=changes,
            new_path=file_action.new_path,
            has_error=False,
            error_message=None,
            change_blocks=change_blocks,
        )
    except Exception as e:
        return PreviewRow(
            path=file_action.path,
            action=file_action.action,
            description=f"Error: {str(e)}",
            changes=ChangeSummary(0, 0),
            new_path=file_action.new_path,
            has_error=True,
            error_message=str(e),
            change_blocks=[],
        )


def _calculate_change_summary(
    file_action: FileAction, workspace_root: Optional[Path] = None
) -> ChangeSummary:
    """Tinh so dong added/removed cho moi action type"""
    action = file_action.action

    if action == "create":
        return _calculate_create_changes(file_action)
    elif action == "rewrite":
        return _calculate_rewrite_changes(file_action, workspace_root)
    elif action == "modify":
        return _calculate_modify_changes(file_action)
    elif action == "delete":
        return _calculate_delete_changes(file_action, workspace_root)
    elif action == "rename":
        return ChangeSummary(0, 0)
    else:
        return ChangeSummary(0, 0)


def _calculate_create_changes(file_action: FileAction) -> ChangeSummary:
    """Tinh changes cho create action"""
    added = 0
    if file_action.changes:
        for change in file_action.changes:
            added += _count_lines(change.content)
    return ChangeSummary(added=added, removed=0)


def _calculate_rewrite_changes(
    file_action: FileAction, workspace_root: Optional[Path] = None
) -> ChangeSummary:
    """Tinh changes cho rewrite action"""
    added = 0
    removed = 0

    # Tinh so dong moi
    if file_action.changes:
        for change in file_action.changes:
            added += _count_lines(change.content)

    # Tinh so dong cu (neu file ton tai)
    file_path = _resolve_path(file_action.path, workspace_root)
    if file_path and file_path.exists():
        try:
            content = file_path.read_text(encoding="utf-8")
            removed = _count_lines(content)
        except Exception:
            pass

    return ChangeSummary(added=added, removed=removed)


def _calculate_modify_changes(file_action: FileAction) -> ChangeSummary:
    """Tinh changes cho modify action (find/replace)"""
    added = 0
    removed = 0

    if file_action.changes:
        for change in file_action.changes:
            # Search lines se bi removed
            search_lines = _count_lines(change.search) if change.search else 1
            # Content lines se duoc added
            content_lines = _count_lines(change.content)

            removed += search_lines
            added += content_lines

    return ChangeSummary(added=added, removed=removed)


def _calculate_delete_changes(
    file_action: FileAction, workspace_root: Optional[Path] = None
) -> ChangeSummary:
    """Tinh changes cho delete action"""
    file_path = _resolve_path(file_action.path, workspace_root)

    if file_path and file_path.exists():
        try:
            content = file_path.read_text(encoding="utf-8")
            removed = _count_lines(content)
            return ChangeSummary(added=0, removed=removed)
        except Exception:
            pass

    # File khong ton tai, estimate 50 lines
    return ChangeSummary(added=0, removed=50)


def _generate_description(file_action: FileAction) -> str:
    """Tao description cho file action"""
    action = file_action.action

    if action == "create":
        if file_action.changes and file_action.changes[0].description:
            return file_action.changes[0].description
        return "Create file"

    elif action == "rewrite":
        if file_action.changes and file_action.changes[0].description:
            return file_action.changes[0].description
        return "Rewrite file"

    elif action == "delete":
        return "Delete file"

    elif action == "rename":
        return f"Rename to {file_action.new_path or 'new location'}"

    elif action == "modify":
        if not file_action.changes or len(file_action.changes) == 0:
            return "Modify file"

        if len(file_action.changes) == 1:
            return file_action.changes[0].description

        if len(file_action.changes) <= 3:
            descriptions = [c.description for c in file_action.changes]
            return " | ".join(descriptions)

        # Neu co nhieu changes, chi hien thi 2 dau tien
        first_two = [c.description for c in file_action.changes[:2]]
        remaining = len(file_action.changes) - 2
        return f"{' | '.join(first_two)} (+{remaining} more)"

    return "Unknown action"


def _count_lines(text: Optional[str]) -> int:
    """Dem so dong trong text"""
    if not text:
        return 0
    return len(text.split("\n"))


def _resolve_path(path: str, workspace_root: Optional[Path] = None) -> Optional[Path]:
    """Resolve path tuong doi hoac tuyet doi"""
    p = Path(path)

    # Neu la absolute path
    if p.is_absolute():
        return p

    # Neu co workspace root, resolve relative
    if workspace_root:
        return workspace_root / path

    return None


def format_change_summary(changes: ChangeSummary) -> str:
    """
    Format change summary thanh string de hien thi.
    Vi du: "+15 / -8" hoac "+0 / -50"
    """
    return f"+{changes.added} / -{changes.removed}"


def get_change_color(changes: ChangeSummary) -> str:
    """
    Tra ve color code dua tren net change.
    - Them nhieu hon bo: Green
    - Bo nhieu hon them: Red
    - Bang nhau: Blue
    """
    from core.theme import ThemeColors

    if changes.added > changes.removed:
        return ThemeColors.SUCCESS  # Green - net add
    elif changes.removed > changes.added:
        return ThemeColors.ERROR  # Red - net remove
    else:
        return ThemeColors.PRIMARY  # Blue - neutral
