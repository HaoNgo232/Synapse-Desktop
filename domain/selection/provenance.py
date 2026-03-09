"""Selection provenance tracking - phân biệt nguồn gốc của file selection."""

from dataclasses import dataclass, field
from typing import Dict, List, Literal


SelectionSource = Literal["user", "agent", "dependency", "review"]

VALID_SOURCES: set[str] = {"user", "agent", "dependency", "review"}


@dataclass
class SelectionState:
    """Trạng thái selection với provenance."""

    paths: List[str] = field(default_factory=list)
    provenance: Dict[str, SelectionSource] = field(default_factory=dict)
    version: int = 2

    def add_paths(self, new_paths: List[str], source: SelectionSource = "user") -> None:
        for p in new_paths:
            if p not in self.paths:
                self.paths.append(p)
            self.provenance[p] = source

    def remove_paths(self, paths_to_remove: List[str]) -> None:
        self.paths = [p for p in self.paths if p not in paths_to_remove]
        for p in paths_to_remove:
            self.provenance.pop(p, None)

    def clear(self) -> None:
        self.paths.clear()
        self.provenance.clear()

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "paths": self.paths,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: object) -> "SelectionState":
        """Parse from dict or list (backward compatible)."""
        if isinstance(data, list):
            # v1 format - just a list of paths
            return cls(paths=data, provenance={p: "user" for p in data})
        if isinstance(data, dict):
            return cls(
                paths=data.get("paths", []),
                provenance=data.get("provenance", {}),
                version=data.get("version", 2),
            )
        return cls()
