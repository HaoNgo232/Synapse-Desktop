"""
Memory Types - Ba lớp memory cho decision tracking.

Layer 1: Action Memory - agent đã sửa gì (existing)
Layer 2: Decision Memory - vì sao chọn approach A thay vì B
Layer 3: Constraint Memory - invariant/rule/domain assumption
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal

MemoryLayer = Literal["action", "decision", "constraint"]


@dataclass
class MemoryEntry:
    """Single memory entry across any layer."""

    layer: MemoryLayer
    content: str
    timestamp: str = ""
    linked_files: List[str] = field(default_factory=list)
    linked_symbols: List[str] = field(default_factory=list)
    workflow: str = ""  # e.g., "rp_build", "rp_review"
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "content": self.content,
            "timestamp": self.timestamp,
            "linked_files": self.linked_files,
            "linked_symbols": self.linked_symbols,
            "workflow": self.workflow,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(
            layer=data.get("layer", "action"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", ""),
            linked_files=data.get("linked_files", []),
            linked_symbols=data.get("linked_symbols", []),
            workflow=data.get("workflow", ""),
            tags=data.get("tags", []),
        )


@dataclass
class MemoryStore:
    """Full memory store with all three layers."""

    entries: List[MemoryEntry] = field(default_factory=list)
    version: int = 2

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)

    def get_by_layer(self, layer: MemoryLayer) -> List[MemoryEntry]:
        return [e for e in self.entries if e.layer == layer]

    def get_by_file(self, file_path: str) -> List[MemoryEntry]:
        return [e for e in self.entries if file_path in e.linked_files]

    def get_by_workflow(self, workflow: str) -> List[MemoryEntry]:
        return [e for e in self.entries if e.workflow == workflow]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryStore":
        entries = [MemoryEntry.from_dict(e) for e in data.get("entries", [])]
        return cls(entries=entries, version=data.get("version", 2))

    def format_for_prompt(self, max_entries: int = 20) -> str:
        """Format memory entries for inclusion in prompts."""
        if not self.entries:
            return ""

        header: Dict[str, str] = {
            "constraint": "Project Constraints",
            "decision": "Past Decisions",
            "action": "Recent Actions",
        }
        sections: List[str] = []
        for layer_name in ("constraint", "decision", "action"):
            layer_entries = self.get_by_layer(layer_name)
            if not layer_entries:
                continue

            recent = layer_entries[-max_entries:]
            lines = [f"<{header[layer_name]}>"]
            for e in recent:
                lines.append(f"- {e.content}")
                if e.linked_files:
                    lines.append(f"  Files: {', '.join(e.linked_files)}")
            lines.append(f"</{header[layer_name]}>")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)
