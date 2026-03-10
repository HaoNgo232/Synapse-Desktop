"""
Stateful Artifact Formatter - Gắn provenance/memory/contract vào workflow artifacts.

Workflow outputs trở thành reusable stateful artifacts với metadata ổn định.
"""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ArtifactMetadata:
    """Metadata cho workflow artifact."""

    workflow_name: str
    task_description: str
    selection_summary: Optional[Dict[str, Any]] = None
    memory_summary: Optional[Dict[str, Any]] = None
    contract_summary: Optional[Dict[str, Any]] = None
    risk_summary: Optional[Dict[str, Any]] = None


def build_artifact_metadata(
    workspace_root: Path,
    workflow_name: str,
    task_description: str,
) -> ArtifactMetadata:
    """Build artifact metadata từ workspace state.

    Args:
        workspace_root: Workspace root
        workflow_name: Tên workflow (rp_build, rp_review, etc.)
        task_description: Task description

    Returns:
        ArtifactMetadata với tất cả state summaries
    """
    metadata = ArtifactMetadata(
        workflow_name=workflow_name,
        task_description=task_description,
    )

    # Selection summary
    try:
        from domain.selection.selection_reader import read_selection_state

        selection_file = workspace_root / ".synapse" / "selection.json"
        state = read_selection_state(selection_file)
        metadata.selection_summary = {
            "paths_count": len(state.paths),
            "paths": state.paths[:10],  # First 10
            "provenance_count": len(state.provenance),
        }
    except Exception as e:
        logger.debug("Failed to build selection summary: %s", e)

    # Memory summary
    try:
        from domain.memory.memory_service import load_memory_store

        store = load_memory_store(workspace_root)
        metadata.memory_summary = {
            "total_entries": len(store.entries),
            "by_layer": {
                "constraint": len(store.get_by_layer("constraint")),
                "decision": len(store.get_by_layer("decision")),
                "action": len(store.get_by_layer("action")),
            },
        }
    except Exception as e:
        logger.debug("Failed to build memory summary: %s", e)

    # Contract summary
    try:
        from domain.contracts.contract_pack import ContractPack

        contract_file = workspace_root / ".synapse" / "contract_pack.json"
        if contract_file.exists():
            data = json.loads(contract_file.read_text(encoding="utf-8"))
            pack = ContractPack.from_dict(data)
            metadata.contract_summary = {
                "conventions_count": len(pack.conventions),
                "anti_patterns_count": len(pack.anti_patterns),
                "guarded_paths_count": len(pack.guarded_paths),
            }
    except Exception as e:
        logger.debug("Failed to build contract summary: %s", e)

    return metadata


def format_artifact_with_metadata(
    artifact_content: str,
    metadata: ArtifactMetadata,
    format_type: str = "json",
) -> str:
    """Format artifact với metadata.

    Args:
        artifact_content: Main artifact content
        metadata: ArtifactMetadata
        format_type: "json" hoặc "xml"

    Returns:
        Formatted artifact string
    """
    if format_type == "json":
        return json.dumps(
            {
                "metadata": asdict(metadata),
                "content": artifact_content,
            },
            indent=2,
        )

    # XML format
    lines = [
        "<artifact>",
        "<metadata>",
        f"  <workflow>{metadata.workflow_name}</workflow>",
        f"  <task>{metadata.task_description}</task>",
    ]

    if metadata.selection_summary:
        lines.append("  <selection>")
        lines.append(
            f"    <paths_count>{metadata.selection_summary['paths_count']}</paths_count>"
        )
        lines.append("  </selection>")

    if metadata.memory_summary:
        lines.append("  <memory>")
        lines.append(
            f"    <total_entries>{metadata.memory_summary['total_entries']}</total_entries>"
        )
        lines.append("  </memory>")

    if metadata.contract_summary:
        lines.append("  <contract>")
        lines.append(
            f"    <conventions>{metadata.contract_summary['conventions_count']}</conventions>"
        )
        lines.append("  </contract>")

    lines.extend(
        [
            "</metadata>",
            "<content>",
            artifact_content,
            "</content>",
            "</artifact>",
        ]
    )

    return "\n".join(lines)
