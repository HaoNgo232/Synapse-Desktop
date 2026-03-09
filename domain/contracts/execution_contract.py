"""
Execution Contract - Artifact duy nhat lien ket planning → coding → review → test.

Planner agent tao contract, coder agent doc va tuan thu,
reviewer agent so patch voi contract, drift detector so ket qua voi contract.

Luu tai .synapse/execution_contract.json
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

EXECUTION_CONTRACT_FILE = "execution_contract.json"


@dataclass
class ExecutionContract:
    """Single execution contract cho mot task."""

    task: str = ""
    scope_files: List[str] = field(default_factory=list)
    guarded_paths: List[str] = field(default_factory=list)
    planned_interfaces: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    required_tests: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    status: str = "draft"  # draft, active, completed, failed

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "scope_files": self.scope_files,
            "guarded_paths": self.guarded_paths,
            "planned_interfaces": self.planned_interfaces,
            "assumptions": self.assumptions,
            "required_tests": self.required_tests,
            "risks": self.risks,
            "success_criteria": self.success_criteria,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionContract":
        return cls(
            task=data.get("task", ""),
            scope_files=data.get("scope_files", []),
            guarded_paths=data.get("guarded_paths", []),
            planned_interfaces=data.get("planned_interfaces", []),
            assumptions=data.get("assumptions", []),
            required_tests=data.get("required_tests", []),
            risks=data.get("risks", []),
            success_criteria=data.get("success_criteria", []),
            status=data.get("status", "draft"),
        )

    def format_for_prompt(self) -> str:
        """Format contract cho inclusion trong prompt."""
        if not self.task:
            return ""

        sections: List[str] = [
            "<execution_contract>",
            f"  <task>{self.task}</task>",
            f"  <status>{self.status}</status>",
        ]

        if self.scope_files:
            sections.append("  <scope_files>")
            for f in self.scope_files:
                sections.append(f"    <file>{f}</file>")
            sections.append("  </scope_files>")

        if self.guarded_paths:
            sections.append("  <guarded_paths>")
            for p in self.guarded_paths:
                sections.append(f"    <path>{p}</path>")
            sections.append("  </guarded_paths>")

        if self.planned_interfaces:
            sections.append("  <planned_interfaces>")
            for i in self.planned_interfaces:
                sections.append(f"    <interface>{i}</interface>")
            sections.append("  </planned_interfaces>")

        if self.assumptions:
            sections.append("  <assumptions>")
            for a in self.assumptions:
                sections.append(f"    <assumption>{a}</assumption>")
            sections.append("  </assumptions>")

        if self.required_tests:
            sections.append("  <required_tests>")
            for t in self.required_tests:
                sections.append(f"    <test>{t}</test>")
            sections.append("  </required_tests>")

        if self.risks:
            sections.append("  <risks>")
            for r in self.risks:
                sections.append(f"    <risk>{r}</risk>")
            sections.append("  </risks>")

        if self.success_criteria:
            sections.append("  <success_criteria>")
            for c in self.success_criteria:
                sections.append(f"    <criterion>{c}</criterion>")
            sections.append("  </success_criteria>")

        sections.append("</execution_contract>")
        return "\n".join(sections)


def load_execution_contract(workspace_root: Path) -> Optional[ExecutionContract]:
    """Load execution contract from .synapse/execution_contract.json."""
    contract_file = workspace_root / ".synapse" / EXECUTION_CONTRACT_FILE
    if not contract_file.exists():
        return None
    try:
        content = contract_file.read_text(encoding="utf-8")
        data = json.loads(content)
        return ExecutionContract.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to load execution contract: %s", e)
        return None


def save_execution_contract(workspace_root: Path, contract: ExecutionContract) -> None:
    """Save execution contract to .synapse/execution_contract.json using atomic write."""
    synapse_dir = workspace_root / ".synapse"
    synapse_dir.mkdir(parents=True, exist_ok=True)
    contract_file = synapse_dir / EXECUTION_CONTRACT_FILE

    # Atomic write pattern
    fd, tmp_path = tempfile.mkstemp(dir=str(synapse_dir), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(contract.to_dict(), f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(contract_file))
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        logger.error("Failed to save execution contract: %s", e)
        raise
