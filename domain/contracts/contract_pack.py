"""
Contract Pack - Workspace contract cho AI agent compliance.

Kết hợp workspace rules, past error patterns, và conventions
để build "contract pack" mà agent phải tuân theo.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ContractPack:
    """Contract pack cho workspace - điều kiện agent phải tuân theo."""

    # Conventions bắt buộc
    conventions: List[str] = field(default_factory=list)

    # Anti-patterns từng gây lỗi trước đó
    anti_patterns: List[str] = field(default_factory=list)

    # Files thường cần sửa cùng nhau
    co_change_groups: List[List[str]] = field(default_factory=list)

    # Điều kiện pass review
    review_checklist: List[str] = field(default_factory=list)

    # Test tối thiểu phải chạy
    required_tests: List[str] = field(default_factory=list)

    # Guarded paths (watchpoints) - files/folders cần cẩn thận
    guarded_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "conventions": self.conventions,
            "anti_patterns": self.anti_patterns,
            "co_change_groups": self.co_change_groups,
            "review_checklist": self.review_checklist,
            "required_tests": self.required_tests,
            "guarded_paths": self.guarded_paths,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContractPack":
        return cls(
            conventions=data.get("conventions", []),
            anti_patterns=data.get("anti_patterns", []),
            co_change_groups=data.get("co_change_groups", []),
            review_checklist=data.get("review_checklist", []),
            required_tests=data.get("required_tests", []),
            guarded_paths=data.get("guarded_paths", []),
        )

    def format_for_prompt(self) -> str:
        """Format contract pack cho inclusion trong prompt."""
        sections: List[str] = []

        if self.conventions:
            lines = ["<conventions>"]
            for c in self.conventions:
                lines.append(f"- {c}")
            lines.append("</conventions>")
            sections.append("\n".join(lines))

        if self.anti_patterns:
            lines = ["<anti_patterns>"]
            for ap in self.anti_patterns:
                lines.append(f"- ⚠️ {ap}")
            lines.append("</anti_patterns>")
            sections.append("\n".join(lines))

        if self.co_change_groups:
            lines = ["<co_change_groups>"]
            for group in self.co_change_groups:
                lines.append(f"- {' + '.join(group)}")
            lines.append("</co_change_groups>")
            sections.append("\n".join(lines))

        if self.review_checklist:
            lines = ["<review_checklist>"]
            for item in self.review_checklist:
                lines.append(f"- [ ] {item}")
            lines.append("</review_checklist>")
            sections.append("\n".join(lines))

        if self.required_tests:
            lines = ["<required_tests>"]
            for t in self.required_tests:
                lines.append(f"- {t}")
            lines.append("</required_tests>")
            sections.append("\n".join(lines))

        if self.guarded_paths:
            lines = ["<guarded_paths>"]
            for gp in self.guarded_paths:
                lines.append(f"- 🔒 {gp}")
            lines.append("</guarded_paths>")
            sections.append("\n".join(lines))

        return "\n\n".join(sections) if sections else ""


def load_contract_pack(workspace_root: Path) -> ContractPack:
    """Load contract pack from .synapse/contract_pack.json."""
    contract_file = workspace_root / ".synapse" / "contract_pack.json"
    if not contract_file.exists():
        return ContractPack()
    try:
        data = json.loads(contract_file.read_text(encoding="utf-8"))
        return ContractPack.from_dict(data)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load contract pack: %s", e)
        return ContractPack()


def save_contract_pack(workspace_root: Path, pack: ContractPack) -> None:
    """Save contract pack to .synapse/contract_pack.json."""
    synapse_dir = workspace_root / ".synapse"
    synapse_dir.mkdir(parents=True, exist_ok=True)
    contract_file = synapse_dir / "contract_pack.json"
    tmp = contract_file.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(pack.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(str(tmp), str(contract_file))
    except OSError as e:
        logger.error("Failed to save contract pack: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def build_contract_pack(
    workspace_root: Path,
    workspace_rules_content: str = "",
    error_patterns: Optional[List[str]] = None,
    co_change_hints: Optional[List[List[str]]] = None,
) -> ContractPack:
    """
    Build contract pack từ workspace rules và error history.

    Kết hợp nhiều nguồn:
    1. Workspace rules (project_rules.json)
    2. Error patterns từ history
    3. Co-change hints từ git history
    """
    pack = load_contract_pack(workspace_root)

    # Parse workspace rules into conventions
    if workspace_rules_content:
        for line in workspace_rules_content.strip().splitlines():
            line = line.strip()
            if line and line not in pack.conventions:
                pack.conventions.append(line)

    # Add error patterns as anti-patterns
    if error_patterns:
        for ep in error_patterns:
            if ep and ep not in pack.anti_patterns:
                pack.anti_patterns.append(ep)

    # Add co-change groups
    if co_change_hints:
        for group in co_change_hints:
            if group and group not in pack.co_change_groups:
                pack.co_change_groups.append(group)

    save_contract_pack(workspace_root, pack)
    return pack
