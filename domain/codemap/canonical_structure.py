"""
Canonical Workspace Summary - Single source of truth cho workspace structure.

Module nay la ENTRY POINT duy nhat de tao workspace summary, thay vi goi truc tiep
nhieu ham rieng le (generate_file_map, generate_repo_map, build_full_tree_string...).

Tat ca cac component can workspace structure nen import tu day:
    from domain.codemap.canonical_structure import build_canonical_summary

Module nay KHONG reimplement logic - chi delegate toi cac ham da co.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from domain.prompt.context_builder_prompts import build_full_tree_string
from domain.prompt.generator import generate_file_map
from infrastructure.adapters.ast_parser import generate_repo_map
from infrastructure.filesystem.file_utils import TreeItem
from infrastructure.git.git_utils import GitDiffResult

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceSummary:
    """
    Ket qua tong hop cua workspace structure.

    Dataclass nay gom tat ca thong tin ve workspace structure trong mot object duy nhat,
    giup cac component khong can biet chi tiet ve tung ham generator rieng le.

    Attributes:
        file_tree: ASCII tree hien thi cac file/folder duoc chon (tu generate_file_map)
        repo_map: AST signatures cua cac file (tu generate_repo_map), rong neu khong yeu cau
        git_changes: Git diff summary (tu build_full_tree_string), None neu khong yeu cau
        stats: Thong ke so luong file/folder duoc chon
        format: Dinh dang da su dung - "tree", "repo_map", "full"
    """

    file_tree: str = ""
    repo_map: str = ""
    git_changes: Optional[str] = None
    stats: dict = field(default_factory=dict)
    format: str = "tree"


def build_canonical_summary(
    tree: TreeItem,
    selected_paths: set[str],
    workspace_root: Optional[Path] = None,
    include_repo_map: bool = False,
    include_git_changes: bool = False,
    git_diffs: Optional[GitDiffResult] = None,
    use_relative_paths: bool = False,
    max_repo_map_files: int = 500,
) -> WorkspaceSummary:
    """
    THE canonical entry point de tao workspace summary.

    Ham nay tong hop tat ca cac ham generator hien co thanh mot API duy nhat.
    Thay vi goi generate_file_map(), generate_repo_map(), build_full_tree_string()
    rieng le, consumer chi can goi ham nay.

    Args:
        tree: Root TreeItem cua file tree (tu file_utils.scan_directory)
        selected_paths: Tap hop cac duong dan file/folder duoc chon
        workspace_root: Thu muc goc cua workspace (de tao relative paths)
        include_repo_map: True de bao gom AST signatures (generate_repo_map)
        include_git_changes: True de bao gom git diff summary
        git_diffs: Ket qua git diff, bat buoc neu include_git_changes=True
        use_relative_paths: True de su dung relative paths thay vi absolute
        max_repo_map_files: Gioi han so file cho repo map (tranh OOM)

    Returns:
        WorkspaceSummary chua tat ca thong tin workspace structure
    """
    # Xac dinh format dua tren options
    fmt = _determine_format(include_repo_map, include_git_changes)

    # 1. Luon tao file tree (co ban nhat)
    file_tree = generate_file_map(
        tree,
        selected_paths,
        workspace_root=workspace_root,
        use_relative_paths=use_relative_paths,
    )

    # 1.5 Build is_dir_map 1 lan
    is_dir_map = _build_is_dir_map(tree)

    # 2. Tao repo map neu duoc yeu cau
    repo_map = ""
    if include_repo_map:
        source_files = _filter_file_paths(selected_paths, is_dir_map)
        if source_files:
            repo_map = generate_repo_map(
                source_files,
                workspace_root=workspace_root,
                max_files=max_repo_map_files,
            )

    # 3. Tao git changes neu duoc yeu cau
    git_changes: Optional[str] = None
    if include_git_changes:
        _, git_changes = build_full_tree_string(
            file_tree_map=file_tree,
            git_diffs=git_diffs,
            include_git=True,
        )

    # 4. Tinh stats
    stats = _compute_stats(selected_paths, is_dir_map)

    return WorkspaceSummary(
        file_tree=file_tree,
        repo_map=repo_map,
        git_changes=git_changes,
        stats=stats,
        format=fmt,
    )


def get_summary_as_text(summary: WorkspaceSummary) -> str:
    """
    Render WorkspaceSummary thanh plain text de hien thi hoac copy.

    Args:
        summary: WorkspaceSummary object can render

    Returns:
        Chuoi text da format, san sang de hien thi hoac gui toi LLM
    """
    sections: list[str] = []

    # File tree luon co mat
    if summary.file_tree:
        sections.append(f"<file_map>\n{summary.file_tree}\n</file_map>")

    # Repo map (AST signatures)
    if summary.repo_map:
        sections.append(f"<repo_map>\n{summary.repo_map}\n</repo_map>")

    # Git changes
    if summary.git_changes:
        sections.append(f"<git_changes>\n{summary.git_changes}\n</git_changes>")

    # Stats summary
    if summary.stats:
        file_count = summary.stats.get("file_count", 0)
        folder_count = summary.stats.get("folder_count", 0)
        sections.append(
            f"<summary>\nSelected: {file_count} files, {folder_count} folders\n</summary>"
        )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _determine_format(include_repo_map: bool, include_git_changes: bool) -> str:
    """Determine format label based on requested components."""
    if include_repo_map and include_git_changes:
        return "full"
    if include_repo_map:
        return "repo_map"
    return "tree"


def _build_is_dir_map(tree: TreeItem) -> dict[str, bool]:
    result: dict[str, bool] = {}

    def _walk(item: TreeItem) -> None:
        result[item.path] = item.is_dir
        for child in item.children:
            _walk(child)

    _walk(tree)
    return result


def _filter_file_paths(
    selected_paths: set[str], is_dir_map: dict[str, bool]
) -> list[str]:
    """
    Loc chi file paths (loai bo folders) tu selected_paths.

    Su dung is_dir_map de xac dinh dau la file, dau la folder.
    """
    return [p for p in sorted(selected_paths) if not is_dir_map.get(p, False)]


def _compute_stats(selected_paths: set[str], is_dir_map: dict[str, bool]) -> dict:
    """
    Tinh thong ke file/folder counts tu selected_paths.

    Returns dict voi keys: file_count, folder_count, total_selected
    """
    file_count = sum(1 for p in selected_paths if not is_dir_map.get(p, False))
    total_selected = len(selected_paths)
    folder_count = total_selected - file_count

    return {
        "file_count": file_count,
        "folder_count": folder_count,
        "total_selected": total_selected,
    }
