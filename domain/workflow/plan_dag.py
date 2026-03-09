"""
Plan DAG - Machine-readable task graph cho agent coordination.

Tao structured output:
- nodes: decision, change, test, review
- edges: implements, must_verify, depends_on, blocks

Planner tao graph -> coder claim node -> reviewer check coverage.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

NodeType = Literal["decision", "change", "test", "review", "config"]
EdgeKind = Literal["implements", "must_verify", "depends_on", "blocks"]


@dataclass
class PlanNode:
    """Mot node trong plan DAG."""

    id: str
    type: NodeType
    title: str
    file: str = ""
    description: str = ""
    status: str = "pending"  # pending, in_progress, completed, skipped

    def to_dict(self) -> dict:
        d: Dict[str, str] = {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "status": self.status,
        }
        if self.file:
            d["file"] = self.file
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PlanNode":
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "change"),
            title=data.get("title", ""),
            file=data.get("file", ""),
            description=data.get("description", ""),
            status=data.get("status", "pending"),
        )


@dataclass
class PlanEdge:
    """Mot edge trong plan DAG."""

    source: str  # from node id
    target: str  # to node id
    kind: EdgeKind

    def to_dict(self) -> dict:
        return {
            "from": self.source,
            "to": self.target,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanEdge":
        return cls(
            source=data.get("from", ""),
            target=data.get("to", ""),
            kind=data.get("kind", "depends_on"),
        )


@dataclass
class PlanDAG:
    """Full plan DAG voi nodes va edges."""

    task: str = ""
    nodes: List[PlanNode] = field(default_factory=list)
    edges: List[PlanEdge] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanDAG":
        nodes = [PlanNode.from_dict(n) for n in data.get("nodes", [])]
        edges = [PlanEdge.from_dict(e) for e in data.get("edges", [])]
        return cls(
            task=data.get("task", ""),
            nodes=nodes,
            edges=edges,
        )

    def add_node(self, node: PlanNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: PlanEdge) -> None:
        self.edges.append(edge)

    def update_node_status(self, node_id: str, status: str) -> bool:
        for node in self.nodes:
            if node.id == node_id:
                node.status = status
                return True
        return False

    def get_pending_nodes(self) -> List[PlanNode]:
        return [n for n in self.nodes if n.status == "pending"]

    def get_node_dependencies(self, node_id: str) -> List[str]:
        """Get IDs of nodes that must complete before this node."""
        return [e.source for e in self.edges if e.target == node_id]

    def get_ready_nodes(self) -> List[PlanNode]:
        """Get nodes whose dependencies are all completed."""
        completed = {n.id for n in self.nodes if n.status == "completed"}
        ready = []
        for node in self.nodes:
            if node.status != "pending":
                continue
            deps = self.get_node_dependencies(node.id)
            if all(d in completed for d in deps):
                ready.append(node)
        return ready

    def format_summary(self) -> str:
        """Format DAG as human-readable summary."""
        lines = [
            "Plan DAG Summary",
            f"{'=' * 40}",
            f"Task: {self.task}",
            f"Nodes: {len(self.nodes)} | Edges: {len(self.edges)}",
            "",
        ]

        status_icons = {
            "pending": "⬜",
            "in_progress": "🔄",
            "completed": "✅",
            "skipped": "⏭️",
        }

        for node in self.nodes:
            icon = status_icons.get(node.status, "⬜")
            file_info = f" ({node.file})" if node.file else ""
            lines.append(
                f"  {icon} [{node.type.upper()}] {node.id}: {node.title}{file_info}"
            )

        if self.edges:
            lines.append("")
            lines.append("Dependencies:")
            for edge in self.edges:
                lines.append(f"  {edge.source} --[{edge.kind}]--> {edge.target}")

        return "\n".join(lines)


PLAN_DAG_FILE = "plan_dag.json"


def load_plan_dag(workspace_root: Path) -> Optional[PlanDAG]:
    """Load plan DAG from .synapse/plan_dag.json."""
    dag_file = workspace_root / ".synapse" / PLAN_DAG_FILE
    if not dag_file.exists():
        return None
    try:
        content = dag_file.read_text(encoding="utf-8")
        data = json.loads(content)
        return PlanDAG.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to load plan DAG: %s", e)
        return None


def save_plan_dag(workspace_root: Path, dag: PlanDAG) -> None:
    """Save plan DAG to .synapse/plan_dag.json."""
    import fcntl

    synapse_dir = workspace_root / ".synapse"
    synapse_dir.mkdir(parents=True, exist_ok=True)
    dag_file = synapse_dir / PLAN_DAG_FILE

    with open(dag_file, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            f.truncate()
            json.dump(dag.to_dict(), f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
