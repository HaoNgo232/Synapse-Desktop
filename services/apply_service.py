"""
Apply Service — Business logic for OPX apply operations.

Extracted from views/apply_view_qt.py to separate concerns.
View layer should only handle UI; this module handles:
- Converting ActionResult to ApplyRowResult (with cascade detection)
- Saving continuous memory blocks to .synapse/memory.xml
"""

import re
import logging
import threading
from pathlib import Path
from typing import List

from core.file_actions import ActionResult
from services.error_context import ApplyRowResult

logger = logging.getLogger(__name__)

# Lock for concurrent memory writes
_memory_write_lock = threading.Lock()


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
    Save a memory block to .synapse/memory.xml.

    Maintains a rolling window of the last `max_blocks` memory blocks.
    Thread-safe via module-level lock.

    Args:
        workspace: Workspace root path
        memory_block: New memory block content (stripped)
        max_blocks: Maximum number of blocks to keep (default 5)
    """
    new_block = memory_block.strip()
    if not new_block:
        return

    with _memory_write_lock:
        try:
            synapse_dir = workspace / ".synapse"
            synapse_dir.mkdir(exist_ok=True, parents=True)
            memory_file = synapse_dir / "memory.xml"

            blocks: List[str] = []
            if memory_file.exists():
                try:
                    content = memory_file.read_text(encoding="utf-8")
                    blocks = re.findall(
                        r"<synapse_memory>\s*(.*?)\s*</synapse_memory>",
                        content,
                        re.IGNORECASE | re.DOTALL,
                    )
                    # Filter out empty/too-short blocks (regex artifacts)
                    blocks = [
                        b.strip()
                        for b in blocks
                        if b and b.strip() and len(b.strip()) > 10
                    ]
                    # Fallback: if parsing failed but file has content
                    if not blocks and content.strip():
                        logger.warning(
                            "Could not parse existing synapse memory blocks, "
                            "preserving truncated raw content."
                        )
                        blocks = [content.strip()[:2000]]
                except Exception as parse_e:
                    logger.warning(
                        "Failed to parse existing synapse memory: %s", parse_e
                    )
                    blocks = []

            blocks.append(new_block)
            blocks = blocks[-max_blocks:]

            formatted_blocks = [
                f"<synapse_memory>\n{b.strip()}\n</synapse_memory>" for b in blocks
            ]

            # Atomic write using temp file
            import os

            tmp_file = memory_file.with_suffix(".tmp")
            tmp_file.write_text("\n\n".join(formatted_blocks) + "\n", encoding="utf-8")
            os.replace(str(tmp_file), str(memory_file))
        except Exception as e:
            logger.error("Failed to save synapse memory: %s", e)
            try:
                tmp_file = memory_file.with_suffix(".tmp")
                if tmp_file.exists():
                    tmp_file.unlink()
            except OSError:
                pass
