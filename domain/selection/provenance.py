"""Selection provenance tracking - phan biet nguon goc cua file selection."""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, cast


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
        """Parse from v2 dict format only."""
        if isinstance(data, dict):
            raw_paths = data.get("paths", [])
            paths: List[str] = (
                [p for p in raw_paths if isinstance(p, str)]
                if isinstance(raw_paths, list)
                else []
            )

            raw_provenance = data.get("provenance", {})
            provenance: Dict[str, SelectionSource] = {}
            if isinstance(raw_provenance, dict):
                for key, value in raw_provenance.items():
                    if (
                        isinstance(key, str)
                        and isinstance(value, str)
                        and value in VALID_SOURCES
                    ):
                        provenance[key] = cast(SelectionSource, value)

            raw_version = data.get("version", 2)
            version = raw_version if isinstance(raw_version, int) else 2

            return cls(paths=paths, provenance=provenance, version=version)
        return cls()
