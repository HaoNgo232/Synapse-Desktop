"""
Apply Service — Business logic for OPX apply operations.

Extracted from views/apply_view_qt.py to separate concerns.
View layer should only handle UI; this module handles:
- Converting ActionResult to ApplyRowResult (with cascade detection)
- Saving continuous memory blocks to unified .synapse/memory_v2.json
"""

import logging
from pathlib import Path
from typing import List

from infrastructure.filesystem.file_actions import ActionResult
from application.services.error_context import ApplyRowResult

logger = logging.getLogger(__name__)


def convert_to_row_results(
    results: List[ActionResult],
    file_actions: list,
) -> List[ApplyRowResult]:
    """
    Convert List[ActionResult] to List[ApplyRowResult] with cascade detection.

    Cascade failure: when a file was successfully modified by an earlier
    operation, subsequent operations on the same file may fail because
    the search pattern no longer matches the modified content.

    Args:
        results: Raw results from apply_file_actions()
        file_actions: Original parsed file actions

    Returns:
        List of ApplyRowResult with cascade metadata
    """
    row_results: List[ApplyRowResult] = []
    modified_files: set = set()

    for i, result in enumerate(results):
        is_cascade = not result.success and result.path in modified_files
        row_results.append(
            ApplyRowResult(
                row_index=i,
                path=result.path,
                action=result.action,
                success=result.success,
                message=result.message,
                is_cascade_failure=is_cascade,
            )
        )
        if result.success:
            modified_files.add(result.path)

    return row_results


def save_memory_block(
    workspace: Path,
    memory_block: str,
    max_blocks: int = 5,
) -> None:
    """
    Save a memory block to unified .synapse/memory_v2.json.

    Uses the structured JSON memory store (action layer) instead of the
    legacy XML format. Maintains backward compatibility for callers.

    Args:
        workspace: Workspace root path
        memory_block: New memory block content (stripped)
        max_blocks: Maximum number of blocks to keep (default 5)
    """
    new_block = memory_block.strip()
    if not new_block:
        return

    try:
        from domain.memory.memory_service import add_memory

        add_memory(
            workspace_root=workspace,
            layer="action",
            content=new_block,
            workflow="apply",
            tags=["opx_memory"],
            max_entries=max_blocks,
        )
    except Exception as e:
        logger.error("Failed to save synapse memory: %s", e)
